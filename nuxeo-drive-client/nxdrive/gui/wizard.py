'''
Created on Jan 16, 2013

@author: mconstantin
'''

from __future__ import division
import sys
import os
import os.path
import subprocess
import urllib

from PySide.QtCore import Qt
from PySide.QtGui import QWizard, QWizardPage, QPixmap, QIcon, QPalette, QApplication
from PySide.QtGui import QLabel, QLineEdit, QGridLayout, QHBoxLayout, QVBoxLayout
from PySide.QtGui import QPushButton, QRadioButton, QCheckBox, QGroupBox, QFileDialog, QDialog, QMessageBox
# from PySide.QtWebKit import QWebView

from folders_dlg import SyncFoldersDlg
from proxy_dlg import ProxyDlg
from nxdrive.model import SyncFolders
from nxdrive.client import ProxyInfo
from nxdrive.utils import QApplicationSingleton, EventFilter
from nxdrive.utils import Communicator
from nxdrive.utils import win32utils
from nxdrive.utils import create_settings
from nxdrive.utils import find_exe_path
from nxdrive.gui.menubar import DEFAULT_EX_NX_DRIVE_FOLDER
from nxdrive import Constants
from nxdrive.logging_config import get_logger
import nxdrive.gui.qrc_resources

if sys.platform == 'win32':
    from nxdrive.protocol_handler import win32

log = get_logger(__name__)

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
        self.controller.synchronizer.register_frontend(self)
        self.session = self.controller.get_session()
        self.communicator = Communicator.getCommunicator()
        # get the server binding for authenticated user and server
        self.local_folder = self.get_local_folder()
        self.server_binding = self.controller.get_server_binding(self.local_folder)  
        self.keep_location = self.server_binding is not None
        self.options = options
        self.skip = False
        
        self.addPage(IntroPage())  # 0
        self.addPage(InstallOptionsPage())  # 1
        self.addPage(GuideOnePage())  # 2
        self.addPage(GuideTwoPage())  # 3
        self.addPage(GuideThreePage())  # 4
        self.addPage(FinalPage())  # 5
        self.addPage(AdvancedPage())  # 6

        self.setWindowIcon(QIcon(Constants.APP_ICON_DIALOG))
        self.setFixedSize(700, 500)
        self.setWindowTitle(self.tr('%s Setup') % Constants.APP_NAME)
        if sys.platform == 'darwin':
            self.setPixmap(QWizard.BackgroundPixmap, QPixmap(Constants.APP_IMG_WIZARD_BKGRND))
            self.setWizardStyle(QWizard.MacStyle)
        elif sys.platform == 'win32':
#            self.setPixmap(QWizard.LogoPixmap, QPixmap(Constants.APP_IMG_WIZARD_BANNER))
            self.setPixmap(QWizard.WatermarkPixmap, QPixmap(Constants.APP_IMG_WIZARD_WATERMARK))
            self.setWizardStyle(QWizard.ModernStyle)

    def add_skip_tour(self, back=True):
        self.setButtonText(QWizard.CustomButton1, self.tr('&Skip Tour'))
        self.setOption(QWizard.HaveCustomButton1 , True)
        self.customButtonClicked.connect(self.custom_button_click)

        btnList = [QWizard.Stretch, 
                   QWizard.CustomButton2, 
                   QWizard.CustomButton1, 
                   QWizard.CommitButton, 
                   QWizard.NextButton, 
                   QWizard.FinishButton,
                  ]
        if back:
            btnList.insert(3, QWizard.BackButton)
        self.setButtonLayout(btnList)

    def remove_skip_tour(self, back=True):
        # NOTE: this cause a Python exception
#        self.setOption(QWizard.CustomButton1, False)
        btn = self.button(QWizard.CustomButton1)
        if btn.text():
            self.customButtonClicked.disconnect(self.custom_button_click)

        self.setOption(QWizard.HaveCustomButton1 , False)
        btnList = [QWizard.Stretch, 
                   QWizard.CustomButton2, 
                   QWizard.CommitButton, 
                   QWizard.NextButton, 
                   QWizard.FinishButton
                   ]
        if back:
            btnList.insert(2, QWizard.BackButton)
        self.setButtonLayout(btnList)

    def add_exit(self):
        self.setButtonText(QWizard.CustomButton2, self.tr('E&xit'))
        self.setOption(QWizard.HaveCustomButton2, True)
        self.customButtonClicked.connect(self.custom_button_click)
        
        btnList = [QWizard.Stretch, 
                   QWizard.CustomButton2, 
                   QWizard.CustomButton1, 
                   QWizard.CommitButton, 
                   QWizard.NextButton, 
                   QWizard.FinishButton,
                  ]
        self.setButtonLayout(btnList)
        
    def remove_back_button(self):
        btnList = [QWizard.Stretch, QWizard.CommitButton, QWizard.NextButton, QWizard.FinishButton]
        self.setButtonLayout(btnList)
        
    def custom_button_click(self, custom_button):
        if custom_button == QWizard.CustomButton1:
            self.skip_tour(custom_button)
        elif custom_button == QWizard.CustomButton2:
            self.reject()
        
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
            self.server_binding = None
            return True
        else:
            return False

    def _bind(self, url, folder):
        self._unbind_if_bound(folder)
        username = self.field('username')
        pwd = self.field('pwd')
        self.server_binding = self.controller.bind_server(folder, url, username, pwd)
        
    def get_local_folder(self):
        # get the connected binding, if any
        server_binding = self.controller.get_server_binding(raise_if_missing=False)
        if server_binding is None:
            bindings = self.controller.list_server_bindings()
            if len(bindings) == 1:
                server_binding = bindings[0]
        if server_binding:
            local_folder = server_binding.local_folder 
        else:
            local_folder = DEFAULT_EX_NX_DRIVE_FOLDER

        return local_folder

    def notify_local_folders(self, local_folders):
        pass

    def accept(self):
        if self.local_folder is not None and not os.path.exists(self.local_folder):
            os.makedirs(self.local_folder)

        self.session.commit()

        if sys.platform == 'win32':
            # create the Favorites shortcut
            shortcut = os.path.join(os.path.expanduser('~'), 'Links', Constants.PRODUCT_NAME + '.lnk')
            win32utils.create_or_replace_shortcut(shortcut, self.local_folder)

        settings = create_settings()
        settings.setValue('preferences/notifications', True)
        settings.setValue('preferences/icon-overlays', True)
        settings.setValue('preferences/autostart', True)
        settings.setValue('preferences/log', True)
        # change wizard mode to false (start as app)
        settings.setValue('wizard', False)
        # save settings now
        settings.sync()
        launch = self.field('launch')
        if launch:
            exe_path = find_exe_path()
            script, ext = os.path.splitext(exe_path)
            params = ['gui', '--start']
            if ext == '.py':
                python = sys.executable
                subprocess.Popen([python, exe_path] + params)
                log.debug('launching %s %s %s', python, exe_path, ' '.join(params))
            else:
                subprocess.Popen([exe_path] + params)
                log.debug('launching %s %s', exe_path, ' '.join(params))

        return super(CpoWizard, self).accept()

    def reject(self):
        self.session.rollback()
        # FEATURE REMOVED - prompt user for wizard mode
#        msgbox = QMessageBox(QMessageBox.Question, Constants.PRODUCT_NAME,
#                                                  self.tr('Do you want to start next time in wizard mode?'))
#        msgbox.setInformativeText(self.tr("Select Yes to start in wizard mode or No to start the normal application, when launched next time."))
#        msgbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
#        ret = msgbox.exec_()
#        if ret == QMessageBox.No:
#            settings = create_settings()
#            settings.setValue('wizard', False)
        settings = create_settings()
        settings.setValue('wizard', False)
        return super(CpoWizard, self).reject()


class IntroPage(QWizardPage):
    def __init__(self, parent=None):
        super(IntroPage, self).__init__(parent)
        self.auth_ok = False

        self.setWindowTitle('%s Setup' % Constants.APP_NAME)
        welcome = self.tr('Welcome to %s') % Constants.APP_NAME
#        greeting = """{\rtf1\ansi\ansicpg1252\cocoartf1187\cocoasubrtf340
#                    {\fonttbl\f0\fswiss\fcharset0 Helvetica;}
#                    {\colortbl;\red255\green255\blue255;\red221\green32\blue103;}
#                    \margl1440\margr1440\vieww10800\viewh8400\viewkind0
#                    \pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural
#                    \f0\fs36 \cf0 %s \cf2 %s\cf0  %s}""" % (welcome, Constants.PRODUCT_NAME, self.tr('Desktop'))
#        self.setTitle(self.tr("<html><style font-size:14px; font-weight:bold>Welcome to %s</style></html>") % Constants.APP_NAME)

        self.setTitle(welcome)
        # force logo display on win32
#        self.setSubTitle(' ')
        self.lblInstr = QLabel(self.tr('Please sign in to %s') % Constants.PRODUCT_NAME)
        self.lblInstr.setToolTip(Constants.CLOUDDESK_URL)
        # BEGIN remove site url
#        self.lblUrl = QLabel("<html><a href='%s'>%s</a></html>" % (Constants.CLOUDDESK_URL, Constants.CLOUDDESK_URL))
#        self.lblUrl.setStyleSheet("QLabel { font-size: 10px }")
#        self.lblUrl.setTextInteractionFlags(Qt.TextBrowserInteraction)
#        self.lblUrl.setOpenExternalLinks(True)
        # END remove site url
        self.lblUsername = QLabel(self.tr('Username'))
        self.lblPwd = QLabel(self.tr('Password'))
        self.txtUsername = QLineEdit()
        self.lblUsername.setBuddy(self.txtUsername)
        self.txtPwd = QLineEdit()
        self.lblPwd.setBuddy(self.txtPwd)
        self.txtPwd.setEchoMode(QLineEdit.Password)
        self.txtPwd.textEdited.connect(self.password_text_changed)
        self.password_has_changed = False
        self.lblMessage = QLabel()
        self.lblMessage.setObjectName('message')
        self.lblMessage.setWordWrap(True)
        self.lblMessage.setStyleSheet("QLabel { font-size: 12px }")
        self.lblMessage.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.lblMessage.setOpenExternalLinks(True)
        self.lblMessage.setVisible(False)
        self.btnProxy = QPushButton(self.tr('Proxy...'))
        self.btnProxy.setVisible(False)

        grid = QGridLayout()
        grid.addWidget(self.lblInstr, 0, 0, 1, 2)
        # BEGIN remove site url
#        grid.addWidget(self.lblUrl, 1, 0, 1, 2)
#        grid.addWidget(self.lblUsername, 2, 0, Qt.AlignRight)
#        grid.addWidget(self.txtUsername, 2, 1)
#        grid.addWidget(self.lblPwd, 3, 0, Qt.AlignRight)
#        grid.addWidget(self.txtPwd, 3, 1)
#        hlayout2 = QHBoxLayout()
#        hlayout2.addWidget(self.lblMessage)
# #        hlayout2.addStretch(1)
#        hlayout2.addWidget(self.btnProxy)
#        hlayout2.setStretch(0, 4)
#        hlayout2.setStretch(1, 1)
#        grid.addLayout(hlayout2, 4, 0, 1, 2, Qt.AlignLeft)
        # END remove site url
        grid.addWidget(self.lblUsername, 1, 0, Qt.AlignRight)
        grid.addWidget(self.txtUsername, 1, 1)
        grid.addWidget(self.lblPwd, 2, 0, Qt.AlignRight)
        grid.addWidget(self.txtPwd, 2, 1)
        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(self.lblMessage)
        hlayout2.addWidget(self.btnProxy)
        hlayout2.setStretch(0, 1)
        grid.addLayout(hlayout2, 3, 0, 1, 2, Qt.AlignLeft)
        self.setLayout(grid)

        self.registerField('username*', self.txtUsername)
        self.registerField('pwd*', self.txtPwd)

    def password_text_changed(self, text):
        if not self.password_has_changed:
            self.password_has_changed = True
            self.auth_ok = False
            self.lblMessage.clear()
        
    def initializePage(self):
#        self.wizard().setTitleFormat(Qt.RichText)
        # clear previous proxy setting
        settings = create_settings()
        settings.setValue('preferences/useProxy', ProxyInfo.PROXY_DIRECT)
        settings.setValue('preferences/proxyUser', '')
        settings.setValue('preferences/proxyPwd', '')
        settings.setValue('preferences/proxyRealm', '')
        settings.setValue('preferences/proxyAuthN', False)
        self.btnProxy.clicked.connect(self.showProxy)

        server_binding = self.wizard().server_binding
        user = server_binding.remote_user if server_binding else Constants.ACCOUNT
        pwd = server_binding.get_remote_password() if server_binding else None
        self.txtUsername.setText(user)
        self.txtPwd.setText(pwd)
        self.txtUsername.setReadOnly(server_binding is not None)
        self.wizard().keep_location = server_binding is not None
        if server_binding \
           and not server_binding.has_invalid_credentials() \
           and not self.password_has_changed:
            self.lblMessage.setText(self.tr("User %s is already signed in.") % user)
            self.lblMessage.setVisible(True)
            self.auth_ok = True

    def login(self):
        if self.auth_ok:
            self.lblMessage.clear()
            self.completeChanged.emit()
            return self.auth_ok

        from nxdrive.client import Unauthorized, DeviceQuotaExceeded
        app = QApplication.instance()
        process_filter = EventFilter(self)

        try:
            app.setOverrideCursor(Qt.WaitCursor)
            self.installEventFilter(process_filter)
            self.auth_ok = False
            url = Constants.CLOUDDESK_URL
            username = self.txtUsername.text()
            password = self.txtPwd.text()
#            self.wizard().controller.validate_credentials(url, username, password)
            self.wizard().local_folder = local_folder = self.wizard().get_local_folder()
            # create the default server binding
            self.wizard()._bind(url, local_folder)
            
            app.restoreOverrideCursor()
            self.removeEventFilter(process_filter)
            msg = self.tr("Connected")
            self.lblMessage.setStyleSheet("QLabel { font-size: 12px; color: green }")
            self.auth_ok = True
            self.btnProxy.setVisible(False)
            self.completeChanged.emit()
        except Unauthorized:
            msg = self.tr('Invalid credentials.')
            self.lblMessage.setStyleSheet("QLabel { font-size: 12px; color: red }")
        except DeviceQuotaExceeded as e:
            controller = self.wizard().controller
            client = controller.remote_doc_client_factory(url, username, controller.device_id, password)
            mydocs = client.get_mydocs()
            p1 = e.href
            if p1[-1] != '/': p1 += '/'
            p2 = 'nxpath/default'
            p3 = mydocs['path']
            if p3[-1] != '/': p3 += '/'
            p4 = e.return_url
            if p4[-1] != '&': p4 += '&'
            query_params = {
                            'user_name': username,
                            'user_password': password,
                            'language': 'en_US',
                            'requestedUrl': '',
                            'form_submitted_marker': '',
                            'Submit': 'Log in'
                            }
            url = p1 + p2 + p3 + p4 + urllib.urlencode(query_params)
            self.lblMessage.setStyleSheet("QLabel { font-size: 12px; color: red }")
            msg = e.message % (e.max_devices, url)
        except RuntimeError as e:
            msg = str(e)
        except Exception as e:
            self.wizard().controller.invalidate_client_cache(Constants.CLOUDDESK_URL)
            self.wizard().controller.reset_proxy()
            # retry with proxy set to auto-detect
            settings = create_settings()
            useProxy = settings.value('preferences/useProxy', ProxyInfo.PROXY_DIRECT)
            if useProxy == ProxyInfo.PROXY_DIRECT:
                settings.setValue('preferences/useProxy', ProxyInfo.PROXY_AUTODETECT)
                self.login()
                return
            elif useProxy == ProxyInfo.PROXY_AUTODETECT:
                settings.setValue('preferences/useProxy', ProxyInfo.PROXY_SERVER)
                msg = self.tr("Unable to connect to %s. If a proxy server is required, please configure it here by selecting the Proxy... button") % \
                        Constants.CLOUDDESK_URL

                self.lblMessage.setStyleSheet("QLabel { font-size: 12px; color: gray }")
                self.btnProxy.setVisible(True)
            else:
                if str(e):
                    detail = ' (%s)' % str(e)
                else:
                    detail = ''
                msg = self.tr('Unable to connect to %s%s') % (Constants.CLOUDDESK_URL, detail)
                self.lblMessage.setStyleSheet("QLabel { font-size: 12px; color: red }")
        finally:
            app.restoreOverrideCursor()
            self.removeEventFilter(process_filter)

        self.lblMessage.setText(msg)
        self.lblMessage.setVisible(True)
        return self.auth_ok

    def showProxy(self):
        dlg = ProxyDlg(frontend=self.wizard())
        self.result = dlg.exec_()

    # use mandatory fields instead
#    def isComplete(self):
#        return bool(self.txtUsername.text()) and bool(self.txtPwd.text())

    def validatePage(self):
        self.password_has_changed = False
        self.lblMessage.clear()
        result = self.login()
        if result:
            self.setCommitPage(True)
        return result      
        

class InstallOptionsPage(QWizardPage):
    def __init__(self, parent=None):
        super(InstallOptionsPage, self).__init__(parent)
#        self.typical = True

        self.setTitle(self.tr('Choose Setup Type'))
        # force logo display on win32
#        self.setSubTitle(' ')
        # Typical option
        self.rdButtonTypical = QRadioButton(self)
#        self.lblImgTypical = QLabel()
#        self.lblImgTypical.setPixmap(QPixmap(Constants.APP_ICON_WIZARD_RB))
        self.lblTypical = QLabel(self.tr('Typical'))
        self.lblTypical2 = QLabel(self.tr('(recommended)'))
        self.lblTypical2.setStyleSheet('QLabel { font-size: 12px; color: gray }')
        self.lblTypical.setStyleSheet('QLabel { font-weight: bold }')
        self.lblTypicalDetail = QLabel(self.tr('Automatically setup %s with default settings.') % Constants.APP_NAME)
        self.lblTypicalDetail.setMinimumWidth(450)
        self.lblTypicalDetail.setStyleSheet('QLabel { font-size: 12px }')
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
#        innerHLayout1.addWidget(self.lblImgTypical)
        innerHLayout1.addLayout(innerVLayout1)
        innerHLayout1.addStretch(10)
        # Advanced option
        self.rdButtonAdvanced = QRadioButton(self)
#        self.lblImgAdvanced = QLabel()
#        self.lblImgAdvanced.setPixmap(QPixmap(Constants.APP_ICON_WIZARD_RB))
        self.lblAdvanced = QLabel(self.tr('Advanced'))
        self.lblAdvanced.setStyleSheet('QLabel { font-weight: bold }')
        self.lblAdvancedDetail = QLabel(self.tr('Customize your %s setup, including %s folder location and which folders to synch.') % 
                                        (Constants.PRODUCT_NAME, Constants.APP_NAME))
        self.lblAdvancedDetail.setStyleSheet('QLabel { font-size: 12px }')
        self.lblAdvancedDetail.setMinimumWidth(450)
        self.lblAdvancedDetail.setWordWrap(True)
        innerVLayout2 = QVBoxLayout()
        innerVLayout2.addWidget(self.lblAdvanced)
        innerVLayout2.addWidget(self.lblAdvancedDetail)
        innerHLayout2 = QHBoxLayout()
        innerHLayout2.addWidget(self.rdButtonAdvanced)
#        innerHLayout2.addWidget(self.lblImgAdvanced)
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
        self.wizard().add_skip_tour(back=False)
        self.wizard().add_exit()

        app = QApplication.instance()
        process_filter = EventFilter(self)
        # Note retrieve folders hierarchy and the sync roots
        try:
            app.setOverrideCursor(Qt.WaitCursor)
            self.installEventFilter(process_filter)
            # get the server binding for authenticated user and server
            server_binding = self.wizard().server_binding
            # retrieve folders for typical setup
            synchronizer = self.wizard().controller.synchronizer
            synchronizer.get_folders(server_binding, update_roots=True, 
                 completion_notifiers={'notify_folders_retrieved': synchronizer,
                                       'notify_folders_retrieved': self})      
            
            app.restoreOverrideCursor()
            self.removeEventFilter(process_filter)
        except Exception as e:
            log.debug('Failed to get folders: %s', e)
        finally:
            app.restoreOverrideCursor()
            self.removeEventFilter(process_filter)

    # NOT USED
    def notify_folders_retrieved(self, local_folder, update):
        self.wizard().communicator.folders.emit(local_folder, update)
                
    def validatePage(self):
        if not self.rdButtonAdvanced.isChecked():
            # 'typical' route
            folder = self.wizard().local_folder

            if os.path.exists(folder) and os.listdir(folder) and not self.wizard().keep_location:
                msgbox = QMessageBox(QMessageBox.Warning, self.tr("Folder Exists"),
                                                          self.tr("Folder %s already exists. Do you want to use it?") % folder)
                msgbox.setInformativeText(self.tr("Select <b>Yes</b> to keep this location or <b>No</b> to select a different one on the Advanced page.\n"
                                                  "Note that if this folder was used by a different user, some files/folders may not be synchronized correctly."))
                msgbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                ret = msgbox.exec_()
                if ret == QMessageBox.No:
                    self.rdButtonAdvanced.setChecked(True)
                    return False

            self.wizard().keep_location = True
            if (not os.path.exists(folder)):
                os.makedirs(folder)

            # if no root binding  exists, bind everything
#            session = self.wizard().session
#            count = session.query(SyncFolders).\
#                   filter(SyncFolders.bind_state == True).count()
#            if count == 0:
#                # check top-level folders as sync roots
#                self.wizard().controller.synchronizer.check_toplevel_folders(session=session)
#
#                # set the synchronized roots
#                app = QApplication.instance()
#                process_filter = EventFilter(self)
#                app.setOverrideCursor(Qt.WaitCursor)
#                self.installEventFilter(process_filter)
#                try:
#                    self.wizard().controller.synchronizer.set_roots()
#                except Exception as e:
#                    username = self.field('username')
#                    log.error(self.tr("Unable to set roots on '%s' for user '%s' (%s)"),
#                                        Constants.CLOUDDESK_URL, username, str(e))
#                finally:
#                    app.restoreOverrideCursor()
#                    self.removeEventFilter(process_filter)

        return True

    def change_option(self, state):
        if state:
            self.wizard().remove_skip_tour(back=False)
        else:
            self.wizard().add_skip_tour(back=False)

class GuideOnePage(QWizardPage):
    def __init__(self, parent=None):
        super(GuideOnePage, self).__init__(parent)
        
        # force logo display on win32
        # Note: title must be initialized with the page since it displays user's name
#        self.setSubTitle(' ')

        click_type = 'right ' if sys.platform == 'win32' else ''    
        from nxdrive.gui.resources import find_icon
        icon1_path = find_icon(Constants.ICON_APP_ENABLED)
        data_uri1 = open(icon1_path, "rb").read().encode("base64").replace("\n", "")
        img_tag1 = '<img alt="sample" src="data:image/png;base64,{0}">'.format(data_uri1)
        self.lblDetail = QLabel(self.tr("<html>The <b>{0}</b> folder on your desktop is a special folder, whose content is synchronized with your "
                                        "on-line {0} content.<br/>"
                                        "Simply add folders or save files here, and they will be synched with your {0} service. <b>You have full control over which folders are synched.</b><br/>"
                                        "To select which folders to synch, simply {1}click {2}, and select <b>Preferences...</b>, then select the <b>Advanced</b> tab.<br/>"
                                        "The {0} folder has two main subfolders, <b>My Docs</b> and <b>Others Docs</b>, allowing you to quickly identify folder trees you've created versus those "
                                        "shared with you by others. This mirrors the {0} website structure.").format(Constants.PRODUCT_NAME, click_type, img_tag1))

        self.lblDetail.setWordWrap(True)
        self.lblDetail.setStyleSheet('QLabel { font-size: 12px }')
        self.lblImg = QLabel()
        self.lblImg.setPixmap(QPixmap(Constants.APP_IMG_WIZARD_FINDER_FOLDERS))
        vLayout = QVBoxLayout()
        vLayout.addWidget(self.lblDetail)
        vLayout.addWidget(self.lblImg)
        self.setLayout(vLayout)

    def initializePage(self):
        username = self.field('username')
        self.setTitle(self.tr('Welcome to %s, %s!') % (Constants.APP_NAME, username))
        # this i sadd the Back button
        self.wizard().add_skip_tour()
        
    def cleanupPage(self):
        advanced = self.wizard().field('advanced')
        self.wizard().add_exit()
        if not advanced:
            self.wizard().add_skip_tour(back=False)
        else:
            self.wizard().remove_skip_tour(back=False)

class GuideTwoPage(QWizardPage):
    def __init__(self, parent=None):
        super(GuideTwoPage, self).__init__(parent)

        self.setTitle(self.tr('Access your files from everywhere using %s!') % Constants.PRODUCT_NAME)
        # force logo display on win32
#        self.setSubTitle(' ')
        click_type = 'right ' if sys.platform == 'win32' else ''
        from nxdrive.gui.resources import find_icon
        icon1_path = find_icon(Constants.ICON_APP_ENABLED)
        data_uri1 = open(icon1_path, "rb").read().encode("base64").replace("\n", "")
        img_tag1 = '<img alt="sample" src="data:image/png;base64,{0}">'.format(data_uri1)
        
        self.lblDetail = QLabel(self.tr("<html>To launch the {0} website, {1}click {2}, select <b>Open {0} <u>Website</u></b>.<br/>"
                                        "To view your synced files, select <b>Open {0} <u>Folder</u></b>.<br/>"
                                        "You can also access your files from any computer at any time by logging into the {0} website "
                                        "at <a href='http://{3}'>{3}</a>.<br/>"
                                        "Once signed-in, you have full access to share, view, save, and more...all from your web browser.<br/>"
                                        "Remember to download the free {0} Mobile app from the Apple Store and/or Google Play!</html>").\
                                format(Constants.PRODUCT_NAME, click_type, img_tag1, 'www.SharpCloudPortal.com'))
                                
        self.lblDetail.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.lblDetail.setOpenExternalLinks(True)
        self.lblDetail.setWordWrap(True)
        self.lblDetail.setStyleSheet('QLabel { font-size: 12px }')
        self.lblImg = QLabel()
        self.lblImg.setPixmap(QPixmap(Constants.APP_IMG_WIZARD_ACCESS_FILES))
        vLayout = QVBoxLayout()
        vLayout.addWidget(self.lblDetail)
        vLayout.addWidget(self.lblImg)
        self.setLayout(vLayout)

class GuideThreePage(QWizardPage):
    def __init__(self, parent=None):
        super(GuideThreePage, self).__init__(parent)

        self.setTitle(self.tr('The %s Notification Icon') % Constants.APP_NAME)
        # force logo display on win32
#        self.setSubTitle(' ')
        from nxdrive.gui.resources import find_icon
        icon1_path = find_icon(Constants.ICON_APP_ENABLED)
        data_uri1 = open(icon1_path, "rb").read().encode("base64").replace("\n", "")
        img_tag1 = '<img alt="sample" src="data:image/png;base64,{0}">'.format(data_uri1)
        icon2_path = find_icon(Constants.ICON_APP_DISABLED)
        data_uri2 = open(icon2_path, "rb").read().encode("base64").replace("\n", "")
        img_tag2 = '<img alt="sample" src="data:image/png;base64,{0}">'.format(data_uri2)
        click_type = 'right ' if sys.platform == 'win32' else ''
        sys_bar = 'PC System Tray' if sys.platform == 'win32' else 'Mac Menu Bar'
        self.lblDetail = QLabel(self.tr("<html><body style='font-size:12px'>Your {0} will display {1} icon for convenient access."
                                        "<br>{2} means you are signed in and connected.<br/>"
                                        "Note: an animated icon indicates synchronization is in progress."
                                        "<br>{3} shows you are offline.<br/>"
                                        "To connect, <b>{4}click</b> {2} and select <b>Preferences...</b>. Select <b>Account</b> tab and enter your credentials. "
                                        "You will be automatically logged in from now on.</body></html>").\
                             format(sys_bar, Constants.PRODUCT_NAME, img_tag1, img_tag2, click_type))
                                
        self.lblDetail.setWordWrap(True)
        self.lblDetail.setStyleSheet('QLabel { font-size: 12px }')
        
        self.lblImg = QLabel()
        self.lblImg.setPixmap(QPixmap(Constants.APP_IMG_WIZARD_APPBAR))

        vLayout = QVBoxLayout()
        vLayout.addWidget(self.lblDetail)
        vLayout.addWidget(self.lblImg)
        self.setLayout(vLayout)

class AdvancedPage(QWizardPage):
    def __init__(self, parent=None):
        super(AdvancedPage, self).__init__(parent)

        self.setTitle(self.tr('Advanced Setup'))
        # force logo display on win32
#        self.setSubTitle(' ')
        # Cannot change the stylesheet for the QGroupBox (or QGroupBox::title)
#        self.folderGroup = QGroupBox(self.tr('Select Location'))
        self.folderGroup = QGroupBox()
        # use a label instead
        self.lblFolderGroup = QLabel(self.tr('Select Location'))
        innerVLayout1 = QVBoxLayout()
        innerVLayout1.setObjectName('innerVLayout1')
        # fake label for default radiobutton
        self.rdLocationDefault = QRadioButton(self.tr('Install the %s folder in this location') % Constants.PRODUCT_NAME)
        self.rdLocationSelect = QRadioButton(self.tr('Choose your %s location') % Constants.PRODUCT_NAME)
        innerVLayout1.addWidget(self.rdLocationDefault)
        innerHLayout1 = QHBoxLayout()
        innerHLayout1.setObjectName('innerHLayout1')
        self.txtLocationSelect = QLineEdit()
        self.txtLocationSelect.setMinimumWidth(320)
        self.btnLocationSelect = QPushButton(self.tr('Change...'))
        self.btnLocationSelect.setMinimumWidth(100)
        innerHLayout1.addWidget(self.txtLocationSelect)
        innerHLayout1.addStretch(1)
        innerHLayout1.addWidget(self.btnLocationSelect)
        innerVLayout1.addWidget(self.rdLocationSelect)
        innerVLayout1.addLayout(innerHLayout1)
        innerVLayout1.setAlignment(Qt.AlignLeft)
        self.folderGroup.setLayout(innerVLayout1)
        # Cannot change the stylesheet for the QGroupBox (or QGroupBox::title)
#        self.syncGroup = QGroupBox(self.tr('Select Folders to Sync'))
        self.syncGroup = QGroupBox()
        # use a label instead
        self.lblSyncGroup = QLabel(self.tr('Select Folders to Sync'))
        innerVLayout2 = QVBoxLayout()
        innerVLayout2.setObjectName('innerVLayout2')
        self.rdSyncDefault = QRadioButton(self.tr('All folders'))
        self.rdSyncSelect = QRadioButton(self.tr('Choose folders to sync'))
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
        self.syncGroup.setLayout(innerVLayout2)

        self.lblMessage = QLabel()
        vLayout = QVBoxLayout()
        vLayout.setObjectName('vLayout')
        vLayout.addWidget(self.lblFolderGroup)
        vLayout.addWidget(self.folderGroup)
        vLayout.addWidget(self.lblSyncGroup)
        vLayout.addWidget(self.syncGroup)
        vLayout.addWidget(self.lblMessage)
        vLayout.addStretch(1)
        # Cannot change the stylesheet for the QGroupBox (or QGroupBox::title)
        self.setStyleSheet('QGroupBox { font-weight: bold; font-size: 12px }')
        self.setStyleSheet('QRadioButton { font-size: 12px }')
        self.setLayout(vLayout)

        self.rdLocationSelect.toggled.connect(self.location_select_toggled)
        self.rdSyncSelect.toggled.connect(self.sync_select_toggled)
        self.btnLocationSelect.clicked.connect(self.location_change)
        self.btnSyncSelect.clicked.connect(self.sync_select)

        self.registerField('folder', self.txtLocationSelect)
        self.registerField('default_location', self.rdLocationDefault)
        self.registerField('default_sync', self.rdSyncDefault)

    def initializePage(self):
        local_folder = self.wizard().local_folder
        self.default_folder = os.path.split(local_folder)[0]
        self.rdLocationDefault.setText(self.tr('Install the %s folder in %s') % (Constants.PRODUCT_NAME, self.default_folder))
        self.rdLocationDefault.setChecked(True)
        self.btnLocationSelect.setEnabled(False)
        self.txtLocationSelect.setText(self.default_folder)
        self.txtLocationSelect.setEnabled(False)
        self.rdSyncDefault.setChecked(True)
        self.btnSyncSelect.setEnabled(False)
        self.wizard().add_skip_tour()

    def validatePage(self):
        local_folder = self.wizard().local_folder
        location = os.path.split(local_folder)[0]
        if not self.rdLocationDefault.isChecked():
            location = self.txtLocationSelect.text()

        local_folder = os.path.join(location, Constants.DEFAULT_NXDRIVE_FOLDER)
        url = Constants.CLOUDDESK_URL
        if os.path.exists(local_folder) and os.listdir(local_folder) and not self.wizard().keep_location:
            msgbox = QMessageBox(QMessageBox.Warning, self.tr("Folder Exists"),
                                                      self.tr("Folder %s already exists. Do you want to use it?") % local_folder)
            msgbox.setInformativeText(self.tr("Select <b>Yes</b> to keep this location or <b>No</b> to select a different one.\n"
                                              "Note that if this folder was used by a different user, some files/folders may not be synchronized correctly."))
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
                self.wizard().local_folder = local_folder
        else:
            if (not os.path.exists(location)):
                mbox = QMessageBox(QMessageBox.Warning, Constants.APP_NAME, self.tr("Folder %s does not exist.") % location)
                mbox.setInformativeText(self.tr("Do you want to create it?"))
                mbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                if mbox.exec_() == QMessageBox.No:
                    self.txtLocationSelect.selectAll()
                    return False

            if not os.path.exists(local_folder):
                os.makedirs(local_folder)
                self.setCommitPage()
                if self.wizard().local_folder is not None:
                    os.unlink(self.wizard().local_folder)

            self.wizard().local_folder = local_folder

        self.wizard()._bind(url, local_folder)
        return True

    def cleanupPage(self):
        advanced = self.wizard().field('advanced')
        self.wizard().add_exit()
        if not advanced:
            self.wizard().add_skip_tour()
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
        if current_location != selected_location:
            self.wizard().keep_location = False
        self.txtLocationSelect.setText(selected_location)

    def sync_select(self):
        # this requires server binding
        if not self.validatePage():
            return

        app = QApplication.instance()
        process_filter = EventFilter(self)

        try:
            dlg = SyncFoldersDlg(frontend=self.wizard())
            if dlg.exec_() == QDialog.Rejected:
                return

            # set the synchronized roots
            app.setOverrideCursor(Qt.WaitCursor)
            self.installEventFilter(process_filter)
            self.wizard().controller.synchronizer.set_roots(session=self.wizard().session)
            self.wizard().session.commit()
            self.setCommitPage(True)

        except Exception as e:
            msg = self.tr('Unable to update folders from %s (%s)') % (Constants.CLOUDDESK_URL, e)
            self.lblMessage.setText(msg)
            self.lblMessage.setStyleSheet("QLabel { font-size: 12px; color: red }")

        finally:
            app.restoreOverrideCursor()
            self.removeEventFilter(process_filter)

class FinalPage(QWizardPage):
    def __init__(self, parent=None):
        super(FinalPage, self).__init__(parent)

        self.setTitle(self.tr('Successfully Completed.'))
        self.setSubTitle(self.tr('Thanks for using it!'))
        self.lblDetail = QLabel(self.tr("<span style='font-size: 12px'>%s has finished installation and is ready to go.</span>") % 
                                Constants.APP_NAME)
        self.lblDetail.setWordWrap(True)
        # Remove image on last page (#2073)
#        self.lblImg = QLabel()
#        self.lblImg.setPixmap(QPixmap(Constants.APP_IMG_WIZARD_FINAL))
        self.rdLaunch = QCheckBox(self.tr("Launch %s") % Constants.APP_NAME)
        self.rdLaunch.setCheckState(Qt.Checked)

        vLayout = QVBoxLayout()
        vLayout.addWidget(self.lblDetail)
        # Remove image on last page (#2073)
#        vLayout.addWidget(self.lblImg)
        vLayout.addWidget(self.rdLaunch)
        vLayout.addStretch(1)
        self.setLayout(vLayout)

        self.registerField('launch', self.rdLaunch)

    def initializePage(self):
        self.wizard().remove_skip_tour()
        self.setFinalPage(True)

    def cleanupPage(self):
        self.wizard().add_skip_tour()


def startWizard(controller, options):
    app = QApplicationSingleton(Constants.APP_ID)
    if app.isRunning(): sys.exit(0)
    
    i = CpoWizard(controller, options)
    i.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(startWizard)
