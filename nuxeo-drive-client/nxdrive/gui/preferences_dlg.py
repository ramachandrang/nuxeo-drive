'''
Created on Dec 13, 2012

@author: mconstantin
'''

import os
import platform
import shutil

from PySide.QtGui import QDialog, QMessageBox, QDialogButtonBox, QFileDialog
from PySide.QtCore import Qt

from nxdrive import Constants
from nxdrive.model import ServerBinding
from nxdrive.controller import default_nuxeo_drive_folder
from nxdrive.logging_config import get_logger

from ui_preferences import Ui_preferencesDlg
from proxy_dlg import ProxyDlg
from progress_dlg import ProgressDialog
from folders_dlg import SyncFoldersDlg

def default_expanded_nuxeo_drive_folder():
    return os.path.expanduser(DEFAULT_NX_DRIVE_FOLDER)

log = get_logger(__name__)

DEFAULT_NX_DRIVE_FOLDER = default_nuxeo_drive_folder()
DEFAULT_EX_NX_DRIVE_FOLDER = default_expanded_nuxeo_drive_folder()


class PreferencesDlg(QDialog, Ui_preferencesDlg):
    def __init__(self, frontend=None, parent=None):
        super(PreferencesDlg, self).__init__(parent)
        self.setupUi(self)
        self.frontend = frontend
        self.controller = frontend.controller
        self.values = None
        self.stop_on_apply = False
        self.local_folder = frontend._get_local_folder() if frontend is not None else DEFAULT_EX_NX_DRIVE_FOLDER
        self.previous_local_folder = None
        self.move_to_folder = self.local_folder
        self.server_binding = self.controller.get_server_binding(self.local_folder, raise_if_missing=False)
        self.proxy = None
        self.rbProxy.setChecked(False)
        applyBtn = self.buttonBox.button(QDialogButtonBox.Apply)
        applyBtn.clicked.connect(self.applyChanges)
        self.btnDisconnect.clicked.connect(self.manageBinding)
        self.btnBrowsefolder.clicked.connect(self.browseFolder)
        self.txtCloudfolder.textChanged.connect(self.changeFolder)
        self.btnSelect.clicked.connect(self.selectFolders)
        self.btnProxy.clicked.connect(self.configProxy)
        self.rbProxy.toggled.connect(lambda checked : self.btnProxy.setEnabled(checked))
        
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        
    def _isConnected(self):
        return self.server_binding is not None
        
    def _getDisconnectText(self):
        return self.tr("Connect...") if not self._isConnected() else self.tr("Disconnect")
        
    def showEvent(self, evt):
        if evt.spontaneous:
            self.lblComputer.setText(platform.node())
            self.lblStorage.setText("123Mb (0.03%) of 4Gb")    
            self.rbProxy.setChecked(self.proxy != None)
            
            if not self._isConnected():
                self.txtUrl.setText(Constants.DEFAULT_CLOUDDESK_URL)
                self.txtAccount.setText(Constants.DEFAULT_ACCOUNT)
                self.txtCloudfolder.setText(os.path.dirname(self.local_folder))
                # Launch the GUI to create a binding
#                ok = self._connect()
#                if not ok:
#                    self.destroy()
#                    return

            self._updateBinding()
            super(PreferencesDlg, self).showEvent(evt)
    
    def selectFolders(self):
        dlg = SyncFoldersDlg(frontend=self)
        if dlg.exec_() == QDialog.Rejected:
            return
        
    def configProxy(self):
        dlg = ProxyDlg(frontend=self)
        if dlg.exec_() == QDialog.Rejected:
            return
        
    def changeFolder(self):
        self.move_to_folder = os.path.join(self.txtCloudfolder.text(), Constants.DEFAULT_NXDRIVE_FOLDER)
          
#        if self._isConnected():
#            #prompt for moving the Nuxeo Drive folder for current binding
#            msg = QMessageBox(QMessageBox.Question, self.tr('Move Root Folder'),
#                              self.tr("This action will move the %s folder and all its subfolders and files\n"
#                              "to a new location. If will also stop the synchronization if running.\n"
#                              ) % self.local_folder,
#                              QMessageBox.Yes | QMessageBox.No)
#            msg.setInformativeText(self.tr("Do you want to proceed?\n"
#                                           "If yes, select the new CloudDesk folder."
#                                           ))
#            if msg.exec_() == QMessageBox.No:
#                return
#                            
#            dst = os.path.join(selectedFld, Constants.DEFAULT_NXDRIVE_FOLDER)
#            if os.path.exists(dst):
#                error = QMessageBox(QMessageBox.Critical, self.tr("Path Error"), 
#                                                          self.tr("Folder %s already exists" % dst))
#                error.setInformativeText(self.tr("Select a folder where %s does not exist." % Constants.DEFAULT_NXDRIVE_FOLDER))
#                error.exec_()
#                return
#               
#            self.move_to_folder = dst
        
    def browseFolder(self):
        """enter or select a new path"""
        defaultFld = self.txtCloudfolder.text()
        if (defaultFld == None):
            defaultFld = self.local_folder
        selectedFld = QFileDialog.getExistingDirectory(self, self.tr("Choose or create CloudDesk parent directory"),
                        defaultFld, QFileDialog.DontResolveSymlinks)
        if (len(selectedFld) == 0):
            selectedFld = defaultFld
        self.txtCloudfolder.setText(selectedFld)
    
    def accept(self):
        pass
        
    def manageBinding(self):
        if (self._isConnected()):
            self._disconnect()
        else:
            self._connect()
        self._updateBinding()
        
    def _updateBinding(self):
        self.btnDisconnect.setText(self._getDisconnectText())
        self.txtCloudfolder.setEnabled(True)
        if (self._isConnected()):
#            local_folder = self.txtCloudfolder.text()
#            if local_folder == '': local_folder = None
            self.txtAccount.setText(self.server_binding.remote_user)
            self.txtAccount.setCursorPosition(0)
            self.txtAccount.setToolTip(self.server_binding.remote_user)
            self.txtUrl.setText(self.server_binding.server_url)
            self.txtUrl.setCursorPosition(0)
            self.txtUrl.setToolTip(self.server_binding.server_url)
            self.txtCloudfolder.setText(os.path.dirname(self.server_binding.local_folder))
            self.txtCloudfolder.setCursorPosition(0)
            self.txtCloudfolder.setToolTip(self.server_binding.local_folder)
            self.txtAccount.setReadOnly(True)
            self.txtAccount.deselect()
            self.txtUrl.setReadOnly(True)
        else:
            self.txtAccount.setReadOnly(False)
            # widget looks still read-only
            self.txtAccount.setEnabled(True)
            self.txtAccount.setSelection(0, len(self.txtAccount.text()))
            self.txtUrl.setReadOnly(False)
            self.txtUrl.setEnabled(True)
    
    def _connect(self):
        # Launch the GUI to create a binding
        from nxdrive.gui.authentication import prompt_authentication
        from nxdrive.commandline import default_nuxeo_drive_folder
        local_folder = os.path.join(self.txtCloudfolder.text(), Constants.DEFAULT_NXDRIVE_FOLDER)
        remote_user = self.txtAccount.text()
        server_url = self.txtUrl.text()
        #validate at least the folder since it could have been entered directly
        if (not os.path.exists(local_folder)):
            mbox = QMessageBox(QMessageBox.Warning, self.tr("CloudDesk"), self.tr("Folder %s does not exist.") % local_folder)
            mbox.setInformativeText(self.tr("Do you want to create it?"))
            mbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)         
            if mbox.exec_() == QMessageBox.No:
                return                  
            os.makedirs(local_folder)
        
        result, self.values = prompt_authentication(self.controller, local_folder, url=server_url, username=remote_user, update=False)
        if result:
            self.server_binding = ServerBinding(local_folder,
                                                self.values['url'],
                                                self.values['username'],
                                                remote_password=self.values['password']
                                                )
            self.local_folder = local_folder
        return result
        
    def _disconnect(self):
        self.previous_local_folder = self.local_folder
        self.local_folder = None
        self.server_binding = None
        
    def applyChanges(self):
        same_binding = False
        previous_binding = None
        if self.previous_local_folder is not None:
            previous_binding = self.controller.get_server_binding(local_folder=self.previous_local_folder, raise_if_missing=False)
        same_binding = self.server_binding == previous_binding 
        
        if same_binding: return
        
        try:
            if previous_binding is not None:
                result = self._stopServer()
                if result == QDialog.Rejected:
                    return QDialog.Rejected            
                # disconnect
                self.controller.unbind_server(self.previous_local_folder)      
                      
            if self._isConnected():
                # should not be any binding!
                assert(len(self.controller.list_server_bindings()) == 0)
                if not os.path.exists(self.local_folder):
                    mbox = QMessageBox(QMessageBox.Warning, self.tr("CloudDesk"), self.tr("Folder %s does not exist.") % self.local_folder)
                    mbox.setInformativeText(self.tr("Do you want to create it?"))
                    mbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)         
                    if mbox.exec_() == QMessageBox.No:
                        return QDialog.Rejected                       
                    os.makedirs(self.local_folder)
                    
                self.controller.bind_server(self.server_binding.local_folder, 
                    self.server_binding.server_url, 
                    self.server_binding.remote_user,
                    self.server_binding.remote_password) 
                            
        except Exception as ex:
            log.debug("failed to bind or unbind: %s", str(ex))
            self._disconnect()
            self._updateBinding()
            QMessageBox(QMessageBox.Critical, self.tr("CloudDesk Error"), self.tr("Failed to connect to server, please try again.")).exec_()
            return QDialog.Rejected
                        
        if self.local_folder is not None and not self.move_to_folder is not None and self.local_folder != self.move_to_folder:           
            if self._isConnected():
                #prompt for moving the Nuxeo Drive folder for current binding
                msg = QMessageBox(QMessageBox.Question, self.tr('Move Root Folder'),
                                  self.tr("This action will move the %s folder and all its subfolders and files\n"
                                  "to a new location. It will also stop the synchronization if running.\n"
                                  ) % self.local_folder,
                                  QMessageBox.Yes | QMessageBox.No)
                msg.setInformativeText(self.tr("Do you want to proceed?"))
                if msg.exec_() == QMessageBox.No:
                    return
                                

            if os.path.exists(self.move_to_folder):
                error = QMessageBox(QMessageBox.Critical, self.tr("Path Error"), 
                                                          self.tr("Folder %s already exists" % self.move_to_folder))
                error.setInformativeText(self.tr("Select a folder where %s does not exist." % Constants.DEFAULT_NXDRIVE_FOLDER))
                error.exec_()
                return QDialog.Rejected
                       
#            if (not os.path.exists(self.move_to_folder)):
#                mbox = QMessageBox(QMessageBox.Warning, self.tr("CloudDesk"), self.tr("Folder %s does not exist.") % self.move_to_folder)
#                mbox.setInformativeText(self.tr("Do you want to create it?"))
#                mbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)         
#                if mbox.exec_() == QMessageBox.No:
#                    return QDialog.Rejected                  
            
            shutil.copytree(self.local_folder, self.move_to_folder)                    
            if self.frontend is not None:
                self.frontend.local_folder = self.local_folder = self.move_to_folder  
                              
        #TODO Apply other changes
        
        self.done(QDialog.Accepted)
        
    def _stopServer(self, cancel=True):
        if self.frontend.worker is not None and self.frontend.worker.isAlive():
            # Ask the controller to stop: the synchronization loop will in turn
            # call notify_sync_stopped and finally handle_stop (without quitting the app)
            self.controller.stop()
            
            # wait in a loop while displaying a message...
            self.dlg = ProgressDialog(self, cancel=cancel)
            return self.dlg.exec_()
            
    def timeout(self):
        if self.frontend.worker is None or not self.frontend.worker.isAlive():
            self.dlg.ok()
            