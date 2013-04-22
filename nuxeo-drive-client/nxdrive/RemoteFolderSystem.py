'''
Created on Dec 21, 2012

@author: mconstantin
'''

import os
from PySide.QtCore import QObject
from PySide.QtGui import QStandardItemModel, QStandardItem, QIcon
from PySide.QtCore import Qt

from nxdrive.model import SyncFolders
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

def get_model(session, folder_dlg):
    model = QStandardItemModel()
    rootItem = model.invisibleRootItem()

    try:
        server_binding = folder_dlg.frontend.server_binding
        controller = folder_dlg.frontend.controller
        if server_binding is None:
            log.debug('invalid get_model() arguments: server_binding')
            return None
        if controller is None:
            log.debug('invalid get_model() arguments: controller')
            return None
        
        controller.synchronizer.get_folders(server_binding, update_roots=True, session=session,
                         completion_notifiers=folder_dlg.notify_folders_retrieved)
        
        sync_folder = session.query(SyncFolders).\
                        filter(SyncFolders.remote_parent == None).\
                        filter(SyncFolders.local_folder == server_binding.local_folder).\
                        one()
                        
        item = QStandardItem(sync_folder.remote_name)
        item.setCheckable(False)
        item.setEnabled(False)
        item.setSelectable(False)
        item.setIcon(QIcon(Constants.APP_ICON_DIALOG))
        item.setData(sync_folder.remote_id, ID_ROLE)
        rootItem.appendRow(item)
        add_subfolders(session, item, sync_folder.remote_id, server_binding.local_folder)
        return model
    except NoResultFound:
        log.debug('Cloud Portal Office root not found.')
        return None
    except MultipleResultsFound:
        log.debug('more than one Cloud Portal Office root found.')
        return None
    except Exception, e:
        log.debug("failed to retrieve folders or sync roots (%s)", str(e))
        return None

def add_subfolders(session, root, data, local_folder):
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
        add_subfolders(session, item, fld.remote_id, local_folder)

def update_model(session, parent, local_folder):
    """Walk the model and inform the view if there are any changes.
    Only process added and deleted folders."""

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
        # otherwise process its children
        for i in range(parent.rowCount()):
            update_model(session, parent.child(i), local_folder)

def no_bindings(session):
    count = session.query(SyncFolders).\
                       filter(not SyncFolders.bind_state == True).count()
    return count == 0
