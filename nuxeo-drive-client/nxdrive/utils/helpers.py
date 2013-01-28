'''
Created on Nov 7, 2012

@author: mconstantin
'''

import sys
import urllib2
from PySide.QtCore import Signal, QObject, QCoreApplication, QSettings, QObject, QEvent
from PySide.QtGui import QSystemTrayIcon, QMessageBox
from nxdrive import Constants
from nxdrive.logging_config import get_logger

log = get_logger(__name__)


class Communicator(QObject):
    """Handle communication between sync and main GUI thread

    Use a signal to notify the main thread event loops about states update by
    the synchronization thread.

    """
    # (event name, new icon, rebuild menu, pause/resume)
    icon = Signal(str)
    menu = Signal()
    stop = Signal()
    invalid_credentials = Signal(str)
    invalid_proxy = Signal(str)
    message = Signal(str, str, QSystemTrayIcon.MessageIcon)
    error = Signal(str, str, QMessageBox.StandardButton)
    folders = Signal()

class RecoverableError(Exception):
    def __init__(self, text, info, buttons = QMessageBox.Ok):
        super(RecoverableError, self).__init__()
        self.text = text
        self.info = info
        self.buttons = buttons

    def __str__(self):
        return ("%s (%s)" % (self.text, self.info))

class ProxyConnectionError(Exception):
    def __init__(self, urlerror):
        if type(urlerror) == urllib2.URLError:
            self.code = urlerror.reason.args[0]
            self.text = urlerror.reason.args[1]
        else:
            self.code = 600
            self.text = ','.join(self.args)

    def __str__(self):
        return ('%d (%s)' % (self.code, self.text))

class ProxyConfigurationError(Exception):
    def __init__(self, msg):
        self.code = 601
        self.text = msg

    def __str__(self):
        return ('%d (%s)' % (self.code, self.text))

class QApplicationSingleton(object):
    # # Stores the unique Singleton instance-
    _iInstance = None

    from PySide.QtGui import QApplication
    # # The constructor
    #  @param self The object pointer.
    def __init__(self, args = []):
        # Check whether we already have an instance
        if QApplicationSingleton._iInstance is None:
            # Create and remember instanc
            QApplicationSingleton._iInstance = QApplicationSingleton.QApplication(args)

        # Store instance reference as the only member in the handle
        self._EventHandler_instance = QApplicationSingleton._iInstance


    # # Delegate access to implementation.
    #  @param self The object pointer.
    #  @param attr Attribute wanted.
    #  @return Attribute
    def __getattr__(self, aAttr):
        return getattr(self._iInstance, aAttr)


    # # Delegate access to implementation.
    #  @param self The object pointer.
    #  @param attr Attribute wanted.
    #  @param value Vaule to be set.
    #  @return Result of operation.
    def __setattr__(self, aAttr, aValue):
        return setattr(self._iInstance, aAttr, aValue)


class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()

#    def __set__(self, cls, owner, value):
#        return classmethod(self.fset).__set__(None, owner, value)()


def create_settings():
    QCoreApplication.setOrganizationDomain(Constants.COMPANY_NAME)
    QCoreApplication.setApplicationName(Constants.SHORT_APP_NAME)
    return QSettings()


class EventFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            return True
        elif event.type() == QEvent.MouseButtonPress:
            return True
        elif event.type() == QEvent.MouseButtonRelease:
            return True
        elif event.type() == QEvent.MouseButtonDblClick:
            return True
        else:
            # standard event processing
            return QObject.eventFilter(self, obj, event)



# Utilities for encrypting the password stored in the local database
try:
    from Crypto.Cipher import AES
    import hashlib
    import base64
    import getpass
    if sys.platform == 'win32':
        import win32crypt
    elif sys.platform == 'darwin':
        import keyring

    log.debug("Crypto.Cipher, etc. successfully imported")
    def encrypt_password(pwd):
        key = hashlib.md5(getpass.getuser()).digest()
        mode = AES.MODE_ECB
        encryptor = AES.new(key, mode)
        pwd = pad_to_multiple_of_16(pwd)
        encpwd = encryptor.encrypt(pwd)
        if sys.platform == 'win32':
            pwdhash = win32crypt.CryptProtectData(key, Constants.SHORT_APP_NAME, None, None, None, 0)
        elif sys.platform == 'darwin':
            keyring.set_password(Constants.SHORT_APP_NAME, getpass.getuser(), key)
            pwdhash = Constants.SHORT_APP_NAME
        else:
            pwdhash = key
        return base64.standard_b64encode(encpwd), base64.standard_b64encode(pwdhash)

    def decrypt_password(encpwd, pwdhash = ''):
        pwdhash = base64.standard_b64decode(pwdhash)
        if sys.platform == 'win32':
            desc = ''
            key = win32crypt.CryptUnprotectData(pwdhash, desc, None, None, 0)[1]
        elif sys.platform == 'darwin':
            key = keyring.get_password(Constants.SHORT_APP_NAME, getpass.getuser())
        else:
            key = pwdhash
        mode = AES.MODE_ECB
        decryptor = AES.new(key, mode)
        encpwd = base64.standard_b64decode(encpwd)
        pwd = decryptor.decrypt(encpwd)
        pwd = remove_pad(pwd)
        return pwd

except ImportError as e:
    log.warning("module is not installed (%s): password will not be encrypted", str(e))
    def encrypt_password(pwd):
        return pwd

    def decrypt_password(encpwd, pwdhash = ''):
        return encpwd


def pad_to_multiple_of_16(indata):
    if len(indata) % 16 != 0:
        diff = 16 - len(indata) % 16
        indata += '\x80'
        if diff > 1:
            indata += ' ' * (diff - 1)

    return indata

def remove_pad(indata):
    pos = indata.rfind('\x80')
    if pos != -1:
        indata = indata[0:pos]

    return indata
