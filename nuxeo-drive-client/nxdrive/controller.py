"""Main API to perform Nuxeo Drive operations"""

from __future__ import division

import os
import sys
import os.path
import urllib2
import md5
#import suds
import base64
import socket
import httplib
import subprocess
from datetime import datetime
from datetime import timedelta
from threading import local
from threading import Thread
from threading import Condition
import logging
        
import nxdrive
from nxdrive.client import LocalClient
from nxdrive.client import RemoteFileSystemClient
from nxdrive.client import RemoteDocumentClient
from nxdrive.client import Unauthorized
from nxdrive.client import BaseAutomationClient
from nxdrive.client import RemoteMaintServiceClient
from nxdrive.client import RemoteUpgradeServiceClient
from nxdrive.client import ProxyInfo
from nxdrive.client import NotFound
from nxdrive.model import init_db
from nxdrive.model import DeviceConfig
from nxdrive.model import ServerBinding
from nxdrive.model import LastKnownState
from nxdrive.model import SyncFolders
from nxdrive.model import ServerEvent
from nxdrive.model import RecentFiles
from nxdrive.synchronizer import Synchronizer
from nxdrive.synchronizer import POSSIBLE_NETWORK_ERROR_TYPES
from nxdrive.logging_config import get_logger
from nxdrive.utils import normalized_path
from nxdrive.utils import safe_long_path
from nxdrive._version import _is_newer_version
from nxdrive import Constants
from nxdrive.utils import ProxyConnectionError, ProxyConfigurationError
from nxdrive.http_server import HttpServer
from nxdrive.http_server import http_server_loop

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy import func
from sqlalchemy import asc
from sqlalchemy import or_


# states used by the icon overlay status requests
SYNC_STATES = ['synchronized']
PROGRESS_STATES = ['unknown',
                   'locally_created',
                   'remotely_created',
                   'locally_modified',
                   'remotely_modified',
                   'remotely_deleted',
                   ]
CONFLICTED_STATES = [ 'conflicted', ]
TRANSITION_STATES = PROGRESS_STATES + CONFLICTED_STATES

schema_url = r'federatedloginservices.xml'
# service_url = 'https://swee.sharpb2bcloud.com/login/auth.ejs'
service_url = r'http://login.sharpb2bcloud.com'
ns = r'http://www.inventua.com/federatedloginservices/'
CLOUDDESK_SCOPE = r'clouddesk'

log = get_logger(__name__)

def default_nuxeo_drive_folder():
    """Find a reasonable location for the root Nuxeo Drive folder

    This folder is user specific, typically under the home folder.
    """
    if sys.platform == "win32":
        # WARNING: it's important to check `Documents` first as under Windows 7
        # there also exists a `My Documents` folder invisible in the explorer and
        # cmd / powershell but visible from Python
        documents = os.path.expanduser(r'~\Documents')
        my_documents = os.path.expanduser(r'~\My Documents')
        if os.path.exists(documents):
            # Regular location for documents under Windows 7 and up
            return os.path.join(documents, Constants.DEFAULT_NXDRIVE_FOLDER)
        elif os.path.exists(my_documents):
            # Compat for Windows XP
            return os.path.join(my_documents, Constants.DEFAULT_NXDRIVE_FOLDER)

    # Fallback to home folder otherwiseConstants.DEFAULT_NXDRIVE_FOLDER)
    return os.path.join(os.path.expanduser('~'), Constants.DEFAULT_NXDRIVE_FOLDER)

class Event(object):
    def __init__(self, name = 'none'):
        self.__name = name

    @property
    def name(self):
        return self.__name

class ExceptionEvent(Event):
    evant_names = {401: 'unauthorized',
                   61: 'invalid_proxy',
                   600: 'invalid_proxy',
                   601: 'invalid_proxy',
                   0: 'none'
                   }

    def __init__(self, exception):
        code = getattr(exception, 'code', 0)
        self.text = getattr(exception, 'text', None)
        super(ExceptionEvent, self).__init__(ExceptionEvent.event_names[code])

class EventHandler:
    def __init__(self, parent = None):
        self.__parent = parent
    def Handle(self, event, **kvargs):
        handler = 'Handle_' + event.name
        if hasattr(self, handler):
            method = getattr(self, handler)
            if method(event, **kvargs):
                return True
        if self.__parent:
            if self.__parent.Handle(event, **kvargs):
                return True
        if hasattr(self, 'HandleDefault'):
            return self.HandleDefault(event, **kvargs)

class ContinueLoopingHandler(EventHandler):
    def Handler_unauthorized(self, event, **kvargs):
        server_binding = kvargs['server_binding']
        session = kvargs['session']
        frontend = kvargs['frontend']
        log.debug('Detected invalid credentials for: %s', server_binding.local_folder)
        Controller.getController()._invalidate_client_cache(server_binding.server_url)
        pwd = server_binding.remote_password
        if not server_binding.has_invalid_credentials():
            server_binding.invalidate_credentials()
            if session is None:
                session = self.get_session()
            session.commit()

        try:
            self.bind_server(server_binding.local_folder, server_binding.server_url,
                             server_binding.remote_user, pwd)
            return True
        except:
            return False

class StopSyncingHandler(EventHandler):
    def Handle_unauthorized(self, event, **kvargs):
        server_binding = kvargs['server_binding']
        frontend = kvargs['frontend']
        if frontend is not None:
            frontend.notify_offline(server_binding.local_folder, event)

class Controller(object):
    """Manage configuration and perform Nuxeo Drive Operations

    This class is thread safe: instance can be shared by multiple threads
    as DB sessions and Nuxeo clients are thread locals.
    """

    # Used for binding server / roots and managing tokens
    remote_doc_client_factory = RemoteDocumentClient

    # Used for FS synchronization operations
    remote_fs_client_factory = RemoteFileSystemClient
    remote_maint_service_client_factory = RemoteMaintServiceClient
    remote_upgrade_service_client_factory = RemoteUpgradeServiceClient
    __instance = None

    @staticmethod
    def getController():
        # not exactly a singleton
        return Controller.__instance

    def __init__(self, config_folder, echo = None, poolclass = None, timeout = 60):

        if Controller.__instance:
            raise Controller.__instance

        # Log the installation location for debug
        nxdrive_install_folder = os.path.dirname(nxdrive.__file__)
        nxdrive_install_folder = os.path.realpath(nxdrive_install_folder)
        log.debug("nxdrive installed in '%s'", nxdrive_install_folder)

        # Log the configuration location for debug
        config_folder = os.path.expanduser(config_folder)
        self.config_folder = os.path.realpath(config_folder)
        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)
        log.debug("nxdrive configured in '%s'", self.config_folder)

        if echo is None:
            echo = os.environ.get('NX_DRIVE_LOG_SQL', None) is not None
        self.timeout = timeout

        # Handle connection to the local Nuxeo Drive configuration and
        # metadata sqlite database.
        self._engine, self._session_maker = init_db(
            self.config_folder, echo=echo, poolclass=poolclass)
        self._local = local()
        self._remote_error = None
        self.device_id = self.get_device_config().device_id
       	self.loop_count = 0
        self._init_storage()
        self.mydocs_folder = None
        self.synchronizer = Synchronizer(self)
        self.http_server = None
        self.status_thread = None
        Controller.__instance = self
        self.sync_condition = Condition()

    def get_session(self):
        """Reuse the thread local session for this controller

        Using the controller in several thread should be thread safe as long as
        this method is always called to fetch the session instance.
        """
        return self._session_maker()

    def get_loop_count(self):
        return self.loop_count

    def get_device_config(self, session = None):
        """Fetch the singleton configuration object for this device"""
        if session is None:
            session = self.get_session()
        try:
            return session.query(DeviceConfig).one()
        except NoResultFound:
            device_config = DeviceConfig()  # generate a unique device id
            session.add(device_config)
            session.commit()
            return device_config

    def stop(self):
        """Stop the Nuxeo Drive synchronization thread

        As the process asking the synchronization to stop might not be the as
        the process runnning the synchronization (especially when used from the
        commandline without the graphical user interface and its tray icon
        menu) we use a simple empty marker file a cross platform way to pass
        the stop message between the two.

        """
        pid = self.synchronizer.check_running(process_name = "sync")
        if pid is None:
            # this could happen if the nxdrive_sync.pid file is in use
            # and the pid could not be written into it at startup
            # TODO Assume there is this process running, investigate...
            log.info("No running synchronization process to stop.")
            pid = os.getpid()

        if pid is not None:
            # Create a stop file marker for the running synchronization
            # process
            log.info("Telling synchronization process %d to stop." % pid)
            stop_file = os.path.join(self.config_folder, "stop_%d" % pid)
            open(safe_long_path(stop_file), 'wb').close()
        else:
            log.info("Failed to get process id, app will not quit.")

    def _children_states(self, folder_path):
        """List the status of the children of a folder

        The state of the folder is a summary of their descendant rather
        than their own instric synchronization step which is of little
        use for the end user.

        """
        session = self.get_session()
        # Find the server binding for this absolute path
        try:
            binding, path = self._binding_path(folder_path, session=session)
        except NotFound:
            return [], None

        try:
            folder_state = session.query(LastKnownState).filter_by(
                local_folder=binding.local_folder,
                local_path=path,
            ).one()
        except NoResultFound:
            return [], path

        states = self._pair_states_recursive(session, folder_state)
        return states, path
        
    def children_states_as_files(self, folder_path):
        states, path = self._children_states(folder_path)
        if not path or not states:
            return states
        else:
            return [(os.path.basename(s.local_path), pair_state)
                    for s, pair_state in states
                    if s.local_parent_path == path]

    def children_states_as_paths(self, folder_path):
        states, path = self._children_states(folder_path)
        if not path or not states:
            return states
        else:
            return [(s.local_path, pair_state)
                    for s, pair_state in states
                    if s.local_parent_path == path]
            
    def children_states(self, folder_path):
        """For backward compatibility"""
        return self.chidren_states_as_files(folder_path)
    
    def _pair_states_recursive(self, session, doc_pair):
        """Recursive call to collect pair state under a given location."""
        if not doc_pair.folderish:
            return [(doc_pair, doc_pair.pair_state)]

        if doc_pair.local_path is not None and doc_pair.remote_ref is not None:
            f = or_(
                LastKnownState.local_parent_path == doc_pair.local_path,
                LastKnownState.remote_parent_ref == doc_pair.remote_ref,
            )
        elif doc_pair.local_path is not None:
            f = LastKnownState.local_parent_path == doc_pair.local_path
        elif doc_pair.remote_ref is not None:
            f = LastKnownState.remote_parent_ref == doc_pair.remote_ref
        else:
            raise ValueError(_("Illegal state %r: at least path or remote_ref"
                             " should be not None.") % doc_pair)

        children_states = session.query(LastKnownState).filter_by(
            local_folder=doc_pair.local_folder).filter(f).order_by(
                asc(LastKnownState.local_name),
                asc(LastKnownState.remote_name),
            ).all()

        results = []
        for child_state in children_states:
            sub_results = self._pair_states_recursive(session, child_state)
            results.extend(sub_results)

        # A folder stays synchronized (or unknown) only if all the descendants
        # are themselfves synchronized.
        pair_state = doc_pair.pair_state
        for _, sub_pair_state in results:
            if sub_pair_state != 'synchronized':
                pair_state = 'children_modified'
            break
        # Pre-pend the folder state to the descendants
        return [(doc_pair, pair_state)] + results

    def _binding_path(self, local_path, session=None):
        """Find a server binding and relative path for a given FS path"""
        local_path = normalized_path(local_path)

        # Check exact binding match
        binding = self.get_server_binding(local_path, session=session,
            raise_if_missing=False)
        if binding is not None:
            return binding, '/'

        # Check for bindings that are prefix of local_path
        session = self.get_session()
        all_bindings = session.query(ServerBinding).all()
        if sys.platform == 'win32':
            matching_bindings = [sb for sb in all_bindings
                                 if local_path.lower().startswith(
                                    sb.local_folder.lower() + os.path.sep)]
        else:
            matching_bindings = [sb for sb in all_bindings
                                 if local_path.startswith(
                                    sb.local_folder + os.path.sep)]
        if len(matching_bindings) == 0:
            raise NotFound(_("Could not find any server binding for ")
                               + local_path)
        elif len(matching_bindings) > 1:
            raise RuntimeError(_("Found more than one binding for %s: %r") % (
                local_path, matching_bindings))
        binding = matching_bindings[0]
        path = local_path[len(binding.local_folder):]
        path = path.replace(os.path.sep, '/')
        return binding, path

    def get_server_binding(self, local_folder = None, raise_if_missing = False,
                           session = None):
        """Find the ServerBinding instance for a given local_folder"""

        if session is None:
            session = self.get_session()
        try:
            if local_folder is None:
                server_binding = session.query(ServerBinding).first()
            else:
                local_folder = normalized_path(local_folder)
                server_binding = session.query(ServerBinding).filter(
                ServerBinding.local_folder == local_folder).one()
            return server_binding
        
        except NoResultFound:
            if raise_if_missing:
                raise RuntimeError(
                    _("Folder '%s' is not bound to any %s server")
                    % (local_folder, Constants.PRODUCT_NAME))
            return None

    def list_server_bindings(self, session = None):
        if session is None:
            session = self.get_session()
        return session.query(ServerBinding).all()

    def bind_server(self, local_folder, server_url, username, password):
        """Bind a local folder to a remote nuxeo server"""
        session = self.get_session()
        local_folder = normalized_path(local_folder)
        if not os.path.exists(local_folder):
            os.makedirs(local_folder)

        # check the connection to the server by issuing an authentication
        # request
        server_url = self._normalize_url(server_url)
        nxclient = self.remote_doc_client_factory(
            server_url, username, self.device_id, password)
        token = nxclient.request_token()
        try:
            server_binding = session.query(ServerBinding).filter(
                ServerBinding.local_folder == local_folder).one()
            if (server_binding.remote_user != username
                or server_binding.server_url != server_url):
                raise RuntimeError(
                    _("%s is already bound to '%s' with user '%s'") % (
                        local_folder, server_binding.server_url,
                        server_binding.remote_user))

            # Alternative solution to use for opening the site: keep the password (encrypted)
            if server_binding.remote_password != password:
                # Update password info if required
                server_binding.remote_password = password
                log.info("Updating password for user '%s' on server '%s'",
                        username, server_url)

            if token is not None and server_binding.remote_token != token:
                log.info("Updating token for user '%s' on server '%s'",
                        username, server_url)
                # Update the token info if required
                server_binding.remote_token = token
            # reset the nag schedules
            server_binding.reset_nags()
            # clear old version upgrade events
            self._reset_upgrade_info(server_binding)

        except NoResultFound:
            log.info("Binding '%s' to '%s' with account '%s'",
                     local_folder, server_url, username)
            server_binding = ServerBinding(local_folder, server_url, username,
                                           remote_password=password,
                                           remote_token=token)
            session.add(server_binding)
            
            # ignore if this fails
            try:
                self.update_server_storage_used(server_url, username, session = session)
            except Exception as e:
                log.debug("Failed to retrieve storage: %s", str(e))

            # Creating the toplevel state for the server binding
            local_client = LocalClient(server_binding.local_folder)
            local_info = local_client.get_info('/')

            remote_client = self.get_remote_fs_client(server_binding)
            remote_info = remote_client.get_filesystem_root_info()

            state = LastKnownState(server_binding.local_folder,
                                   local_info=local_info,
                                   local_state='synchronized',
                                   remote_info=remote_info,
                                   remote_state='synchronized')
            session.add(state)
            session.commit()
            return server_binding
        except Exception as e:
            log.debug("Failed to bind server: %s", str(e))
            session.rollback()
            return None

        session.commit()
        return server_binding

    def unbind_server(self, local_folder):
        """Remove the binding to a Nuxeo server

        Local files are not deleted"""
        session = self.get_session()
        local_folder = normalized_path(local_folder)
        binding = self.get_server_binding(local_folder, raise_if_missing = True,
                                          session = session)

        # Revoke token if necessary
        if binding.remote_token is not None:
            try:
                nxclient = self.remote_doc_client_factory(
                        binding.server_url,
                        binding.remote_user,
                        self.device_id,
                        token = binding.remote_token)
                log.info("Revoking token for '%s' with account '%s'",
                         binding.server_url, binding.remote_user)
                nxclient.revoke_token()
            except POSSIBLE_NETWORK_ERROR_TYPES:
                log.warning("Could not connect to server '%s' to revoke token",
                            binding.server_url)
            except Unauthorized:
                # Token is already revoked
                pass

        # Invalidate client cache
        self.invalidate_client_cache(binding.server_url)

        # Delete binding info in local DB
        log.info("Unbinding '%s' from '%s' with account '%s'",
                 local_folder, binding.server_url, binding.remote_user)

        # delete all sync folders but do not clear sync roots on server
        # other device(s) may be linked to the same server, using the same account
        sync_folders = session.query(SyncFolders).filter(SyncFolders.local_folder == binding.local_folder).all()
        for sf in sync_folders:
            session.delete(sf)
        # delete recent files
        recent_files = session.query(RecentFiles).filter(RecentFiles.local_folder == binding.local_folder).all()
        for f in recent_files:
            session.delete(f)
        # delete server events
        server_events = session.query(ServerEvent).filter(ServerEvent.local_folder == binding.local_folder).all()
        for se in server_events:
            session.delete(se)
                
        session.delete(binding)
        session.commit()

    def unbind_all(self):
        """Unbind all server and revoke all tokens

        This is useful for cleanup in integration test code.
        """
        session = self.get_session()
        for sb in session.query(ServerBinding).all():
            self.unbind_server(sb.local_folder)

    def validate_credentials(self, server_url, username, password):
        # check the connection to the server by issuing an authenticated 'fetch API' request
        # if invalid credentials, raises Unauthorized, or for invalid url, a generic exception
        server_url = self._normalize_url(server_url)
        nxclient = self.remote_doc_client_factory(server_url, username, self.device_id,
                                                  password)
        # TODO request token
        # How to validate the returned token that it is a valid token (vs e,g, the login page)
        if nxclient.request_token() is None:
            raise Unauthorized(server_url, username)

    def _update_hash(self, password):
        return md5.new(password).digest()

    def _rerequest_clouddesk_token(self, username, pwdhash):
        """Request and return a token for CloudDesk (federated authentication)"""

        data_path = self.find_data_path()
        location = os.path.join(data_path, schema_url)
        logging.getLogger('suds.client').setLevel(logging.DEBUG)

        try:
            cli = suds.client.Client('file:///' + location)
            cli.wsdl.services[0].setlocation(service_url)
            validateUserActionFlags = cli.factory.create('ValidateUserActionFlags')
            log.trace("calling %s to validate user", service_url)
            result = cli.service.ValidateUser(username, pwdhash, validateUserActionFlags.Login, CLOUDDESK_SCOPE)
            status = cli.factory.create('ResultStatus')
            if result.Status == status.Validated or result.Status == status.LoggedIn:
                return result.ID
            else:
                return None

        except urllib2.URLError as e:
            log.error('error connecting to %s: %s', service_url, str(e))
            return None
        except suds.WebFault as fault:
            log.error('error connecting to %s: %s', service_url, fault)
            return None
        except Exception as e:
            log.error('error retrieving %s token: %s', Constants.APP_NAME, str(e))
            return None

    def _request_clouddesk_token(self, username, password):
        pwdhash = base64.b16encode(md5.new(password).digest()).lower()
        return self._rerequest_clouddesk_token(username, pwdhash), pwdhash

    def get_browser_token(self, local_folder, session = None):
        """Retrieve federated token if it exists and is still valid, or request a new one"""

        server_binding = self.get_server_binding(local_folder, raise_if_missing = False)
        if server_binding is None:
            return None

        fdtoken = server_binding.fdtoken
        if fdtoken is not None:
            duration = datetime.now() - server_binding.fdtoken_creation_date
            if duration.total_seconds() > Constants.FDTOKEN_DURATION:
                fdtoken = None

        if fdtoken is not None:
            return fdtoken

        try:
            fdtoken = self._rerequest_clouddesk_token(server_binding.remote_user, server_binding.password_hash)
            server_binding.fdtoken = fdtoken
            if session is None:
                session = self.get_session()
            session.commit()
        except Exception as e:
            log.error('failed to get browser token for user %s from $: %s',
                      server_binding.remote_user,
                      server_binding.server_url,
                      str(e))
            pass

        return fdtoken

    def bind_root(self, local_folder, remote_ref, repository='default',
                  session=None):
        """Bind local root to a remote root (folderish document in Nuxeo).

        local_folder must be already bound to an existing Nuxeo server.

        remote_ref must be the IdRef or PathRef of an existing folderish
        document on the remote server bound to the local folder.

        """
        session = self.get_session() if session is None else session
        local_folder = normalized_path(local_folder)
        server_binding = self.get_server_binding(
            local_folder, raise_if_missing=True, session=session)

        nxclient = self.get_remote_doc_client(server_binding,
            repository=repository)

        # Register the root on the server
        nxclient.register_as_root(remote_ref)

    def unbind_root(self, local_folder, remote_ref, repository='default',
                    session=None):
        """Remove binding to remote folder"""
        session = self.get_session() if session is None else session
        server_binding = self.get_server_binding(
            local_folder, raise_if_missing=True, session=session)

        nxclient = self.get_remote_doc_client(server_binding,
            repository=repository)

        # Unregister the root on the server
        nxclient.unregister_as_root(remote_ref)

    def list_pending(self, limit=100, local_folder=None, ignore_in_error=None,
                     session=None):
        """List pending files to synchronize, ordered by path

        Ordering by path makes it possible to synchronize sub folders content
        only once the parent folders have already been synchronized.

        If ingore_in_error is not None and is a duration in second, skip pair
        states states that have recently triggered a synchronization error.
        """
        if session is None:
            session = self.get_session()

        predicates = [LastKnownState.pair_state != 'synchronized']
        if local_folder is not None:
            predicates.append(LastKnownState.local_folder == local_folder)

        if ignore_in_error is not None and ignore_in_error > 0:
            max_date = datetime.utcnow() - timedelta(seconds=ignore_in_error)
            predicates.append(or_(
                LastKnownState.last_sync_error_date == None,
                LastKnownState.last_sync_error_date < max_date))

        return session.query(LastKnownState).filter(
            *predicates
        ).order_by(
            # Ensure that newly created local folders will be synchronized
            # before their children
            asc(LastKnownState.local_path),

            # Ensure that newly created remote folders will be synchronized
            # before their children while keeping a fixed named based
            # deterministic ordering to make the tests readable
            asc(LastKnownState.remote_parent_path),
            asc(LastKnownState.remote_name),
            asc(LastKnownState.remote_ref)
        ).limit(limit).all()

    def next_pending(self, local_folder=None, session=None):
        """Return the next pending file to synchronize or None"""
        pending = self.list_pending(limit=1, local_folder=local_folder,
                                    session=session)
        return pending[0] if len(pending) > 0 else None

    def _get_client_cache(self):
        if not hasattr(self._local, 'remote_clients'):
            self._local.remote_clients = dict()
        return self._local.remote_clients

    def get_remote_fs_client(self, server_binding):
        """Return a client for the FileSystem abstraction."""
        cache = self._get_client_cache()
        sb = server_binding
        cache_key = (sb.server_url, sb.remote_user, self.device_id)
        remote_client = cache.get(cache_key)

        if remote_client is None:
            remote_client = self.remote_fs_client_factory(
                sb.server_url, sb.remote_user, self.device_id,
                token=sb.remote_token, password=sb.remote_password,
                timeout=self.timeout)
            cache[cache_key] = remote_client
        # Make it possible to have the remote client simulate any kind of
        # failure
        remote_client.make_raise(self._remote_error)
        return remote_client

    def get_remote_doc_client(self, sb, repository = 'default',
                              base_folder = None):
        """Return an instance of Nuxeo Document Client"""

        return self.remote_doc_client_factory(
            sb.server_url, sb.remote_user, self.device_id,
            token=sb.remote_token, password=sb.remote_password,
            repository=repository, base_folder=base_folder,
            timeout=self.timeout)

    def get_remote_client(self, server_binding, repository='default',
                          base_folder=None):
        # Backward compat
        return self.get_remote_doc_client(server_binding,
            repository=repository, base_folder=base_folder)

    def invalidate_client_cache(self, server_url):
        cache = self._get_client_cache()
        for key, client in cache.items():
            if client.server_url == server_url:
                del cache[key]

    def _get_mydocs_folder(self, server_binding, session = None):
        if self.mydocs_folder is None:
            if session is None:
                session = self.get_session()
    
            try:
                mydocs = session.query(SyncFolders).\
                    filter(SyncFolders.remote_name == Constants.MY_DOCS).one()
                self.mydocs_folder = mydocs.remote_id
            except NoResultFound:
                self.mydocs_folder = None
                
        return self.mydocs_folder
    
    def _log_offline(self, exception, context):
        if isinstance(exception, urllib2.HTTPError):
            msg = (_("Client offline in %s: HTTP error with code %d")
                    % (context, exception.code))
        else:
            msg = _("Client offline in %s: %s") % (context, exception)
        log.trace(msg)

    def get_state(self, server_url, remote_ref):
        """Find a pair state for the provided remote document identifiers."""
        server_url = self._normalize_url(server_url)
        session = self.get_session()
        try:
            states = session.query(LastKnownState).filter_by(
                remote_ref = remote_ref,
            ).all()
            for state in states:
                if (state.server_binding.server_url == server_url):
                    return state
        except NoResultFound:
            return None

    def get_state_for_local_path(self, local_os_path):
        """Find a DB state from a local filesystem path"""
        session = self.get_session()
        sb, local_path = self._binding_path(local_os_path, session=session)
        return session.query(LastKnownState).filter_by(
            local_folder=sb.local_folder, local_path=local_path).one()

    def recover_from_invalid_credentials(self, server_binding, exception, session = None):
        code = getattr(exception, 'code', None)
        if code == 401 or code == 403:
            log.debug('Detected invalid credentials for: %s', server_binding.local_folder)
            self.invalidate_client_cache(server_binding.server_url)
            folder = server_binding.local_folder
            url = server_binding.server_url
            user = server_binding.remote_user
            pwd = server_binding.remote_password
            server_binding.invalidate_credentials()
            if session is None:
                session = self.get_session()
            session.commit()

            try:
                log.debug('trying to get a new token [calling bind_server]')
                self.bind_server(folder, url, user, pwd)
                return True
            except POSSIBLE_NETWORK_ERROR_TYPES as e:
                # This may be the case when the password has changed
                # getting the token still failed (unauthorized)
                log.debug('failed to get a new token (error: %s)', str(e))
                # return False to indicate to switch to off-line mode
                return False
        else:
            return False

    def launch_file_editor(self, server_url, remote_ref):
        """Find the local file if any and start OS editor on it."""

        state = self.get_state(server_url, remote_ref)
        if state is None:
            # TODO: synchronize to a dedicated special root for one time edit
            log.warning('Could not find local file for server_url=%s '
                        'and remote_ref=%s', server_url, remote_ref)
            return

        # TODO: check synchronization of this state first

        # Find the best editor for the file according to the OS configuration
        file_path = state.get_local_abspath()
        self.open_local_file(file_path)

    def open_local_file(self, file_path):
        """Launch the local operating system program on the given file / folder."""
        log.debug('Launching editor on %s', file_path)
        if sys.platform == 'win32':
            os.startfile(file_path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', file_path])
        else:
            try:
                subprocess.Popen(['xdg-open', file_path])
            except OSError:
                # xdg-open should be supported by recent Gnome, KDE, Xfce
                log.error("Failed to find and editor for: '%s'", file_path)

    def make_remote_raise(self, error):
        """Helper method to simulate network failure for testing"""
        self._remote_error = error

    def dispose(self):
        """Release all database resources"""
        self.get_session().close_all()
        self._engine.pool.dispose()

    def _normalize_url(self, url):
        """Ensure that user provided url always has a trailing '/'"""
        if url is None or not url:
            raise ValueError(_("Invalid url: %r") % url)
        if not url.endswith('/'):
            return url + '/'
        return url

    def _init_storage(self):
        self.storage = {}
        session = self.get_session()
        for sb in session.query(ServerBinding).all():
            storage_key = (sb.server_url, sb.remote_user)
            self.storage[storage_key] = None

    def update_storage_used(self, session = None):
        if session is None:
            session = self.get_session()
        for sb in session.query(ServerBinding).all():
            remote_client = self.get_remote_client(sb)
            if remote_client is not None:
                try:
                    sb.used_storage, sb.total_storage = remote_client.get_storage_used()
                except ValueError:
                    # operation not implemented
                    pass

    def update_server_storage_used(self, url, user, session = None):
        if session is None:
            session = self.get_session()
        for sb in session.query(ServerBinding).all():
            if url.startswith(sb.server_url) and user == sb.remote_user:
                remote_client = self.get_remote_client(sb)
                if remote_client is not None:
                    try:
                        sb.used_storage, sb.total_storage = remote_client.get_storage_used()
                        return sb.used_storage, sb.total_storage
                    except ValueError:
                        # operation not implemented
                        pass
                break

        return (0, 0)
        
    def get_storage(self, server_binding):
        try:
            used, total = server_binding.used_storage, server_binding.total_storage
            if total == 0:
                return None
            else:
                return '{:.2f}GB ({:.2%}) of {:.2f}GB'.format(used / 1000000000, used / total, total / 1000000000)
        except KeyError:
            return None
        except InvalidRequestError:
            session = self.get_session()
            session.rollback()
            return None

    def enable_trace(self, state):
        BaseAutomationClient._enable_trace = state

    def start_status_thread(self):
        if self.status_thread is None or not self.status_thread.isAlive():
            self.http_server = HttpServer(Constants.INTERNAL_HTTP_PORT, self.sync_status_app)
            self.status_thread = Thread(target=http_server_loop,
                                      args=(self.http_server,))
            self.status_thread.start()
            
    def stop_status_thread(self):
        if self.http_server:
            self.http_server.stop()

#    def sync_status_app(self, environ, start_response):
#        import json
#        from cgi import parse_qs, escape
#
#        # Returns a dictionary containing lists as values.
#        d = parse_qs(environ['QUERY_STRING'])
#        # select the first state
#        state = d.get('state', [''])[0]
#        transition = d.get('transition', False)
#        folders = d.get('folder', [])
#
#        # Always escape user input to avoid script injection
#        state = escape(state)
#        folders = [escape(folder) for folder in folders]
#
#        status = '200 OK'
#
#        # response is json in the following format:
#        # { "list": ["folder" : {"name": "/users/bob/loud portal office desktop/My Docs/work",
#        #                         "files": ["foo.txt",
#        #                                   "bar.doc"
#        #                                  ]
#        #                        },
#        #             "folder" : {"name": "/users/bob/loud portal office desktop/My Docs/hobby",
#        #                         "files": ["itinerary.doc",
#        #                                   "reservation.html"
#        #                                  ]
#        #                        }
#        #            ]
#        # }
#
#        json_struct = { 'list': {}}
#        folder_list = []
#        
#        for folder in folders:
#            # force a local scan
#            self.synchronizer.scan_local(folder)
#            folder_struct = {}
#            folder_struct['name'] = folder
#            if state == 'synchronized':
#                states = self.children_states_as_files(folder)
#                files = [f for f, status in states if status == state]
#            elif state == 'progress' and not transition:
#                states = self.children_states_as_files(folder)
#                files = [f for f, status in states if status in PROGRESS_STATES]
#            elif state == 'progress' and transition:
#                states = self.children_states_as_paths(folder)
#                files = [f for f, status in states if status in PROGRESS_STATES]
#                files = self.get_next_synced_files(files)
#            elif state == 'conflicted' and not transition:
#                states = self.children_states_as_files(folder)
#                files = [f for f, status in states if status in CONFLICTED_STATES]
#            elif state == 'conflicted' and transition:
#                states = self.children_states_as_paths(folder)
#                files = [f for f, status in states if status in CONFLICTED_STATES]
#                files = self.get_next_synced_files(files)
#            else:
#                files = []
#                
#            folder_struct['files'] = files
#            folder_list.append({'folder': folder_struct})
#            
#        json_struct['list'] = folder_list
#        response_body = json.dumps(json_struct)
#        http_status = '200 OK'
#        response_headers = [('Content-Type', 'application/json'),
#                            ('Content-Length', str(len(response_body)))]
#
#        start_response(http_status, response_headers)
#        return [response_body]

    def sync_status_app(self, state=None, folders=None, transition=False):
        import json
        from cgi import escape
        import cherrypy

        # Always escape user input to avoid script injection
        state = escape(state)
        folders = [escape(folder) for folder in folders]

        # response is json in the following format:
        # { "list": ["folder" : {"name": "/users/bob/loud portal office desktop/My Docs/work",
        #                         "files": ["foo.txt",
        #                                   "bar.doc"
        #                                  ]
        #                        },
        #             "folder" : {"name": "/users/bob/loud portal office desktop/My Docs/hobby",
        #                         "files": ["itinerary.doc",
        #                                   "reservation.html"
        #                                  ]
        #                        }
        #            ]
        # }
            
        json_struct = { 'list': {}}
        folder_list = []
        
        for folder in folders:
            # force a local scan
            self.synchronizer.scan_local(folder)
            folder_struct = {}
            folder_struct['name'] = folder
            if state == 'synchronized':
                states = self.children_states_as_files(folder)
                files = [f for f, status in states if status == state]
            elif state == 'progress' and not transition:
                states = self.children_states_as_files(folder)
                files = [f for f, status in states if status in PROGRESS_STATES]
            elif state == 'progress' and transition:
                states = self.children_states_as_paths(folder)
                files = [f for f, status in states if status in PROGRESS_STATES]
                files = self.get_next_synced_files(files)
            elif state == 'conflicted' and not transition:
                states = self.children_states_as_files(folder)
                files = [f for f, status in states if status in CONFLICTED_STATES]
            elif state == 'conflicted' and transition:
                states = self.children_states_as_paths(folder)
                files = [f for f, status in states if status in CONFLICTED_STATES]
                files = self.get_next_synced_files(files)
            else:
                files = []
                
            folder_struct['files'] = files
            folder_list.append({'folder': folder_struct})
            
        json_struct['list'] = folder_list
        response_body = json.dumps(json_struct)
        cherrypy.response.status = '200 OK'
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.headers['Content-Length'] = str(len(response_body))

        return response_body    

    def get_next_synced_files(self, paths):
        """Called from the http thread to return file(s) which transitioned from 
        'in progress' or 'conflicted' state to 'synchronized' state."""

        session = self.get_session()
        self.sync_condition.acquire()
        num_synced = session.query(LastKnownState).filter(LastKnownState.pair_state == 'synchronized').\
                                filter(LastKnownState.local_path.in_(paths)).count()
        if num_synced == 0:
            self.sync_condition.wait()
        synced = session.query(LastKnownState).filter(LastKnownState.pair_state == 'synchronized').\
                                filter(LastKnownState.local_path in paths).all()
        self.sync_condition.release()
        return synced               

    def reset_proxy(self):
        BaseAutomationClient.set_proxy()

    def setProxy(self):
        BaseAutomationClient.set_proxy(ProxyInfo.get_proxy())
        
    def proxy_changed(self):
        return BaseAutomationClient.get_proxy() != ProxyInfo.get_proxy()


    def get_upgrade_service_client(self, server_binding):
        """Return a client for the external software upgrade service."""
        from nxdrive._version import __version__

        cache = self._get_client_cache()
        url = Constants.UPGRADE_SERVICE_URL + Constants.SHORT_APP_NAME + '/' + __version__ + '/' + sys.platform
        cache_key = (url, None, self.device_id)
        remote_client = cache.get(cache_key)

        if remote_client is None:
            is_automation = url.startswith(server_binding.server_url)
            remote_client = self.remote_upgrade_service_client_factory(
                url, None, self.device_id,
                timeout = self.timeout, is_automation = is_automation)
            cache[cache_key] = remote_client
        # Make it possible to have the remote client simulate any kind of
        # failure
        remote_client.make_raise(self._remote_error)
        return remote_client

    def get_maint_service_client(self, server_binding):
        """Return a client for the external maintenance service."""

        cache = self._get_client_cache()
        netloc = urlparse.urlsplit(server_binding.server_url).netloc
        url = urlparse.urljoin(Constants.MAINTENANCE_SERVICE_URL, netloc)
        cache_key = (url, None, self.device_id)
        remote_client = cache.get(cache_key)

        if remote_client is None:
            is_automation = url.startswith(server_binding.server_url)
            remote_client = self.remote_maint_service_client_factory(
                url, None, self.device_id,
                timeout = self.timeout, is_automation = is_automation)
            cache[cache_key] = remote_client
        # Make it possible to have the remote client simulate any kind of
        # failure
        remote_client.make_raise(self._remote_error)
        return remote_client

    def _reset_upgrade_info(self, sb, session = None):
        """Remove all upgrade info with same or lower version number than the current one."""
        if session is None:
            session = self.get_session()

        versions = session.query(ServerEvent).filter(ServerEvent.message_type == 'upgrade').\
                            filter(ServerEvent.local_folder == sb.local_folder).all()
        older_versions = [version for version in versions if not _is_newer_version(version.data1)]
        if len(older_versions) > 0:
            map(session.delete, older_versions)

    def _get_folders_and_sync_roots(self, controller, server_binding):
        session = controller.get_session()
        controller.synchronizer.get_folders(server_binding = server_binding, session = session)
        controller.synchronizer.update_roots(server_binding = server_binding, session = session)

    def start_folders_thread(self, server_binding):
            Thread(target = self._get_folders_and_sync_roots,
                                      args = (self, server_binding,)).start()
            