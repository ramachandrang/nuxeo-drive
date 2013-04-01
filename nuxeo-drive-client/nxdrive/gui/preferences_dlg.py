'''
Created on Dec 13, 2012

@author: mconstantin
'''

from __future__ import division
import os
import sys
import platform
import shutil
from time import time

from PySide.QtGui import QApplication, QDialog, QMessageBox, QDialogButtonBox, QFileDialog, QIcon
from PySide.QtCore import Qt, QSettings
from PySide.QtCore import Signal, Slot, QObject

from nxdrive import Constants
from nxdrive.model import ServerBinding, RecentFiles, LastKnownState, ServerEvent, SyncFolders
from nxdrive.controller import default_nuxeo_drive_folder
from nxdrive.logging_config import get_logger
from nxdrive.utils import create_settings
from nxdrive.utils import register_startup_darwin
from nxdrive.utils import EventFilter
from nxdrive.utils import win32utils
from nxdrive.utils.helpers import find_exe_path
from nxdrive.client.base_automation_client import ProxyInfo
from ui_preferences import Ui_preferencesDlg
from proxy_dlg import ProxyDlg
from progress_dlg import ProgressDialog
from folders_dlg import SyncFoldersDlg
import nxdrive.gui.qrc_resources


def default_expanded_nuxeo_drive_folder():
    return os.path.expanduser(DEFAULT_NX_DRIVE_FOLDER)

log = get_logger(__name__)

settings = create_settings()

DEFAULT_NX_DRIVE_FOLDER = default_nuxeo_drive_folder()
DEFAULT_EX_NX_DRIVE_FOLDER = default_expanded_nuxeo_drive_folder()

settings = QSettings()

class ClickDetector(QObject):
    clicked = Signal()
    MAX_TIME = 5
    
    def __init__(self):
        super(ClickDetector, self).__init__()
        self._clear()
        
    def _clear(self):
        self.num_clicks = 0
        self.start = time()
            
    def click(self):
        current = time()
        if current - self.start > ClickDetector.MAX_TIME:
            self._clear()
        self.num_clicks += 1
        if self.num_clicks == 5:
            self.clicked.emit()
            self._clear()
        
        
class PreferencesDlg(QDialog, Ui_preferencesDlg):
    def __init__(self, frontend = None, parent = None):
        super(PreferencesDlg, self).__init__(parent)
        self.setupUi(self)
        self.setWindowIcon(QIcon(Constants.APP_ICON_DIALOG))
        self.setWindowTitle('%s Preferences' % Constants.APP_NAME)
        self.tabWidget.setCurrentIndex(0)
        self.cbAutostart.setText(self.tr('Start automatically when starting this computer'))
        # BEGIN remove site url
#        self.label_3.setText(self.tr('Site Url:'))
        # END remove site url
        self.label_7.setText(self.tr('Folder location'))
        self.groupboxSite.setTitle(self.tr('%s Site') % Constants.PRODUCT_NAME)
        self.groupboxSite.setToolTip(Constants.CLOUDDESK_URL)
        self.frontend = frontend
        self.controller = frontend.controller
        self.result = ProgressDialog.OK_AND_NO_RESTART
        self.values = None
        self.stop_on_apply = False
        self.local_folder = frontend._get_local_folder() if frontend is not None else DEFAULT_EX_NX_DRIVE_FOLDER
        self.previous_local_folder = self.local_folder
        self.local_folder_text_changed = False
        self.prev_local_folder = self.local_folder
        self.reuse_folder = False
        self.bknd_clicks = ClickDetector()
        self.server_binding = self.controller.get_server_binding(self.local_folder, raise_if_missing = False)
        self.proxy = None
        self.rbProxy.setCheckable(True)
        self.rbDirect.setCheckable(True)
        applyBtn = self.buttonBox.button(QDialogButtonBox.Apply)
        applyBtn.clicked.connect(self.applyChanges)
        self.btnDisconnect.clicked.connect(self.manageBinding)
        self.btnBrowsefolder.clicked.connect(self.browseFolder)
        self.txtCloudfolder.editingFinished.connect(self.changeFolder)
        self.txtCloudfolder.textEdited.connect(self.folder_text_changed)
        self.btnSelect.clicked.connect(self.selectFolders)
        self.btnProxy.clicked.connect(self.configProxy)
#        self.cbEnablelog.stateChanged.connect(self.enableLog)
        self.cbNotifications.stateChanged.connect(self.setNotifications)
        self.cbAutostart.stateChanged.connect(self.setAutostart)
        self.rbProxy.toggled.connect(self.setProxy)
        # REMOVE proxy auto-detect
        self.rbAutodetect.toggled.connect(self.setProxy)
        self.bknd_clicks.clicked.connect(self.toggle_debug_mode)

        self.cbIconOverlays.stateChanged.connect(self.setShowIconOverlays)
        if sys.platform == 'win32':
            autostart = settings.value('preferences/autostart', 'true')
            if autostart.lower() == 'true':
                self.autostart = True
            elif autostart.lower() == 'false':
                self.autostart = False
            else:
                self.autostart = True
            iconOverlays = settings.value('preferences/icon-overlays', 'true')
            if iconOverlays.lower() == 'true':
                self.iconOverlays = True
            elif iconOverlays.lower() == 'false':
                self.iconOverlays = False
            else:
                self.iconOverlays = True
            notifications = settings.value('preferences/notifications', 'true')
            if notifications.lower() == 'true':
                self.notifications = True
            elif notifications.lower() == 'false':
                self.notifications = False
            else:
                self.notifications = True
            logEnabled = settings.value('preferences/log', 'true')
            if logEnabled.lower() == 'true':
                self.logEnabled = True
            elif logEnabled.lower() == 'false':
                self.logEnabled = False
            else:
                self.logEnabled = True
        else:
            self.autostart = settings.value('preferences/autostart', True)
            self.iconOverlays = settings.value('preferences/icon-overlays', True)
            self.notifications = settings.value('preferences/notifications', True)
            self.logEnabled = settings.value('preferences/log', True)

        self.useProxy = settings.value('preferences/useProxy', ProxyInfo.PROXY_DIRECT)

        self.rbProxy.setChecked(self.useProxy == ProxyInfo.PROXY_SERVER)
        self.rbDirect.setChecked(self.useProxy == ProxyInfo.PROXY_DIRECT)
        # REMOVE proxy auto-detect
        self.rbAutodetect.setChecked(self.useProxy == ProxyInfo.PROXY_AUTODETECT)
        self.btnProxy.setEnabled(self.useProxy == ProxyInfo.PROXY_SERVER)

        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self.tabWidget.currentChanged.connect(self.tab_changed)
        # set tabs icons
        self.tabWidget.setTabIcon(0, QIcon(Constants.APP_ICON_TAB_GENERAL))
        self.tabWidget.setTabIcon(1, QIcon(Constants.APP_ICON_TAB_ACCOUNT))
        self.tabWidget.setTabIcon(2, QIcon(Constants.APP_ICON_TAB_NETWORK))
        self.tabWidget.setTabIcon(3, QIcon(Constants.APP_ICON_TAB_ADVANCED))

    def _isConnected(self):
        return (self.server_binding is not None and
                (self.server_binding.remote_password is not None or self.server_binding.remote_token is not None))

    def _getDisconnectText(self):
        return self.tr("Sign In...") if not self._isConnected() else self.tr("Sign Out")

    def showEvent(self, evt):
        if evt.spontaneous:
            if self.server_binding is None:
                storage_text, exceeded = None, False
            else:
                storage_text, exceeded = self.controller.get_storage(self.server_binding)
            if storage_text is None:
                self.lblStorage.setText(self.tr('Not available'))
            else:
                self.lblStorage.setVisible(True)
                if exceeded:
                    storage_text = "<img src='%s'>%s</img>" % (Constants.APP_ICON_MENU_QUOTA, storage_text)
                self.lblStorage.setText(storage_text)

            self.lblComputer.setText(platform.node())
            self.rbProxy.setChecked(self.proxy != None)
            self.cbAutostart.setChecked(self.autostart)
            self.cbIconOverlays.setChecked(self.iconOverlays)
            self.cbNotifications.setChecked(self.notifications)
#            self.cbEnablelog.setChecked(self.logEnabled)

            if not self._isConnected():
                # BEGIN remove site url
#                self.txtUrl.setText(Constants.CLOUDDESK_URL)
                # END remove site url
                self.txtAccount.setText(Constants.ACCOUNT)
                self.txtCloudfolder.setText(os.path.dirname(self.local_folder))

            self._updateBinding()
            super(PreferencesDlg, self).showEvent(evt)

    def tab_changed(self, index):
        pass
#        if index != -1:
#            self.tabWidget.setTabIcon(index, QIcon(Constants.APP_ICON_ABOUT))

    def selectFolders(self):
        # this requires a server binding
        if not self._isConnected():
            self._connect()
                    
        # TODO folders are retrieved here by user or, when the synchronizer starts
        # In between they are not updated if there are server changes
        app = QApplication.instance()
        process_filter = EventFilter(self)

        dlg = SyncFoldersDlg(frontend = self.frontend)
        if dlg.exec_() == QDialog.Rejected:
            return

        # set the synchronized roots
        app.setOverrideCursor(Qt.WaitCursor)
        self.installEventFilter(process_filter)
        try:
            self.controller.synchronizer.set_roots(self.server_binding)
        except Exception as e:
            log.error(self.tr('Unable to set roots for %s (%s)'), self.server_binding.server_url, str(e))
        finally:
            app.restoreOverrideCursor()
            self.removeEventFilter(process_filter)


    def configProxy(self):
        # Proxy... button is only enabled in this case
        self.useProxy = ProxyInfo.PROXY_SERVER
        dlg = ProxyDlg(frontend = self.frontend)
        self.result = dlg.exec_()

    def setAutostart(self, state):
        self.autostart = True if state == Qt.Checked else False

    def setShowIconOverlays(self, state):
        self.iconOverlays = True if state == Qt.Checked else False

    def setNotifications(self, state):
        self.notifications = True if state == Qt.Checked else False

    def enableLog(self, state):
        self.logEnabled = True if state == Qt.Checked else False

    def setProxy(self, state):
        # ignore state as is called from multiple toggle events
        if self.rbProxy.isChecked():
            self.btnProxy.setEnabled(True)
        # REMOVE proxy auto-detect
        elif self.rbAutodetect.isChecked():
            self.btnProxy.setEnabled(False)
        else:
            self.btnProxy.setEnabled(False)

    def folder_text_changed(self, text):
        self.local_folder_text_changed = True
        
    def changeFolder(self):
        if not self.local_folder_text_changed:
            return
        parent_folder = self.txtCloudfolder.text()
        folder = os.path.normpath(os.path.join(parent_folder, Constants.DEFAULT_NXDRIVE_FOLDER))
        if folder == self.prev_local_folder:
            return
        # validate at least the folder since it could have been entered directly
        if (not os.path.exists(parent_folder)):
            mbox = QMessageBox(QMessageBox.Warning, Constants.APP_NAME, self.tr("Folder %s does not exist.") % parent_folder)
            mbox.setInformativeText(self.tr("Do you want to create it?"))
            mbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            if mbox.exec_() == QMessageBox.No:
                self.local_folder_text_changed = False
                return
         
        if os.path.exists(folder):
            error = QMessageBox(QMessageBox.Warning, self.tr("Path Error"),
                                                      self.tr("Folder %s already exists") % folder,
                                                      QMessageBox.Ok,
                                                      self)
            error.setInformativeText(self.tr("Select a folder where %s does not exist." % Constants.DEFAULT_NXDRIVE_FOLDER))
            error.exec_()
            self.local_folder_text_changed = False
            self.tabWidget.setCurrentIndex(3)
            return
            
#        os.makedirs(folder)
        self.local_folder = folder
        self.local_folder_text_changed = False
        self.reuse_folder = True

    def browseFolder(self):
        """enter or select a new path"""
        defaultFld = self.txtCloudfolder.text()
        if (defaultFld == None):
            defaultFld = self.local_folder
        selectedFld = QFileDialog.getExistingDirectory(self, self.tr("Choose or create %s folder location") % Constants.PRODUCT_NAME,
                        defaultFld, QFileDialog.DontResolveSymlinks)
        if (len(selectedFld) == 0):
            selectedFld = defaultFld
        self.txtCloudfolder.setText(selectedFld)
        self.local_folder_text_changed = True
        self.changeFolder()

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
            # BEGIN remove site url
#            self.txtUrl.setText(self.server_binding.server_url)
#            self.txtUrl.setCursorPosition(0)
#            self.txtUrl.setToolTip(self.server_binding.server_url)
            # END remove site url
            self.txtCloudfolder.setText(os.path.dirname(self.server_binding.local_folder))
            self.txtCloudfolder.setCursorPosition(0)
            self.txtCloudfolder.setToolTip(self.server_binding.local_folder)
            self.txtAccount.setReadOnly(True)
            self.txtAccount.deselect()
            # BEGIN remove site url
#            self.txtUrl.setReadOnly(True)
            # END remove site url
            self.btnSelect.setEnabled(True)
        else:
            self.txtAccount.setReadOnly(False)
            # widget looks still read-only
            self.txtAccount.setEnabled(True)
            self.txtAccount.setSelection(0, len(self.txtAccount.text()))
            # BEGIN remove site url
#            self.txtUrl.setReadOnly(False)
#            self.txtUrl.setEnabled(True)
            # END remove site url
            self.btnSelect.setEnabled(False)

    def _connect(self):
        # Launch the GUI to create a binding
        from nxdrive.gui.authentication import prompt_authentication

        parent_folder = self.txtCloudfolder.text()
        local_folder = os.path.join(parent_folder, Constants.DEFAULT_NXDRIVE_FOLDER)
        if not self.reuse_folder:
            msg = QMessageBox(QMessageBox.Warning, self.tr('Folder Exists'),
                              self.tr("The folder %s already exists.") % local_folder,
                              QMessageBox.Ok)
            msg.setInformativeText(self.tr("Select a folder where %s does not exist.") % Constants.DEFAULT_NXDRIVE_FOLDER)
            msg.exec_()
            self.tabWidget.setCurrentIndex(3)
            return
                
        self.reuse_folder = True
        remote_user = self.txtAccount.text()
        # BEGIN remove site url
#        server_url = self.txtUrl.text()
        server_url = Constants.CLOUDDESK_URL
        # BEGIN remove site url
        # validate at least the folder since it could have been entered directly
        if (not os.path.exists(local_folder)):
            mbox = QMessageBox(QMessageBox.Warning, Constants.APP_NAME, self.tr("Folder %s does not exist.") % local_folder)
            mbox.setInformativeText(self.tr("Do you want to create it?"))
            mbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            if mbox.exec_() == QMessageBox.No:
                self.tabWidget.setCurrentIndex(3)
                return
            os.makedirs(local_folder)

        result, self.values = prompt_authentication(self.controller, local_folder, url = server_url, username = remote_user, update = False)
        if result:
            self.frontend.server_binding = self.server_binding = ServerBinding(local_folder,
                                                                                self.values['url'],
                                                                                self.values['username'],
                                                                                remote_password = self.values['password']
                                                                                )
            self.frontend.local_folder = self.local_folder = local_folder
        return result

    def _disconnect(self):
        self.previous_local_folder = self.local_folder
        self.local_folder = None
        self.server_binding = None
        self.reuse_folder = False

    def applyChanges(self):
        same_binding = False
        previous_binding = None
        if self.previous_local_folder is not None:
            previous_binding = self.controller.get_server_binding(local_folder = self.previous_local_folder, raise_if_missing = False)
        same_binding = self.server_binding == previous_binding

        if not same_binding:
            try:
                if previous_binding is not None:
                    self.result = ProgressDialog.stopServer(self.frontend, parent = self)
                    if self.result == ProgressDialog.CANCELLED:
                        return QDialog.Rejected
                    # disconnect
                    self.controller.unbind_server(self.previous_local_folder)

                if self._isConnected():
                    # the binding may exist but credentials are invalid
#                    assert(len(self.controller.list_server_bindings()) == 0)
                    if not os.path.exists(self.local_folder):
                        mbox = QMessageBox(QMessageBox.Warning, Constants.APP_NAME, self.tr("Folder %s does not exist.") % self.local_folder)
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
                QMessageBox(QMessageBox.Critical, self.tr("%s Error") % Constants.APP_NAME, self.tr("Failed to connect to server, please try again.")).exec_()
                return QDialog.Rejected

        if self.local_folder is not None and self.prev_local_folder is not None and self.local_folder != self.prev_local_folder:
            if self._isConnected():
                # prompt for moving the Nuxeo Drive folder for current binding
                msg = QMessageBox(QMessageBox.Question, self.tr('Move Root Folder'),
                                  self.tr("This action will move the %s folder and all its subfolders and files\n"
                                  "to a new location. It will also stop the synchronization if running.\n"
                                  ) % self.local_folder,
                                  QMessageBox.Yes | QMessageBox.No)
                msg.setInformativeText(self.tr("Do you want to proceed?"))
                if msg.exec_() == QMessageBox.No:
                    return


            if os.path.exists(self.local_folder):
                error = QMessageBox(QMessageBox.Warning, self.tr("Path Error"),
                                                          self.tr("Folder %s already exists" % self.local_folder),
                                                          QMessageBox.Ok)
                error.setInformativeText(self.tr("Select a folder where %s does not exist." % Constants.DEFAULT_NXDRIVE_FOLDER))
                error.exec_()
                return QDialog.Rejected

            self.result = ProgressDialog.stopServer(self.frontend, parent = self)
            if self.result == ProgressDialog.CANCELLED:
                return QDialog.Rejected
            try:
                shutil.move(self.prev_local_folder, self.local_folder)
            except shutil.Error as e:
                error = QMessageBox(QMessageBox.Critical, self.tr("Move Error"),
                                                          self.tr("Error moving folder %s to %s" % (self.prev_local_folder, self.local_folder)))
                error.setInformativeText(str(e))
                error.exec_()
                return QDialog.Rejected


            # Update the database
            if self.frontend is not None:
                session = self.frontend.controller.get_session()
                recent_files = session.query(RecentFiles).all()
                for rf in recent_files:
#                    rf.local_folder = rf.local_root.replace(self.local_folder, self.local_folder)
                    rf.local_folder = self.local_folder

                last_known_states = session.query(LastKnownState).all()
                for lks in last_known_states:
#                    if lks.local_root.find(self.local_folder) != -1:
#                        lks.local_root = lks.local_root.replace(self.local_folder, self.local_folder)
                    lks.local_folder = self.local_folder

                # Update this last as it cascades primary key change to the other tables
                server_bindings = session.query(ServerBinding).filter(ServerBinding.local_folder == self.local_folder).all()
                for sb in server_bindings:
                    sb.local_folder = self.local_folder
                    
                server_events = session.query(ServerEvent).filter(ServerEvent.local_folder == self.local_folder).all()
                for se in server_events:
                    se.local_folder = self.local_folder
                    
                sync_folders = session.query(SyncFolders).filter(SyncFolders.local_folder == self.local_folder).all()
                for sf in sync_folders:
                    sf.local_folder = self.local_folder
                session.commit()

                self.frontend.local_folder = self.local_folder

        # Update the Favorites link (Windows only)
        if sys.platform == 'win32':
            if self.server_binding is not None:
                shortcut = os.path.join(os.path.expanduser('~'), 'Links', Constants.PRODUCT_NAME + '.lnk')
                win32utils.create_or_replace_shortcut(shortcut, self.local_folder)

        # Apply other changes
        if self.rbProxy.isChecked():
            useProxy = ProxyInfo.PROXY_SERVER
        # REMOVE proxy auto-detect
        elif self.rbAutodetect.isChecked():
            useProxy = ProxyInfo.PROXY_AUTODETECT
        else:
            useProxy = ProxyInfo.PROXY_DIRECT

        if useProxy != self.useProxy:
            if useProxy == ProxyInfo.PROXY_SERVER:
                dlg = ProxyDlg(frontend = self)
                if dlg.exec_() == QDialog.Rejected:
                    return
            elif useProxy == ProxyInfo.PROXY_DIRECT:
                # restart sync to clear all cached remote clients using the proxy
                self.result = ProgressDialog.stopServer(self.frontend, parent = self)
                if self.result == ProgressDialog.CANCELLED:
                    return QDialog.Rejected
#                self.controller.nuxeo_client_factory(...).proxy = None
                # NOTE: this will not work for a remote client factory different from RemoteDocumentClient
                # but requires at least 4 params
                self.controller.reset_proxy()

            self.useProxy = useProxy
            if self.useProxy == ProxyInfo.PROXY_AUTODETECT or self.useProxy == ProxyInfo.PROXY_DIRECT:
                settings.setValue('preferences/proxyServer', '')
                settings.setValue('preferences/proxyPort', '')
            if self.useProxy == ProxyInfo.PROXY_DIRECT:
                settings.setValue('preferences/proxyUser', '')
                settings.setValue('preferences/proxyPwd', '')
                settings.setValue('preferences/proxyAuthN', False)
        elif useProxy and self.controller.proxy_changed():
            self.result = ProgressDialog.stopServer(self.frontend, parent = self)
            if self.result == ProgressDialog.CANCELLED:
                return QDialog.Rejected
            self.controller.set_proxy()

        settings.setValue('preferences/useProxy', self.useProxy)
        settings.setValue('preferences/notifications', self.notifications)
        settings.setValue('preferences/icon-overlays', self.iconOverlays)
        settings.setValue('preferences/autostart', self.autostart)
        settings.setValue('preferences/log', self.logEnabled)

        if sys.platform == 'win32':
            startup_folder = os.path.expanduser('~/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup')
            startup_folder = os.path.normpath(startup_folder)
            shortcut_path = os.path.join(startup_folder, Constants.SHORT_APP_NAME + '.lnk')
            if self.autostart:
                target = find_exe_path()
                if os.path.splitext(target)[1] == '.py':
                    # FOR TESTING
                    target = sys.executable + ' ' + target + ' gui --start'
                win32utils.create_shortcut_if_not_exists(shortcut_path, target)
            else:
                try:
                    os.unlink(shortcut_path)
                except WindowsError as e:
                    log.debug('error deleting shortcut: %s', e)
                    
        elif sys.platform == 'darwin':
#            plist_settings = QSettings(os.path.expanduser('~/Library/LaunchAgents/%s.%s.plist') % (Constants.COMPANY_NAME, Constants.SHORT_APP_NAME),
#                                       QSettings.NativeFormat)
#            if not plist_settings.contains('Label'):
#                # create the plist
#                plist_settings.setValue('Label', '%s.%s' % (Constants.COMPANY_NAME, Constants.SHORT_APP_NAME))
#                path = '/Applications/%s.app/Contents/MacOS/%s' % (Constants.OSX_APP_NAME, Constants.OSX_APP_NAME)
#                plist_settings.setValue('Program', path)
#                plist_settings.setValue('ProgramArguments', [path, 'gui'])
#
#            # start when it loads the agent
#            plist_settings.setValue('RunAtLoad', self.autostart)
#            # restart if app stops with a non-normal exit status, i.e. non-zero (crash?)
#            if self.autostart:
#                plist_settings.setValue('KeepAlive', {'SuccessfulExit': False})
#            else:
#                plist_settings.remove('KeepAlive')
            if self.autostart:
                register_startup_darwin()

        settings.sync()

        self.check_and_restart(self.result)
        self.done(QDialog.Accepted)

    def check_and_restart(self, result):
        """Restart syncing if it was stopped."""

        if self.result == ProgressDialog.OK_AND_RESTART and self.frontend.state == Constants.APP_STATE_STOPPED:
            self.frontend._doSync()

    def mousePressEvent(self, event):
        self.bknd_clicks.click()
        super(PreferencesDlg, self).mousePressEvent(event)
        
    @Slot()
    def toggle_debug_mode(self):
        nxdrive.DEBUG = not nxdrive.DEBUG
        
        
