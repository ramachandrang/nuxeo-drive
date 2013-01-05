'''
Created on Dec 13, 2012

@author: mconstantin
'''

import socket
from PySide.QtGui import QDialog, QDialogButtonBox, QMessageBox, QIcon

from nxdrive.gui.ui_proxy import Ui_ProxyDialog
from nxdrive.logging_config import get_logger
from nxdrive.utils.helpers import create_settings
from nxdrive.client import ProxyInfo
from nxdrive import Constants

settings = create_settings()
PORT = '8090'
PORT_INTEGER = int(PORT)
TYPES = ['HTTP','SOCKS4', 'SOCKS5']
    
class ProxyDlg(QDialog, Ui_ProxyDialog):
    def __init__(self, frontend=None, parent=None):
        super(ProxyDlg, self).__init__(parent)
        self.setupUi(self)
        self.setWindowIcon(QIcon(Constants.APP_ICON_ENABLED))
        self.setWindowTitle(Constants.APP_NAME + self.tr(' Proxy Configuration'))
        self.frontend = frontend
        self.controller = frontend.controller
        
        applyBtn = self.buttonBox.button(QDialogButtonBox.Apply)
        applyBtn.clicked.connect(self.applyChanges)
        self.comboType.addItems(TYPES)
        self.comboType.setCurrentIndex(0)
        self.comboType.activated.connect(self.setType)
        self.cbAuthN.toggled.connect(self.setAuthN)
        
        self.proxyType = self.comboType.currentText()
        self.server = None
        self.port = None
        self.user = None
        self.pwd = None
        self.AuthN = False
        
        proxy = ProxyInfo.get_proxy()
        if proxy is None:
            self.txtServer.clear()
            self.txtPort.clear()
            self.txtUser.clear()
            self.txtPwd.clear()
            self.cbAuthN.setChecked(False)
        else:
            if proxy.type is not None:
                self.proxyType = proxy.type
            self.server = proxy.server_url
            self.port = proxy.port
            self.user = proxy.user
            self.pwd = proxy.pwd
            if proxy.authn_required is not None:
                self.AuthN = proxy.authn_required
                
            self.txtServer.setText(self.server)
            self.txtPort.setText(str(self.port))
            self.comboType.setCurrentIndex(TYPES.index(self.proxyType, ))
            self.cbAuthN.setChecked(self.AuthN)
            if self.AuthN:
                self.txtUser.setEnabled(True)
                self.txtUser.setText(self.user)
                self.txtPwd.setEnabled(True)
                self.txtPwd.setText(self.pwd)
            else:
                self.txtUser.setEnabled(False)
                self.txtUser.clear()
                self.txtPwd.setEnabled(False)
                self.txtPwd.clear()
            
               
    def setType(self, state):
        self.proxyType = self.comboType.currentText()
        
    def setAuthN(self, state):
        self.AuthN = state
        if self.AuthN:
            self.txtUser.setEnabled(True)
            self.txtPwd.setEnabled(True)
        else:
            self.txtUser.setEnabled(False)
            self.txtPwd.setEnabled(False)
            self.txtUser.clear()
            self.txtPwd.clear()
        
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
            host = '127.0.0.1'
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect((host, port))
                s.shutdown(2)
            except:
                mbox = QMessageBox(QMessageBox.Critical, Constants.APP_NAME,\
                                   self.tr('port %s is in use.') % self.txtPort.text(),\
                                   QMessageBox.Yes | QMessageBox.No)
                mbox.setInformativeText(self.tr('If this port is used by the proxy, click Yes, otherwise click No and use another port between 1024 and 65535.'))        
                if mbox.exec_() == QMessageBox.No:
                    return
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect((host, port))
                s.shutdown(2)
            except:
                mbox = QMessageBox(QMessageBox.Critical, Constants.APP_NAME,\
                                   self.tr('port %s is in use.') % self.txtPort.text(),\
                                   QMessageBox.Yes | QMessageBox.No)
                mbox.setInformativeText(self.tr('If this port is used by the proxy, click Yes, otherwise click No and use another port between 1024 and 65535.'))        
                if mbox.exec_() == QMessageBox.No:
                    return
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
            
        settings.setValue('preferences/proxyType', self.proxyType)
        settings.setValue('preferences/proxyServer', self.server)
        settings.setValue('preferences/proxyUser', self.user)
        settings.setValue('preferences/proxyPwd', self.pwd)
        settings.setValue('preferences/proxyAuthN', self.AuthN)
        settings.setValue('preferences/proxyPort', self.port)
        settings.sync()
        
        # invalidate remote client cache if necessary
        if invalidate and self.frontend is not None:
            cache = self.frontend.controller._get_client_cache()
            cache.clear()
            
        self.done(QDialog.Accepted)
        