'''
Created on Dec 13, 2012

@author: mconstantin
'''

from PySide.QtGui import QDialog, QDialogButtonBox, QIcon

from nxdrive.gui.ui_proxy_authn import Ui_ProxyAuthnDialog
from nxdrive.utils import create_settings
from nxdrive.client.base_automation_client import ProxyInfo
from nxdrive import Constants
from nxdrive.gui.progress_dlg import ProgressDialog

settings = create_settings()

class ProxyAuthnDlg(QDialog, Ui_ProxyAuthnDialog):
    def __init__(self, frontend=None, parent=None):
        super(ProxyAuthnDlg, self).__init__(parent)
        self.setupUi(self)
        self.setWindowIcon(QIcon(Constants.APP_ICON_DIALOG))
        self.setWindowTitle(Constants.APP_NAME + self.tr(' Proxy Authentication'))
        self.frontend = frontend
        self.controller = frontend.controller

        applyBtn = self.buttonBox.button(QDialogButtonBox.Apply)
        applyBtn.clicked.connect(self.applyChanges)
        self.user = None
        self.pwd = None
        self.realm = None

        proxy = ProxyInfo.get_proxy()
        if proxy is None:
            self.txtUser.clear()
            self.txtPwd.clear()
#            self.txtRealm.clear()
        else:
            self.user = proxy.user
            self.pwd = proxy.pwd
            self.txtUser.setText(self.user)
            self.txtPwd.setText(self.pwd)
#            self.txtRealm.setText(self.realm)

    def applyChanges(self):
        invalidate = False
        user = self.txtUser.text()
        if user != self.user:
            self.user = user
            invalidate = True
        pwd = self.txtPwd.text()
        if pwd != self.pwd:
            self.pwd = pwd
            invalidate = True
#        realm = self.txtRealm.text()
#        if realm != self.realm:
#            self.realm = realm
#            invalidate = True
            
        if invalidate:
            result = ProgressDialog.stopServer(self.frontend, parent=self)
            if result == ProgressDialog.CANCELLED:
                return QDialog.Rejected   

            settings.setValue('preferences/proxyUser', self.user)
            settings.setValue('preferences/proxyPwd', self.pwd)
#            settings.setValue('preferences/proxyRealm', self.realm)
            settings.sync()
        else:
            result = ProgressDialog.OK_AND_NO_RESTART
                    
        self.done(QDialog.Accepted)
        return result
    
