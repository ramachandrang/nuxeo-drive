import os
import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Sequence
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.orm import backref
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import synonym
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.pool import SingletonThreadPool

from nxdrive.client import RemoteFileSystemClient
from nxdrive.client import LocalClient
from nxdrive.utils import normalized_path
from nxdrive.utils import encrypt_password, decrypt_password
from nxdrive import Constants

WindowsError = None
try:
    from exceptions import WindowsError
except ImportError:
    # This will never be raised under unix
    pass


log = logging.getLogger(__name__)


# make the declarative base class for the ORM mapping
Base = declarative_base()


__model_version__ = 1

# Summary status from last known pair of states

PAIR_STATES = {
    # regular cases
    ('unknown', 'unknown'): 'unknown',
    ('synchronized', 'synchronized'): 'synchronized',
    ('created', 'unknown'): 'locally_created',
    ('unknown', 'created'): 'remotely_created',
    ('modified', 'synchronized'): 'locally_modified',
    ('synchronized', 'modified'): 'remotely_modified',
    ('modified', 'unknown'): 'locally_modified',
    ('unknown', 'modified'): 'remotely_modified',
    ('deleted', 'synchronized'): 'locally_deleted',
    ('synchronized', 'deleted'): 'remotely_deleted',
    ('deleted', 'deleted'): 'deleted',

    # conflicts with automatic resolution
    ('created', 'deleted'): 'locally_created',
    ('deleted', 'created'): 'remotely_created',
    ('modified', 'deleted'): 'locally_created',
    ('deleted', 'modified'): 'remotely_created',

    # conflict cases that need special
    ('modified', 'modified'): 'conflicted',
    ('created', 'created'): 'conflicted',
}


class DeviceConfig(Base):
    """Holds Nuxeo Drive configuration parameters

    This is expected to be a single row table.
    """
    __tablename__ = 'device_config'

    device_id = Column(String, primary_key = True)

    def __init__(self, device_id = None):
        self.device_id = uuid.uuid1().hex if device_id is None else device_id


class ServerBinding(Base):
    __tablename__ = 'server_bindings'

    local_folder = Column(String, primary_key = True)
    server_url = Column(String)
    remote_user = Column(String)
    nag_signin = Column(Boolean)
    quota_exceeded = Column(Boolean)
    maintenance = Column(Boolean)
    next_nag_quota = Column(DateTime)
    next_nag_maintenance = Column(DateTime)
    next_maintenance_check = Column(DateTime)
    remote_password = Column(String)
    __remote_password = Column('remote_password', String)
    remote_token = Column(String)
    last_sync_date = Column(Integer)
    last_root_definitions = Column(String)
    __fdtoken = Column('fdtoken', String)
    password_hash = Column(String)
    password_key = Column(String)
    fdtoken_creation_date = Column(DateTime)
    total_storage = Column(Integer)
    used_storage = Column(Integer)
    # passive_updates=False *only* needed if the database
    # does not implement ON UPDATE CASCADE
#    roots = relationship("RootBinding", passive_updates = False, passive_deletes = True, cascade = "all, delete, delete-orphan")
    folders = relationship("SyncFolders", passive_updates = False, passive_deletes = True, cascade = "all, delete, delete-orphan")

    def __init__(self, local_folder, server_url, remote_user,
                 remote_password = None, remote_token = None,
                 fdtoken = None, password_hash = None, fdtoken_creation_date = None):
        self.local_folder = local_folder
        self.server_url = server_url
        self.remote_user = remote_user
        self.nag_signin = False
        self.quota_exceeded = False
        self.maintenance = False
        self.next_nag_quota = None
        self.next_nag_maintenance = datetime.now()
        self.next_maintenance_check = None
        # Password is only stored if the server does not support token based authentication
        # CHANGED: Password IS currently stored for (1) refresh the token when it expires,
        # and (2) open the site in the browser.
        # Password is also encrypted.
        self.remote_password = remote_password
        self.remote_token = remote_token
        # Used for browser to access CloudDesk without log in prompting
        self.fdtoken = fdtoken
        if fdtoken_creation_date is not None:
            self.fdtoken_creation_date = fdtoken_creation_date
        # Used to re-generate the federated token (expires in 15min by default)
        self.password_hash = password_hash
        self.total_storage = 0
        self.used_storage = 0

    @declared_attr
    def fdtoken(self):
        return synonym('__fdtoken', descriptor = property(self.get_fdtoken, self.set_fdtoken))

    def get_fdtoken(self):
        return self.__fdtoken

    def set_fdtoken(self, v):
        self.__fdtoken = v
        if v is not None:
            self.fdtoken_creation_date = datetime.now()

    @declared_attr
    def remote_password(self):
        return synonym('__remote_password', descriptor = property(self.get_remote_password, self.set_remote_password))

    def get_remote_password(self):
        return decrypt_password(self.__remote_password, self.password_key)

    def set_remote_password(self, v):
        if v is not None:
            self.__remote_password, self.password_key = encrypt_password(v)

    def invalidate_credentials(self):
        """Ensure that all stored credentials are zeroed."""
        self.remote_password = None
        self.remote_token = None
        self.password_hash = None
        self.federated_token = None

    def has_invalid_credentials(self):
        """Check whether at least one credential is active"""
        return self.remote_password is None and self.remote_token is None

    def __eq__(self, other):
        return (isinstance(other, ServerBinding) and
                self.local_folder == other.local_folder and
                self.server_url == other.server_url and
                self.remote_user == other.remote_user)

    def __ne__(self, other):
        return not self.__eq__(other)

    def update_server_quota_status(self, used, total, size):
        if self.quota_exceeded:
            if total - used > size:
                self.quota_exceeded = False
        else:
            self.quota_exceeded = True
            self.next_nag_quota = datetime.now()

    def update_server_maintenance_status(self, retry_after):
        # TODO if not in maintenance mode, set the maintenance status
        if retry_after > 0:
            self.maintenance = True
        else:
            self.maintenance = False
        self.next_maintenance_check = datetime.now() + timedelta(seconds=retry_after)
        
    def update_server_maintenance_schedule(self):
        self.next_nag_maintenance = datetime.now() + timedelta(seconds=Constants.SERVICE_NOTIFICATION_INTERVAL)

    def nag_maintenance_schedule(self):
        if self.maintenance:
            return False
        elif self.next_nag_maintenance is None:
            return False
        elif not self.maintenance and datetime.now() > self.next_nag_maintenance:
            return True
        else:
            return False
            
    def check_for_maintenance(self):
        if self.maintenance and datetime.now() > self.next_maintenance_check:
            self.maintenance = False
            return True
        else:
            return False
            
    def nag_quota_exceeded(self):
        if self.next_nag_quota is None:
            return False
        elif self.quota_exceeded and datetime.now() > self.next_nag_quota:
            self.nag_quota_exceeded = datetime.now() + timedelta(seconds=Constants.SERVICE_NOTIFICATION_INTERVAL)
            return True
        else:
            return False
        
    def update_storage(self, used, total):
        self.total_storage = total
        self.used_storage = used

#class RootBinding(Base):
#    __tablename__ = 'root_bindings'
#
#    local_root = Column(String, primary_key = True)
#    remote_repo = Column(String)
#    remote_root = Column(String, ForeignKey('sync_folders.remote_id'))
#    local_folder = Column(String, ForeignKey('server_bindings.local_folder', onupdate = "cascade", ondelete = "cascade"))
#    server_binding = relationship('ServerBinding')
#
#    def __init__(self, local_root, remote_repo, remote_root, local_folder = None):
#        local_root = normalized_path(local_root)
#        self.local_root = local_root
#        self.remote_repo = remote_repo
#        self.remote_root = remote_root
#
#        # expected local folder should be the direct parent of the local root
#        # MC That's not always the case, example:
#        # - roots under "Others' Docs" in CloudDesk are under "Others Docs" locally
#        if local_folder is None:
#            local_folder = normalized_path(os.path.join(local_root, '..'))
#        self.local_folder = local_folder
#
#    def __repr__(self):
#        return ("RootBinding<local_root=%r, local_folder=%r, remote_repo=%r,"
#                "remote_root=%r>" % (self.local_root, self.local_folder,
#                                     self.remote_repo, self.remote_root))

class SyncFolders(Base):
    __tablename__ = 'sync_folders'

    remote_id = Column(String, primary_key = True)
    remote_name = Column(String)
    remote_root = Column(Integer)
    remote_parent = Column(String, ForeignKey('sync_folders.remote_id'))
    check_state = Column(Boolean) # indicates whether the checkbox in the selection UI us checked (True)
    bind_state = Column(Boolean) # indicates whether it is a registered sync root (True)
    local_folder = Column(String, ForeignKey('server_bindings.local_folder', onupdate = "cascade", ondelete = "cascade"))
# TO BE DELETED
#    checked = relationship('RootBinding', uselist = False, backref = 'folder')

#    server_binding = relationship(
#                    'ServerBinding', backref=backref("folders", cascade="all, delete-orphan"))
    server_binding = relationship('ServerBinding')
    children = relationship("SyncFolders")

    def __init__(self, remote_id, remote_name, remote_parent, local_folder, remote_root = None, check_state = False, bind_state = False):
        self.remote_id = remote_id
        self.remote_name = remote_name
        self.remote_parent = remote_parent
        self.remote_root = remote_root
        self.local_folder = local_folder
        self.check_state = check_state
        self.bind_state = bind_state

    def __str__(self):
        return ("SyncFolders<remote_name=%r, remote_id=%r, remote_parent=%r, "
                "local_folder=%r, %checked, %synced>" % (self.remote_name, self.remote_id, self.remote_parent,
                                      self.local_folder, '' if self.check_state else 'not ', '' if self.bind_state else 'not '))

class RecentFiles(Base):
    __tablename__ = 'recent_files'

    id = Column(Integer, Sequence('file_id_seq'), primary_key = True)
    local_name = Column(String)
    local_root = Column(String)
    local_folder = Column(String)
    local_update = Column(DateTime, index = True)
    pair_state = Column(String)

    def __init__(self, local_name, local_root, local_folder, pair_state):
        self.local_name = local_name
        self.local_root = local_root
        self.local_folder = local_folder
        self.pair_state = pair_state
        self.local_update = datetime.now()

class LastKnownState(Base):
    """Aggregate state aggregated from last collected events."""
    __tablename__ = 'last_known_states'

    id = Column(Integer, Sequence('state_id_seq'), primary_key=True)

    local_folder = Column(String, ForeignKey('server_bindings.local_folder'),
                          index=True)
    server_binding = relationship(
        'ServerBinding',
        backref=backref("states", cascade="all, delete-orphan"))

    # Timestamps to detect modifications
    last_local_updated = Column(DateTime)
    last_remote_updated = Column(DateTime)

    # Save the digest too for better updates / moves detection
    local_digest = Column(String, index = True)
    remote_digest = Column(String, index = True)

    # Path from root using unix separator, '/' for the root it-self.
    local_path = Column(String, index=True)

    # Remote reference (instead of path based lookup)
    remote_ref = Column(String, index = True)

    # Parent path from root / ref for fast children queries,
    # can be None for the root it-self.
    local_parent_path = Column(String, index=True)
    remote_parent_ref = Column(String, index=True)
    remote_parent_path = Column(String)  # for ordering only

    # Names for fast alignment queries
    local_name = Column(String, index = True)
    remote_name = Column(String, index = True)

    folderish = Column(Integer)

    # Last known state based on event log
    local_state = Column(String)
    remote_state = Column(String)
    pair_state = Column(String, index = True)

    # Track move operations to avoid loosing history
    locally_moved_from = Column(String)
    locally_moved_to = Column(String)
    remotely_moved_from = Column(String)
    remotely_moved_to = Column(String)

    # Log date of sync errors to be able to skip documents in error for some
    # time
    last_sync_error_date = Column(DateTime)

    def __init__(self, local_folder, local_info=None,
                 remote_info=None, local_state='unknown',
                 remote_state='unknown'):
        self.local_folder = local_folder
        if local_info is None and remote_info is None:
            raise ValueError(
                "At least local_info or remote_info should be provided")

        if local_info is not None:
            self.update_local(local_info)
        if remote_info is not None:
            self.update_remote(remote_info)

        self.update_state(local_state = local_state, remote_state = remote_state)

    def update_state(self, local_state=None, remote_state=None):
        if local_state is not None and self.local_state != local_state:
            self.local_state = local_state
        if remote_state is not None and self.remote_state != remote_state:
            self.remote_state = remote_state

        # Detect heuristically aligned situations
        if (self.local_path is not None and self.remote_ref is not None
            and self.local_state == self.remote_state == 'unknown'):
            if self.folderish or self.local_digest == self.remote_digest:
                self.local_state = 'synchronized'
                self.remote_state = 'synchronized'

        pair = (self.local_state, self.remote_state)
        pair_state = PAIR_STATES.get(pair, 'unknown')
        if self.pair_state != pair_state:
            self.pair_state = pair_state

    def __repr__(self):
        return ("LastKnownState<local_folder=%r, local_path=%r, "
                "remote_name=%r, local_state=%r, remote_state=%r>") % (
                    os.path.basename(self.local_folder),
                    self.local_path, self.remote_name,
                    self.local_state, self.remote_state)

    def get_local_client(self):
        return LocalClient(self.local_folder)

    def get_remote_client(self):
        sb = self.server_binding
        return RemoteFileSystemClient(sb.server_url, sb.remote_user,
             sb.remote_password)

    def refresh_local(self, client = None):
        """Update the state from the local filesystem info."""
        client = client if client is not None else self.get_local_client()
        local_info = client.get_info(self.local_path, raise_if_missing=False)
        self.update_local(local_info)
        return local_info

    def update_local(self, local_info):
        """Update the state from pre-fetched local filesystem info."""
        if local_info is None:
            if self.local_state in ('unknown', 'created', 'modified',
                                    'synchronized'):
                # the file use to exist, it has been deleted
                self.update_state(local_state='deleted')
            return

        local_state = None

        if self.local_path is None:
            # This state only has a remote info and this is the first time
            # we update the local info from the file system
            self.local_path = local_info.path
            if self.local_path != '/':
                self.local_name = os.path.basename(local_info.path)
                local_parent_path, _ = local_info.path.rsplit('/', 1)
                if local_parent_path == '':
                    self.local_parent_path = '/'
                else:
                    self.local_parent_path = local_parent_path
            else:
                self.local_name = os.path.basename(self.local_folder)
                self.local_parent_path = None

        if self.local_path != local_info.path:
            raise ValueError("State %r cannot be mapped to '%s%s'" % (
                self, self.local_folder, local_info.path))

        # Shall we recompute the digest from the current file?
        update_digest = self.local_digest == None

        if self.last_local_updated is None:
            self.last_local_updated = local_info.last_modification_time
            self.folderish = local_info.folderish
            update_digest = True

        elif local_info.last_modification_time > self.last_local_updated:
            self.last_local_updated = local_info.last_modification_time
            self.folderish = local_info.folderish
            if not self.folderish:
                # The time stamp of folderish folder seems to be updated when
                # children are added under Linux? Is this the same under OSX
                # and Windows?
                local_state = 'modified'
            update_digest = True

        if update_digest:
            try:
                self.local_digest = local_info.get_digest()
            except (IOError, WindowsError):
                # This can fail when another process is writing the same file
                # let's postpone digest computation in that case
                log.debug("Delaying local digest computation for %r"
                          " due to possible concurrent file access.",
                          local_info.filepath)

        # XXX: shall we store local_folderish and remote_folderish to
        # detect such kind of conflicts instead?
        self.update_state(local_state = local_state)

    def refresh_remote(self, client = None, fetch_parent_uid = True):
        """Update the state from the remote server info.

        Can reuse an existing client to spare some redundant client init HTTP
        request.
        """
        client = client if client is not None else self.get_remote_client()
        remote_info = client.get_info(self.remote_ref, fetch_parent_uid = fetch_parent_uid, raise_if_missing = False)
        self.update_remote(remote_info)
        return remote_info

    def update_remote(self, remote_info):
        """Update the state from the pre-fetched remote server info."""
        if remote_info is None:
            if self.remote_state in ('unknown', 'created', 'modified',
                                     'synchronized'):
                self.update_state(remote_state='deleted')
            return

        remote_state = None
        if self.remote_ref is None:
            self.remote_ref = remote_info.uid
            self.remote_parent_ref = remote_info.parent_uid

        if self.remote_ref != remote_info.uid:
            raise ValueError("State %r (%s) cannot be mapped to remote"
                             " doc %r (%s)" % (
                self, self.remote_ref, remote_info.name, remote_info.uid))

        # Use last known modification time to detect updates
        if self.last_remote_updated is None:
            self.last_remote_updated = remote_info.last_modification_time
        elif remote_info.last_modification_time > self.last_remote_updated:
            self.last_remote_updated = remote_info.last_modification_time
            remote_state = 'modified'

        # Update the remaining metadata
        self.remote_digest = remote_info.get_digest()
        self.folderish = remote_info.folderish
        self.remote_name = remote_info.name
        suffix_len = len(remote_info.uid) + 1
        self.remote_parent_path = remote_info.path[:-suffix_len]
        self.update_state(remote_state=remote_state)

    def get_local_abspath(self):
        relative_path = self.local_path[1:].replace('/', os.path.sep)
        return os.path.join(self.local_folder, relative_path)


class FileEvent(Base):
    __tablename__ = 'fileevents'

    id = Column(Integer, Sequence('fileevent_id_seq'), primary_key=True)
    local_folder = Column(String, ForeignKey('server_bindings.local_folder'))
    utc_time = Column(DateTime)
    path = Column(String)

    server_binding = relationship("ServerBinding")

    def __init__(self, local_folder, path, utc_time=None):
        self.local_folder = local_folder
        if utc_time is None:
            utc_time = datetime.utcnow()


class ServerEvent(Base):
    __tablename__ = 'serverevents'

    id = Column(Integer, Sequence('serverevent_id_seq'), primary_key = True)
    local_folder = Column(String, ForeignKey('server_bindings.local_folder'))
    utc_time = Column(DateTime)
    message = Column(String)
    message_type = Column(String)

    server_binding = relationship("ServerBinding", uselist=False, backref="server_events")

    def __init__(self, local_folder, message, message_type, utc_time = None):
        self.local_folder = local_folder
        self.message = message
        self.message_type = message_type
        if utc_time is None:
            self.utc_time = datetime.utcnow()
        else:
            self.utc_time = utc_time
            
def init_db(nxdrive_home, echo = False, scoped_sessions = True, poolclass = None):
    """Return an engine and session maker configured for using nxdrive_home

    The database is created in nxdrive_home if missing and the tables
    are intialized based on the model classes from this module (they
    all inherit the same abstract base class.

    If scoped_sessions is True, sessions built with this maker are reusable
    thread local singletons.

    """
    # We store the DB as SQLite files in the nxdrive_home folder
    dbfile = os.path.join(normalized_path(nxdrive_home), 'nxdrive.db')

    # SQLite cannot share connections across threads hence it's safer to
    # enforce this at the connection pool level
    poolclass = SingletonThreadPool if poolclass is None else poolclass
    engine = create_engine('sqlite:///' + dbfile, echo=echo,
                           poolclass=poolclass)

    # Ensure that the tables are properly initialized
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    if scoped_sessions:
        maker = scoped_session(maker)
    return engine, maker