'''
Created on Nov 7, 2012

@author: mconstantin
'''

from PySide.QtCore import Signal, QObject, QCoreApplication, QSettings
from PySide.QtGui import QSystemTrayIcon, QMessageBox

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
    message = Signal(str, str, QSystemTrayIcon.MessageIcon)
    error = Signal(str, str, QMessageBox.StandardButton)
    folders = Signal()

class ProxyInfo(QObject):
    PROXY_TYPE_HTTP = 1
    PROXY_TYPE_SOCKS4 = 2
    PROXY_TYPE_SOCKS5 = 3
    
    proxy_url = None
    proxy_port = None
    username = None
    password = None
    
    def __init__(self):
        self.proxy_type = ProxyInfo.PROXY_TYPE_HTTP
        self.proxy_use_authn = False
        
class RecoverableError(Exception):
    def __init__(self, text, info, buttons=QMessageBox.Ok):
        super(RecoverableError, self).__init__()
        self.text = text
        self.info = info
        self.buttons = buttons
        
    def __str__(self):
        return ("%s (%s)" % (self.text, self.info))
    
class QApplicationSingleton( object ):
    ## Stores the unique Singleton instance-
    _iInstance = None
 
    from PySide.QtGui import QApplication
    ## The constructor
    #  @param self The object pointer.
    def __init__( self, args=[]):
        # Check whether we already have an instance
        if QApplicationSingleton._iInstance is None:
            # Create and remember instanc
            QApplicationSingleton._iInstance = QApplicationSingleton.QApplication(args)
 
        # Store instance reference as the only member in the handle
        self._EventHandler_instance = QApplicationSingleton._iInstance
 
 
    ## Delegate access to implementation.
    #  @param self The object pointer.
    #  @param attr Attribute wanted.
    #  @return Attribute
    def __getattr__(self, aAttr):
        return getattr(self._iInstance, aAttr)
 
 
    ## Delegate access to implementation.
    #  @param self The object pointer.
    #  @param attr Attribute wanted.
    #  @param value Vaule to be set.
    #  @return Result of operation.
    def __setattr__(self, aAttr, aValue):
        return setattr(self._iInstance, aAttr, aValue)
 
        
def create_settings():      
    QCoreApplication.setOrganizationDomain('sharplabs.com')
    QCoreApplication.setApplicationName('sla')
    QCoreApplication.setApplicationName('CloudDesk.Sync')
    return QSettings()
