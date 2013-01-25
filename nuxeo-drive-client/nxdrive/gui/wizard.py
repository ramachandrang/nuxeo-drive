'''
Created on Jan 16, 2013

@author: mconstantin
'''

import sys
import os.path
import subprocess

from PySide.QtCore import Qt
from PySide.QtGui import QWizard, QWizardPage, QPixmap, QIcon, QPalette, QApplication
from PySide.QtGui import QLabel, QLineEdit, QGridLayout, QHBoxLayout, QVBoxLayout
from PySide.QtGui import QPushButton, QRadioButton, QCheckBox, QGroupBox, QFileDialog, QDialog, QMessageBox
from PySide.QtWebKit import QWebView

from folders_dlg import SyncFoldersDlg
from nxdrive.utils.helpers import QApplicationSingleton, EventFilter
from nxdrive.utils.helpers import Communicator
from nxdrive.gui.menubar import DEFAULT_EX_NX_DRIVE_FOLDER
from nxdrive.protocol_handler import win32
from nxdrive import Constants
import nxdrive.gui.qrc_resources


class CpoWizard(QWizard):
    pages = {
             'IntroPage': 1,
             'InstallOptionsPage': 2,
             'GuideOnePage': 3,
             'GuideTwoPage': 4,
             'GuideThreePage': 5,
             'AdvancedPage': 6,
             'FinalPage': 7,
             }
    
    IntroPageId = 0
    InstallOptionsPageId = 1
    GuideOnePageId = 2
    GuideTwoPageId = 3
    GuideThreePageId = 4
    FinalPageId = 5
    AdvancedPageId = 6
    
    def __init__(self, controller, options=None, parent=None):
        super(CpoWizard, self).__init__(parent)
        
        self.controller = controller
        self.session = self.controller.get_session()
        self.communicator = Communicator()
        self.options = options
        self.skip = False
        self.keep_location = False
        self.local_folder = None
        
        self.addPage(IntroPage())           #0
        self.addPage(InstallOptionsPage())  #1
        self.addPage(GuideOnePage())        #2
        self.addPage(GuideTwoPage())        #3
        self.addPage(GuideThreePage())      #4
        self.addPage(FinalPage())           #5
        self.addPage(AdvancedPage())        #6
        
        self.setWindowIcon(QIcon(Constants.APP_ICON_ENABLED))
        self.setFixedSize(700, 500)      
        self.setPixmap(QWizard.LogoPixmap, QPixmap(Constants.APP_IMG_WIZARD_BANNER))
        self.setWindowTitle(self.tr('%s Setup') % Constants.APP_NAME)
        if sys.platform == 'win32':
            self.setWizardStyle(QWizard.ModernStyle)
        elif sys.platform == 'darwin':
            self.setWizardStyle(QWizard.MacStyle)
            
    def add_skip_tour(self, forward):
        self.setButtonText(QWizard.CustomButton1, self.tr('&Skip Tour'))
        self.setOption(QWizard.HaveCustomButton1 ,True)
        self.customButtonClicked.connect(self.skip_tour)
       
        btnList = [QWizard.Stretch, QWizard.CustomButton1, QWizard.CommitButton, QWizard.BackButton, QWizard.NextButton, QWizard.FinishButton]                   
        self.setButtonLayout(btnList)
        
    def remove_skip_tour(self):
        # NOTE: this cause a Python exception
#        self.setOption(QWizard.CustomButton1, False)
        btn = self.button(QWizard.CustomButton1)
        if btn.text():
            self.customButtonClicked.disconnect(self.skip_tour)
            
        self.setOption(QWizard.HaveCustomButton1 ,False)
        btnList = [QWizard.Stretch, QWizard.BackButton, QWizard.CommitButton, QWizard.NextButton, QWizard.FinishButton]
        self.setButtonLayout(btnList)
        
    def skip_tour(self, custom_button):
        if custom_button == QWizard.CustomButton1:
            # Skip Tour button
            self.skip = True
            self.next()
            self.skip = False
            
    def nextId(self):
        if self.currentId() == CpoWizard.FinalPageId:
            return -1  
        
        if self.skip:
            return CpoWizard.FinalPageId
            
        if self.currentId() == CpoWizard.InstallOptionsPageId:
            advanced = self.field('advanced')
            if advanced:
                return CpoWizard.AdvancedPageId
            else:
                return CpoWizard.GuideOnePageId

        if self.currentId() == CpoWizard.AdvancedPageId:
            return CpoWizard.GuideOnePageId
                    
        return self.currentId() + 1 
 
    def _unbind_if_bound(self, folder):
        server_binding = self.controller.get_server_binding(session=self.session, raise_if_missing=False)
        unbind = False
        if server_binding is not None:
            unbind = server_binding.local_folder != folder
            if sys.platform == 'win32':
                unbind = server_binding.local_folder.upper() != folder.upper()
        else:
            return True
                
        if unbind:
            self.controller.unbind_server(server_binding.local_folder)
            return True
        else:
            return False
            
    def _bind(self, folder):
        self._unbind_if_bound(folder)
        username = self.field('username')
        pwd = self.field('pwd')
        url = Constants.DEFAULT_CLOUDDESK_URL
        self.controller.bind_server(folder, url, username, pwd) 
    
    def notify_folders_changed(self):
        self.communicator.folders.emit()
            
    def notify_local_folders(self, local_folders):
        pass

    def accept(self):
        from nxdrive.client import ProxyInfo
        from nxdrive.utils.helpers import create_settings
        
        if self.local_folder is not None and not os.path.exists(self.local_folder):
            os.makedirs(self.local_folder)
            
        self.session.commit()
                
        if sys.platform == 'win32':
            # create the Favorites shortcut
            shortcut = os.path.join(os.path.expanduser('~'), 'Links', Constants.PRODUCT_NAME + '.lnk')
            win32.create_or_replace_shortcut(shortcut, self.local_folder)
                    
        settings = create_settings()
        settings.setValue('preferences/useProxy', ProxyInfo.PROXY_DIRECT)
        settings.setValue('preferences/proxyUser', '')
        settings.setValue('preferences/proxyPwd', '')
        settings.setValue('preferences/proxyAuthN', False)
        settings.setValue('preferences/notifications', True)
        settings.setValue('preferences/icon-overlays', True)
        settings.setValue('preferences/autostart', True)
        settings.setValue('preferences/log', True)
        
        launch = self.field('launch')
        if launch:
            exe_path = win32.find_exe_path()
            if exe_path is not None:
                subprocess.Popen([exe_path, '--start'])
            else:
                base = os.path.split(os.path.split(__file__)[0])[0]
                script = os.path.join(base, 'commandline.py')
                python = sys.executable
                subprocess.Popen([python, script, '--start'])
        
        return super(CpoWizard,self).accept()
        
    def reject(self):
        self.session.rollback()
        return super(CpoWizard,self).reject()
    
    
class IntroPage(QWizardPage):
    def __init__(self, parent=None):
        super(IntroPage, self).__init__(parent)
        self.auth_ok = False
        
        self.setWindowTitle('<html><b><font color="red">%s</font></b></html> Setup' % Constants.APP_NAME)
        self.setSubTitle(self.tr('Welcome to %s') % Constants.APP_NAME)
        self.setPixmap(QWizard.BackgroundPixmap, QPixmap(Constants.APP_IMG_WIZARD_BKGRND))
        self.setPixmap(QWizard.WatermarkPixmap, QPixmap(Constants.APP_IMG_WIZARD_WATERMARK))
        
        self.lblInstr = QLabel(self.tr('Please log in to %s') % Constants.PRODUCT_NAME)
        self.lblUrl = QLabel("<html><a href='%s'>%s</a></html>" % (Constants.DEFAULT_CLOUDDESK_URL, Constants.DEFAULT_CLOUDDESK_URL))
        self.lblUrl.setStyleSheet("QLabel { font-size: 10px }")
        self.lblUrl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.lblUrl.setOpenExternalLinks(True)
        self.lblUsername = QLabel(self.tr('Username'))
        self.lblPwd = QLabel(self.tr('Password'))
        self.txtUsername = QLineEdit()
        self.lblUsername.setBuddy(self.txtUsername)
        self.txtPwd = QLineEdit()
        self.lblPwd.setBuddy(self.txtPwd)
        self.txtPwd.setEchoMode(QLineEdit.Password)
        self.btnLogin = QPushButton(self.tr('Login'))
        self.lblMessage = QLabel()
        self.lblMessage.setObjectName('message')
        
        self.lblMessage.setWordWrap(True)
        self.lblMessage.setVisible(False)
          
        grid = QGridLayout()
        grid.addWidget(self.lblInstr, 0, 0, 1, 2)
        grid.addWidget(self.lblUrl, 1, 0, 1, 2)
        grid.addWidget(self.lblUsername, 2, 0, Qt.AlignRight)
        grid.addWidget(self.txtUsername, 2, 1)
        grid.addWidget(self.lblPwd, 3, 0, Qt.AlignRight)
        grid.addWidget(self.txtPwd, 3, 1)
        hlayout = QHBoxLayout()
        hlayout.addStretch(10)
        hlayout.addWidget(self.btnLogin)
        grid.addLayout(hlayout, 4, 1)
        grid.addWidget(self.lblMessage, 5, 0, 1, 2)
        self.setLayout(grid)
        
        self.registerField('username', self.txtUsername)
        self.registerField('pwd', self.txtPwd)
        
    def initializePage(self):
        self.btnLogin.setText(self.tr('Logout') if self.auth_ok else self.tr('Login'))
        self.btnLogin.clicked.connect(self.login)
        
    def login(self):
        if self.auth_ok:
            self.auth_ok = False
            self.btnLogin.setText(self.tr('Login'))
            self.lblMessage.clear()
            self.completeChanged.emit()
            return
        
        from nxdrive.client import Unauthorized
        app = QApplication.instance()
        process_filter = EventFilter(self)
        
        try:
            app.setOverrideCursor(Qt.WaitCursor)
            self.installEventFilter(process_filter)
            
            self.wizard().controller.validate_credentials(Constants.DEFAULT_CLOUDDESK_URL, 
                self.txtUsername.text(), self.txtPwd.text())
            
            app.restoreOverrideCursor()
            self.removeEventFilter(process_filter)
            self.lblMessage.setText(self.tr("You used 123Mb (0.03%) of 4Gb"))
            self.lblMessage.setStyleSheet("QLabel { font-size: 10px; color: green }")
            self.auth_ok = True
            self.completeChanged.emit()
        except Unauthorized:
            self.lblMessage.setText(self.tr('Invalid credentials.'))
            self.lblMessage.setStyleSheet("QLabel { font-size: 10px; color: red }")
            self.auth_ok = False
        except Exception as e:
            msg = self.tr('Unable to connect to %s') % Constants.DEFAULT_CLOUDDESK_URL
            if hasattr(e, 'msg'):
                msg = e.msg
            self.lblMessage.setText(msg)
            self.lblMessage.setStyleSheet("QLabel { font-size: 10px; color: red }")
            self.auth_ok = False
        finally:
            app.restoreOverrideCursor()
            self.removeEventFilter(process_filter)
            
        self.lblMessage.setVisible(True)
        self.btnLogin.setText(self.tr('Logout') if self.auth_ok else self.tr('Login'))

    def isComplete(self):
        return self.auth_ok
        # TODO remove this - for test only
#        return True
        
class InstallOptionsPage(QWizardPage):
    def __init__(self, parent=None):
        super(InstallOptionsPage, self).__init__(parent)
#        self.typical = True
        
        self.setSubTitle(self.tr('Choose Setup Type'))
        self.setPixmap(QWizard.BackgroundPixmap, QPixmap(Constants.APP_IMG_WIZARD_BKGRND))
        self.setPixmap(QWizard.WatermarkPixmap, QPixmap(Constants.APP_IMG_WIZARD_WATERMARK))

        # Typical option
        self.rdButtonTypical = QRadioButton(self)
        self.lblImgTypical = QLabel()
        self.lblImgTypical.setPixmap(QPixmap(Constants.APP_ICON_WIZARD_RB))
        self.lblTypical = QLabel(self.tr('Typical'))
        self.lblTypical2 = QLabel(self.tr('(recommended)'))
        self.lblTypical2.setStyleSheet('QLabel { font-size: 10px; color: gray }')
        self.lblTypical.setStyleSheet('QLabel { font-weight: bold }')
        self.lblTypicalDetail = QLabel(self.tr('Setup %s with normal settings') % Constants.APP_NAME)
        self.lblTypicalDetail.setStyleSheet('QLabel { font-size: 10px }')
        self.lblTypicalDetail.setWordWrap(True)
        innerinnerHLayout = QHBoxLayout()
        innerinnerHLayout.addWidget(self.lblTypical)
        innerinnerHLayout.addWidget(self.lblTypical2)
        innerinnerHLayout.addStretch(10)
        innerVLayout1 = QVBoxLayout()
        innerVLayout1.addLayout(innerinnerHLayout)
        innerVLayout1.addWidget(self.lblTypicalDetail)
        innerHLayout1 = QHBoxLayout()
        innerHLayout1.addWidget(self.rdButtonTypical)
        innerHLayout1.addWidget(self.lblImgTypical)
        innerHLayout1.addLayout(innerVLayout1)
        innerHLayout1.addStretch(10)
        # Advanced option
        self.rdButtonAdvanced = QRadioButton(self)
        self.lblImgAdvanced = QLabel()
        self.lblImgAdvanced.setPixmap(QPixmap(Constants.APP_ICON_WIZARD_RB))
        self.lblAdvanced = QLabel(self.tr('Advanced'))
        self.lblAdvanced.setStyleSheet('QLabel { font-weight: bold }')
        self.lblAdvancedDetail = QLabel(self.tr('Select your %s folder location, folders to synchronize, etc.') % Constants.PRODUCT_NAME)
        self.lblAdvancedDetail.setStyleSheet('QLabel { font-size: 10px }')
        self.lblAdvancedDetail.setWordWrap(True)
        innerVLayout2 = QVBoxLayout()
        innerVLayout2.addWidget(self.lblAdvanced)
        innerVLayout2.addWidget(self.lblAdvancedDetail)
        innerHLayout2 = QHBoxLayout()
        innerHLayout2.addWidget(self.rdButtonAdvanced)
        innerHLayout2.addWidget(self.lblImgAdvanced)
        innerHLayout2.addLayout(innerVLayout2)
        innerHLayout2.addStretch(10)
                               
        vLayout = QVBoxLayout()
        vLayout.addLayout(innerHLayout1)
        vLayout.addLayout(innerHLayout2)
        self.setLayout(vLayout)
        
        self.rdButtonAdvanced.toggled.connect(self.change_option)
        self.registerField('advanced', self.rdButtonAdvanced)
        
    def initializePage(self):
        self.rdButtonTypical.setChecked(True)
        self.wizard().add_skip_tour(True)
        
    def validatePage(self):
        if not self.rdButtonAdvanced.isChecked():
            folder = DEFAULT_EX_NX_DRIVE_FOLDER
            
            if os.path.exists(folder) and not self.wizard().keep_location:
                msgbox = QMessageBox(QMessageBox.Warning, self.tr("Folder Exists"), 
                                                          self.tr("Folder %s already exists. Do you want to use it?" % folder))
                msgbox.setInformativeText(self.tr("Select Yes to keep this location or No to select a different one on the Advanced next page."))
                msgbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                ret = msgbox.exec_()
                if ret == QMessageBox.No:
                    self.rdButtonAdvanced.setChecked(True)
                    return False
                
            self.wizard().keep_location = True
            if (not os.path.exists(folder)):
                os.makedirs(folder)
                if self.wizard().local_folder is not None:
                    os.unlink(self.wizard().local_folder)
            
            self.wizard().local_folder = folder               
            if self.wizard()._unbind_if_bound(folder):
                # create the default server binding      
                self.wizard()._bind(folder)

        return True
            
    def change_option(self, state):
        if state:
            self.wizard().remove_skip_tour()
        else:
            self.wizard().add_skip_tour(True)

class GuideOnePage(QWizardPage):
    def __init__(self, parent=None):
        super(GuideOnePage, self).__init__(parent)
        
        self.setPixmap(QWizard.BackgroundPixmap, QPixmap(Constants.APP_IMG_WIZARD_BKGRND))
        self.setPixmap(QWizard.WatermarkPixmap, QPixmap(Constants.APP_IMG_WIZARD_WATERMARK))
        username = self.field('username')
            
        self.setSubTitle(self.tr('Welcome to %s, %s!') % (Constants.APP_NAME, username))
        self.lblDetail = QLabel(self.tr("<html>The %s is a special folder which synchronizes content under <b>My Docs</b> and "
                                        "<b>Others Docs</b> folders with the same folders under your personal workspace of the %s. "
                                        "Only subfolders of <b>My Docs</b> and <b>Others Docs</b> that have been specifically selected will be synchronized. "
                                        "Drop files (or folders) under any of those synchronized folders and they will appear in the same location "
                                        "in your cloud workspace. Similarly, files (or folders) added to your workspace will appear in the same location "
                                        "on your desktop.</html>") % (Constants.PRODUCT_NAME, Constants.PRODUCT_NAME))
        self.lblDetail.setWordWrap(True)
        self.lblDetail.setStyleSheet('QLabel { font-size: 10px }')
        self.lblImg = QLabel()
        self.lblImg.setPixmap(QPixmap(Constants.APP_IMG_WIZARD_FINDER_FOLDERS))
        vLayout = QVBoxLayout()
        vLayout.addWidget(self.lblDetail)
        vLayout.addWidget(self.lblImg)
        self.setLayout(vLayout)
        
    def cleanupPage(self):
        advanced = self.wizard().field('advanced')
        if not advanced:
            self.wizard().add_skip_tour(False)
        else:
            self.wizard().remove_skip_tour()

class GuideTwoPage(QWizardPage):
    def __init__(self, parent=None):
        super(GuideTwoPage, self).__init__(parent)
        
        self.setPixmap(QWizard.BackgroundPixmap, QPixmap(Constants.APP_IMG_WIZARD_BKGRND))
        self.setPixmap(QWizard.WatermarkPixmap, QPixmap(Constants.APP_IMG_WIZARD_WATERMARK))
            
        self.setSubTitle(self.tr('Access your files from everywhere using %s!') % Constants.PRODUCT_NAME)
        self.lblDetail = QLabel(self.tr("<html>To access your files from a different computer, log in to %s. "
                                        "There you can preview, download or upload files using just your web browser.</html>") % Constants.PRODUCT_NAME)
        self.lblDetail.setWordWrap(True)
        self.lblDetail.setStyleSheet('QLabel { font-size: 10px }')
        self.lblImg = QLabel()
        self.lblImg.setPixmap(QPixmap(Constants.APP_IMG_WIZARD_ACCESS_FILES))
        vLayout = QVBoxLayout()
        vLayout.addWidget(self.lblDetail)
        vLayout.addWidget(self.lblImg)
        self.setLayout(vLayout)

class GuideThreePage(QWizardPage):
    def __init__(self, parent=None):
        super(GuideThreePage, self).__init__(parent)
        
        self.setPixmap(QWizard.BackgroundPixmap, QPixmap(Constants.APP_IMG_WIZARD_BKGRND))
        self.setPixmap(QWizard.WatermarkPixmap, QPixmap(Constants.APP_IMG_WIZARD_WATERMARK))
            
        self.setSubTitle(self.tr('The %s Notification Icon') % Constants.APP_NAME)
#        self.lblDetail = QLabel(self.tr("<html>Access your %s from the Mac Menu Bar. "
#                                        "A <img href='%s'></img> icon indicates that the client is connected ready to synchronize your files. "
#                                        "If the icon is animated, synchronization is in progress. "
#                                        "A <img href='%s'></img> icon indicates that the client is not connected or not started yet. "
#                                        "Use the Start menu or check your Preferences to connect to %s site. "
#                                        "Also from the same menu, you can open your %s folder, access the site, or change other settings.</html>") % 
#                                (Constants.PRODUCT_NAME, 'nxdrive/data/icons/nuxeo_drive_icon_16_enabled.png', Constants.APP_ICON_DISABLED, Constants.PRODUCT_NAME, Constants.APP_NAME))
#        self.lblDetail.setWordWrap(True)
#        self.lblDetail.setStyleSheet('QLabel { font-size: 10px }')
#        self.lblImg = QLabel()
#        self.lblImg.setPixmap(QPixmap(Constants.APP_IMG_WIZARD_APPBAR))
#        vLayout = QVBoxLayout()
#        vLayout.addWidget(self.lblDetail)
#        vLayout.addWidget(self.lblImg)
#        self.setLayout(vLayout)
        self.lblImg = QLabel()
        self.lblImg.setPixmap(QPixmap(Constants.APP_IMG_WIZARD_APPBAR))
        self.webView = QWebView(self)
        self.webView.setFixedHeight(130)
        
        from nxdrive.gui.resources import find_icon
        icon1_path = find_icon(Constants.ICON_APP_ENABLED)
        data_uri1 = open(icon1_path, "rb").read().encode("base64").replace("\n", "")
        img_tag1 = '<img alt="sample" src="data:image/png;base64,{0}">'.format(data_uri1)
        icon2_path = find_icon(Constants.ICON_APP_DISABLED)
        data_uri2 = open(icon2_path, "rb").read().encode("base64").replace("\n", "")
        img_tag2 = '<img alt="sample" src="data:image/png;base64,{0}">'.format(data_uri2)        
        self.webView.setHtml(self.tr("<html><body style='background:WhiteSmoke; font-size:10px'>Access your %s from the Mac Menu Bar."
                                        "<br>A %s icon indicates that the client is connected ready to synchronize your files. "
                                        "<br>If the icon is animated, synchronization is in progress. "
                                        "<br>A %s icon indicates that the client is not connected or not started yet. "
                                        "<br>Use the Start menu or check your Preferences to connect to %s site. "
                                        "<br>Also from the same menu, you can open your %s folder, access the site, or change other settings.</body></html>") % 
                                (Constants.PRODUCT_NAME, img_tag1, img_tag2, Constants.PRODUCT_NAME, Constants.APP_NAME))
#        palette = self.webView.palette();
#        palette.setBrush(QPalette.Base, Qt.transparent);
#        self.webView.page().setPalette(palette);
#        self.webView.setAttribute(Qt.WA_OpaquePaintEvent, False);
#        self.webView.setAutoFillBackground(False)
#        
#        p1 = self.palette()
#        c = p1.color(self.backgroundRole())
#        p2 = self.webView.palette()
#        p2.setColor(self.webView.backgroundRole(), c)
#        self.webView.setPalette(p2)
        vLayout = QVBoxLayout()
        vLayout.addWidget(self.webView)
        vLayout.addWidget(self.lblImg)
        self.webView.show()
        self.setLayout(vLayout)
        
class AdvancedPage(QWizardPage):
    def __init__(self, parent=None):
        super(AdvancedPage, self).__init__(parent)
        
        self.setPixmap(QWizard.BackgroundPixmap, QPixmap(Constants.APP_IMG_WIZARD_BKGRND))
        self.setPixmap(QWizard.WatermarkPixmap, QPixmap(Constants.APP_IMG_WIZARD_WATERMARK))
        self.setSubTitle(self.tr('Advanced Setup'))
        
        folderGroup = QGroupBox(self.tr('Select Location'))
        innerVLayout1 = QVBoxLayout()
        innerVLayout1.setObjectName('innerVLayout1')
        self.default_folder = os.path.split(DEFAULT_EX_NX_DRIVE_FOLDER)[0]
        self.rdLocationDefault = QRadioButton(self.tr('Install the %s folder in %s') % (Constants.PRODUCT_NAME, self.default_folder))
        self.rdLocationSelect = QRadioButton(self.tr('Choose your %s location') % Constants.PRODUCT_NAME)
        innerVLayout1.addWidget(self.rdLocationDefault)
        innerHLayout1 = QHBoxLayout()
        innerHLayout1.setObjectName('innerHLayout1')
        self.txtLocationSelect = QLineEdit()
        self.txtLocationSelect.setMinimumWidth(320)
        self.txtLocationSelect.setText(self.default_folder)
        self.btnLocationSelect = QPushButton(self.tr('Change...'))
        self.btnLocationSelect.setMinimumWidth(100)
        innerHLayout1.addWidget(self.txtLocationSelect)
        innerHLayout1.addStretch(1)
        innerHLayout1.addWidget(self.btnLocationSelect)
        innerVLayout1.addWidget(self.rdLocationSelect)
        innerVLayout1.addLayout(innerHLayout1)
        innerVLayout1.setAlignment(Qt.AlignLeft)
        folderGroup.setLayout(innerVLayout1)
        
        syncGroup = QGroupBox(self.tr('Select Folders to Sync'))
        innerVLayout2 = QVBoxLayout()
        innerVLayout2.setObjectName('innerVLayout2')
        self.rdSyncDefault = QRadioButton(self.tr('Use Current Workspace Selection (from %s site)') % Constants.PRODUCT_NAME)
        self.rdSyncSelect = QRadioButton(self.tr('Chose your folders to sync'))
        innerHLayout2 = QHBoxLayout()
        innerHLayout2.setObjectName('innerHLayout2')
        self.btnSyncSelect = QPushButton(self.tr('Select...'))
        self.btnSyncSelect.setMinimumWidth(100)
        innerHLayout2.addStretch(1)
        innerHLayout2.addWidget(self.btnSyncSelect)
        innerVLayout2.addWidget(self.rdSyncDefault)
        innerVLayout2.addWidget(self.rdSyncSelect)
        innerVLayout2.addLayout(innerHLayout2)
        innerVLayout2.setAlignment(Qt.AlignLeft)
        syncGroup.setLayout(innerVLayout2)
        
        self.lblMessage = QLabel()
        vLayout = QVBoxLayout()
        vLayout.setObjectName('vLayout')
        vLayout.addWidget(folderGroup)
        vLayout.addWidget(syncGroup)
        vLayout.addWidget(self.lblMessage)
        vLayout.addStretch(1)
        
        self.setStyleSheet('QGroupBox { font-weight: bold }')
        self.setStyleSheet('QRadioButton { font-size: 10px }')
        self.setLayout(vLayout)
        
        self.rdLocationSelect.toggled.connect(self.location_select_toggled)
        self.rdSyncSelect.toggled.connect(self.sync_select_toggled)
        self.btnLocationSelect.clicked.connect(self.location_change)
        self.btnSyncSelect.clicked.connect(self.sync_select)
        
        self.registerField('folder', self.txtLocationSelect)
        self.registerField('default_location', self.rdLocationDefault)
        self.registerField('default_sync', self.rdSyncDefault)
        
    def initializePage(self):
        self.rdLocationDefault.setChecked(True)
        self.btnLocationSelect.setEnabled(False)
        self.txtLocationSelect.setEnabled(False)
        self.rdSyncDefault.setChecked(True)
        self.btnSyncSelect.setEnabled(False)
        self.wizard().add_skip_tour(True)
        
    def validatePage(self):
        location = os.path.split(DEFAULT_EX_NX_DRIVE_FOLDER)[0]
        if not self.rdLocationDefault.isChecked():
            location = self.txtLocationSelect.text()
            
        folder = os.path.join(location, Constants.DEFAULT_NXDRIVE_FOLDER)
        if os.path.exists(folder) and not self.wizard().keep_location:
            msgbox = QMessageBox(QMessageBox.Warning, self.tr("Folder Exists"), 
                                                      self.tr("Folder %s already exists. Do you want to use it?" % folder))
            msgbox.setInformativeText(self.tr("Select Yes to keep this location or No to select a different one."))
            msgbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            ret = msgbox.exec_()
            # BUG?! when the default (radio button) location is selected, the MessageBox is ok.
            # When the select (radio button) location is selected, the MessageBox is missing the title and main text
            # (only the informative text is shown)!!

            if ret == QMessageBox.No:
                self.rdLocationSelect.setChecked(True)
                self.txtLocationSelect.setEnabled(True)
                self.txtLocationSelect.selectAll()
                return False
            else:
                self.wizard().keep_location = True
                self.wizard().local_folder = folder
        else:            
            if (not os.path.exists(location)):
                mbox = QMessageBox(QMessageBox.Warning, Constants.APP_NAME, self.tr("Folder %s does not exist.") % location)
                mbox.setInformativeText(self.tr("Do you want to create it?"))
                mbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)         
                if mbox.exec_() == QMessageBox.No:
                    self.txtLocationSelect.selectAll()
                    return False
                
            if not os.path.exists(folder):
                os.makedirs(folder)
                self.setCommitPage()
                if self.wizard().local_folder is not None:
                    os.unlink(self.wizard().local_folder)
                
            self.wizard().local_folder = folder
                          
        if self.wizard()._unbind_if_bound(folder):
            self.wizard()._bind(folder) 
       
        return True
    
    def cleanupPage(self):
        advanced = self.wizard().field('advanced')
        if not advanced:
            self.wizard().add_skip_tour(False)
        else:
            self.wizard().remove_skip_tour()
            
    def location_select_toggled(self, state):
        self.btnLocationSelect.setEnabled(state)
        self.txtLocationSelect.setEnabled(state)
        
    def sync_select_toggled(self, state):
        self.btnSyncSelect.setEnabled(state)
        
    def location_change(self):
        """enter or select a new location"""
        current_location = self.txtLocationSelect.text()
        if not current_location:
            current_location = self.default_folder
        selected_location = QFileDialog.getExistingDirectory(self, self.tr("Choose or create %s folder location") % Constants.PRODUCT_NAME,
                        current_location, QFileDialog.DontResolveSymlinks)
        if not selected_location:
            selected_location = self.default_folder
        self.txtLocationSelect.setText(selected_location)
    
    def sync_select(self):
        # this requires server binding
        if not self.validatePage():
            return
            
        app = QApplication.instance()
        process_filter = EventFilter(self)
        
        try:
            app.setOverrideCursor(Qt.WaitCursor)
            self.installEventFilter(process_filter)
            # retrieve folders
            self.wizard().controller.get_folders(frontend=self.wizard())
            self.wizard().controller.update_roots(frontend=self.wizard())
            app.restoreOverrideCursor()
            self.removeEventFilter(process_filter)
            
            dlg = SyncFoldersDlg(frontend=self.wizard())
            if dlg.exec_() == QDialog.Rejected:
                return
            
            # set the synchronized roots
            app.setOverrideCursor(Qt.WaitCursor)
            self.installEventFilter(process_filter)
            self.wizard().controller.set_roots(session=self.wizard().session)
            self.wizard().session.commit()
            self.setCommitPage(True)
            
        except Exception as e:
            msg = self.tr('Unable to update folders from %s (%s)') % (Constants.DEFAULT_CLOUDDESK_URL, e)
            self.lblMessage.setText(msg)
            self.lblMessage.setStyleSheet("QLabel { font-size: 10px; color: red }")

        finally:
            app.restoreOverrideCursor()
            self.removeEventFilter(process_filter)
            
class FinalPage(QWizardPage):
    def __init__(self, parent=None):
        super(FinalPage, self).__init__(parent)
        
        self.setPixmap(QWizard.BackgroundPixmap, QPixmap(Constants.APP_IMG_WIZARD_BKGRND))
        self.setPixmap(QWizard.WatermarkPixmap, QPixmap(Constants.APP_IMG_WIZARD_WATERMARK))
            
        self.setSubTitle(self.tr('Successfully Completed.'))
        self.lblDetail = QLabel(self.tr("<html><span style='font-size: 12px'>%s has finished installation and is ready to go.</span>"
                                        "<p><span style='font-size: 10px; font-weight: bold; color: lightseagreen'>Thanks for using it!</span></html>") % Constants.APP_NAME)
        self.lblDetail.setWordWrap(True)
        self.lblImg = QLabel()
        self.lblImg.setPixmap(QPixmap(Constants.APP_IMG_WIZARD_FINAL))
        self.rdLaunch = QCheckBox(self.tr("Launch %s") % Constants.APP_NAME)

        vLayout = QVBoxLayout()
        vLayout.addWidget(self.lblDetail)
        vLayout.addWidget(self.lblImg)
        vLayout.addWidget(self.rdLaunch)
        vLayout.addStretch(1)
        self.setLayout(vLayout)
        
        self.registerField('launch', self.rdLaunch)

    def initializePage(self):
        self.wizard().remove_skip_tour()
        self.setFinalPage(True)
        
    def cleanupPage(self):
        self.wizard().add_skip_tour(False)

        
def startWizard(controller, options):
    app = QApplicationSingleton()
    i = CpoWizard(controller, options)
    i.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(startWizard)