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
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

log = get_logger(__name__)
    
    
class IdWrapper(object):
    cache = {}
    def __init__(self, id):
        self.id = id
        IdWrapper.cache[id] = self
        
        #DEBUG
        print {key:type(key) for key in IdWrapper.cache.iterkeys()}
        
    def __call__(self):
        return self.id
    
class CheckedRemoteFileSystem(QAbstractItemModel):
    
    def __init__(self, local_folder, session, parent=None):
        super(CheckedRemoteFileSystem, self).__init__(parent)
        self.session = session
        # never commit it
        self.root = SyncFolders(None, 'CloudDesk', None, None, local_folder)

    def index(self, row, column, parent):
        if row == 0 and column == 0:
            return self.createIndex(0, 0, IdWrapper(None))
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        
        parent_remote_id = None
        try:
            if parent.isValid():
                parent_remote_id = parent.internalPointer()()
        except TypeError:
            pass
            
        try:
            item_id = self.session.query(SyncFolders).\
                        filter(SyncFolders.remote_parent == parent_remote_id).\
                        order_by(SyncFolders.remote_id).\
                        offset(row).\
                        limit(1).all()
            # return is a list of tuples!!!
            return self.createIndex(row, column, IdWrapper(item_id[0].remote_id))
        
        except NoResultFound:
            parent_msg = 'top level' if parent_remote_id is None else 'parent %s' % parent_remote_id
            log.error("child %d for %s does not exist", row, parent_msg)
            return QModelIndex()
        
        
    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        
        item_id = None
        try:
            item_id = index.internalPointer()()
        except TypeError:
            pass
        
        if item_id is None:
            return QModelIndex()
        # TODO itemt_id is a tuple!!!
#        if isinstance(item_id, tuple):
#            item_id = item_id[0]
            
        try:
            folder = self.session.query(SyncFolders).\
                        filter(SyncFolders.remote_id == item_id).\
                        one()
                                 
            remote_parent = folder.remote_parent

            # get all children for this parent
            children = self.session.query(SyncFolders).\
                        filter(SyncFolders.remote_parent == remote_parent).\
                        order_by(SyncFolders.remote_id).\
                        all()
            # children is a list of tuples!!!
            row = [c.remote_id for c in children].index(item_id)
            return self.createIndex(row, 0, IdWrapper(remote_parent))
        
        except NoResultFound:
            log.error("row with remoteId=%s does not exist", item_id)
            raise ValueError('invalid index')
        except MultipleResultsFound:
            log.error("multiple rows with remoteId=%s", item_id)
            raise ValueError('invalid db')
        
                
    def rowCount(self, parent):
        # should use column 0 since each row may have different number of columns
        if parent.column() > 0:
            return 0
        
        parent_id = self.root.remote_parent
        try:
            if parent.isValid():
                parent_id = parent.internalPointer()()
        except TypeError:
            pass
        
        rows = self.session.query(SyncFolders).\
                    filter(SyncFolders.remote_parent == parent_id).\
                    count()
        return rows
        
    def columnCount(self, parent):
        if parent.isValid():
            return 2
        else:
            return 1
        
        
    def hasChildren(self, parent):
        if parent.column() > 0:
            return 0
        
        parent_id = self.root.remote_parent
        try:
            if parent.isValid():
                parent_id = parent.internalPointer()()
        except TypeError:
            pass
        # TODO parent_id here is a tuple!!!
#        if isinstance(parent_id, tuple):
#            parent_id = parent_id[0]
            
        rows = self.session.query(SyncFolders).\
                    filter(SyncFolders.remote_parent == parent_id).\
                    count()  
        return rows > 0 
    
        
    def flags(self, index):
        if not index.isValid():
            return 0
        
        try:
            item_id = index.internalPointer()()
        except TypeError:
            pass
        
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 0 and item_id is not None:
            f |= Qt.ItemIsUserCheckable
            
        return f
    
    def data(self, index, role):
        if not index.isValid():
            return None
        
        if role != Qt.DisplayRole and role != Qt.CheckStateRole:
            return None
        
        folder = self.root
        try:
            item_id = index.internalPointer()()
        except TypeError:
            pass
        
        if item_id is not None:
            try:
                folder = self.session.query(SyncFolders).\
                        filter(SyncFolders.remote_id == item_id).\
                        one()
                
            except NoResultFound:
                log.error("row with remoteId=%s does not exist", item_id)
                raise ValueError('invalid index')
            except MultipleResultsFound:
                log.error("multiple rows with remoteId=%s", item_id)
                raise ValueError('invalid db')
                      
        if index.column() == 0 and folder.remote_id is not None and role == Qt.CheckStateRole:
            # other than the very root none (CloudDesk)
            return Qt.Checked if folder.checked2 else Qt.Unchecked
        elif index.column() == 1 and folder.remote_id is not None and role == Qt.DisplayRole:
            return folder.remote_name
        elif index.column() == 0 and folder.remote_id is None and role == Qt.DisplayRole:
            return folder.remote_name
        else:
            return None      
        
        
    def setData(self, index, value, role):
        if index.isValid() and index.column() == 0 and role == Qt.CheckStateRole:
            self._set_item(index, value)
            # set all the children as well. The model shows only directories anyway
            self.set_children(index, value)
            top_left, bottom_right = self._set_children(index, value)
            self.dataChanged.emit(top_left, bottom_right)
            
            return True

    def _set_item(self, index, value):
        item_id = index.internalPointer()
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
                