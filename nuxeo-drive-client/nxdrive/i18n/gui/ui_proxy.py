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
        ProxyDialog.resize(583, 241)
        self.lblServer = QtGui.QLabel(ProxyDialog)
        self.lblServer.setGeometry(QtCore.QRect(10, 60, 91, 16))
        self.lblServer.setObjectName("lblServer")
        self.cbAuthN = QtGui.QCheckBox(ProxyDialog)
        self.cbAuthN.setGeometry(QtCore.QRect(90, 100, 301, 20))
        self.cbAuthN.setObjectName("cbAuthN")
        self.lblUser = QtGui.QLabel(ProxyDialog)
        self.lblUser.setGeometry(QtCore.QRect(10, 130, 62, 16))
        self.lblUser.setObjectName("lblUser")
        self.lblPwd = QtGui.QLabel(ProxyDialog)
        self.lblPwd.setGeometry(QtCore.QRect(10, 160, 62, 16))
        self.lblPwd.setObjectName("lblPwd")
        self.lblPort = QtGui.QLabel(ProxyDialog)
        self.lblPort.setGeometry(QtCore.QRect(420, 50, 62, 16))
        self.lblPort.setObjectName("lblPort")
        self.txtServer = QtGui.QLineEdit(ProxyDialog)
        self.txtServer.setGeometry(QtCore.QRect(90, 50, 311, 22))
        self.txtServer.setObjectName("txtServer")
        self.txtPort = QtGui.QLineEdit(ProxyDialog)
        self.txtPort.setGeometry(QtCore.QRect(460, 51, 91, 21))
        self.txtPort.setObjectName("txtPort")
        self.line = QtGui.QFrame(ProxyDialog)
        self.line.setGeometry(QtCore.QRect(10, 82, 541, 16))
        self.line.setFrameShape(QtGui.QFrame.HLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)
        self.line.setObjectName("line")
        self.txtUser = QtGui.QLineEdit(ProxyDialog)
        self.txtUser.setGeometry(QtCore.QRect(90, 130, 311, 22))
        self.txtUser.setObjectName("txtUser")
        self.txtPwd = QtGui.QLineEdit(ProxyDialog)
        self.txtPwd.setGeometry(QtCore.QRect(90, 160, 311, 22))
        self.txtPwd.setEchoMode(QtGui.QLineEdit.PasswordEchoOnEdit)
        self.txtPwd.setObjectName("txtPwd")
        self.widget = QtGui.QWidget(ProxyDialog)
        self.widget.setGeometry(QtCore.QRect(10, 200, 564, 32))
        self.widget.setObjectName("widget")
        self.horizontalLayout = QtGui.QHBoxLayout(self.widget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtGui.QSpacerItem(388, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.buttonBox = QtGui.QDialogButtonBox(self.widget)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Apply|QtGui.QDialogButtonBox.Cancel)
        self.buttonBox.setObjectName("buttonBox")
        self.horizontalLayout.addWidget(self.buttonBox)

        self.retranslateUi(ProxyDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("accepted()"), ProxyDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), ProxyDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(ProxyDialog)

    def retranslateUi(self, ProxyDialog):
        ProxyDialog.setWindowTitle(QtGui.QApplication.translate("ProxyDialog", "Proxy Configuration", None, QtGui.QApplication.UnicodeUTF8))
        self.lblServer.setText(QtGui.QApplication.translate("ProxyDialog", "Server", None, QtGui.QApplication.UnicodeUTF8))
        self.cbAuthN.setText(QtGui.QApplication.translate("ProxyDialog", "Proxy requires authentication", None, QtGui.QApplication.UnicodeUTF8))
        self.lblUser.setText(QtGui.QApplication.translate("ProxyDialog", "Username", None, QtGui.QApplication.UnicodeUTF8))
        self.lblPwd.setText(QtGui.QApplication.translate("ProxyDialog", "Password", None, QtGui.QApplication.UnicodeUTF8))
        self.lblPort.setText(QtGui.QApplication.translate("ProxyDialog", "Port", None, QtGui.QApplication.UnicodeUTF8))

