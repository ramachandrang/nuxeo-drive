'''
Created on Dec 18, 2012

@author: mconstantin
'''

from PySide.QtCore import QAbstractItemModel, QModelIndex
from PySide.QtCore import Qt
from collections import Iterable
from pprint import pprint

from logging_config import get_logger
from nxdrive.model import SyncFolders
from nxdrive import Constants

from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound


log = get_logger(__name__)
    
    
class IdWrapper(object):
    cache = {}
    def __init__(self, id):
        self.id = id
        IdWrapper.cache[id] = self        
#       #DEBUG
        print {key:type(key) for key in IdWrapper.cache.iterkeys()}
                
    def __call__(self):
        return self.id
    
class CheckedRemoteFileSystem(QAbstractItemModel):
    
    def __init__(self, local_folder, session, parent=None):
        super(CheckedRemoteFileSystem, self).__init__(parent)
        self.session = session
        self.root_id = Constants.CLOUDDESK_UID
        
    def get_root(self):
        root = self.session.query(SyncFolders).\
                    filter(SyncFolders.remote_id == self.root_id).one()
        return root
    
    def createIndex(self, row, col, value):
        if type(value) != unicode:
            log.error('%s is of type %s', value, type(value))
        return super(CheckedRemoteFileSystem, self).createIndex(row, col, IdWrapper(value))


    def internalPointer(self, index):
        if index.isValid():
            try:
                wrap = index.internalPointer()
#                log.debug("internal pointer of type %s", type(wrap))
                return wrap.id
            except AttributeError:
                log.error("wrong index %s", str(index))
                return None
        else:
            return None
        
    def index(self, row, column, parent):
        log.debug("index(%d, %d)", row, column)
#        if not self.hasIndex(row, column, parent):
#            log.debug("index() returned invalid node")
#            return QModelIndex()
        
        parent_remote_id = self.root_id
        if parent.isValid():
            parent_remote_id = self.internalPointer(parent)
            
        try:
            item_id = self.session.query(SyncFolders).\
                        filter(SyncFolders.remote_parent == parent_remote_id).\
                        order_by(SyncFolders.remote_id).\
                        offset(row).\
                        limit(1).one()
            
            log.debug("index() returned item %s, parent %s", item_id.remote_id, parent_remote_id)
            return self.createIndex(row, column, item_id.remote_id)
        
        except NoResultFound:
            parent_msg = 'top level' if parent_remote_id is None else 'parent %s' % parent_remote_id
            log.error("child %d for %s does not exist", row, parent_msg)
            return QModelIndex()
        
        
    def parent(self, index):
        log.debug("parent() of (%d, %d)", index.row(), index.column())
        if not index.isValid():
            log.debug("parent() returned invalid node")
            return QModelIndex()
        
        item_id = self.internalPointer(index)
        try:
            folder = self.session.query(SyncFolders).\
                        filter(SyncFolders.remote_id == item_id).\
                        one()
                                 
            remote_parent = folder.remote_parent
            if remote_parent == self.root_id:
                log.debug("parent() returned invalid node")
                return QModelIndex()

            # get all children for this parent
            children = self.session.query(SyncFolders).\
                        filter(SyncFolders.remote_parent == remote_parent).\
                        order_by(SyncFolders.remote_id).\
                        all()
            # children is a list of tuples!!!
            row = [c.remote_id for c in children].index(item_id)
            log.debug("parent() returned %s for %s", remote_parent, item_id)
            return self.createIndex(row, 0, remote_parent)
        
        except NoResultFound:
            log.error("row with remoteId=%s does not exist", item_id)
            raise ValueError('invalid index')
        except MultipleResultsFound:
            log.error("multiple rows with remoteId=%s", item_id)
            raise ValueError('invalid db')
        
                
    def rowCount(self, parent):
        log.debug("rowCount() for parent (%d, %d)", parent.row(), parent.column())
        # should use column 0 since each row may have different number of columns
#        if parent.column() > 0:
#            log.debug("rowCount() returned 0")
#            return 0
        
        parent_id = self.root_id
        if parent.isValid():    
            parent_id = self.internalPointer(parent)
        
        rows = self.session.query(SyncFolders).\
                    filter(SyncFolders.remote_parent == parent_id).\
                    count()
                    
        log.debug("rowCount() returned %d for parent %s", rows, parent_id)
        return rows
        
    def columnCount(self, parent):
        log.debug("columnCount() for parent (%d, %d)", parent.row(), parent.column())
        if parent.isValid():
            log.debug("columnCount() returned %d", 2)
            return 2
        else:
            log.debug("columnCount() returned %d", 2)
            return 2
       
        
    def hasChildren(self, parent):
        log.debug("hasChildren() for parent (%d, %d)", parent.row(), parent.column())
        row_count = self.rowCount(parent)
        log.debug("hasChildren() returned %s", "true" if row_count > 0 else "false")
        return row_count > 0
    
        
    def flags(self, index):
        if not index.isValid():
            return 0
        
        item_id = self.internalPointer(index)
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 0:
            f |= Qt.ItemIsUserCheckable
            
        return f
    
    def data(self, index, role):
        if not index.isValid():
            return None
        
        item_id = self.internalPointer(index)
        if role != Qt.DisplayRole and role != Qt.CheckStateRole:
            return None
        
        try:
            folder = self.session.query(SyncFolders).\
                    filter(SyncFolders.remote_id == item_id).\
                    one()
            if role == Qt.DisplayRole and index.column() == 1:
                return folder.remote_name
            elif role == Qt.DisplayRole and index.column() == 0:
                return ''
            
            if role == Qt.CheckStateRole and index.column() == 0:
                if item_id == self.root_id:
                    return Qt.Unchecked
                else:
                    return folder.checked2
            elif role == Qt.CheckStateRole and index.column() == 1:
                return ''
            
        except NoResultFound:
            log.error("row with remoteId=%s does not exist", item_id)
            raise ValueError('invalid index')
        except MultipleResultsFound:
            log.error("multiple rows with remoteId=%s", item_id)
            raise ValueError('invalid db')     
        
        
    def setData(self, index, value, role):
        if index.isValid() and index.column() == 0 and role == Qt.CheckStateRole:
            self._set_item(index, value)
            # set all the children as well. The model shows only directories anyway
            self.set_children(index, value)
            top_left, bottom_right = self._set_children(index, value)
            self.dataChanged.emit(top_left, bottom_right)
            
            return True

    def _set_item(self, index, value):
        item_id = self.internalPointer(index)
        if item_id is None:
            return
        folder = self.session.query(SyncFolders).\
                        filter(SyncFolders.remote_id == item_id).\
                        one()

        folder.checked2 = value
        self.session.commit()
        log.debug('folder %s %schecked', folder.remote_name, '' if value == Qt.Checked else 'un')
        
    def _set_children(self, index, value):
        if self.hasChildren():
            for i in range(0, self.rowCount(index)):
                child = self.index(i, 0, index)
                if child.isValid():
                    self.setData(child, value, Qt.CheckStateRole)
                                      
            return self.index(0, 0, index), self.index(self.rowCount(index), 0, index)
                
    def canFetchMore(self, parent):
        return True
                