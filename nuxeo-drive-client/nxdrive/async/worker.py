'''
Created on Nov 6, 2012

@author: mconstantin
'''
from PySide.QtCore import QThread, QMutexLocker

class Worker(QThread):
    def __init__(self, operation, parent=None):
        QThread.__init__(self, parent)
        self.operation = operation
        
    #Note: cannot use QMutex with 'with' Python statement
    # May use the convenience wrapper QMutexLocker which locks when created and unlocks when destructed
    # but I'm not sure how it works in PySide (vs C++) if non-deterministic destruction..
    
    def isPaused(self):
        status = False
        if not self.operation == None:
            #QMutexLocker(self.operation.mutex)
            self.operation.mutex.lock()  
            status = self.operation.paused
            self.operation.mutex.unlock()                
        return status
    
    def isPausing(self):
        status = False
        if not self.operation == None:
            #QMutexLocker(self.operation.mutex)
            self.operation.mutex.lock()  
            status = self.operation.pause and not self.operation.paused
            self.operation.mutex.unlock()                
        return status
    
    def pause(self):
        if not self.operation == None:
            #QMutexLocker(self.operation.mutex) 
            self.operation.mutex.lock()  
            self.operation.pause = True
            self.operation.mutex.unlock()      
        
    def resume(self):
        if not self.operation == None:
            QMutexLocker(self.operation.mutex)                 
            self.operation.pause = False
            self.operation.condition.wakeAll()
    
    def run(self):
        self.operation.work()
   
                

