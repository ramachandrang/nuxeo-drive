"""Main API to perform Nuxeo Drive operations"""

import sys
from time import time
from time import sleep
# TOBE REMOVED
from datetime import datetime
import os.path
from threading import local
import urllib2
import md5
import suds
import base64
import socket
import httplib
import subprocess
import psutil
import logging
from collections import defaultdict, Iterable
from pprint import pprint
import uuid

import nxdrive
from nxdrive.client import NuxeoClient
from nxdrive.client import LocalClient
from nxdrive.client import safe_filename
from nxdrive.client import NotFound
from nxdrive.client import Unauthorized
from nxdrive.client import FolderInfo
from nxdrive.model import init_db
from nxdrive.model import DeviceConfig, ServerBinding, RootBinding, LastKnownState, SyncFolders, RecentFiles
from nxdrive.logging_config import get_logger
from nxdrive import Constants
from nxdrive.utils.helpers import RecoverableError, ProxyError
#from nxdrive.utils.helpers import Notifier

from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy import func
from sqlalchemy import asc
from sqlalchemy import not_
from sqlalchemy import or_
from sqlalchemy import desc

WindowsError = None
try:
    from exceptions import WindowsError
except ImportError:
    pass  # this will never be raised under unix


POSSIBLE_NETWORK_ERROR_TYPES = (
    Unauthorized,
    urllib2.URLError,
    urllib2.HTTPError,
    httplib.HTTPException,
    socket.error,
    ProxyError,
)

schema_url = 'nxdrive/data/federatedloginservices.xml'
service_url = 'https://swee.sharpb2bcloud.com/login/auth.ejs'
ns = "http://www.inventua.com/federatedloginservices/"
CLOUDDESK_SCOPE = 'clouddesk'

log = get_logger(__name__)

def tree():
    """Tree structure for returning folder hierarchy"""
    return defaultdict(tree)

def dicts(t): 
    """Used for printing tree structure"""
    if isinstance(t, Iterable):
        return {k: dicts(t[k]) for k in t}
    else:
        return str(t)

def default_nuxeo_drive_folder():
    """Find a reasonable location for the root Nuxeo Drive folder

    This folder is user specific, typically under the home folder.
    """
    if sys.platform == "win32":
        if os.path.exists(os.path.expanduser(r'~\My Documents')):
            # Compat for Windows XP
            return os.path.join(r'~\My Documents', Constants.DEFAULT_NXDRIVE_FOLDER)
        else:
            # Default Documents folder with navigation shortcuts in Windows 7
            # and up.
            return os.path.join(r'~\Documents', Constants.DEFAULT_NXDRIVE_FOLDER)
    else:
        return os.path.join('~', Constants.DEFAULT_NXDRIVE_FOLDER)

        
class Controller(object):
    """Manage configuration and perform Nuxeo Drive Operations

    This class is thread safe: instance can be shared by multiple threads
    as DB sessions and Nuxeo clients are thread locals.
    """

    def __init__(self, config_folder, nuxeo_client_factory=None, echo=None,
                 poolclass=None):
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
            self.config_folder, echo=echo, poolclass=poolclass)

        # Make it possible to pass an arbitrary nuxeo client factory
        # for testing
        if nuxeo_client_factory is not None:
            self.nuxeo_client_factory = nuxeo_client_factory
        else:
            self.nuxeo_client_factory = NuxeoClient

        self._local = local()
        self._remote_error = None
        self.device_id = self.get_device_config().device_id
#        self.notifier = Notifier()
        self.fault_tolerant = True


    def get_session(self):
        """Reuse the thread local session for this controller

        Using the controller in several thread should be thread safe as long as
        this method is always called to fetch the session instance.
        """
        return self._session_maker()

    def get_device_config(self, session=None):
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

    def start(self):
        """Start the Nuxeo Drive main daemon if not already started"""
        # TODO, see:
        # https://github.com/mozilla-services/circus/blob/master/circus/
        # circusd.py#L34

    def stop(self):
        """Stop the Nuxeo Drive synchronization thread

        As the process asking the synchronization to stop might not be the as
        the process runnning the synchronization (especially when used from the
        commandline without the graphical user interface and its tray icon
        menu) we use a simple empty marker file a cross platform way to pass
        the stop message between the two.

        """
        pid = self.check_running(process_name="sync")
        if pid is not None:
            # Create a stop file marker for the running synchronization
            # process
            log.info("Telling synchronization process %d to stop." % pid)
            stop_file = os.path.join(self.config_folder, "stop_%d" % pid)
            open(stop_file, 'wb').close()
        else:
            log.info("No running synchronization process to stop.")

    def children_states(self, folder_path, full_states=False):
        """List the status of the children of a folder

        The state of the folder is a summary of their descendant rather
        than their own instric synchronization step which is of little
        use for the end user.

        If full is True the full state object is returned instead of just the
        local path.
        """
        session = self.get_session()
        server_binding = self.get_server_binding(folder_path, session=session)
        if server_binding is not None:
            # TODO: if folder_path is the top level Nuxeo Drive folder, list
            # all the root binding states
            raise NotImplementedError(
                "Children States of a server binding is not yet implemented")

        # Find the root binding for this absolute path
        binding, path = self._binding_path(folder_path, session=session)

        try:
            folder_state = session.query(LastKnownState).filter_by(
                local_root=binding.local_root,
                path=path,
            ).one()
        except NoResultFound:
            return []

        states = self._pair_states_recursive(binding.local_root, session,
                                             folder_state)
        if full_states:
            return [(s, pair_state) for s, pair_state in states
                    if (s.parent_path == path
                        or s.remote_parent_ref == folder_state.remote_ref)]

        return [(s.path, pair_state) for s, pair_state in states
                if s.path is not None and s.parent_path == path]

    def _pair_states_recursive(self, local_root, session, doc_pair):
        """TODO: write me"""
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
            local_root=local_root).filter(f).order_by(
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

    def _binding_path(self, folder_path, session=None):
        """Find a root binding and relative path for a given FS path"""
        folder_path = os.path.abspath(folder_path)

        # Check exact root binding match
        binding = self.get_root_binding(folder_path, session=session)
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

    def get_server_binding(self, local_folder=None, raise_if_missing=None,
                           session=None):
        """Find the ServerBinding instance for a given local_folder"""
        if raise_if_missing == None:
            raise_if_missing = not self.fault_tolerant
        if session is None:
            session = self.get_session()
        try:
            if local_folder is None:
                return session.query(ServerBinding).first()
            else:
                return session.query(ServerBinding).filter(
                ServerBinding.local_folder == local_folder).one()
        except NoResultFound:
            if raise_if_missing:
                raise RuntimeError(
                    "Folder '%s' is not bound to any Nuxeo server"
                    % local_folder)
            return None

    def list_server_bindings(self, session=None):
        if session is None:
            session = self.get_session()
        return session.query(ServerBinding).all()

    def bind_server(self, local_folder, server_url, username, password):
        """Bind a local folder to a remote nuxeo server"""
        session = self.get_session()
        local_folder = os.path.abspath(os.path.expanduser(local_folder))

        # check the connection to the server by issuing an authentication
        # request
        server_url = self._normalize_url(server_url)
        nxclient = self.nuxeo_client_factory(server_url, username, self.device_id,
                                             password)
        token = nxclient.request_token()
        #get federated token for CloudDesk
        fdtoken, password_hash = self._request_clouddesk_token(username, password)
        
        if token is not None:
            # The server supports token based identification: do not store the
            # password in the DB
            password = None
        try:
            server_binding = session.query(ServerBinding).filter(
                ServerBinding.local_folder == local_folder).one()
            if (server_binding.remote_user != username
                or server_binding.server_url != server_url):
                raise RuntimeError(
                    "%s is already bound to '%s' with user '%s'" % (
                        local_folder, server_binding.server_url,
                        server_binding.remote_user))

            if token is None and server_binding.remote_password != password:
                # Update password info if required
                server_binding.remote_password = password
                log.info("Updating password for user '%s' on server '%s'",
                        username, server_url)

            if token is not None and server_binding.remote_token != token:
                log.info("Updating token for user '%s' on server '%s'",
                        username, server_url)
                # Update the token info if required
                server_binding.remote_token = token

                # Ensure that the password is not stored in the DB
                if server_binding.remote_password is not None:
                    server_binding.remote_password = None
                    
            if fdtoken is not None and server_binding.fdtoken != fdtoken:
                log.info("Updating federated token for user '%s' on server '%s, using token server %s'",
                    username, server_url, service_url)
                server_binding.fdtoken = fdtoken
                server_binding.password_hash = password_hash

        except NoResultFound:
            log.info("Binding '%s' to '%s' with account '%s'",
                     local_folder, server_url, username)
            session.add(ServerBinding(local_folder, server_url, username,
                                      remote_password=password,
                                      remote_token=token,
                                      fdtoken=fdtoken,
                                      password_hash=password_hash
                                      ))

        # Create the local folder to host the synchronized files: this
        # is useless as long as bind_root is not called
        if not os.path.exists(local_folder):
            os.makedirs(local_folder)

        session.commit()

    def unbind_server(self, local_folder):
        """Remove the binding to a Nuxeo server

        Local files are not deleted"""
        session = self.get_session()
        local_folder = os.path.abspath(os.path.expanduser(local_folder))
        binding = self.get_server_binding(local_folder, raise_if_missing=False,
                                          session=session)
        if binding is None: return
        
        log.info("Unbinding '%s' from '%s' with account '%s'",
                 local_folder, binding.server_url, binding.remote_user)
        session.delete(binding)
        session.commit()

    def get_root_binding(self, local_root, raise_if_missing=False,
                         session=None):
        """Find the RootBinding instance for a given local_root

        It is the responsability of the caller to commit any change in
        the same thread if needed.
        """
        local_root = os.path.abspath(os.path.expanduser(local_root))
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
        
    # NOT USED - this uses HTTP GET
#    def _request_clouddesk_token(self, username, password):
#        """Request and return a token for CloudDesk (federated authentication)"""
#        parameters = {
#                      'UserName': username,
#                      'PasswordHash': self._update_hash(password),
#                      'ActionFlag': 'Login',
#                      'Scope': 'clouddesk'
#                      } 
#        
#        url = Constants.FEDERATED_SERVICES_URL + '/ValidateUser?'
#        url += urllib.urlencode(parameters)
#        base_error_message = (
#            "Failed not connect to token server on %r"
#            " with user %r"
#        ) % (url, username)
#        
#        try:
#            log.trace("calling %s to validate user", Constants.FEDERATED_SERVICES_URL)
#            req = urllib2.Request(url)
#            token = urllib2.urlopen(req)
#            
#            #TODO parse the result to extract the token (guid)
#            return token
#        except urllib2.HTTPError as e:
#            if e.code == 401  or e.code == 403:
#                raise Unauthorized(url, self.user_id, e.code)
#            elif e.code == 404:
#                # ValidateUser method is not supported by this server
#                return None
#            else:
#                e.msg = base_error_message + ": HTTP error %d" % e.code
#                raise e
#        except Exception as e:
#            if hasattr(e, 'msg'):
#                e.msg = base_error_message + ": " + e.msg
#            raise            
        
                  
    def _rerequest_clouddesk_token(self, username, pwdhash):
        """Request and return a token for CloudDesk (federated authentication)"""
        location = os.path.join(os.getcwd(), schema_url)
        logging.getLogger('suds.client').setLevel(logging.DEBUG)
        
        try:              
            cli = suds.client.Client('file://' + location)
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
            log.error('error retrieving CloudDeskk token: %s', str(e))
            return None
               
    def _request_clouddesk_token(self, username, password):
        pwdhash = base64.b16encode(md5.new(password).digest()).lower()
        return self._rerequest_clouddesk_token(username, pwdhash), pwdhash
          
    def get_browser_token(self, local_folder, session=None):
        """Retrieve federated token if it exists and is still valid, or request a new one"""

        server_binding = self.get_server_binding(local_folder, raise_if_missing=False)
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
        
    def get_sync_status(self, local_folder=None, from_time=None, delay=10):
        """retrieve count of created/modified/deleted local files since 'from_time'.
        If 'from_time is None, use current time minus delay.
        If local_folder is None, return results for all bindings.
        Return a list of tuples of the form [('<local_folder>', '<pair_state>', count),...]
        """
        after = from_time if from_time is not None else datetime.now() - delay

        #query for result of last synchronize cycle
        session = self.get_session()
        q = session.query(RootBinding.local_folder, LastKnownState.pair_state, func.count(LastKnownState.pair_state)).\
                    filter(RootBinding.local_root == LastKnownState.local_root).\
                    filter(LastKnownState.folderish==0).\
                    filter(LastKnownState.last_local_updated >= after).\
                    group_by(RootBinding.local_folder).\
                    group_by(LastKnownState.pair_state)
                    
        if local_folder is None:
            return q.all()
        else:
            return q.filter(RootBinding.local_folder == local_folder).all()


    def bind_root(self, local_folder, remote_root, repository='default'):
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
        local_folder = os.path.abspath(os.path.expanduser(local_folder))
        server_binding = self.get_server_binding(local_folder,
                                                 raise_if_missing=self.fault_tolerant,
                                                 session=session)

        # Check the remote root exists and is an editable folder by current
        # user.
        try:
            nxclient = self.get_remote_client(server_binding,
                                              repository=repository,
                                              base_folder=remote_root)
            remote_info = nxclient.get_info('/', fetch_parent_uid=False)
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


        if nxclient.is_addon_installed():
            # register the root on the server
            nxclient.register_as_root(remote_info.uid)
            self.update_roots(session, server_binding=server_binding,
                              repository=repository)
        else:
            # manual local-only bounding: the server is not aware of any root
            # config
            self._local_bind_root(server_binding, remote_info, nxclient,
                                  session, fault_tolerant=self.fault_tolerant)

    def _local_bind_root(self, server_binding, remote_info, nxclient, session, 
                         fault_tolerant=False, frontend=None):
        # Check that this workspace does not already exist locally
        # TODO: shall we handle deduplication for root names too?
        
        folder_name = remote_info.name
        # show it as a top-level folder - error!
        local_root = os.path.join(server_binding.local_folder,
                  safe_filename(remote_info.name))
 
        try:
            sync_folder = session.query(SyncFolders).filter(SyncFolders.remote_id==remote_info.uid).one()
            if sync_folder.remote_root == Constants.ROOT_CLOUDDESK and sync_folder.remote_id == Constants.OTHERS_DOCS_UID:
                # this binding root is Others' Docs
                local_root = os.path.join(server_binding.local_folder,
                                  safe_filename(Constants.OTHERS_DOCS))

            elif sync_folder.remote_root == Constants.ROOT_CLOUDDESK:
                # this is My Docs
                local_root = os.path.join(server_binding.local_folder,
                                  safe_filename(Constants.MY_DOCS))

            elif sync_folder.remote_root == Constants.ROOT_MYDOCS:
                # child of My Docs
                local_root = os.path.join(server_binding.local_folder,
                                  safe_filename(Constants.MY_DOCS),
                                  safe_filename(folder_name))

            elif sync_folder.remote_root == Constants.ROOT_OTHERS_DOCS:
                # child of Others Docs
                local_root = os.path.join(server_binding.local_folder,
                                  safe_filename(Constants.OTHERS_DOCS),
                                  safe_filename(folder_name))
                
        except NoResultFound:
            log.error("binding root %s is not a synced folder", remote_info.name)
        except MultipleResultsFound:
            log.error("binding root %s is two or more  synced folders", remote_info.name)
            
        repository = nxclient.repository
        if not os.path.exists(local_root):
            os.makedirs(local_root)
        lcclient = LocalClient(local_root, fault_tolerant=fault_tolerant)
        local_info = lcclient.get_info('/')

        try:
            existing_binding = session.query(RootBinding).filter_by(
                local_root=local_root,
            ).one()
            if (existing_binding.remote_repo != repository
                or existing_binding.remote_root != remote_info.uid):
                raise RuntimeError(
                    "%r is already bound to %r on repo %r of %r" % (
                        local_root,
                        existing_binding.remote_root,
                        existing_binding.remote_repo,
                        existing_binding.server_binding.server_url))
        except NoResultFound:
            # Register the new binding itself
            log.info("Binding local root '%s' to '%s' (id=%s) on server '%s'",
                 local_root, remote_info.name, remote_info.uid,
                     server_binding.server_url)
            binding = RootBinding(local_root, repository, remote_info.uid, server_binding.local_folder)
            session.add(binding)

            # Initialize the metadata info by recursive walk on the remote
            # folder structure
            self._recursive_init(lcclient, local_info, nxclient, remote_info)
            session.commit()
            if frontend is not None:
                frontend.notify_folders_changed()            


    def _recursive_init(self, local_client, local_info, remote_client,
                        remote_info):
        """Initialize the metadata table by walking the binding tree"""

        folderish = remote_info.folderish
        state = LastKnownState(local_client.base_folder,
                               local_info=local_info,
                               remote_info=remote_info,
                               fault_tolerant=self.fault_tolerant)
        if folderish:
            # Mark as synchronized as there is nothing to download later
            state.update_state(local_state='synchronized',
                               remote_state='synchronized')
        else:
            # Mark remote as updated to trigger a download of the binary
            # attachment during the next synchro
            state.update_state(local_state='synchronized',
                               remote_state='modified')
        session = self.get_session()
        session.add(state)

        if folderish:
            # TODO: how to handle the too many children case properly?
            # Shall we introduce some pagination or shall we raise an
            # exception if a folder contains too many children?
            children = remote_client.get_children_info(remote_info.uid)
            for child_remote_info in children:
                if child_remote_info.folderish:
                    child_local_path = local_client.make_folder(
                        local_info.path, child_remote_info.name)
                else:
                    child_local_path = local_client.make_file(
                        local_info.path, child_remote_info.name)
                child_local_info = local_client.get_info(child_local_path)
                self._recursive_init(local_client, child_local_info,
                                     remote_client, child_remote_info)

    def unbind_root(self, local_root, session=None):
        """Remove binding on a root folder"""
        local_root = os.path.abspath(os.path.expanduser(local_root))
        if session is None:
            session = self.get_session()
        binding = self.get_root_binding(local_root, raise_if_missing=self.fault_tolerant,
                                        session=session)

        nxclient = self.get_remote_client(binding.server_binding,
                                          repository=binding.remote_repo,
                                          base_folder=binding.remote_root)
        if nxclient.is_addon_installed():
            # register the root on the server
            nxclient.unregister_as_root(binding.remote_root)
            self.update_roots(session=session,
                              server_binding=binding.server_binding,
                              repository=binding.remote_repo)
        else:
            # manual bounding: the server is not aware
            self._local_unbind_root(binding, session)

    def _local_unbind_root(self, binding, session, frontend=None):
        log.info("Unbinding local root '%s'.", binding.local_root)
        session.delete(binding)
        session.commit()
        if frontend is not None:
            frontend.notify_folders_changed()

    def get_folders(self, session=None, server_binding=None,
                    repository=None, frontend=None):
        """Retrieve all folder hierarchy from server.
        If a server is not responding it is skipped.
        """
        
        dirty= {}
        dirty['add'] = 0
        dirty['del'] = 0
        if session is None:
            session = self.get_session()
        if server_binding is not None:
            server_bindings = [server_binding]
        else:
            server_bindings = session.query(ServerBinding).all()
        for sb in server_bindings:
            if sb.has_invalid_credentials():
                # Skip servers with missing credentials
                continue
            try:
                nxclient = self.get_remote_client(sb)
                if not nxclient.is_addon_installed():
                    continue
                if repository is not None:
                    repositories = [repository]
                else:
                    repositories = nxclient.get_repository_names()
                for repo in repositories:
                    nxclient = self.get_remote_client(sb, repository=repo)
                    self._update_clouddesk_root(repo, sb.local_folder)
                    mydocs_folder = nxclient.get_mydocs()
                    mydocs_folder[u'title'] = Constants.MY_DOCS
#                    print 'MyDocs: '
#                    pprint(mydocs_folder, depth=2)

                    nodes = tree()
                    nxclient.get_subfolders(mydocs_folder, nodes)
#                    pprint(dicts(nodes))
                                                            
                    self._update_docs(mydocs_folder, nodes, sb.local_folder, session=session, dirty=dirty)

                    othersdocs_folders = nxclient.get_othersdocs()
#                    print "Others's Docs subfolders: " 
#                    pprint(othersdocs_folders, depth=2)

                    # create a fake Others' Docs folder
                    othersdocs_folder = {
                                         u'uid': Constants.OTHERS_DOCS_UID,
                                         u'title': Constants.OTHERS_DOCS,
                                         u'repository': mydocs_folder[u'repository'],
                                         }
                    nodes = tree()
                    for fld in othersdocs_folders:
                        nodes[fld[u'title']]['value'] = FolderInfo(fld[u'uid'], fld[u'title'], othersdocs_folder[u'uid'])
                        nxclient.get_subfolders(fld, nodes[fld[u'title']])
                        
#                    pprint(dicts(nodes))
                    self._update_docs(othersdocs_folder, nodes, sb.local_folder, session=session, dirty=dirty)

            except POSSIBLE_NETWORK_ERROR_TYPES as e:
                # Ignore expected possible network related errors
                self._log_offline(e, "get folders")
                log.trace("Traceback of ignored network error:",
                        exc_info=True)
                if frontend is not None:
                    frontend.notify_offline(sb.local_folder, e)
                self._invalidate_client_cache(sb.server_url)

        if frontend is not None:
            # session is being flushed by queries
#            if len(session.new) > 0 or len(session.deleted) > 0:  
            try:
                if dirty['add'] > 0 or dirty['del'] > 0:               
                    frontend.notify_folders_changed()
            except KeyError:
                pass
        
    def update_roots(self, session=None, server_binding=None,
                     repository=None, frontend=None):
        """Ensure that the list of bound roots match server-side info

        If a server is not responding it is skipped.
        """
        if session is None:
            session = self.get_session()
        if server_binding is not None:
            server_bindings = [server_binding]
        else:
            server_bindings = session.query(ServerBinding).all()
        for sb in server_bindings:
            if sb.has_invalid_credentials():
                # Skip servers with missing credentials
                continue
            try:
                nxclient = self.get_remote_client(sb)
                if not nxclient.is_addon_installed():
                    continue
                if repository is not None:
                    repositories = [repository]
                else:
                    repositories = nxclient.get_repository_names()
                for repo in repositories:
                    nxclient = self.get_remote_client(sb, repository=repo)
                    remote_roots = nxclient.get_roots()
                    local_roots = [r for r in sb.roots
                                   if r.remote_repo == repo]
                    self._update_roots(sb, session, local_roots, remote_roots,
                                       repo, frontend=frontend)
            except POSSIBLE_NETWORK_ERROR_TYPES as e:
                # Ignore expected possible network related errors
                self._log_offline(e, "update roots")
                log.trace("Traceback of ignored network error:",
                        exc_info=True)
                if frontend is not None:
                    frontend.notify_offline(sb.local_folder, e)
                self._invalidate_client_cache(sb.server_url)

        if frontend is not None:
            local_folders = [sb.local_folder
                    for sb in session.query(ServerBinding).all()]
            frontend.notify_local_folders(local_folders)

    def _update_roots(self, server_binding, session, local_roots,
                      remote_roots, repository, frontend=None):
        """Align the roots for a given server and repository"""
        local_roots_by_id = dict((r.remote_root, r) for r in local_roots)
        local_root_ids = set(local_roots_by_id.keys())

        remote_roots_by_id = dict((r.uid, r) for r in remote_roots)
        remote_root_ids = set(remote_roots_by_id.keys())

        to_remove = local_root_ids - remote_root_ids
        to_add = remote_root_ids - local_root_ids

        for ref in to_remove:
            self._local_unbind_root(local_roots_by_id[ref], session, 
                                    frontend=frontend)

        for ref in to_add:
            # get a client with the right base folder
            rc = self.get_remote_client(server_binding,
                                        repository=repository,
                                        base_folder=ref)
            self._local_bind_root(server_binding, remote_roots_by_id[ref],
                                  rc, session, fault_tolerant=self.fault_tolerant, 
                                  frontend=frontend)
            
    def set_roots(self, session=None, frontend=None):
        """Update binding roots based on client folders selection"""
        
        if session is None:
            session = self.get_session()
            
        roots_to_register = session.query(SyncFolders, ServerBinding).\
                            filter(SyncFolders.state == True).\
                            filter(SyncFolders.checked == None).\
                            filter(ServerBinding.local_folder == SyncFolders.local_folder).\
                            all()
                            
        roots_to_unregister = session.query(SyncFolders, ServerBinding).\
                            filter(SyncFolders.state == False).\
                            filter(SyncFolders.checked != None).\
                            filter(ServerBinding.local_folder == SyncFolders.local_folder).\
                            all()
                            
        for tuple in roots_to_register:
            remote_client = self.get_remote_client(tuple[1], base_folder=tuple[0].remote_id, repository=tuple[0].remote_repo)
            remote_client.register_as_root(tuple[0].remote_id)
            
        for tuple in roots_to_unregister:
            remote_client = self.get_remote_client(tuple[1], base_folder=tuple[0].remote_id, repository=tuple[0].remote_repo)
            remote_client.unregister_as_root(tuple[0].remote_id)            
        
            
    def _update_clouddesk_root(self, repo, local_folder, session=None):
        if session is None:
            session = self.get_session()
        try:
            folder = session.query(SyncFolders).filter_by(remote_id=Constants.CLOUDDESK_UID).one()
        except MultipleResultsFound:
            log.error("more than one CloudDesk folder found!")
        except NoResultFound:
            # Other's Doc is not a real remote folder
            folder = SyncFolders(Constants.CLOUDDESK_UID,
                                 Constants.DEFAULT_NXDRIVE_FOLDER,
                                 None,
                                 repo,
                                 local_folder
                                 )

            session.add(folder)
            session.commit()
        
    def _update_docs(self, docs, nodes, local_folder, session=None, dirty=None):
        if session is None:
            session = self.get_session()
            
        repo = docs[u'repository']
        docId = docs[u'uid']
        # check if already exists
        try:
            folder = session.query(SyncFolders).filter_by(remote_id=docId).one()
        except MultipleResultsFound:
            log.error("more than one of 'My Docs' or 'Others' Docs' folder each found!")
        except NoResultFound:
            # Other's Doc is not a real remote folder
            folder = SyncFolders(docId,
                                 docs[u'title'],
                                 Constants.CLOUDDESK_UID,
                                 repo,
                                 local_folder
                                 )

            session.add(folder)
            
        # add all subfolders
        root_folder = Constants.ROOT_OTHERS_DOCS if docId == Constants.OTHERS_DOCS_UID else Constants.ROOT_MYDOCS
        self._remove_folders(nodes, docId, session, dirty=dirty)
        self._add_folders(nodes, repo, local_folder, root_folder, session, dirty=dirty)        
        session.commit()
        
    def _add_folders(self, t, repo, local_folder, root_folder, session=None, dirty=None):
        if isinstance(t, Iterable):
            for k in t:
                self._add_folders(t[k], repo, local_folder, root_folder, session, dirty)
        else:
            self._add_folder(t, repo, local_folder, root_folder, session, dirty)
                    
    def _add_folder(self, folder_info, repo, local_folder, root_folder, session=None, dirty=None):
        if session is None:
            session = self.get_session()
        folder = SyncFolders(folder_info.docId, folder_info.title, folder_info.parentId, repo, local_folder, remote_root=root_folder)

        try:
            sync_folder = session.query(SyncFolders).filter_by(remote_id=folder_info.docId).one()
#            sync_folder.remote_name = folder_info.title
#            sync_folder.remote_parent = folder_info.parentId
#            sync_folder.remote_repo = repo
#            sync_folder.remote_root = root_folder
        except NoResultFound:
            session.add(folder)
            if dirty is not None:
                dirty['add'] += 1
                
        
    def _remove_folders(self, t, docId, session=None, dirty=None):
        if session is None:
            session = self.get_session()
        for folder in session.query(SyncFolders).filter(SyncFolders.remote_parent == docId).all():
            if not t.has_key(folder.remote_name):
                session.delete(folder)
                if dirty is not None:
                    dirty['del'] += 1
            else:
                self._remove_folders(t[folder.remote_name], folder.remote_id, session, dirty)
        
    def scan_local(self, local_root, session=None):
        """Recursively scan the bound local folder looking for updates"""
        if session is None:
            session = self.get_session()

        root_state = session.query(LastKnownState).filter_by(
            local_root=local_root, path='/').one()

        client = root_state.get_local_client()
        root_info = client.get_info('/')
        # recursive update
        self._scan_local_recursive(local_root, session, client,
                                   root_state, root_info)
        session.commit()

    def _mark_deleted_local_recursive(self, local_root, session, doc_pair):
        """Update the metadata of the descendants of locally deleted doc"""
        # delete descendants first
        children = session.query(LastKnownState).filter_by(
            local_root=local_root, parent_path=doc_pair.path).all()
        for child in children:
            self._mark_deleted_local_recursive(local_root, session, child)

        # update the state of the parent it-self
        if doc_pair.remote_ref is None:
            # Unbound child metadata can be removed
            session.delete(doc_pair)
        else:
            # mark it for remote deletion
            doc_pair.update_local(None)

    def _scan_local_recursive(self, local_root, session, client,
                              doc_pair, local_info):
        """Recursively scan the bound local folder looking for updates"""
        if local_info is None:
            log.error("Cannot bind %r to missing local info" %
                             doc_pair)
#            raise ValueError("Cannot bind %r to missing local info" %
#                             doc_pair)
            # TODO: the database is corrupted or a binding root has been deleted manually
            # What is the recovery? create another root?
            raise RecoverableError("Cannot find %s" % doc_pair.local_root, "Verify the CloudDesk folder in Preferences...")

        # Update the pair state from the collected local info
        doc_pair.update_local(local_info)

        if not local_info.folderish:
            # No children to align, early stop.
            return

        # detect recently deleted children
        try:
            children_info = client.get_children_info(local_info.path)
        except OSError:
            # The folder has been deleted in the mean time
            return

        children_path = set(c.path for c in children_info)

        q = session.query(LastKnownState).filter_by(
            local_root=local_root,
            parent_path=local_info.path,
        )
        if len(children_path) > 0:
            q = q.filter(not_(LastKnownState.path.in_(children_path)))

        for deleted in q.all():
            self._mark_deleted_local_recursive(local_root, session, deleted)

        # recursively update children
        for child_info in children_info:

            # TODO: detect whether this is a __digit suffix name and relax the
            # alignment queries accordingly
            child_name = os.path.basename(child_info.path)
            child_pair = session.query(LastKnownState).filter_by(
                local_root=local_root,
                path=child_info.path).first()

            if child_pair is None:
                # Try to find an existing remote doc that has not yet been
                # bound to any local file that would align with both name
                # and digest
                try:
                    child_digest = child_info.get_digest()
                    child_pair = session.query(LastKnownState).filter_by(
                        local_root=local_root,
                        path=None,
                        remote_parent_ref=doc_pair.remote_ref,
                        remote_name=child_name,
                        folderish=child_info.folderish,
                        remote_digest=child_digest,
                    ).first()
                except (IOError, WindowsError):
                    # The file is currently being accessed and we cannot
                    # compute the digest
                    log.debug("Cannot perform alignment of %r using"
                              " digest info due to concurrent file"
                              " access", local_info.filepath)

            if child_pair is None:
                # Previous attempt has failed: relax the digest constraint
                child_pair = session.query(LastKnownState).filter_by(
                    local_root=local_root,
                    path=None,
                    remote_parent_ref=doc_pair.remote_ref,
                    remote_name=child_name,
                    folderish=child_info.folderish,
                ).first()

            if child_pair is None:
                # Could not find any pair state to align to, create one
                child_pair = LastKnownState(local_root, local_info=child_info, fault_tolerant=self.fault_tolerant)
                session.add(child_pair)

            self._scan_local_recursive(local_root, session, client,
                                       child_pair, child_info)

    def scan_remote(self, local_root, session=None):
        """Recursively scan the bound remote folder looking for updates"""
        if session is None:
            session = self.get_session()

        root_state = session.query(LastKnownState).filter_by(
            local_root=local_root, path='/').one()

        try:
            client = self.get_remote_client_from_docpair(root_state)
            root_info = client.get_info(root_state.remote_ref,
                                        fetch_parent_uid=False)
        except NotFound:
            # remote folder has been deleted, remote the binding
            log.debug("Unbinding %r because of remote deletion.",
                      local_root)
            self.unbind_root(local_root, session=session)
            return

        # recursive update
        self._scan_remote_recursive(local_root, session, client,
                                    root_state, root_info)
        session.commit()

    def _mark_deleted_remote_recursive(self, local_root, session, doc_pair):
        """Update the metadata of the descendants of remotely deleted doc"""
        # delete descendants first
        children = session.query(LastKnownState).filter_by(
            local_root=local_root,
            remote_parent_ref=doc_pair.remote_ref).all()
        for child in children:
            self._mark_deleted_remote_recursive(local_root, session, child)

        # update the state of the parent it-self
        if doc_pair.path is None:
            # Unbound child metadata can be removed
            session.delete(doc_pair)
        else:
            # schedule it for local deletion
            doc_pair.update_remote(None)

    def _scan_remote_recursive(self, local_root, session, client,
                               doc_pair, remote_info):
        """Recursively scan the bound remote folder looking for updates"""
        if remote_info is None:
            raise ValueError("Cannot bind %r to missing remote info" %
                             doc_pair)

        # Update the pair state from the collected remote info
        doc_pair.update_remote(remote_info)

        if not remote_info.folderish:
            # No children to align, early stop.
            return

        # detect recently deleted children
        children_info = client.get_children_info(remote_info.uid)
        children_refs = set(c.uid for c in children_info)

        q = session.query(LastKnownState).filter_by(
            local_root=local_root,
            remote_parent_ref=remote_info.uid,
        )
        if len(children_refs) > 0:
            q = q.filter(not_(LastKnownState.remote_ref.in_(children_refs)))

        for deleted in q.all():
            self._mark_deleted_remote_recursive(local_root, session, deleted)

        # recursively update children
        for child_info in children_info:

            # TODO: detect whether this is a __digit suffix name and relax the
            # alignment queries accordingly
            child_name = child_info.name
            child_pair = session.query(LastKnownState).filter_by(
                local_root=local_root,
                remote_ref=child_info.uid).first()

            if child_pair is None:
                # Try to find an existing local doc that has not yet been
                # bound to any remote file that would align with both name
                # and digest
                child_pair = session.query(LastKnownState).filter_by(
                    local_root=local_root,
                    remote_ref=None,
                    parent_path=doc_pair.path,
                    local_name=child_name,
                    folderish=child_info.folderish,
                    local_digest=child_info.get_digest(),
                ).first()

            if child_pair is None:
                # Previous attempt has failed: relax the digest constraint
                child_pair = session.query(LastKnownState).filter_by(
                    local_root=local_root,
                    remote_ref=None,
                    parent_path=doc_pair.path,
                    local_name=child_name,
                    folderish=child_info.folderish,
                ).first()

            if child_pair is None:
                # Could not find any pair state to align to, create one
                child_pair = LastKnownState(
                    local_root, remote_info=child_info, fault_tolerant=self.fault_tolerant)
                session.add(child_pair)

            self._scan_remote_recursive(local_root, session, client,
                                        child_pair, child_info)

    def refresh_remote_folders_from_log(self, root_binding):
        """Query the remote server audit log looking for state updates."""
        # TODO
        raise NotImplementedError()

    def list_pending(self, limit=100, local_root=None, session=None):
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

    def next_pending(self, local_root=None, session=None):
        """Return the next pending file to synchronize or None"""
        pending = self.list_pending(limit=1, local_root=local_root,
                                    session=session)
        return pending[0] if len(pending) > 0 else None

    def _get_client_cache(self):
        if not hasattr(self._local, 'remote_clients'):
            self._local.remote_clients = dict()
        return self._local.remote_clients

    def get_remote_client(self, server_binding, base_folder=None,
                          repository='default'):
        cache = self._get_client_cache()
        sb = server_binding
        cache_key = (sb.server_url, sb.remote_user, self.device_id, base_folder,
                     repository)
        remote_client = cache.get(cache_key)

        if remote_client is None:
            remote_client = self.nuxeo_client_factory(
                sb.server_url, sb.remote_user, self.device_id,
                token=sb.remote_token, password=sb.remote_password,
                base_folder=base_folder, repository=repository)
            cache[cache_key] = remote_client
        # Make it possible to have the remote client simulate any kind of
        # failure
        remote_client.make_raise(self._remote_error)
        return remote_client

    def _invalidate_client_cache(self, server_url):
        cache = self._get_client_cache()
        for key, client in cache.items():
            if client.server_url == server_url:
                del cache[key]

    def get_remote_client_from_docpair(self, doc_pair):
        """Fetch a client from the cache or create a new instance"""
        rb = doc_pair.root_binding
        sb = rb.server_binding
        return self.get_remote_client(sb, base_folder=rb.remote_root,
                                      repository=rb.remote_repo)

    # TODO: move the synchronization related methods in a dedicated class

    def synchronize_one(self, doc_pair, session=None, frontend=None, status=None):
        """Refresh state a perform network transfer for a pair of documents."""
        if frontend is not None:
            frontend.notify_start_transfer()
            
        if session is None:
            session = self.get_session()
        # Find a cached remote client for the server binding of the file to
        # synchronize
        remote_client = self.get_remote_client_from_docpair(doc_pair)
        # local clients are cheap
        local_client = doc_pair.get_local_client()

        # Update the status the collected info of this file to make sure
        # we won't perfom inconsistent operations

        if doc_pair.path is not None:
            doc_pair.refresh_local(local_client)
        if doc_pair.remote_ref is not None:
            remote_info = doc_pair.refresh_remote(remote_client)

        # Detect creation
        if (doc_pair.local_state != 'deleted'
            and doc_pair.remote_state != 'deleted'):
            if doc_pair.remote_ref is None and doc_pair.path is not None:
                doc_pair.update_state(local_state='created')
            if doc_pair.remote_ref is not None and doc_pair.path is None:
                doc_pair.update_state(remote_state='created')

        if len(session.dirty):
            # Make refreshed state immediately available to other
            # processes as file transfer can take a long time
            session.commit()

        # TODO: refactor blob access API to avoid loading content in memory
        # as python strings

        if doc_pair.pair_state == 'locally_modified':
            # TODO: handle smart versionning policy here (or maybe delegate to
            # a dedicated server-side operation)
            if doc_pair.remote_digest != doc_pair.local_digest:
                log.debug("Updating remote document '%s'.",
                          doc_pair.remote_name)
                remote_client.update_content(
                    doc_pair.remote_ref,
                    local_client.get_content(doc_pair.path),
                    name=doc_pair.remote_name,
                )
                doc_pair.refresh_remote(remote_client)
            doc_pair.update_state('synchronized', 'synchronized')

        elif doc_pair.pair_state == 'remotely_modified':
            if doc_pair.remote_digest != doc_pair.local_digest != None:
                log.debug("Updating local file '%s'.",
                          doc_pair.get_local_abspath())
                content = remote_client.get_content(doc_pair.remote_ref)
                try:
                    local_client.update_content(doc_pair.path, content)
                    doc_pair.refresh_local(local_client)
                    self.update_recent_files(doc_pair, session=session)
                    doc_pair.update_state('synchronized', 'synchronized', status=status)
                except (IOError, WindowsError):
                    log.debug("Delaying update for remotely modified "
                              "content %r due to concurrent file access.",
                              doc_pair)
            else:
                # digest agree, no need to transfer additional bytes over the
                # network
                doc_pair.update_state('synchronized', 'synchronized', status=status)

        elif doc_pair.pair_state == 'locally_created':
            name = os.path.basename(doc_pair.path)
            # Find the parent pair to find the ref of the remote folder to
            # create the document
            parent_pair = session.query(LastKnownState).filter_by(
                local_root=doc_pair.local_root, path=doc_pair.parent_path
            ).first()
            if parent_pair is None or parent_pair.remote_ref is None:
                log.warning(
                    "Parent folder of %r/%r is not bound to a remote folder",
                    doc_pair.local_root, doc_pair.path)
                # Inconsistent state: delete and let the next scan redetect for
                # now
                # TODO: how to handle this case in incremental mode?
                session.delete(doc_pair)
                session.commit()
                return
            parent_ref = parent_pair.remote_ref
            if doc_pair.folderish:
                log.debug("Creating remote folder '%s' in folder '%s'",
                          name, parent_pair.remote_name)
                remote_ref = remote_client.make_folder(parent_ref, name)
            else:
                remote_ref = remote_client.make_file(
                    parent_ref, name,
                    content=local_client.get_content(doc_pair.path))
                log.debug("Creating remote document '%s' in folder '%s'",
                          name, parent_pair.remote_name)
            doc_pair.update_remote(remote_client.get_info(remote_ref))
            doc_pair.update_state('synchronized', 'synchronized')

        elif doc_pair.pair_state == 'remotely_created':
            name = remote_info.name
            # Find the parent pair to find the path of the local folder to
            # create the document into
            parent_pair = session.query(LastKnownState).filter_by(
                local_root=doc_pair.local_root,
                remote_ref=remote_info.parent_uid,
            ).first()
            if parent_pair is None or parent_pair.path is None:
                log.warning(
                    "Parent folder of doc %r (%r:%r) is not bound to a local"
                    " folder",
                    name, doc_pair.remote_path, doc_pair.remote_ref)
                # Inconsistent state: delete and let the next scan redetect for
                # now
                # TODO: how to handle this case in incremental mode?
                session.delete(doc_pair)
                session.commit()
                return
            parent_path = parent_pair.path
            if doc_pair.folderish:
                path = local_client.make_folder(parent_path, name)
                log.debug("Creating local folder '%s' in '%s'", name,
                          parent_pair.get_local_abspath())
            else:
                path = local_client.make_file(
                    parent_path, name,
                    content=remote_client.get_content(doc_pair.remote_ref))
                log.debug("Creating local document '%s' in '%s'", name,
                          parent_pair.get_local_abspath())
            doc_pair.update_local(local_client.get_info(path))
            self.update_recent_files(doc_pair, session=session)
            doc_pair.update_state('synchronized', 'synchronized', status=status)

        elif doc_pair.pair_state == 'locally_deleted':
            if doc_pair.path == '/':
                log.debug("Unbinding local root '%s'", doc_pair.local_root)
                # Special case: unbind root instead of performing deletion
                self.unbind_root(doc_pair.local_root, session=session)
            else:
                if doc_pair.remote_ref is not None:
                    # TODO: handle trash management with a dedicated server
                    # side operations?
                    log.debug("Deleting remote doc '%s' (%s)",
                              doc_pair.remote_name, doc_pair.remote_ref)
                    remote_client.delete(doc_pair.remote_ref)
                # XXX: shall we also delete all the subcontent / folder at
                # once in the medata table?
                session.delete(doc_pair)

        elif doc_pair.pair_state == 'remotely_deleted':
            if doc_pair.path is not None:
                try:
                    # TODO: handle OS-specific trash management?
                    log.debug("Deleting local doc '%s'",
                              doc_pair.get_local_abspath())
                    self.update_recent_files(doc_pair, session=session)
                    local_client.delete(doc_pair.path)
                    doc_pair.update_state(status=status)
                    session.delete(doc_pair)
                    # XXX: shall we also delete all the subcontent / folder at
                    # once in the medata table?
                except (IOError, WindowsError):
                    # Under Windows deletion can be impossible while another
                    # process is accessing the same file (e.g. word processor)
                    # TODO: be more specific as detecting this case:
                    # shall we restrict to the case e.errno == 13 ?
                    log.debug(
                        "Deletion of '%s' delayed due to concurrent"
                        "editing of this file by another process.",
                        doc_pair.get_local_abspath())
            else:
                session.delete(doc_pair)

        elif doc_pair.pair_state == 'deleted':
            # No need to store this information any further
            self.update_recent_files(doc_pair, session=session)
            session.delete(doc_pair)
            session.commit()

        elif doc_pair.pair_state == 'conflicted':
            if doc_pair.local_digest == doc_pair.remote_digest != None:
                # Automated conflict resolution based on digest content:
                doc_pair.update_state('synchronized', 'synchronized', status=status)
        else:
            log.warning("Unhandled pair_state: %r for %r",
                          doc_pair.pair_state, doc_pair)

        # TODO: handle other cases such as moves and lock updates

        # Ensure that concurrent process can monitor the synchronization
        # progress
        if len(session.dirty) != 0 or len(session.deleted) != 0:
            session.commit()
            
        if frontend is not None:
            frontend.notify_stop_transfer()

    def synchronize(self, limit=None, local_root=None, fault_tolerant=False, sync_operation=None, frontend=None, status=None):
        """Synchronize one file at a time from the pending list.

        Fault tolerant mode is meant to be skip problematic documents while not
        preventing the rest of the synchronization loop to work on documents
        that work as expected.

        This mode will probably hide real Nuxeo Drive bugs in the
        logs. It should thus not be enabled when running tests for the
        synchronization code but might be useful when running Nuxeo
        Drive in daemon mode.
        """
        synchronized = 0
        session = self.get_session()
        doc_pair = self.next_pending(local_root=local_root, session=session)
        while doc_pair is not None and (limit is None or synchronized < limit):
            if self.should_pause_synchronization(sync_operation):
                break
            
            if fault_tolerant:
                try:
                    self.synchronize_one(doc_pair, session=session, frontend=frontend, status=status)
                    synchronized += 1
                except Exception as e:
                    log.error("Failed to synchronize %r: %r",
                              doc_pair, e, exc_info=True)
                    # TODO: flag pending and all descendant as failed with a
                    # time stamp and make next_pending ignore recently (e.g.
                    # up to 30s) failed synchronized pairs
                    raise NotImplementedError(
                        'Fault tolerant synchronization not implemented yet.')
            else:
                self.synchronize_one(doc_pair, session=session, frontend=frontend, status=status)
                synchronized += 1

            doc_pair = self.next_pending(local_root=local_root,
                                         session=session)
   
        return synchronized

    def _get_sync_pid_filepath(self, process_name="sync"):
        return os.path.join(self.config_folder, 'nxdrive_%s.pid' % process_name)

    def check_running(self, process_name="sync"):
        """Check whether another sync process is already runnning

        If nxdrive.pid file already exists and the pid points to a running
        nxdrive program then return the pid. Return None otherwise.

        """
        pid_filepath = self._get_sync_pid_filepath(process_name=process_name)
        if os.path.exists(pid_filepath):
            with open(pid_filepath, 'rb') as f:
                pid = int(f.read().strip())
                try:
                    p = psutil.Process(pid)
                    # Check that this is a nxdrive process by looking at the
                    # process name and commandline
                    # TODO: be more specific using the p.exe attribute
                    if 'ndrive' in p.name:
                        return pid
                    if 'Nuxeo Drive' in p.name:
                        return pid
                    for component in p.cmdline:
                        if 'ndrive' in component:
                            return pid
                        if 'nxdrive' in component:
                            return pid
                except psutil.NoSuchProcess:
                    pass
                # This is a pid file pointing to either a stopped process
                # or a non-nxdrive process: let's delete it if possible
                try:
                    os.unlink(pid_filepath)
                    log.info("Removed old pid file: %s for"
                            " stopped process %d", pid_filepath, pid)
                except Exception, e:
                    log.warning("Failed to remove stalled pid file: %s"
                            " for stopped process %d: %r",
                            pid_filepath, pid, e)
                return None
        return None

    def should_stop_synchronization(self):
        """Check whether another process has told the synchronizer to stop"""
        stop_file = os.path.join(self.config_folder, "stop_%d" % os.getpid())
        if os.path.exists(stop_file):
            os.unlink(stop_file)
            return True
        return False

    def should_pause_synchronization(self, sync_operation=None, frontend=None):
        """Check if GUI paused the synchronization.
        User can use "Pause" and "Resume" actions.
		Alternatively, check whether another process has told the synchronizer to stop.
		"""
        if not sync_operation == None: 
            paused = False
            with sync_operation.lock:
                if sync_operation.pause:
                    paused = sync_operation.paused = True     
                    sync_operation.pause = False        
             
            while paused:
                log.debug("pausing synchronization")
                if frontend is not None:
                    frontend.notify_stop_transfer()
                sync_operation.event.wait()
                #check whether should stop instead of resuming
                if self.should_stop_synchronization():
                    return True
                log.debug("resuming synchronization")
                paused = False
                with sync_operation.lock:
                    if sync_operation.pause:
                        paused = sync_operation.paused = True     
                        sync_operation.pause = False   
                    else: 
                        sync_operation.paused = False
                        
            return False
             
    def _log_offline(self, exception, context):
        if isinstance(exception, urllib2.HTTPError):
            msg = ("Client offline in %s: HTTP error with code %d"
                    % (context, exception.code))
        else:
            msg = "Client offline in %s: %s" % (context, exception)
        log.trace(msg)

    def loop(self, full_local_scan=True, full_remote_scan=True, delay=10,
             max_sync_step=50, max_loops=None, fault_tolerant=True,
             frontend=None, limit_pending=100, sync_operation=None):
        """Forever loop to scan / refresh states and perform synchronization

        delay is a delay in seconds that ensures that two consecutive
        scans won't happen too closely from one another.
        """
        
        self.fault_tolerant = fault_tolerant
        if frontend is not None:
            frontend.notify_sync_started()
        pid = self.check_running(process_name="sync")
        if pid is not None:
            log.warning(
                    "Synchronization process with pid %d already running.",
                    pid)
            return

        # Write the pid of this process
        pid_filepath = self._get_sync_pid_filepath(process_name="sync")
        pid = os.getpid()
        with open(pid_filepath, 'wb') as f:
            f.write(str(pid))

        log.info("Starting synchronization (pid=%d)", pid)
        self.continue_synchronization = True
        if not full_local_scan:
            # TODO: ensure that the watchdog thread for incremental state
            # update is started thread is started (and make sure it's able to
            # detect new bindings while running)
            raise NotImplementedError()

#        previous_time = time()
        previous_time = datetime.now()
        first_pass = True
        session = self.get_session()
        
        loop_count = 0
        try:
            while True:

                if self.should_stop_synchronization():
                    log.info("Stopping synchronization (pid=%d)", pid)
                    break
                if (max_loops is not None and loop_count > max_loops):
                    log.info("Stopping synchronization after %d loops",
                             loop_count)
                    break
                
                self.get_folders(session, frontend=frontend)
                self.update_roots(session, frontend=frontend)

                bindings = session.query(RootBinding).all()
                status = {}
                for rb in bindings:
                    try:
                        if self.should_pause_synchronization(sync_operation):
                            break;
                        # the alternative to local full scan is the watchdog
                        # thread
                        if full_local_scan or first_pass:
                            self.scan_local(rb.local_root, session)

                        if rb.server_binding.has_invalid_credentials():
                            # Skip roots for servers with missing credentials
                            continue

                        if full_remote_scan or first_pass:
                            self.scan_remote(rb.local_root, session)
                        else:
                            self.refresh_remote_from_log(rb.remote_ref)
                        if frontend is not None:
                            n_pending = len(self.list_pending(limit=limit_pending))
                            reached_limit = n_pending == limit_pending
                            frontend.notify_pending(rb.local_folder, n_pending,
                                    or_more=reached_limit)

                        self.synchronize(limit=max_sync_step,
                                         local_root=rb.local_root,
                                         fault_tolerant=fault_tolerant,
                                         sync_operation=sync_operation,
                                         frontend=frontend,
                                         status=status)
                    except POSSIBLE_NETWORK_ERROR_TYPES as e:
                        # Ignore expected possible network related errors
                        self._log_offline(e, "synchronization loop")
                        log.trace("Traceback of ignored network error:",
                                exc_info=True)
                        if frontend is not None:
                            frontend.notify_offline(rb.local_folder, e)

                        # TODO: add a special handling for the invalid
                        # credentials case and mark the server binding
                        # with a special flag in the DB to be skipped by
                        # the synchronization loop until the user decides
                        # to reenable it in the systray menu with a dedicated
                        # action instead
                        self._invalidate_client_cache(
                                rb.server_binding.server_url)

                # safety net to ensure that Nuxe Drive won't eat all the CPU,
                # disk and network resources of the machine scanning over an
                # over the bound folders too often.
#                current_time = time()
                current_time = datetime.now()
                spent = (current_time - previous_time).total_seconds()
                
                # show notifications
                if frontend is not None:
                    frontend.notify_sync_completed(status)
                # update recent files
                    
                if spent < delay:
                    sleep(delay - spent)
                previous_time = current_time
                first_pass = False
                log.debug("loop count=%d", loop_count)
                loop_count += 1

        except KeyboardInterrupt:
            self.get_session().rollback()
            log.info("Interrupted synchronization on user's request.")
            #log.trace("Synchronization interruption at:", exc_info=True)
        except RecoverableError:
            raise
        except:
            self.get_session().rollback()
            raise

        # Clean pid file
        pid_filepath = self._get_sync_pid_filepath()
        try:
            os.unlink(pid_filepath)
        except Exception, e:
            log.warning("Failed to remove stalled pid file: %s"
                    " for stopped process %d: %r",
                    pid_filepath, pid, e)

        finally:
            # Notify UI frontend to take synchronization stop into account and
            # potentially quit the app
            if frontend is not None:
                frontend.notify_sync_stopped()


    def get_state(self, server_url, remote_repo, remote_ref):
        """Find a pair state for the provided remote document identifiers."""
        server_url = self._normalize_url(server_url)
        session = self.get_session()
        try:
            states = session.query(LastKnownState).filter_by(
                remote_ref=remote_ref,
            ).all()
            for state in states:
                rb = state.root_binding
                sb = rb.server_binding
                if (sb.server_url == server_url
                    and rb.remote_repo == remote_repo):
                    return state
        except NoResultFound:
            return None
        
    def update_recent_files(self, doc_pair, session=None):
        if doc_pair.folderish == 1:
            return
        if session is None:
            session = self.get_session()
            
        session.add(RecentFiles(doc_pair.local_name, doc_pair.local_root, doc_pair.pair_state))
        to_be_deleted = session.query(RecentFiles).\
                                order_by(RecentFiles.local_update.desc()).\
                                offset(Constants.RECENT_FILES_COUNT).all()
        map(session.delete, to_be_deleted)
        # if the same file appears as created, modified, etc. AND delete, keep only the deleted one
        stmt = session.query(RecentFiles).filter(RecentFiles.pair_state == 'remotely_deleted').subquery()
        duplicate_files = session.query(RecentFiles).filter(RecentFiles.local_name == stmt.c.local_name).\
                                        filter(RecentFiles.pair_state != 'remotely_deleted').all()
        map(session.delete, duplicate_files)
#        session.commit()

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

                
    def open_local_file(self, fp):
        file_path = os.path.expanduser(fp)
        log.debug('Launching local OS on %s', file_path)
        if sys.platform == 'win32':
            os.startfile(file_path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', file_path])
        else:
            try:
                subprocess.Popen(['xdg-open', file_path])
            except OSError:
                # xdg-open should be supported by recent Gnome, KDE, Xfce
                log.error("Failed to open folder for: '%s'", file_path)        

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
