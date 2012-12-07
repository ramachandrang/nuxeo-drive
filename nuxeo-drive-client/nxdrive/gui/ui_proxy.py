# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'proxy.ui'
#
# Created: Tue Dec  4 22:08:42 2012
#      by: pyside-uic 0.2.13 running on PySide 1.1.0
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_ProxyDialog(object):
    def setupUi(self, ProxyDialog):
        ProxyDialog.setObjectName("ProxyDialog")
        ProxyDialog.resize(583, 241)
        self.buttonBox = QtGui.QDialogButtonBox(ProxyDialog)
        self.buttonBox.setGeometry(QtCore.QRect(10, 200, 561, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.lblProxy = QtGui.QLabel(ProxyDialog)
        self.lblProxy.setGeometry(QtCore.QRect(10, 20, 81, 16))
        self.lblProxy.setObjectName("lblProxy")
        self.lblServer = QtGui.QLabel(ProxyDialog)
        self.lblServer.setGeometry(QtCore.QRect(10, 60, 91, 16))
        self.lblServer.setObjectName("lblServer")
        self.checkBox = QtGui.QCheckBox(ProxyDialog)
        self.checkBox.setGeometry(QtCore.QRect(90, 100, 301, 20))
        self.checkBox.setObjectName("checkBox")
        self.lblUser = QtGui.QLabel(ProxyDialog)
        self.lblUser.setGeometry(QtCore.QRect(10, 130, 62, 16))
        self.lblUser.setObjectName("lblUser")
        self.lblPwd = QtGui.QLabel(ProxyDialog)
        self.lblPwd.setGeometry(QtCore.QRect(10, 160, 62, 16))
        self.lblPwd.setObjectName("lblPwd")
        self.lblPort = QtGui.QLabel(ProxyDialog)
        self.lblPort.setGeometry(QtCore.QRect(420, 50, 62, 16))
        self.lblPort.setObjectName("lblPort")
        self.comboBox = QtGui.QComboBox(ProxyDialog)
        self.comboBox.setGeometry(QtCore.QRect(90, 16, 111, 26))
        self.comboBox.setMaxVisibleItems(3)
        self.comboBox.setObjectName("comboBox")
        self.lineEdit = QtGui.QLineEdit(ProxyDialog)
        self.lineEdit.setGeometry(QtCore.QRect(90, 50, 311, 22))
        self.lineEdit.setObjectName("lineEdit")
        self.lineEdit_2 = QtGui.QLineEdit(ProxyDialog)
        self.lineEdit_2.setGeometry(QtCore.QRect(460, 51, 91, 21))
        self.lineEdit_2.setObjectName("lineEdit_2")
        self.line = QtGui.QFrame(ProxyDialog)
        self.line.setGeometry(QtCore.QRect(10, 82, 541, 16))
        self.line.setFrameShape(QtGui.QFrame.HLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)
        self.line.setObjectName("line")
        self.lineEdit_3 = QtGui.QLineEdit(ProxyDialog)
        self.lineEdit_3.setGeometry(QtCore.QRect(90, 130, 311, 22))
        self.lineEdit_3.setObjectName("lineEdit_3")
        self.lineEdit_4 = QtGui.QLineEdit(ProxyDialog)
        self.lineEdit_4.setGeometry(QtCore.QRect(90, 160, 311, 22))
        self.lineEdit_4.setObjectName("lineEdit_4")

        self.retranslateUi(ProxyDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("accepted()"), ProxyDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), ProxyDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(ProxyDialog)

    def retranslateUi(self, ProxyDialog):
        ProxyDialog.setWindowTitle(QtGui.QApplication.translate("ProxyDialog", "Proxy Configuration", None, QtGui.QApplication.UnicodeUTF8))
        self.lblProxy.setText(QtGui.QApplication.translate("ProxyDialog", "Proxy Type", None, QtGui.QApplication.UnicodeUTF8))
        self.lblServer.setText(QtGui.QApplication.translate("ProxyDialog", "Server", None, QtGui.QApplication.UnicodeUTF8))
        self.checkBox.setText(QtGui.QApplication.translate("ProxyDialog", "Proxy requires authentication", None, QtGui.QApplication.UnicodeUTF8))
        self.lblUser.setText(QtGui.QApplication.translate("ProxyDialog", "Username", None, QtGui.QApplication.UnicodeUTF8))
        self.lblPwd.setText(QtGui.QApplication.translate("ProxyDialog", "Password", None, QtGui.QApplication.UnicodeUTF8))
        self.lblPort.setText(QtGui.QApplication.translate("ProxyDialog", "Port", None, QtGui.QApplication.UnicodeUTF8))

