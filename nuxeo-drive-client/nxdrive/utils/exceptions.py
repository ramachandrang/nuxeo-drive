'''
Created on Feb 6, 2013

@author: mconstantin
'''

import urllib2
from PySide.QtGui import QMessageBox

class RecoverableError(Exception):
    def __init__(self, text, info, buttons=QMessageBox.Ok):
        super(RecoverableError, self).__init__()
        self.text = text
        self.info = info
        self.buttons = buttons

    def __str__(self):
        return ("%s (%s)" % (self.text, self.info))

class ProxyConnectionError(Exception):
    def __init__(self, urlerror):
        if type(urlerror) == urllib2.URLError:
            if len(urlerror.reason.args) < 2:
                self.code = 600
                self.text = urlerror.reason.args[0]
            else:
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
    
