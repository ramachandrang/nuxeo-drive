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
    attempts = 0
    while attempts < 2:
        try:
            sync_folder = session.query(SyncFolders).filter(SyncFolders.remote_parent == None).one()
            break
        except NoResultFound:
            log.warn("root does not exist.")
            if controller is None:
                raise RuntimeError(tr("An internal error occurred: Please restart the program"))
            controller.get_folders()
            attempts += 1
        except MultipleResultsFound:
            log.error("multiple roots exist.")
            config_folder = os.path.expanduser(r'~\.nuxeo_drive')
            if controller is not None:
                config_folder = controller.config_folder
            raise ValueError(tr('An internal error occurred: Please delete %s' % os.path.join(config_folder, 'nxdrive.db')))
        
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
        check_state = Qt.Checked if fld.checked is not None else Qt.Unchecked
        item.setData(check_state, CHECKED_ROLE)
        root.appendRow(item)
        add_subfolders(session, item, fld.remote_id)
        
        
    
