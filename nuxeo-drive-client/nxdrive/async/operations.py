'''
Created on Oct 29, 2012

@author: mconstantin
'''

from PySide.QtCore import QMutex, QWaitCondition, QThread
from nxdrive.logging_config import get_logger

log = get_logger(__name__)

class SyncOperations:
    def __init__(self, dowork):
        self.dowork = dowork
        self.pause = False
        self.paused = False
        #Note: cannot use QMutex with 'with' Python statement
        # May use the convenience wrapper QMutexLocker which locks when created and unlocks when destructed
        # but I'm not sure how it works in PySide (vs C++) if non-deterministic destruction..
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        
    def work(self):
        try:
            log.debug("started worker thread (id=%s)", QThread.currentThread())
            self.dowork(self)
        except:
            raise
        finally:
            log.debug("terminated worker thread (id=%s)", QThread.currentThread())
            