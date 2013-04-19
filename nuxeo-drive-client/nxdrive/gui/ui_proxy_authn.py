# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'proxy.ui'
# 
# Created: Wed Jan  2 17:15:53 2013
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
# 
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_ProxyAuthnDialog(object):
    def setupUi(self, ProxyAuthnDialog):
        ProxyAuthnDialog.setObjectName("ProxyAuthnDialog")
        ProxyAuthnDialog.setMinimumSize(350, 100)
        self.lblRealm = QtGui.QLabel(ProxyAuthnDialog)
        self.lblRealm.setObjectName("lblRealm")
        self.lblUser = QtGui.QLabel(ProxyAuthnDialog)
        self.lblUser.setObjectName("lblUser")
        self.lblPwd = QtGui.QLabel(ProxyAuthnDialog)
        self.lblPwd.setObjectName("lblPwd")
        self.txtRealm = QtGui.QLineEdit(ProxyAuthnDialog)
        self.txtRealm.setObjectName("txtRealm")
        self.txtRealm.setMaximumWidth(150)
        self.txtUser = QtGui.QLineEdit(ProxyAuthnDialog)
        self.txtUser.setObjectName("txtUser")
        self.txtPwd = QtGui.QLineEdit(ProxyAuthnDialog)
        self.txtPwd.setEchoMode(QtGui.QLineEdit.Password)
        self.txtPwd.setObjectName("txtPwd")
        gridLayout = QtGui.QGridLayout()
        gridLayout.addWidget(self.lblRealm, 0, 0, 1, 1)
        gridLayout.addWidget(self.txtRealm, 0, 1, 1, 1)
        gridLayout.addWidget(self.lblUser, 1, 0, 1, 1)
        gridLayout.addWidget(self.txtUser, 1, 1, 1, 1)
        gridLayout.addWidget(self.lblPwd, 2, 0, 1, 1)
        gridLayout.addWidget(self.txtPwd, 2, 1, 1, 1)
        self.buttonBox = QtGui.QDialogButtonBox(ProxyAuthnDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Apply | QtGui.QDialogButtonBox.Cancel)
        self.buttonBox.setObjectName("buttonBox")
        gridLayout.addWidget(self.buttonBox, 3, 0, 1, 2, QtCore.Qt.AlignRight)
        self.setLayout(gridLayout)
        
        self.retranslateUi(ProxyAuthnDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("accepted()"), ProxyAuthnDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), ProxyAuthnDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(ProxyAuthnDialog)

    def retranslateUi(self, ProxyDialog):
        ProxyDialog.setWindowTitle(QtGui.QApplication.translate("ProxyAuthnDialog", "Proxy Authentication", None, QtGui.QApplication.UnicodeUTF8))
        self.lblRealm.setText(QtGui.QApplication.translate("ProxyAuthnDialog", "Realm:", None, QtGui.QApplication.UnicodeUTF8))
        self.lblUser.setText(QtGui.QApplication.translate("ProxyAuthnDialog", "Username:", None, QtGui.QApplication.UnicodeUTF8))
        self.lblPwd.setText(QtGui.QApplication.translate("ProxyAuthnDialog", "Password:", None, QtGui.QApplication.UnicodeUTF8))
