'''
Created on Dec 21, 2012

@author: mconstantin
'''

import os
import weakref
from PySide.QtCore import QObject
from PySide.QtGui import QStandardItemModel, QStandardItem, QIcon
from PySide.QtCore import Qt

from nxdrive.model import SyncFolders
from nxdrive.client import MaintenanceMode
from nxdrive import Constants
import nxdrive.gui.qrc_resources
from nxdrive.logging_config import get_logger

from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

log = get_logger(__name__)

ID_ROLE = Qt.UserRole + 1
CHECKED_ROLE = Qt.UserRole + 2

class ModelUpdater(QObject):
    def __init__(self, model, server_binding, controller):
        self.model = model
        self.server_binding = server_binding
        self.controller = controller

class RemoteFoldersModel():
    def __init__(self, folder_dlg):
        self.folder_dlg = folder_dlg
        self.controller = self.folder_dlg.frontend.controller
        if self.controller is None:
            error = 'invalid get_model() arguments: controller'
            log.debug(error)
            raise Exception(error)
        self.server_binding = self.folder_dlg.frontend.server_binding
        if self.server_binding is None:
            error = 'invalid get_model() arguments: server_binding'
            log.debug(error)
            raise Exception(error)
        self.model = QStandardItemModel()
            
    def get_model(self):
        return self.model
    
    def populate_model(self, session=None):
        if session is None:
            session = self.folder_dlg.frontend.controller.get_session()
        rootItem = self.model.invisibleRootItem()
        try:
            sync_folder = session.query(SyncFolders).\
                            filter(SyncFolders.remote_parent == None).\
                            filter(SyncFolders.local_folder == self.server_binding.local_folder).\
                            one()
            mydocs = self.controller.synchronizer.get_mydocs(self.server_binding, session=session)
            if not mydocs: return
            
            othersdocs = {u'uid': Constants.OTHERS_DOCS_UID,
                          u'title': Constants.OTHERS_DOCS,
                          u'repository': mydocs['repository']
                         }
            self.controller.synchronizer.get_all_subfolders_async(
                        self.server_binding.local_folder, 
                        mydocs,
                        othersdocs,
                        update_roots=True, 
                        session=session,
                        completion_notifiers={'notify_folders_retrieved': weakref.proxy(self.folder_dlg)},
                        threads=self.folder_dlg.frontend.threads) 
        except NoResultFound:
            log.debug('Cloud Portal Office root not found.')
            self.controller.synchronizer.get_folders(
                        self.server_binding, 
                        update_roots=True, 
                        session=session,
                        completion_notifiers={'notify_folders_retrieved': self.folder_dlg}) 
            sync_folder = session.query(SyncFolders).\
                            filter(SyncFolders.remote_parent == None).\
                            filter(SyncFolders.local_folder == self.server_binding.local_folder).\
                            one()
        except MultipleResultsFound:
            log.debug('more than one Cloud Portal Office root found.')
            return
        except MaintenanceMode:
            raise
        except Exception, e:
            log.debug("failed to retrieve folders or sync roots (%s)", str(e))
            return
        
        try:
            item = QStandardItem(sync_folder.remote_name)
            item.setCheckable(False)
            item.setEnabled(False)
            item.setSelectable(False)
            item.setIcon(QIcon(Constants.APP_ICON_DIALOG))
            item.setData(sync_folder.remote_id, ID_ROLE)
            rootItem.appendRow(item)
            self._add_subfolders(session, item, sync_folder.remote_id, self.server_binding.local_folder)
        except Exception, e:
            log.debug("failed to retrieve folders or sync roots (%s)", str(e))
    
    def _add_subfolders(self, session, root, data, local_folder):
        sync_folders = session.query(SyncFolders).\
                               filter(SyncFolders.remote_parent == data).\
                               filter(SyncFolders.local_folder == local_folder).\
                               order_by(SyncFolders.remote_name).all()
    
        if len(sync_folders) > 1:
            root.setTristate(True)
    
        for fld in sync_folders:
            item = QStandardItem(fld.remote_name)
            item.setCheckable(True)
            item.setData(fld.remote_id, ID_ROLE)
            check_state = Qt.Checked if fld.check_state else Qt.Unchecked
            item.setData(check_state, CHECKED_ROLE)
            root.appendRow(item)
            self._add_subfolders(session, item, fld.remote_id, local_folder)
    
    def update_model(self, parent, local_folder, session=None):
        """Walk the model and inform the view if there are any changes.
        Only process added and deleted folders."""
    
        if session is None:
            session = self.folder_dlg.frontend.controller.get_session()
        # TODO Should it process renamed folders?
        parentId = parent.data(ID_ROLE)
        subfolders = session.query(SyncFolders).\
                            filter(SyncFolders.remote_parent == parentId).\
                            filter(SyncFolders.local_folder == local_folder).\
                            order_by(SyncFolders.remote_name).all()
        subfolders_dict = dict((folder.remote_id, folder) for folder in subfolders)
    
        subitems = [parent.child(i) for i in range(parent.rowCount())]
        subitems_dict = dict((item.data(ID_ROLE), item) for item in subitems)
        subfolders_ids = set(subfolders_dict.keys())
        subitems_ids = set(subitems_dict.keys())
        items_to_add = subfolders_ids - subitems_ids
        items_to_remove = subitems_ids - subfolders_ids
        matched_ids = set.intersection(subfolders_ids, subitems_ids)
        
        # update the model
        if len(items_to_add) > 0 or len(items_to_remove) > 0:
            parent.model().layoutAboutToBeChanged.emit()
            for itemId in items_to_add:
                new_item = QStandardItem(subfolders_dict[itemId].remote_name)
                new_item.setData(itemId, ID_ROLE)
                new_item.setCheckable(True)
                check_state = Qt.Checked if subfolders_dict[itemId].bind_state else Qt.Unchecked
                if parent.data(CHECKED_ROLE) == Qt.Checked:
                    check_state = Qt.Checked
                # TODO new child is not checked if parent is
                new_item.setData(check_state, CHECKED_ROLE)
    
                # insert in order of item (i.e. folder) name
                for item in enumerate(subitems):
                    if item[1].data(Qt.DisplayRole) > subfolders_dict[itemId].remote_name:
                        parent.insertRow(item[0], new_item)
                        break
                else:
                    parent.appendRow(new_item)
    
            for itemId in items_to_remove:
                # index method does not work (operator not implemented) for QStandardItem
    #            row = subitems.index(subitems_dict[itemId])
                for item in enumerate(subitems):
                    if item[1].data(ID_ROLE) == itemId:
                        parent.removeRow(item[0])
                        subitems = [parent.child(i) for i in range(parent.rowCount())]
                        break
    
            # the slot should update the entire tree
            parent.model().layoutChanged.emit()
        else:
            # update checked state
            for item_id in matched_ids:
                server_state = subfolders_dict[item_id].bind_state
                subitems_dict[item_id].setData(Qt.Checked if server_state else Qt.Unchecked, CHECKED_ROLE)
                     
            # and process its children
            for i in range(parent.rowCount()):
                self.update_model(parent.child(i), local_folder, session=session)
    
    def no_bindings(self, session):
        count = session.query(SyncFolders).\
                           filter(not SyncFolders.bind_state == True).count()
        return count == 0
