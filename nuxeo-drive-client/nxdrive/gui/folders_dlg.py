'''
Created on Dec 13, 2012

@author: mconstantin
'''

from PySide.QtGui import QDialog, QStandardItem, QIcon, QDialogButtonBox
from PySide.QtCore import Qt, QObject, Signal, Slot, QModelIndex

from nxdrive.model import SyncFolders
from ui_sync_folders import Ui_FoldersDlg
from nxdrive.RemoteFolderSystem import RemoteFoldersModel
from nxdrive.RemoteFolderSystem import ID_ROLE, CHECKED_ROLE
from nxdrive.client import MaintenanceMode
from nxdrive import Constants
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from nxdrive.logging_config import get_logger

log = get_logger(__name__)

class Communicator(QObject):
    ancestorChanged = Signal(QStandardItem)
    folders = Signal(str, bool)


class SyncFoldersDlg(QDialog, Ui_FoldersDlg):
    def __init__(self, frontend = None, parent = None):
        super(SyncFoldersDlg, self).__init__(parent)
        self.setupUi(self)
        self.setWindowIcon(QIcon(Constants.APP_ICON_DIALOG))
        self.setWindowTitle(Constants.APP_NAME + self.tr(' Synced Folders'))
        self.help_message = self.tr('Select the folders from your %s account to sync with this computer.') %\
                                    Constants.PRODUCT_NAME
        self.lblHelp.setText(self.help_message)
        if frontend is None:
            return
        self.model = None
        self.frontend = frontend
        self.controller = self.frontend.controller
        self.server_binding = self.frontend.server_binding
        # connect the click event
        self.treeView.clicked[QModelIndex].connect(self.item_clicked)
        # connect event to set the ancestors accordingly
        # TO DO this crashes the Python interpreter!!!
        self.communicator = Communicator()
        self.communicator.ancestorChanged.connect(self.set_ascendant_state)
        # Note: connect this signals before running thread(s)
        self.communicator.folders.connect(self.folders_changed)
        self.frontend.communicator.folders.connect(self.folders_changed)

        try:
            self.lblHelp.setText(self.help_message + self.tr(" <font color='#00BFFF'>Retrieving data...</font>"))
            self.model = RemoteFoldersModel(self)
            self.model.populate_model()
            self.root = self.model.get_model().invisibleRootItem().child(0)
            self.treeView.setModel(self.model.get_model())
            if self.root:
                self.clear_all(self.root)
                self.set_checked_state(self.root)
                self.expand()
                # hide header and all columns but first one
                self.treeView.setHeaderHidden(True)
                self.treeView.resizeColumnToContents(0)
            return
        except MaintenanceMode as e:
            msg = '%s (%s)' % (e.msg, e.detail)
            self.lblHelp.setText("<font size='3' color='red'><bold>%s</bold></font>" % msg)
        except Exception:
            self.lblHelp.setText("<font size='3' color='red'><bold>%s</bold></font>" % self.tr('Failed to retrieve folders'))
 
        self.lblHelp.setAlignment(Qt.AlignHCenter)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.progressBar.reset()
        self.progressBar.setVisible(False)

    @Slot(str, bool)
    def folders_changed(self, local_folder, update):
        session = self.frontend.controller.get_session()
        self.progressBar.reset()
        self.progressBar.setVisible(False)
        self.lblHelp.setText(self.help_message)
        if update:
            self.model.update_model(self.root, local_folder, session=session)
            self.set_checked_state(self.root)

    def set_checked_state(self, parent):
        """Initialize the state of all checkboxes based on the model."""

        for i in range(parent.rowCount()):
            item = parent.child(i)
            check_state = item.data(CHECKED_ROLE)
            if item.isCheckable() and check_state == Qt.Checked and item.checkState() != Qt.Checked:
                # NOT EMITTING THE SIGNAL!!!
                self.treeView.clicked[QModelIndex].emit(item.index())
                # set state for this item and all its descendants
                self.set_descendant_state(item, Qt.Checked)

            self.set_checked_state(item)

    def clear_all(self, parent):
        for i in range(parent.rowCount()):
            parent.child(i).setCheckState(Qt.Unchecked)
            self.clear_all(parent.child(i))

    def set_all(self, parent):
        for i in range(parent.rowCount()):
            parent.child(i).setCheckState(Qt.Checked)
            self.set_all(parent.child(i))

    def expand(self, parent = QModelIndex(), level = 2):
        if level <= 0:
            return
        level -= 1
        model = self.treeView.model()
        for i in range(model.rowCount(parent)):
            index = model.index(i, 0, parent)
            self.treeView.expand(index)
            self.expand(index, level = level)


    def item_clicked(self, index):
        item = self.model.get_model().itemFromIndex(index)
        if not item.isEnabled():
            return
        # get status of all children
        children_state = self._get_states(item)
        checked = self._get_count(children_state, Qt.Checked)
        unchecked = self._get_count(children_state, Qt.Unchecked)
        next_state = item.checkState()
        if next_state == Qt.PartiallyChecked:
            # partially checked, chose the opposite of the predominant children state
            if checked >= unchecked:
                next_state = Qt.Unchecked
            else:
                next_state = Qt.Checked

        self.set_descendant_state(item, next_state)
        # THIS CRASHES the Python interpreter
#        self.communicator.ancestorChanged.emit(item)


#    def item_changed(self, item):
#        item_name = item.data(ID_ROLE)
#        log.debug('item %s changed', item_name)
#
#        if not item.isEnabled():
#            return
#        # get status of all children
#        children_state = self._get_states(item)
#        checked = self._get_count(children_state, Qt.Checked)
#        unchecked = self._get_count(children_state, Qt.Unchecked)
#        next_state = item.checkState()
#        if next_state == Qt.PartiallyChecked:
#            # partially checked, chose the opposite of the predominant children state
#            if checked >= unchecked:
#                next_state = Qt.Unchecked
#            else:
#                next_state = Qt.Checked
#
#        self.set_descendant_state(item, next_state)
#        self.communicator.ancestorChanged.emit(item)
#        self.set_ascendant_state(item)

    def _get_states(self, item):
        if item.rowCount() > 0:
            return [item.checkState(), [self._get_states(item.child(i)) for i in range(item.rowCount())]]
        else:
            return item.checkState()

    def _get_count(self, states, value, count = 0):
        f = lambda c: 1 if c == value else 0
        count = 0
        if isinstance(states, list):
            for i in range(len(states)):
                count += self._get_count(states[i], value, count = count)
        else:
            return count + f(states)

        return count

    def set_descendant_state(self, item, state):
        if state == Qt.PartiallyChecked:
            return
        item.setCheckState(state)
        for i in range(item.rowCount()):
            self.set_descendant_state(item.child(i), state)

    @Slot(QStandardItem)
    def set_ascendant_state(self, item):
        item_name = item.data(ID_ROLE)
        log.debug('set parent for item %s', item_name)
        parent = item.parent()
        if not parent.isEnabled():
            return

        if parent.rowCount() == 1:
            # set the parent to same state as the child
            parent.setCheckState(item.checkState())
        elif parent.rowCount() > 1:
            # get states of immediate descendants
            states = [parent.child(i).checkState() for i in range(parent.rowCount())]
            for i in range(1, len(states)):
                if states[0] != states[i]:
                    parent.setCheckState(Qt.PartiallyChecked)
                    break
            else:
                parent.setCheckState(states[0])

        self.set_ascendant_state(parent)

    def accept(self):
        # update the sync_folders db table
        self._update_state(self.root)
        super(SyncFoldersDlg, self).accept()

    def _update_state(self, parent, clear = False):
        folder_id = parent.data(ID_ROLE)
        session = self.frontend.controller.get_session()
        try:
            sync_folder = session.query(SyncFolders).\
                                filter(SyncFolders.remote_id == folder_id).\
                                filter(SyncFolders.local_folder == self.server_binding.local_folder).\
                                one()

            if parent.rowCount() == 0:
                if clear:
                    sync_folder.check_state = False
                else:
                    sync_folder.check_state = True if parent.checkState() == Qt.Checked else False
                    
            if not folder_id == Constants.CLOUDDESK_UID:
    #            states = [parent.child(i).checkState() for i in range(parent.rowCount())]
    #            first_state = states[0]
    #            other_states = filter(lambda state: state != first_state, states[1:])
                if clear:
                    sync_folder.check_state = False
                else:
                    # get status of all children
                    children_state = self._get_states(parent)
                    checked = self._get_count(children_state, Qt.Checked)
                    unchecked = self._get_count(children_state, Qt.Unchecked)
                    if checked > 0 and unchecked > 0:
                        sync_folder.check_state = False
                    else:
                        sync_folder.check_state = True if checked > 0 else False
                        # make an exception for Others Docs since it cannot be a synchronization root
                        if folder_id != Constants.OTHERS_DOCS_UID:
                            clear = True
    
            for i in range(parent.rowCount()):
                self._update_state(parent.child(i), clear = clear)
                                
            session.commit()

        except MultipleResultsFound:
            log.debug('multiple folders with id %s found', folder_id)
        except NoResultFound:
            log.debug('folder with id %s not found', folder_id)
        except Exception, e:
            log.debug('failed to update folder state: %s', e)

    def notify_folders_retrieved(self, local_folder, update):
        self.communicator.folders.emit(self.server_binding.local_folder, update)

