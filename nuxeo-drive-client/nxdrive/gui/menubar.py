'''
Created on Oct 27, 2012

@author: mconstantin
'''

import sys
import os
import platform
import itertools

import PySide
from PySide import QtGui
from PySide import QtCore
from PySide.QtGui import QDialog, QMessageBox, QDialogButtonBox, QFileDialog, QImage, QPainter, QIcon, QPixmap
from PySide.QtCore import QTimer
from PySide.QtCore import Slot
from nxdrive import Constants
from nxdrive.gui.ui_preferences import Ui_preferencesDlg
from nxdrive.async.operations import SyncOperations
# this import is flagged erroneously as unused import - do not remove
import nxdrive.gui.qrc_resources
from nxdrive.async.worker import Worker
from nxdrive.controller import default_nuxeo_drive_folder
from nxdrive.logging_config import get_logger
                

DEFAULT_NX_DRIVE_FOLDER = default_nuxeo_drive_folder()

log = get_logger(__name__)

class CloudDeskTray(QtGui.QSystemTrayIcon):
    def __init__(self, controller, dowork):
        super(CloudDeskTray, self).__init__()
        self.controller = controller
        self.dowork = dowork
        self.setupMenu()
        self.setupMisc()
        self.worker = None
        self.opInProgress = None
#        self.setupProcessing()

        
    def setupMenu(self):
        self.menuCloudDesk = QtGui.QMenu()
        self.menuCloudDesk.setObjectName("self.menuCloudDesk")
        self.actionStatus = QtGui.QAction(self.tr("sync status"), self)
        self.actionStatus.setObjectName("actionStatus")
        self.actionCommand = QtGui.QAction(self.tr("action"), self)
        self.actionCommand.setObjectName("actionCommand")
        self.actionOpenCloudDeskFolder = QtGui.QAction(self.tr("Open CloudDesk folder"), self)
        self.actionOpenCloudDeskFolder.setObjectName("actionOpenCloudDeskFolder")
        self.actionShowClouDeskInfo = QtGui.QAction(self.tr("Show ClouDesk info"), self)
        self.actionShowClouDeskInfo.setObjectName("actionShowClouDeskInfo")
        self.actionViewSharedDocuments = QtGui.QAction(self.tr("View others shared documents"), self)
        self.actionViewSharedDocuments.setObjectName("actionViewSharedDocuments")
        self.actionUsername = QtGui.QAction(self.tr("login_name"), self)
        self.actionUsername.setObjectName("actionUsername")
        self.actionUsedStorage = QtGui.QAction(self.tr("used storage"), self)
        self.actionUsedStorage.setObjectName("actionUsedStorage")
        self.actionPreferences = QtGui.QAction(self.tr("Preferences..."), self)
        self.actionPreferences.setObjectName("actionPreferences")
        self.actionHelp = QtGui.QAction(self.tr("Help"), self)
        self.actionHelp.setObjectName("actionHelp")
        self.actionAbout = QtGui.QAction(self.tr("About"),self)
        self.actionAbout.setObjectName("actionAbout")
        self.actionQuit = QtGui.QAction(self.tr("Quit CloudDesk Sync"), self)
        self.actionQuit.setObjectName("actionQuit")
        self.menuCloudDesk.addAction(self.actionStatus)
        self.menuCloudDesk.addAction(self.actionCommand)
        self.menuCloudDesk.addSeparator()
        self.menuCloudDesk.addAction(self.actionOpenCloudDeskFolder)
        self.menuCloudDesk.addAction(self.actionShowClouDeskInfo)
        self.menuCloudDesk.addAction(self.actionViewSharedDocuments)
        self.menuCloudDesk.addSeparator()
        self.menuCloudDesk.addAction(self.actionUsername)
        self.menuCloudDesk.addAction(self.actionUsedStorage)
        self.menuCloudDesk.addSeparator()
        self.menuCloudDesk.addAction(self.actionPreferences)
        self.menuCloudDesk.addAction(self.actionHelp)
        self.menuCloudDesk.addAction(self.actionAbout)
        self.menuCloudDesk.addSeparator()
        self.menuCloudDesk.addAction(self.actionQuit)
        # this is just an indicator
        self.actionStatus.setEnabled(False)

    def setupMisc(self):
        self.setIcon(QIcon(Constants.APP_ICON))
        self.setContextMenu(self.menuCloudDesk)
        self.actionQuit.triggered.connect(self.quit)
        self.menuCloudDesk.aboutToShow.connect(self.updateMenus)
        self.actionPreferences.triggered.connect(self.showPreferences)
        self.actionCommand.triggered.connect(self.doWork)
        self.actionAbout.triggered.connect(self.about)
        self.controller.notifier.register(self._updateOperationStatus)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._onTimer)
        self.startDelay = True

    def about(self):
        msgbox = QMessageBox()
#        msgbox.setTsetTitle(self.tr("CloudDesk Sync"))
        msgbox.setText(self.tr("About CloudDesk Sync"))
        msgbox.setStandardButtons(QMessageBox.Ok)
        msgbox.setInformativeText("""version<b>%s</b>
                <p>Copyright &copy; 2012 SHARP CORPORATION
                All Rights Reserved.
                <p>Platform Details: %s</p>
                <p style="font-size: small">Python %s</p>
                <p style="font-size: small">PySide %s</p>
                <p style="font-size: small">Qt %s</p>""" % (Constants.__version__, platform.system(), 
                            platform.python_version(), PySide.__version__, QtCore.__version__))
        icon = QIcon(Constants.APP_ICON_ABOUT)
        msgbox.setIconPixmap(icon.pixmap(48, 48))
        msgbox.setDetailedText(open(Constants.COPYRIGHT_FILE).read())
        msgbox.setDefaultButton(QMessageBox.Ok)
        msgbox.exec_()

        
    # also using a flag in the worker thread to update the menu
    @Slot(int)
    def _updateOperationStatus(self, sync_status):
        if (not self.worker == None and self.worker.isRunning()):
            if sync_status == Constants.SYNC_STATUS_START:
                self._startAnimationDelay()
            elif sync_status == Constants.SYNC_STATUS_STOP:
                self._stopAnimation()
        
    def _startAnimationDelay(self):
        QTimer.singleShot(Constants.ICON_ANIMATION_START_DELAY, self._onTimerDelay)
        self.startDelay = True
        log.debug("started animation delay")
        
    def _startAnimation(self):
        if not self.startDelay:
            self.timer.start(Constants.ICON_ANIMATION_DELAY)
            self.iterator = itertools.cycle('2341')
            log.debug("started animation")
    
    def _stopAnimation(self):
        if self.startDelay:
            self.startDelay = False
            log.debug("animation stopped before starting")
        else:
            self.timer.stop()
            self.setIcon(QIcon(Constants.APP_ICON))
            log.debug("animation stopped")
        
    def _onTimerDelay(self):
        if self.startDelay:
            # stopped before delay elapsed, do not start animation
            self.startDelay = False
            log.debug("animation not started after delay (stopped before)")
            return
        else:
            self.startDelay = False
            log.debug("animation delay elapsed")
            self._startAnimation()
        
    def _onTimer(self):
#        iconBase = QImage(':/menubar_icon.png')
#        iconOverlay = QImage(Constants.APP_ICON_PATTERN % (self.iterator.next()))
#        icon = QIcon(QPixmap.fromImage(self._createImageWithOverlay(iconBase, iconOverlay)))
        # not using overlays
        icon = QIcon(Constants.APP_ICON_PATTERN % (self.iterator.next()))
        self.setIcon(icon)
        
    def quit(self):
        QtGui.QApplication.quit()
        
    def updateMenus(self):
        self.actionUsername.setText(self._getUserName())
        #TO DO retrieve storage used
        self.actionUsedStorage.setText("123Mb (0.03%) of 4Gb")
        self.actionStatus.setText(self._syncStatus())
        self.actionCommand.setText(self._syncCommand())
        # if thread is sleeping, cannot use command action
#        if (not self.worker == None and self.worker.operation.waiting):
#            self.actionCommand.setEnabled(False)
#        else:
#            self.actionCommand.setEnabled(True)
            
        
    def showPreferences(self):
        dlg = PreferencesDlg(self.controller)
        dlg.exec_()
        

    def setupProcessing(self):
        self.opInProgress = SyncOperations(self.dowork)       
        self.worker = Worker(self.opInProgress)
        self.worker.finished.connect(self.finished)
        self.worker.terminated.connect(self.finished)  #should distinguish between finished and terminated
        self.worker.start()
        
    def _syncCommand(self):
        if (not self.worker or not self.worker.isRunning()):
            self.actionCommand.setEnabled(True)
            return self.tr("Start")
        elif (self.worker.isPaused()):
            self.actionCommand.setEnabled(True)
            return self.tr("Resume")
        elif self.worker.isPausing():
            self.actionCommand.setEnabled(False)
            return self.tr("Resume")
        else:
            self.actionCommand.setEnabled(True)
            return self.tr("Pause")
        
    def _syncStatus(self):
        if (not self.worker or not self.worker.isRunning()):
            return self.tr("Completed")
        elif self.worker.isPaused():
            return self.tr("Paused") 
        elif self.worker.isPausing():
            
            return self.tr("Pausing")         
        else: 
            return self.tr("Syncing")       
        
    def doWork(self):
        if (not self.worker or not self.worker.isRunning()):
            self._doSync()
        elif (not self.worker.isPaused()):
            self._pauseSync()
        else:
            self._resumeSync()
            
        
    def _doSync(self):
        if len(self.controller.list_server_bindings()) == 0:
            # Launch the GUI to create a binding
            from nxdrive.gui.authentication import prompt_authentication
            ok = prompt_authentication(self.controller, DEFAULT_NX_DRIVE_FOLDER,
                                       url=Constants.DEFAULT_CLOUDDESK_URL,
                                       username=Constants.DEFAULT_ACCOUNT)
            if not ok: return
            
        self.setupProcessing()
#        self._updateOperationStatus(Constants.SYNC_STATUS_START)
    
    def started(self):
        self.actionCommand.setText("Pause")
        self.actionStatus.setText("Syncing")
        
    def finished(self):
        self.opInProgress = None
        self.worker = None
        self.actionCommand.setText("Start")
        self.actionStatus.setText("Completed")
        
    def _pauseSync(self):
        self.worker.pause()
#        self._updateOperationStatus(Constants.SYNC_STATUS_STOP)
            
    def _resumeSync(self):
        self.worker.resume()
#        self._updateOperationStatus(Constants.SYNC_STATUS_START)
                
    def _getUserName(self):
        local_folder = default_nuxeo_drive_folder()
        local_folder = os.path.abspath(os.path.expanduser(local_folder))
        server_binding = self.controller.get_server_binding(local_folder)
        return server_binding.remote_user if not server_binding == None else Constants.DEFAULT_ACCOUNT
            
    def _createImageWithOverlay(self, baseImage, overlayImage):
        imageWithOverlay = QImage(baseImage.size(), QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(imageWithOverlay)
        
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(imageWithOverlay.rect(), QtCore.Qt.transparent)
        
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(0, 0, baseImage)
        
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        baseRect = baseImage.rect()
        overlayRect = overlayImage.rect()      
        painter.drawImage(baseRect.width()-overlayRect.width(), baseRect.height()-overlayRect.height(), overlayImage)

        painter.end()
        return imageWithOverlay
            
  
class PreferencesDlg(QDialog, Ui_preferencesDlg):
    def __init__(self, controller, parent=None):
        super(PreferencesDlg, self).__init__(parent)
        self.setupUi(self)
        self.controller = controller
        applyBtn = self.buttonBox.button(QDialogButtonBox.Apply)
        applyBtn.clicked.connect(self.applyChanges)
        self.btnDisconnect.clicked.connect(self.manageBinding)
        self.btnBrowsefolder.clicked.connect(self.browseFolder)

        
    def _isConnected(self):
        return not (len(self.controller.list_server_bindings()) == 0)
        
    def _getDisconnectText(self):
        return self.tr("Connect...") if not self._isConnected() else self.tr("Disconnect")
        
    def showEvent(self, evt):
        if evt.spontaneous:
            self.lblComputer.setText(platform.node())
            self.lblStorage.setText("123Mb (0.03%) of 4Gb")    
            
            if not self._isConnected():
                self.txtUrl.setText(Constants.DEFAULT_CLOUDDESK_URL)
                self.txtAccount.setText(Constants.DEFAULT_ACCOUNT)
                self.txtCloudfolder.setText(self._getDefaultFolder())
                # Launch the GUI to create a binding
                ok = self._connect()
                if not ok:
                    self.destroy()
                    return

            self._updateBinding()
            super(PreferencesDlg, self).showEvent(evt)
        
    def _getDefaultFolder(self):
        # get home directory
        # this does not work in Windows
#        home = os.environ["HOME"]
        home = os.path.expanduser("~")
        if (home[-1] != os.sep):
            home += os.sep
        home += Constants.DEFAULT_NXDRIVE_FOLDER
        return home
    
    def browseFolder(self):
        defaultFld = self.txtCloudfolder.text()
        if (defaultFld == None):
            defaultFld = self._getDefaultFolder()
        selectedFld = QFileDialog.getExistingDirectory(self, self.tr("Choose or create directory"),
                        defaultFld, QFileDialog.DontResolveSymlinks)
        if (len(selectedFld) == 0):
            selectedFld = defaultFld
        self.txtCloudfolder.setText(selectedFld)
        
    def accept(self):
        # test
        print "changes accepted"
        
    def manageBinding(self):
        if (self._isConnected()):
            self._disconnect()
        else:
            self._connect()
        self._updateBinding()
        
    def _updateBinding(self):
        self.btnDisconnect.setText(self._getDisconnectText())
        if (self._isConnected()):
            local_folder = self.txtCloudfolder.text()
            if local_folder == '': local_folder = None
            binding = self.controller.get_server_binding(local_folder)
            self.txtAccount.setText(binding.remote_user)
            self.txtAccount.setCursorPosition(0)
            self.txtAccount.setToolTip(binding.remote_user)
            self.txtUrl.setText(binding.server_url)
            self.txtUrl.setCursorPosition(0)
            self.txtUrl.setToolTip(binding.server_url)
            self.txtCloudfolder.setText(binding.local_folder)
            self.txtCloudfolder.setCursorPosition(0)
            self.txtCloudfolder.setToolTip(binding.local_folder)
            self.txtAccount.setReadOnly(True)
            self.txtAccount.deselect()
            self.txtCloudfolder.setReadOnly(True)
            self.txtUrl.setReadOnly(True)
            self.btnBrowsefolder.setEnabled(False)
        else:
            self.txtAccount.setReadOnly(False)
            # widget looks still read-only
            self.txtAccount.setEnabled(True)
            self.txtAccount.setSelection(0, len(self.txtAccount.text()))
            self.txtCloudfolder.setReadOnly(False)
            self.txtCloudfolder.setEnabled(True)
            self.txtUrl.setReadOnly(False)
            self.txtUrl.setEnabled(True)
            self.btnBrowsefolder.setEnabled(True)
    
    def _connect(self):
        # Launch the GUI to create a binding
        from nxdrive.gui.authentication import prompt_authentication
        from nxdrive.commandline import default_nuxeo_drive_folder
        local_folder = self.txtCloudfolder.text() if self.txtCloudfolder.text() else DEFAULT_NX_DRIVE_FOLDER
        remote_user = self.txtAccount.text() if self.txtAccount.text() else Constants.DEFAULT_ACCOUNT
        server_url = self.txtUrl.text() if self.txtUrl.text() else Constants.DEFAULT_CLOUDDESK_URL
        return prompt_authentication(self.controller, local_folder, url=server_url, username=remote_user)
                
    def _disconnect(self):
        local_folder = self.txtCloudfolder.text()
        self.controller.unbind_server(local_folder)
        
    def applyChanges(self):
        # test
        print "button box button clicked"
        self.close()
        
    
from nxdrive.utils.helpers import QApplicationSingleton

def startApp(controller, start):
    app = QApplicationSingleton()
    app.setQuitOnLastWindowClosed(False)
    i = CloudDeskTray(controller, start)
    i.show()
    return app.exec_()

#   del i
#   del app

if __name__ == "__main__":
    sys.exit(startApp)
        