'''
Created on Nov 7, 2012

@author: mconstantin
'''

import os
import sys
from PySide.QtCore import Signal, QCoreApplication, QSettings, QObject, QEvent
from PySide.QtGui import QSystemTrayIcon, QMessageBox
from nxdrive import Constants
from nxdrive.logging_config import get_logger

log = get_logger(__name__)

WIN32_SUFFIX = os.path.join('library.zip', 'nxdrive')
OSX_SUFFIX = "Contents/Resources/lib/python2.7/site-packages.zip/nxdrive"


def normalized_path(path):
    """Return absolute, normalized file path"""
    # XXX: we could os.path.normcase as well under Windows but it might be the
    # source of unexpected troubles so no doing it for now.
    return os.path.normpath(os.path.abspath(os.path.expanduser(path)))

def safe_long_path(path):
    """Utility to prefix path with the long path marker for Windows

    http://msdn.microsoft.com/en-us/library/aa365247.aspx#maxpath

    """
    if sys.platform == 'win32':
        path = u"\\\\?\\" + path
    return path

def find_exe_path():
    """Introspect the Python runtime to find the frozen Windows exe/OSX app"""
    import nxdrive
    nxdrive_path = os.path.realpath(os.path.dirname(nxdrive.__file__))

    # Detect frozen win32 executable under Windows
    if nxdrive_path.endswith(WIN32_SUFFIX):
        exe_path = nxdrive_path.replace(WIN32_SUFFIX, '%s.exe' % Constants.SHORT_APP_NAME)
        if os.path.exists(exe_path):
            return exe_path

    # Detect OSX frozen app
    if nxdrive_path.endswith(OSX_SUFFIX):
        exe_path = nxdrive_path.replace(OSX_SUFFIX, 'Contents/MacOS/%s' % Constants.APP_NAME)
        if os.path.exists(exe_path):
            return exe_path

    # Fall-back to the regular method that should work both the ndrive script
    return sys.argv[0]

def get_maintenance_message(status, schedule=None):
    from dateutil import tz
    from datetime import datetime

    # NOTE only notify about the Cloud Office Portal service.
    # Ignore the 'Service' in the schedule because the service url is 
    # passed in the request anyway.
    if schedule is None and status == 'maintenance':
        msg = '%s is currently offline.' % Constants.SERVICE_NAME
        detail = 'Due to maintenance.'
    elif schedule is not None:
        service = schedule['Service']
        # get UTC times
        start_utc = datetime.strptime(schedule['FromDate'], '%Y-%m-%dT%H:%M:%SZ')
        end_utc = datetime.strptime(schedule['ToDate'], '%Y-%m-%dT%H:%M:%SZ')
        # convert to local times
        from_tz = tz.tzutc()
        to_tz = tz.tzlocal()
        start_utc = start_utc.replace(tzinfo = from_tz)
        end_utc = end_utc.replace(tzinfo = from_tz)
        start_local = start_utc.astimezone(to_tz)
        end_local = end_utc.astimezone(to_tz)
        if status == 'maintenance':
            msg = "%s is currently offline." % service                           
            detail = "Due to maintenance from %s to %s." %\
                             (start_local.strftime("%x %X"), end_local.strftime("%x %X"))
        elif status == 'available':
            msg = "%s is scheduled for maintenance." % service
            detail = "From %s to %s." %\
                             (start_local.strftime("%x %X"), end_local.strftime("%x %X"))
        else:
            msg = detail = None       
    else:
        msg = detail = None
    return msg, detail

def create_settings():
    QCoreApplication.setOrganizationDomain(Constants.COMPANY_NAME)
    QCoreApplication.setApplicationName(Constants.SHORT_APP_NAME)
    return QSettings()


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


class classproperty(property):
    def __get__(self, cls, owner):
#        return classmethod(self.fget).__get__(None, owner)()
        return self.fget.__get__(None, owner)()

    def __set__(self, cls, owner, value):
        return self.fset.__set__(None, owner, value)()
