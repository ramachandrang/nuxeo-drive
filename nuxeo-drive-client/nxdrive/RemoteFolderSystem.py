'''
Created on Dec 21, 2012

@author: mconstantin
'''

import os
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
        
    
def get_model(session, controller=None):
    model = QStandardItemModel()
    rootItem = model.invisibleRootItem()
    
    # get the root CloudDesk item
#    attempts = 0
#    while attempts < 2:
#        try:
#            sync_folder = session.query(SyncFolders).filter(SyncFolders.remote_parent == None).one()
#            break
#        except NoResultFound:
#            log.warn("root does not exist.")
#            if controller is None:
#                raise RuntimeError(tr("An internal error occurred: Please restart the program"))
#            controller.get_folders()
#            controller.synchronizer.update_roots(controller.get_server_binding())
#            attempts += 1
#        except MultipleResultsFound:
#            log.error("multiple roots exist.")
#            config_folder = os.path.expanduser(r'~\.nuxeo_drive')
#            if controller is not None:
#                config_folder = controller.config_folder
#            raise ValueError(tr('An internal error occurred: Please delete %s' % os.path.join(config_folder, 'nxdrive.db')))
        
    try:
        server_binding = controller.get_server_binding()
        controller.synchronizer.get_folders(server_binding=server_binding, session=session)
        controller.synchronizer.update_roots(server_binding=server_binding, session=session)
    except Exception, e:
        log.debug("failed to retrieve folders or sync roots (%s)", str(e))
        
    sync_folder = session.query(SyncFolders).filter(SyncFolders.remote_parent == None).one()
    item = QStandardItem(sync_folder.remote_name)
    item.setCheckable(False)
    item.setEnabled(False)
    item.setSelectable(False)
    item.setIcon(QIcon(Constants.APP_ICON_ENABLED))
    item.setData(sync_folder.remote_id, ID_ROLE)
    rootItem.appendRow(item)
    add_subfolders(session, item, sync_folder.remote_id)
    return model

    
def add_subfolders(session, root, data):
    sync_folders = session.query(SyncFolders).\
                           filter(SyncFolders.remote_parent == data).\
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
        add_subfolders(session, item, fld.remote_id)
        
def update_model(session, parent):
    """Walk the model and inform the view if there are any changes.
    Only process added and deleted folders."""
    
    # TODO Should it process renamed folders?
    
    parentId = parent.data(ID_ROLE)
    subfolders = session.query(SyncFolders).\
                        filter(SyncFolders.remote_parent == parentId).\
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
            update_model(session, parent.child(i))


def no_bindings(session):
    count = session.query(SyncFolders).\
                       filter(not SyncFolders.bind_state == True).count()
    return count == 0
    