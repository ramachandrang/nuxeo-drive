'''
Created on Nov 7, 2012

@author: mconstantin
'''

from PySide.QtCore import Signal, QObject
from PySide.QtGui import QSystemTrayIcon

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
 
# Not used anymore
#class Notifier(QObject):   
#    uistatus = Signal(int, name='uistatus') 
#    
#    def __init__(self):
#        # signal for updating UI status
#        QObject.__init__(self)
#          
#    def notify(self, status):
#        self.uistatus.emit(status)
#        
#    def register(self, f):
#        self.uistatus.connect(f)
#        
#    def unregister(self):
#        self.uistatus.disconnect()
        
        
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
#    uistatus = Signal(int)
    