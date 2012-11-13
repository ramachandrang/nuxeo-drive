'''
Created on Nov 7, 2012

@author: mconstantin
'''
from PySide.QtCore import Signal, QObject


#from nxdrive.utils.decorators import singleton
#
#@singleton
#class QApplicationSingleton(QtGui.QApplication):
#    def __init__(self, args=[]):
#        super(QApplicationSingleton, self).__init__(args)
        
#class QApplicationSingleton(object):
#    _instance = None
#    def __new__(cls, *args, **kwargs):
#        if not cls._instance:
#            cls._instance = super(QApplicationSingleton, cls).__new__(
#                                cls, *args, **kwargs)
#        return cls._instance
#    
#    def __init__(self, args=[]):
#        super(QApplicationSingleton, self).__init__(args)


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
 
 
class Notifier(QObject):   
    uistatus = Signal(int, name='uistatus') 
    
    def __init__(self):
        # signal for updating UI status
        QObject.__init__(self)
          
    def notify(self, status):
        self.uistatus.emit(status)
        
    def register(self, f):
        self.uistatus.connect(f)
        
    def unregister(self):
        self.uistatus.disconnect()
        