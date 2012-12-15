'''
Created on Dec 13, 2012

@author: mconstantin
'''

from PySide.QtGui import QDialog

from nxdrive.gui.ui_proxy import Ui_ProxyDialog
    
class ProxyDlg(QDialog, Ui_ProxyDialog):
    def __init__(self, frontend=None, parent=None):
        super(ProxyDlg, self).__init__(parent)
        self.setupUi(self)
        self.frontend = frontend
        self.controller = frontend.controller
        
        