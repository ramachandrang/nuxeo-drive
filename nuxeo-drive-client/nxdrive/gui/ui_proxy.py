# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'proxy.ui'
#
# Created: Wed Jan  2 17:15:53 2013
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_ProxyDialog(object):
    def setupUi(self, ProxyDialog):
        ProxyDialog.setObjectName("ProxyDialog")
        ProxyDialog.setMinimumSize(500, 200)
        self.lblServer = QtGui.QLabel(ProxyDialog)
        self.lblServer.setObjectName("lblServer")
        self.cbAuthN = QtGui.QCheckBox(ProxyDialog)
        self.cbAuthN.setObjectName("cbAuthN")
        self.lblUser = QtGui.QLabel(ProxyDialog)
        self.lblUser.setObjectName("lblUser")
        self.lblPwd = QtGui.QLabel(ProxyDialog)
        self.lblPwd.setObjectName("lblPwd")
        self.lblRealm = QtGui.QLabel(ProxyDialog)
        self.lblRealm.setObjectName("lblRealm")
        self.lblPort = QtGui.QLabel(ProxyDialog)
        self.lblPort.setObjectName("lblPort")
        self.txtServer = QtGui.QLineEdit(ProxyDialog)
        self.txtServer.setObjectName("txtServer")
        self.txtServer.setMinimumWidth(150)
        self.txtPort = QtGui.QLineEdit(ProxyDialog)
        self.txtPort.setMinimumWidth(40)
        self.txtPort.setMaximumWidth(55)
        self.txtPort.setObjectName("txtPort")
        self.line = QtGui.QFrame(ProxyDialog)
        self.line.setFrameShape(QtGui.QFrame.HLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)
        self.line.setObjectName("line")
        self.txtUser = QtGui.QLineEdit(ProxyDialog)
        self.txtUser.setObjectName("txtUser")
        self.txtPwd = QtGui.QLineEdit(ProxyDialog)
        self.txtPwd.setEchoMode(QtGui.QLineEdit.Password)
        self.txtPwd.setObjectName("txtPwd")
        self.txtRealm = QtGui.QLineEdit(ProxyDialog)
        self.txtRealm.setObjectName("txtRealm")
        self.txtRealm.setMaximumWidth(150)
        self.buttonBox = QtGui.QDialogButtonBox(ProxyDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Apply|QtGui.QDialogButtonBox.Cancel)
        self.buttonBox.setObjectName("buttonBox")
        grid = QtGui.QGridLayout(ProxyDialog)
        grid.addWidget(self.lblServer, 0, 0, 1, 1)
        grid.addWidget(self.txtServer, 0, 1, 1, 1)
        grid.addWidget(self.lblPort, 0, 2, 1, 1)
        grid.addWidget(self.txtPort, 0, 3, 1, 1)
        grid.addWidget(self.line, 1, 0, 1, 4)
        grid.addWidget(self.cbAuthN, 2, 1, 1, 1)
        grid.addWidget(self.lblRealm, 3, 0, 1, 1)
        grid.addWidget(self.txtRealm, 3, 1, 1, 1)
        grid.addWidget(self.lblUser, 4, 0, 1, 1)
        grid.addWidget(self.txtUser, 4, 1, 1, 1)
        grid.addWidget(self.lblPwd, 5, 0, 1, 1)
        grid.addWidget(self.txtPwd, 5, 1, 1, 1)
        grid.addWidget(self.buttonBox, 6, 0, 1, 4, QtCore.Qt.AlignRight)
        ProxyDialog.setLayout(grid)
        
        self.retranslateUi(ProxyDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("accepted()"), ProxyDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), ProxyDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(ProxyDialog)

    def retranslateUi(self, ProxyDialog):
        ProxyDialog.setWindowTitle(QtGui.QApplication.translate("ProxyDialog", "Proxy Configuration", None, QtGui.QApplication.UnicodeUTF8))
        self.lblServer.setText(QtGui.QApplication.translate("ProxyDialog", "Server:", None, QtGui.QApplication.UnicodeUTF8))
        self.cbAuthN.setText(QtGui.QApplication.translate("ProxyDialog", "Proxy requires authentication", None, QtGui.QApplication.UnicodeUTF8))
        self.lblUser.setText(QtGui.QApplication.translate("ProxyDialog", "Username:", None, QtGui.QApplication.UnicodeUTF8))
        self.lblPwd.setText(QtGui.QApplication.translate("ProxyDialog", "Password:", None, QtGui.QApplication.UnicodeUTF8))
        self.lblRealm.setText(QtGui.QApplication.translate("ProxyDialog", "Realm:", None, QtGui.QApplication.UnicodeUTF8))
        self.lblPort.setText(QtGui.QApplication.translate("ProxyDialog", "Port:", None, QtGui.QApplication.UnicodeUTF8))

