"""Main API to perform Nuxeo Drive operations"""

import sys
import os.path
from datetime import datetime
from time import sleep
from threading import local
import urllib2
import md5
import suds
import base64
import socket
import httplib
import subprocess
import logging

import nxdrive
from nxdrive.client import BaseAutomationClient
from nxdrive.client import NuxeoClient
from nxdrive.client import NotFound
from nxdrive.client import Unauthorized
from nxdrive.model import init_db
from nxdrive.model import DeviceConfig
from nxdrive.model import ServerBinding
from nxdrive.model import LastKnownState
from nxdrive.model import SyncFolders
from nxdrive.model import RootBinding
from nxdrive.synchronizer import Synchronizer
from nxdrive.logging_config import get_logger
from nxdrive.utils import normalized_path
from nxdrive import Constants
from nxdrive.utils import ProxyConnectionError, ProxyConfigurationError

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func
from sqlalchemy import asc
from sqlalchemy import or_


POSSIBLE_NETWORK_ERROR_TYPES = (
    Unauthorized,
    urllib2.URLError,
    urllib2.HTTPError,
    httplib.HTTPException,
    socket.error,
    ProxyConnectionError,
    ProxyConfigurationError,
)

schema_url = r'federatedloginservices.xml'
# service_url = 'https://swee.sharpb2bcloud.com/login/auth.ejs'
service_url = r'http://login.sharpb2bcloud.com'
ns = r'http://www.inventua.com/federatedloginservices/'
CLOUDDESK_SCOPE = r'clouddesk'
DEFAULT_STORAGE = (0, 1000000000)

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

    __instance = None

    @staticmethod
    def getController():
        # not exactly a singleton
        return Controller.__instance

    def __init__(self, config_folder, nuxeo_client_factory = None, echo = None,
                 poolclass = None):

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

        # Handle connection to the local Nuxeo Drive configuration and
        # metadata sqlite database.
        self._engine, self._session_maker = init_db(
            self.config_folder, echo = echo, poolclass = poolclass)

        # Make it possible to pass an arbitrary nuxeo client factory
        # for testing
        if nuxeo_client_factory is not None:
            self.nuxeo_client_factory = nuxeo_client_factory
        else:
            self.nuxeo_client_factory = NuxeoClient

        self._local = local()
        self._remote_error = None
        self.device_id = self.get_device_config().device_id
        self.fault_tolerant = True
        self.loop_count = 0
        self._init_storage()
        Controller.__instance = self
        self.synchronizer = Synchronizer(self)

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
        if pid is not None:
            # Create a stop file marker for the running synchronization
            # process
            log.info("Telling synchronization process %d to stop." % pid)
            stop_file = os.path.join(self.config_folder, "stop_%d" % pid)
            open(stop_file, 'wb').close()
        else:
            log.info("No running synchronization process to stop.")

    def _pair_states_recursive(self, local_root, session, doc_pair):
        """Recursive call to collect pair state under a given location."""
        if not doc_pair.folderish:
            return [(doc_pair, doc_pair.pair_state)]

        if doc_pair.path is not None and doc_pair.remote_ref is not None:
            f = or_(
                LastKnownState.parent_path == doc_pair.path,
                LastKnownState.remote_parent_ref == doc_pair.remote_ref,
            )
        elif doc_pair.path is not None:
            f = LastKnownState.parent_path == doc_pair.path
        elif doc_pair.remote_ref is not None:
            f = LastKnownState.remote_parent_ref == doc_pair.remote_ref
        else:
            raise ValueError("Illegal state %r: at least path or remote_ref"
                             " should be not None." % doc_pair)

        children_states = session.query(LastKnownState).filter_by(
            local_root = local_root).filter(f).order_by(
                asc(LastKnownState.local_name),
                asc(LastKnownState.remote_name),
            ).all()

        results = []
        for child_state in children_states:
            sub_results = self._pair_states_recursive(
                local_root, session, child_state)
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

    def _binding_path(self, folder_path, session = None):
        """Find a root binding and relative path for a given FS path"""
        folder_path = normalized_path(folder_path)

        # Check exact root binding match
        binding = self.get_root_binding(folder_path, session = session)
        if binding is not None:
            return binding, '/'

        # Check for root bindings that are prefix of folder_path
        session = self.get_session()
        all_root_bindings = session.query(RootBinding).all()
        root_bindings = [rb for rb in all_root_bindings
                         if folder_path.startswith(
                             rb.local_root + os.path.sep)]
        if len(root_bindings) == 0:
            raise NotFound("Could not find any root binding for "
                               + folder_path)
        elif len(root_bindings) > 1:
            raise RuntimeError("Found more than one binding for %s: %r" % (
                folder_path, root_bindings))
        binding = root_bindings[0]
        path = folder_path[len(binding.local_root):]
        path = path.replace(os.path.sep, '/')
        return binding, path

    def get_server_binding(self, local_folder = None, raise_if_missing = False,
                           session = None):
        """Find the ServerBinding instance for a given local_folder"""
        if session is None:
            session = self.get_session()
        try:
            if local_folder is None:
                return session.query(ServerBinding).first()
            else:
                local_folder = normalized_path(local_folder)
                return session.query(ServerBinding).filter(
                ServerBinding.local_folder == local_folder).one()
        except NoResultFound:
            if raise_if_missing:
                raise RuntimeError(
                    "Folder '%s' is not bound to any %s server"
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

        # check the connection to the server by issuing an authentication
        # request
        server_url = self._normalize_url(server_url)
        nxclient = self.nuxeo_client_factory(server_url, username, self.device_id,
                                             password)
        token = nxclient.request_token()
        try:
            server_binding = session.query(ServerBinding).filter(
                ServerBinding.local_folder == local_folder).one()
            if (server_binding.remote_user != username
                or server_binding.server_url != server_url):
                raise RuntimeError(
                    "%s is already bound to '%s' with user '%s'" % (
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
            server_binding.nag_signin = False

        except NoResultFound:
            log.info("Binding '%s' to '%s' with account '%s'",
                     local_folder, server_url, username)
            session.add(ServerBinding(local_folder, server_url, username,
                                      remote_password = password,
                                      remote_token = token))

        # Create the local folder to host the synchronized files: this
        # is useless as long as bind_root is not called
        if not os.path.exists(local_folder):
            os.makedirs(local_folder)

        session.commit()

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
                nxclient = self.nuxeo_client_factory(
                        binding.server_url,
                        binding.remote_user,
                        self.device_id,
                        token = binding.remote_token)
                log.info("Revoking token for '%s' with account '%s'",
                         binding.server_url, binding.remote_user)
                nxclient.revoke_token()
            except Unauthorized:
                log.warning("Could not connect to server '%s' to revoke token",
                            binding.server_url)

        # Invalidate client cache
        self.invalidate_client_cache(binding.server_url)

        # Delete binding info in local DB
        log.info("Unbinding '%s' from '%s' with account '%s'",
                 local_folder, binding.server_url, binding.remote_user)

        # delete all binding roots for this server
        root_bindings = session.query(RootBinding).filter(RootBinding.local_folder == binding.local_folder).all()
        for rb in root_bindings:
            session.delete(rb)

        # delete all sync folders
        sync_folders = session.query(SyncFolders).filter(SyncFolders.local_folder == binding.local_folder).all()
        for sf in sync_folders:
            session.delete(sf)

        session.delete(binding)
        session.commit()

    def unbind_all(self):
        """Unbind all server and revoke all tokens

        This is useful for cleanup in integration test code.
        """
        session = self.get_session()
        for sb in session.query(ServerBinding).all():
            self.unbind_server(sb.local_folder)

    def get_root_binding(self, local_root, raise_if_missing = False,
                         session = None):
        """Find the RootBinding instance for a given local_root

        It is the responsability of the caller to commit any change in
        the same thread if needed.
        """
        local_root = normalized_path(local_root)
        if session is None:
            session = self.get_session()
        try:
            return session.query(RootBinding).filter(
                RootBinding.local_root == local_root).one()
        except NoResultFound:
            if raise_if_missing:
                raise RuntimeError(
                    "Folder '%s' is not bound as a root."
                    % local_root)
            return None

    def validate_credentials(self, server_url, username, password):
        # check the connection to the server by issuing an authenticated 'fetch API' request
        # if invalid credentials, raises Unauthorized, or for invalid url, a generic exception
        server_url = self._normalize_url(server_url)
        nxclient = self.nuxeo_client_factory(server_url, username, self.device_id,
                                             password)

    def _update_hash(self, password):
        return md5.new(password).digest()

    def find_data_path(self):
        """Introspect the Python runtime to find the frozen 'data' path."""

        nxdrive_path = os.path.dirname(nxdrive.__file__)
        data_path = os.path.join(nxdrive_path, 'data')
        frozen_suffix = os.path.join('library.zip', 'nxdrive')
        if nxdrive_path.endswith(frozen_suffix):
            # installed version
            data_path = os.path.join(os.path.dirname(os.path.dirname(nxdrive_path)), 'data')
        # TODO: handle the python.exe + python script as sys.argv[0] case as well
        return data_path

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

    def get_sync_status(self, local_folder = None, from_time = None, delay = 10):
        """retrieve count of created/modified/deleted local files since 'from_time'.
        If 'from_time is None, use current time minus delay.
        If local_folder is None, return results for all bindings.
        Return a list of tuples of the form [('<local_folder>', '<pair_state>', count),...]
        """
        after = from_time if from_time is not None else datetime.now() - delay

        # query for result of last synchronize cycle
        session = self.get_session()
        q = session.query(RootBinding.local_folder, LastKnownState.pair_state, func.count(LastKnownState.pair_state)).\
                    filter(RootBinding.local_root == LastKnownState.local_root).\
                    filter(LastKnownState.folderish == 0).\
                    filter(LastKnownState.last_local_updated >= after).\
                    group_by(RootBinding.local_folder).\
                    group_by(LastKnownState.pair_state)

        if local_folder is None:
            return q.all()
        else:
            return q.filter(RootBinding.local_folder == local_folder).all()


    def bind_root(self, local_folder, remote_root, repository = 'default'):
        """Bind local root to a remote root (folderish document in Nuxeo).

        local_folder must be already bound to an existing Nuxeo server. A
        new folder will be created under that folder to bind the remote
        root.

        remote_root must be the IdRef or PathRef of an existing folderish
        document on the remote server bound to the local folder. The
        user account must have write access to that folder, otherwise
        a RuntimeError will be raised.
        """
        # Check that local_root is a subfolder of bound folder
        session = self.get_session()
        local_folder = normalized_path(local_folder)
        server_binding = self.get_server_binding(local_folder,
                                                 raise_if_missing = True,
                                                 session = session)

        # Check the remote root exists and is an editable folder by current
        # user.
        try:
            nxclient = self.get_remote_client(server_binding,
                                              repository = repository,
                                              base_folder = remote_root)
            remote_info = nxclient.get_info('/', fetch_parent_uid = False)
        except NotFound:
            remote_info = None
        if remote_info is None or not remote_info.folderish:
            raise RuntimeError(
                'No folder at "%s:%s" visible by "%s" on server "%s"'
                % (repository, remote_root, server_binding.remote_user,
                   server_binding.server_url))

        if not nxclient.check_writable(remote_root):
            raise RuntimeError(
                'Folder at "%s:%s" is not editable by "%s" on server "%s"'
                % (repository, remote_root, server_binding.remote_user,
                   server_binding.server_url))

        # register the root on the server
        if nxclient.register_as_root(remote_info.uid):
            self.synchronizer.update_roots(server_binding, session = session,
                    repository = repository)
        else:
            # For the tests only
            self._local_bind_root(server_binding, remote_info, nxclient,
                    session = session)

    def unbind_root(self, local_root, session = None):
        """Remove binding on a root folder"""
        local_root = normalized_path(local_root)
        if session is None:
            session = self.get_session()
        binding = self.get_root_binding(local_root, raise_if_missing = True,
                                        session = session)

        nxclient = self.get_remote_client(binding.server_binding,
                                          repository = binding.remote_repo,
                                          base_folder = binding.remote_root)
        if nxclient.is_addon_installed():
            # unregister the root on the server
            nxclient.unregister_as_root(binding.remote_root)
            self.synchronizer.update_roots(binding.server_binding,
                    session = session, repository = binding.remote_repo)
        else:
            # manual bounding: the server is not aware
            self._local_unbind_root(binding, session)

    def refresh_remote_folders_from_log(self, root_binding):
        """Query the remote server audit log looking for state updates."""
        # TODO
        raise NotImplementedError()

    def list_pending(self, limit = 100, local_root = None, session = None):
        """List pending files to synchronize, ordered by path

        Ordering by path makes it possible to synchronize sub folders content
        only once the parent folders have already been synchronized.
        """
        if session is None:
            session = self.get_session()
        if local_root is not None:
            return session.query(LastKnownState).filter(
                LastKnownState.pair_state != 'synchronized',
                LastKnownState.local_root == local_root
            ).order_by(
                asc(LastKnownState.path),
                asc(LastKnownState.remote_path),
            ).limit(limit).all()
        else:
            return session.query(LastKnownState).filter(
                LastKnownState.pair_state != 'synchronized'
            ).order_by(
                asc(LastKnownState.path),
                asc(LastKnownState.remote_path),
            ).limit(limit).all()

    def next_pending(self, local_root = None, session = None):
        """Return the next pending file to synchronize or None"""
        pending = self.list_pending(limit = 1, local_root = local_root,
                                    session = session)
        return pending[0] if len(pending) > 0 else None

    def _get_client_cache(self):
        if not hasattr(self._local, 'remote_clients'):
            self._local.remote_clients = dict()
        return self._local.remote_clients

    def get_remote_client(self, server_binding, base_folder = None,
                          repository = 'default'):
        cache = self._get_client_cache()
        sb = server_binding
        cache_key = (sb.server_url, sb.remote_user, self.device_id, base_folder,
                     repository)
        remote_client = cache.get(cache_key)

        if remote_client is None:
            remote_client = self.nuxeo_client_factory(
                sb.server_url, sb.remote_user, self.device_id,
                token = sb.remote_token, password = sb.remote_password,
                base_folder = base_folder, repository = repository)
            cache[cache_key] = remote_client
        # Make it possible to have the remote client simulate any kind of
        # failure
        remote_client.make_raise(self._remote_error)
        return remote_client

    def invalidate_client_cache(self, server_url):
        cache = self._get_client_cache()
        for key, client in cache.items():
            if client.server_url == server_url:
                del cache[key]

    def _log_offline(self, exception, context):
        if isinstance(exception, urllib2.HTTPError):
            msg = ("Client offline in %s: HTTP error with code %d"
                    % (context, exception.code))
        else:
            msg = "Client offline in %s: %s" % (context, exception)
        log.trace(msg)

    def get_state(self, server_url, remote_repo, remote_ref):
        """Find a pair state for the provided remote document identifiers."""
        server_url = self._normalize_url(server_url)
        session = self.get_session()
        try:
            states = session.query(LastKnownState).filter_by(
                remote_ref = remote_ref,
            ).all()
            for state in states:
                rb = state.root_binding
                sb = rb.server_binding
                if (sb.server_url == server_url
                    and rb.remote_repo == remote_repo):
                    return state
        except NoResultFound:
            return None

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

    def get_storage(self, local_folder):
        try:
            return self.storage[local_folder]
        except KeyError:
            return DEFAULT_STORAGE

    def launch_file_editor(self, server_url, remote_repo, remote_ref):
        """Find the local file if any and start OS editor on it."""
        state = self.get_state(server_url, remote_repo, remote_ref)
        if state is None:
            # TODO: synchronize to a dedicated special root for one time edit
            # TODO: find a better exception
            log.warning('Could not find local file for %s/nxdoc/%s/%s'
                    '/view_documents', server_url, remote_repo, remote_ref)
            return

        # TODO: synchronize this state first

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
            raise ValueError("Invalid url: %r" % url)
        if not url.endswith('/'):
            return url + '/'
        return url

    def _init_storage(self):
        self.storage = {}
        session = self.get_session()
        for sb in session.query(ServerBinding).all():
            self.storage[sb.local_folder] = DEFAULT_STORAGE

    def enable_trace(self, state):
        BaseAutomationClient._enable_trace = state
