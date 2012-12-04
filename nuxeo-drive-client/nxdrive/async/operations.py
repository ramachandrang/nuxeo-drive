'''
Created on Nov 29, 2012

@author: mconstantin
'''
from threading import Lock, Event
from nxdrive.logging_config import get_logger

log = get_logger(__name__)

class SyncOperations:
    def __init__(self):
        self.pause = False
        self.paused = False
        self.lock = Lock()
        self.event = Event()
        