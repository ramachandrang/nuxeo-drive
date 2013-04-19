'''
Created on Nov 29, 2012

@author: mconstantin
'''
from threading import Thread

class Worker(Thread):
    def __init__(self, operation, group=None, target=None, name=None, args=(), kvargs={}):
        Thread.__init__(self, group, target, name, args, kvargs)
        self.operation = operation
        
    def isPaused(self):
        status = False
        if self.operation is not None:
            with self.operation.lock:
                status = self.operation.paused               
        return status
    
    def isPausing(self):
        status = False
        if self.operation is not None:
            with self.operation.lock:
                status = self.operation.pause and not self.operation.paused
              
        return status
    
    def pause(self):
        if self.operation is not None:
            with self.operation.lock:
                self.operation.pause = True   
            self.operation.event.clear() 
        
    def resume(self):
        if self.operation is not None:
            with self.operation.lock:             
                self.operation.pause = False
            self.operation.event.set()
    
        
