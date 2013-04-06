'''
Created on Dec 13, 2012

@author: mconstantin
'''

import socket
from PySide.QtGui import QDialog, QDialogButtonBox, QMessageBox, QIcon

from nxdrive.gui.ui_proxy import Ui_ProxyDialog
from nxdrive.logging_config import get_logger
from nxdrive.utils import create_settings
from nxdrive.client.base_automation_client import ProxyInfo
from nxdrive import Constants
from nxdrive.gui.progress_dlg import ProgressDialog

settings = create_settings()
PORT = '8080'
PORT_INTEGER = int(PORT)

class ProxyDlg(QDialog, Ui_ProxyDialog):
    def __init__(self, frontend = None, parent = None):
        super(ProxyDlg, self).__init__(parent)
        self.setupUi(self)
        self.setWindowIcon(QIcon(Constants.APP_ICON_DIALOG))
        self.setWindowTitle(Constants.APP_NAME + self.tr(' Proxy Configuration'))
        self.frontend = frontend
        self.controller = frontend.controller

        applyBtn = self.buttonBox.button(QDialogButtonBox.Apply)
        applyBtn.clicked.connect(self.applyChanges)
        self.cbAuthN.toggled.connect(self.setAuthN)

        self.server = None
        self.port = None
        self.user = None
        self.pwd = None
        self.realm = None
        self.AuthN = False

        proxy = ProxyInfo.get_proxy()
        if proxy is None:
            self.txtServer.clear()
            self.txtPort.clear()
            self.txtUser.clear()
            self.txtPwd.clear()
            self.txtRealm.clear()
            self.cbAuthN.setChecked(False)
            self.txtUser.setEnabled(False)
            self.txtPwd.setEnabled(False)
        else:
            self.server = proxy.server_url
            self.port = proxy.port
            self.user = proxy.user
            self.pwd = proxy.pwd
            self.realm = proxy.realm
            if proxy.authn_required:
                self.AuthN = proxy.authn_required

            self.txtServer.setText(self.server)
            self.txtPort.setText(str(self.port) if self.port else '')
            self.cbAuthN.setChecked(self.AuthN)
            if self.AuthN:
                self.txtUser.setEnabled(True)
                self.txtUser.setText(self.user)
                self.txtPwd.setEnabled(True)
                self.txtPwd.setText(self.pwd)
                self.txtRealm.setText(self.realm)
            else:
                self.txtUser.setEnabled(False)
                self.txtUser.clear()
                self.txtPwd.setEnabled(False)
                self.txtPwd.clear()
                self.txtRealm.clear()

    def setAuthN(self, state):
        self.AuthN = state
        if self.AuthN:
            self.txtUser.setEnabled(True)
            self.txtPwd.setEnabled(True)
            self.txtRealm.setEnabled(True)
        else:
            self.txtUser.setEnabled(False)
            self.txtPwd.setEnabled(False)
            self.txtRealm.setEnabled(False)
            self.txtUser.clear()
            self.txtPwd.clear()
            self.txtRealm.clear()

    def applyChanges(self):
        invalidate = False
        server = self.txtServer.text()
        if self.server != server:
            self.server = server
            invalidate = True
        port = 0
        try:
            port = int(self.txtPort.text())
            if port < 1024 or port > 65535:
                mbox = QMessageBox(QMessageBox.Critical, Constants.APP_NAME, self.tr('port %s is invalid.') % self.txtPort.text())
                mbox.setInformativeText(self.tr('Must be between 1024 and 65535.'))
                mbox.exec_()
                return
            
            server_ip = socket.gethostbyname(self.server)
            host = '127.0.0.1'
            if server_ip == host:
                show_mb = True
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    s.bind((host, port))
                    s.listen(5)
                    s.close()
                except Exception:
                    mbox = QMessageBox(QMessageBox.Critical, Constants.APP_NAME, \
                                       self.tr('port %s is in use.') % self.txtPort.text(), \
                                       QMessageBox.Yes | QMessageBox.No)
                    mbox.setInformativeText(self.tr('If this port is used by the proxy, click Yes, otherwise click No and use another port between 1024 and 65535.'))
                    if mbox.exec_() == QMessageBox.No:
                        return
                    show_mb = False
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    s.bind((host, port))
                    s.listen(5)
                    s.close()
                except:
                    if show_mb:
                        mbox = QMessageBox(QMessageBox.Critical, Constants.APP_NAME, \
                                           self.tr('port %s is in use.') % self.txtPort.text(), \
                                           QMessageBox.Yes | QMessageBox.No)
                        mbox.setInformativeText(self.tr('If this port is used by the proxy, click Yes, otherwise click No and use another port between 1024 and 65535.'))
                        if mbox.exec_() == QMessageBox.No:
                            return
                    show_mb = False
        except ValueError:
            mbox = QMessageBox(QMessageBox.Critical, Constants.APP_NAME, self.tr('port %s is invalid.') % self.txtPort.text())
            mbox.setInformativeText(self.tr('Must be a numeric value.'))
            mbox.exec_()
            return

        if port != self.port:
            self.port = port
            invalidate = True

        # TODO test successful login here?
        if self.AuthN:
            user = self.txtUser.text()
            if user != self.user:
                self.user = user
                invalidate = True
            pwd = self.txtPwd.text()
            if pwd != self.pwd:
                self.pwd = pwd
                invalidate = True
            realm = self.txtRealm.text()
            if realm != self.realm:
                self.realm = realm
                invalidate = True
                
        if invalidate:
            result = ProgressDialog.stopServer(self.frontend, parent = self)
            if result == ProgressDialog.CANCELLED:
                return QDialog.Rejected   

            settings.setValue('preferences/proxyServer', self.server)
            settings.setValue('preferences/proxyUser', self.user)
            settings.setValue('preferences/proxyPwd', self.pwd)
            settings.setValue('preferences/proxyRealm', self.realm)
            settings.setValue('preferences/proxyAuthN', self.AuthN)
            settings.setValue('preferences/proxyPort', self.port)
            settings.sync()
        else:
            result = ProgressDialog.OK_AND_NO_RESTART
                    
        self.done(QDialog.Accepted)
        return result
    