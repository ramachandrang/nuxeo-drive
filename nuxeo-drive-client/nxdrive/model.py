import os
import uuid
import logging
import datetime
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
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import synonym
from sqlalchemy.ext.declarative import declared_attr

from nxdrive.client import NuxeoClient
from nxdrive.client import LocalClient
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

    device_id = Column(String, primary_key=True)

    def __init__(self, device_id=None):
        self.device_id = uuid.uuid1().hex if device_id is None else device_id


class ServerBinding(Base):
    __tablename__ = 'server_bindings'

    local_folder = Column(String, primary_key=True)
    server_url = Column(String)
    remote_user = Column(String)
    remote_password = Column(String)
    remote_token = Column(String)
    __fdtoken = Column('fdtoken', String)
    password_hash = Column(String)
    fdtoken_creation_date = Column(DateTime)

    def __init__(self, local_folder, server_url, remote_user,
                 remote_password=None, remote_token=None, 
                 fdtoken=None, password_hash=None, fdtoken_creation_date=None):
        self.local_folder = local_folder
        self.server_url = server_url
        self.remote_user = remote_user
        # Password is only stored if the server does not support token based
        # auth
        self.remote_password = remote_password
        self.remote_token = remote_token
        # Used for browser to access CloudDesk without log in prompting
        self.fdtoken = fdtoken
        if fdtoken_creation_date is not None:
            self.fdtoken_creation_date = fdtoken_creation_date           
        # Used to re-generate the federated token (expires in 15min by default)
        self.password_hash = password_hash
        
    @declared_attr
    def fdtoken(self):
        return synonym('__fdtoken', descriptor=property(self.get_fdtoken, self.set_fdtoken))
    
    def get_fdtoken(self):
        return self.__fdtoken
    
    def set_fdtoken(self, v):
        self.__fdtoken = v
        if v is not None: 
            self.fdtoken_creation_date = datetime.datetime.now()

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

class RootBinding(Base):
    __tablename__ = 'root_bindings'

    local_root = Column(String, primary_key=True)
    remote_repo = Column(String)
    remote_root = Column(String, ForeignKey('sync_folders.remote_id'))
    local_folder = Column(String, ForeignKey('server_bindings.local_folder'))

    server_binding = relationship(
        'ServerBinding',
        backref=backref("roots", cascade="all, delete-orphan"))

    def __init__(self, local_root, remote_repo, remote_root, local_folder=None):
        local_root = os.path.abspath(local_root)
        self.local_root = local_root
        self.remote_repo = remote_repo
        self.remote_root = remote_root

        # expected local folder should be the direct parent of the local root
        # MC That's not always the case, example:
        # - roots under "Others' Docs" in CloudDesk are under "Others Docs" locally
        if local_folder is None:
            local_folder = os.path.abspath(os.path.join(local_root, '..'))
        self.local_folder = local_folder

    def __repr__(self):
        return ("RootBinding<local_root=%r, local_folder=%r, remote_repo=%r,"
                "remote_root=%r>" % (self.local_root, self.local_folder,
                                     self.remote_repo, self.remote_root))

class SyncFolders(Base):
    __tablename__ = 'sync_folders'
    
    remote_id = Column(String, primary_key=True)
    remote_repo = Column(String)
    remote_name = Column(String)
    remote_root = Column(Integer)
    remote_parent = Column(String, ForeignKey('sync_folders.remote_id'))
    state = Column(Boolean)
    local_folder = Column(String, ForeignKey('server_bindings.local_folder'))
    checked = relationship('RootBinding', uselist=False, backref='folder')
    
    server_binding = relationship(
                    'ServerBinding', backref=backref("folders", cascade="all, delete-orphan"))
    children = relationship("SyncFolders")
    
    def __init__(self, remote_id, remote_name, remote_parent, remote_repo, local_folder, remote_root=Constants.ROOT_CLOUDDESK, checked=False):
        self.remote_id = remote_id
        self.remote_name = remote_name
        self.remote_parent = remote_parent
        self.remote_repo = remote_repo
        self.remote_root = remote_root
        self.local_folder = local_folder
        self.checked2 = checked
        
    def __str__(self):
        return ("SyncFolders<remote_name=%r, remote_id=%r, remote_parent=%r, remote_repo=%r, "
                "local_folder=%r, %checked>" % (self.remote_name, self.remote_id, self.remote_parent, 
                                      self.remote_repo, self.local_folder, '' if self.checked2 else 'not '))
        
class LastKnownState(Base):
    """Aggregate state aggregated from last collected events."""
    __tablename__ = 'last_known_states'

    id = Column(Integer, Sequence('state_id_seq'), primary_key=True)
    local_root = Column(String, ForeignKey('root_bindings.local_root'),
                        index=True)
    root_binding = relationship(
        'RootBinding',
        backref=backref("states", cascade="all, delete-orphan"))

    # Timestamps to detect modifications
    last_local_updated = Column(DateTime)
    last_remote_updated = Column(DateTime)

    # Save the digest too for better updates / moves detection
    local_digest = Column(String, index=True)
    remote_digest = Column(String, index=True)

    # Path from root using unix separator, '/' for the root it-self.
    path = Column(String, index=True)
    remote_path = Column(String)  # for ordering only

    # Remote reference (instead of path based lookup)
    remote_ref = Column(String, index=True)

    # Parent path from root / ref for fast children queries,
    # can be None for the root it-self.
    parent_path = Column(String, index=True)
    remote_parent_ref = Column(String, index=True)

    # Names for fast alignment queries
    local_name = Column(String, index=True)
    remote_name = Column(String, index=True)

    folderish = Column(Integer)

    # Last known state based on event log
    local_state = Column(String)
    remote_state = Column(String)
    pair_state = Column(String, index=True)

    # Track move operations to avoid loosing history
    locally_moved_from = Column(String)
    locally_moved_to = Column(String)
    remotely_moved_from = Column(String)
    remotely_moved_to = Column(String)

    def __init__(self, local_root, local_info=None, remote_info=None,
                 local_state='unknown', remote_state='unknown', fault_tolerant=None):
        self.local_root = local_root
        if local_info is None and remote_info is None:
            raise ValueError(
                "At least local_info or remote_info should be provided")

        if local_info is not None:
            self.update_local(local_info)
        if remote_info is not None:
            self.update_remote(remote_info)

        self.update_state(local_state=local_state, remote_state=remote_state)
        self.fault_tolerant = fault_tolerant

    def update_state(self, local_state=None, remote_state=None, status=None):
        if local_state is not None:
            self.local_state = local_state
        if remote_state is not None:
            self.remote_state = remote_state
        pair = (self.local_state, self.remote_state)
        if status is not None and self.folderish == 0:
            try:
                status_item = status[self.pair_state]
                status_item[0] += 1
                if status_item[1] is not None: status_item[1] = self.local_name
                status[self.pair_state] = status_item
            except KeyError:
                status[self.pair_state] = [1, self.local_name]
 
        self.pair_state = PAIR_STATES.get(pair, 'unknown')

    def __repr__(self):
        return ("LastKnownState<local_root=%r, path=%r, "
                "remote_name=%r, local_state=%r, remote_state=%r>") % (
                    os.path.basename(self.local_root),
                    self.path, self.remote_name,
                    self.local_state, self.remote_state)

    def get_local_client(self):
        return LocalClient(self.local_root)

    def get_remote_client(self, factory=None):
        if factory is None:
            factory = NuxeoClient
        rb = self.root_binding
        sb = rb.server_binding
        return factory(
            sb.server_url, sb.remote_user, sb.remote_password,
            base_folder=rb.remote_root, repository=rb.remote_repo,
            fault_tolerant=self.fault_tolerant)

    def refresh_local(self, client=None):
        """Update the state from the local filesystem info."""
        client = client if client is not None else self.get_local_client()
        local_info = client.get_info(self.path, raise_if_missing=None)
        self.update_local(local_info)
        return local_info

    def update_local(self, local_info):
        """Update the state from pre-fetched local filesystem info."""
        if local_info is None:
            if self.local_state in ('unknown', 'created', 'modified',
                                    'synchronized'):
                # the file use to exist, it has been deleted
                self.update_state(local_state='deleted')
                self.local_digest = None
            return

        if self.path is None:
            self.path = local_info.path
            if self.path != '/':
                self.local_name = os.path.basename(local_info.path)
                parent_path, _ = local_info.path.rsplit('/', 1)
                self.parent_path = '/' if parent_path == '' else parent_path
            else:
                self.local_name = os.path.basename(self.local_root)
                self.parent_path = None

        if self.path != local_info.path:
            raise ValueError("State %r cannot be mapped to '%s%s'" % (
                self, self.local_root, local_info.path))

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
                self.update_state(local_state='modified')
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

        # else: nothing to do

    def refresh_remote(self, client=None):
        """Update the state from the remote server info.

        Can reuse an existing client to spare some redundant client init HTTP
        request.
        """
        client = client if client is not None else self.get_remote_client()
        fetch_parent_uid = self.path != '/'
        remote_info = client.get_info(self.remote_ref, raise_if_missing=True,
                                      fetch_parent_uid=fetch_parent_uid)
        self.update_remote(remote_info)
        return remote_info

    def update_remote(self, remote_info):
        """Update the state from the pre-fetched remote server info."""
        if remote_info is None:
            if self.remote_state in ('unknown', 'created', 'modified',
                                     'synchronized'):
                self.update_state(remote_state='deleted')
                self.remote_digest = None
            return

        if self.remote_ref is None:
            self.remote_ref = remote_info.uid
            self.remote_parent_ref = remote_info.parent_uid
            self.remote_name = remote_info.name
            self.remote_path = remote_info.path

        if self.remote_ref != remote_info.uid:
            raise ValueError("State %r cannot be mapped to remote doc %r" % (
                self, remote_info.name))

        if self.last_remote_updated is None:
            self.last_remote_updated = remote_info.last_modification_time
            self.remote_digest = remote_info.get_digest()
            self.folderish = remote_info.folderish
            self.remote_name = remote_info.name
            self.remote_path = remote_info.path

        elif remote_info.last_modification_time > self.last_remote_updated:
            self.last_remote_updated = remote_info.last_modification_time
            self.update_state(remote_state='modified')
            self.remote_digest = remote_info.get_digest()
            self.folderish = remote_info.folderish
            self.remote_name = remote_info.name
            self.remote_path = remote_info.path

        # else: nothing to update

    def get_local_abspath(self):
        relative_path = self.path[1:].replace('/', os.path.sep)
        return os.path.join(self.local_root, relative_path)


class FileEvent(Base):
    __tablename__ = 'fileevents'

    id = Column(Integer, Sequence('fileevent_id_seq'), primary_key=True)
    local_root = Column(String, ForeignKey('root_bindings.local_root'))
    utc_time = Column(DateTime)
    path = Column(String)

    root_binding = relationship("RootBinding")

    def __init__(self, local_root, path, utc_time=None):
        self.local_root = local_root
        if utc_time is None:
            utc_time = datetime.datetime.utcnow()


def init_db(nxdrive_home, echo=False, scoped_sessions=True, poolclass=None):
    """Return an engine and session maker configured for using nxdrive_home

    The database is created in nxdrive_home if missing and the tables
    are intialized based on the model classes from this module (they
    all inherit the same abstract base class.

    If scoped_sessions is True, sessions built with this maker are reusable
    thread local singletons.

    """
    # We store the DB as SQLite files in the nxdrive_home folder
    dbfile = os.path.join(os.path.abspath(nxdrive_home), 'nxdrive.db')
    engine = create_engine('sqlite:///' + dbfile, echo=echo,
                           poolclass=poolclass)

    # Ensure that the tables are properly initialized
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    if scoped_sessions:
        maker = scoped_session(maker)
    return engine, maker
