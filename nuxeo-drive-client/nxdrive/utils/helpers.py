'''
Created on Nov 7, 2012

@author: mconstantin
'''

import os
import sys
import ConfigParser

from PySide.QtCore import Signal, QCoreApplication, QSettings, QObject, QEvent
from PySide.QtCore import QIODevice, QTimer, Signal, QCoreApplication, QTextStream
from PySide.QtGui import QSystemTrayIcon, QMessageBox, QApplication
from PySide.QtNetwork import QLocalServer, QLocalSocket

import nxdrive
from nxdrive import Constants
from nxdrive import Defaults

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

def find_data_path():
    """Introspect the Python runtime to find the frozen 'data' path."""

    import nxdrive
    nxdrive_path = os.path.realpath(os.path.dirname(nxdrive.__file__))

    # Detect frozen win32 executable under Windows
    if nxdrive_path.endswith(WIN32_SUFFIX):
        exe_path = nxdrive_path.replace(WIN32_SUFFIX, 'data')
        if os.path.exists(exe_path):
            return exe_path

    # Detect OSX frozen app
    if nxdrive_path.endswith(OSX_SUFFIX):
        exe_path = nxdrive_path.replace(OSX_SUFFIX, 'Contents/MacOS/Resources/data')
        if os.path.exists(exe_path):
            return exe_path

    # Fall-back to the regular method that should work both the ndrive script
    return os.path.join(os.path.split(sys.argv[0])[0], 'data')
    
def get_maintenance_message(status, schedule=None):
    from dateutil import tz
    from datetime import datetime

    # NOTE only notify about the Cloud Office Portal service.
    # Ignore the 'Service' in the schedule because the service url is
    # passed in the request anyway.
    if schedule is None and status == 'maintenance':
        msg = '%s is currently offline.' % Constants.SERVICE_NAME
        detail = 'Due to maintenance.'
        data1 = data2 = None
    elif schedule is not None:
        # DO NOT use the service name... it' the wrong string: "Cloud portal Service".
        # use "Cloud Portal Office" instead
        service = schedule['Service']
        # get UTC times
        start_utc = datetime.strptime(schedule['FromDate'], '%Y-%m-%dT%H:%M:%SZ')
        end_utc = datetime.strptime(schedule['ToDate'], '%Y-%m-%dT%H:%M:%SZ')
        # convert to local times
        from_tz = tz.tzutc()
        to_tz = tz.tzlocal()
        # grab utc times for database
        data1 = start_utc
        data2 = end_utc
        # convert local time for message
        start_utc = start_utc.replace(tzinfo=from_tz)
        end_utc = end_utc.replace(tzinfo=from_tz)
        start_local = start_utc.astimezone(to_tz)
        end_local = end_utc.astimezone(to_tz)
        if status == 'maintenance':
#            msg = _("%s is currently offline.") % service
            msg = _("%s is currently offline due to maintenance.") % Constants.SERVICE_NAME
            detail = _("Due to maintenance from %s to %s.") % \
                             (start_local.strftime("%x %X"), end_local.strftime("%x %X"))
        elif status == 'available':
#            msg = _("%s is scheduled for maintenance.") % service
            msg = _("%s is scheduled for maintenance.") % Constants.SERVICE_NAME
            detail = _("From %s to %s.") % \
                             (start_local.strftime("%x %X"), end_local.strftime("%x %X"))
        else:
            msg = detail = None
    else:
        msg = detail = data1 = data2 = None
    return msg, detail, data1, data2

def create_settings():
    QCoreApplication.setOrganizationDomain(Constants.COMPANY_NAME)
    QCoreApplication.setApplicationName(Constants.APP_NAME)
    return QSettings()

def create_config_file(config_file):    
    config = ConfigParser.RawConfigParser()
    
    # When adding sections or items, add them in the reverse order of
    # how you want them to be displayed in the actual file.
    # In addition, please note that using RawConfigParser's and the raw
    # mode of ConfigParser's respective set functions, you can assign
    # non-string values to keys internally, but will receive an error
    # when attempting to write to a file or when you get it in non-raw
    # mode. SafeConfigParser does not allow such assignments to take place.
    config.add_section('support')
    config.set('support', '; this turns on debug menus', '')
    config.set('support', 'debug', str(nxdrive.DEBUG))
    
    config.add_section('misc')
    config.set('misc', '; duration of the notification balloon [sec]', '')
    config.set('misc', 'notification-delay', str(Defaults.NOTIFICATION_MESSAGE_DELAY))
    config.set('misc', '; number of files in the Recently Changed Files menu', '')
    config.set('misc', 'recent-files-count', str(Defaults.RECENT_FILES_COUNT))
    
    config.add_section('services')
    config.set('services', 'maintenance-url', Defaults.MAINTENANCE_SERVICE_URL)
    config.set('services', 'upgrade-url', Defaults.UPGRADE_SERVICE_URL)
    config.set('services', 'notification-interval', str(Defaults.SERVICE_NOTIFICATION_INTERVAL))
    
    config.add_section('cloud-portal-office')
    config.set('cloud-portal-office', 'server', Defaults.DEFAULT_CLOUDDESK_URL)
    
    # Writing our configuration file
    with open(config_file, 'wb') as cfg:
        config.write(cfg)
    
def read_config_file(config_file):
    defaults = {
                'debug': str(nxdrive.DEBUG),
                'notification-delay': str(Defaults.NOTIFICATION_MESSAGE_DELAY),
                'recent-files-count': str(Defaults.RECENT_FILES_COUNT),
                'maintenance-url': Defaults.MAINTENANCE_SERVICE_URL,
                'upgrade-url': Defaults.UPGRADE_SERVICE_URL,
                'notification-interval': str(Defaults.SERVICE_NOTIFICATION_INTERVAL),
                'server': Defaults.DEFAULT_CLOUDDESK_URL
                }
    config = ConfigParser.RawConfigParser(defaults)
    config.read(config_file)
    
    try:
        nxdrive.DEBUG = config.getboolean('support', 'debug')
        Constants.NOTIFICATION_MESSAGE_DELAY = config.getint('misc', 'notification-delay')
        Constants.RECENT_FILES_COUNT = config.getint('misc', 'recent-files-count')
        Constants.MAINTENANCE_SERVICE_URL = config.get('services', 'maintenance-url')
        Constants.UPGRADE_SERVICE_URL = config.get('services', 'upgrade-url')
        Constants.NOTIFICATION_MESSAGE_DELAY = config.getint('services', 'notification-interval')
        Constants.CLOUDDESK_URL = config.get('cloud-portal-office', 'server')
    except Exception as e:
        log.debug('failed to read configuration file %s: %s', config_file, e)

def reload_config_file(config_file):
    defaults = {
                'debug': str(nxdrive.DEBUG),
                'notification-delay': str(Defaults.NOTIFICATION_MESSAGE_DELAY),
                'recent-files-count': str(Defaults.RECENT_FILES_COUNT),
                'notification-interval': str(Defaults.SERVICE_NOTIFICATION_INTERVAL)
                }
    config = ConfigParser.RawConfigParser(defaults)
    config.read(config_file)
    
    try:
        nxdrive.DEBUG = config.getboolean('support', 'debug')
        Constants.NOTIFICATION_MESSAGE_DELAY = config.getint('misc', 'notification-delay')
        Constants.RECENT_FILES_COUNT = config.getint('misc', 'recent-files-count')
        Constants.NOTIFICATION_MESSAGE_DELAY = config.getint('services', 'notification-interval')
    except Exception as e:
        log.debug('failed to reload configuration file %s: %s', config_file, e)
    
class Communicator(QObject):
    """Handle communication between sync and main GUI thread

    Use a signal to notify the main thread event loops about states update by
    the synchronization thread.
    """
    # Stores the unique Singleton instance-
    _iInstance = None
    @staticmethod
    def getCommunicator():
        if not Communicator._iInstance:
            Communicator._iInstance = Communicator()
        return Communicator._iInstance
    
    # (event name, new icon, rebuild menu, pause/resume)
    icon = Signal(str)
    menu = Signal()
    stop = Signal()
    invalid_credentials = Signal(str)
    invalid_proxy = Signal(str, str)
    message = Signal(str, str, QSystemTrayIcon.MessageIcon)
    error = Signal(str, str, QMessageBox.StandardButton)
    folders = Signal(str, bool)
    messageReceived = Signal(str)

    def __init__(self):
        if Communicator._iInstance:
            raise Communicator._iInstance
        super(Communicator, self).__init__()
        Communicator._iInstance = self

class classproperty(property):
    def __get__(self, cls, owner):
#        return classmethod(self.fget).__get__(None, owner)()
        return self.fget.__get__(None, owner)()

    def __set__(self, cls, owner, value):
        return self.fset.__set__(None, owner, value)()
    
class QSingleInstanceApplication(QApplication):
    messageReceived = Signal(str)
    
    def __init__(self, appid, args=sys.argv):
        super(QSingleInstanceApplication, self).__init__(args)
        self._id = appid

        # Is there another instance running?
        self._outSocket = QLocalSocket()
        log.trace("connecting to server %s" % self._id)
        self._outSocket.connectToServer(self._id)
        self._isRunning = self._outSocket.waitForConnected()
        
        if self._isRunning:
            # Yes, there is.
            log.trace("another instance is running")
            self._outStream = QTextStream(self._outSocket)
            self._outStream.setCodec('UTF-8')
            self.sendMessage('another instance was started')
        else:
            # No, there isn't.
            print "first instance running as %s" % self._id
            self._outSocket = None
            self._outStream = None
            self._inSocket = None
            self._inStream = None
            self._server = QLocalServer()
            self._server.removeServer(self._id)
            self._server.listen(self._id)
            self._server.newConnection.connect(self._onNewConnection)
            
    def isRunning(self):
        return self._isRunning

    def id(self):
        return self._id

    def sendMessage(self, msg):
        if not self._outStream:
            return False
        self._outStream << msg << '\n'
        self._outStream.flush()
        return self._outSocket.waitForBytesWritten()

    def _onNewConnection(self):
        if self._inSocket:
            self._inSocket.readyRead.disconnect(self._onReadyRead)
        self._inSocket = self._server.nextPendingConnection()
        if not self._inSocket:
            return
        self._inStream = QTextStream(self._inSocket)
        self._inStream.setCodec('UTF-8')
        self._inSocket.readyRead.connect(self._onReadyRead)

    def _onReadyRead(self):
        while True:
            msg = self._inStream.readLine()
            if not msg: break
            Communicator.getCommunicator().messageReceived.emit(msg)
      
class QApplicationSingleton(object):
    # # Stores the unique Singleton instance-
    _iInstance = None
    
    # # The constructor
    #  @param self The object pointer.
    def __init__(self, appid, args=[]):
        # Check whether we already have an instance
        if QApplicationSingleton._iInstance is None:
            # Create and remember instance
            QApplicationSingleton._iInstance = QSingleInstanceApplication(appid, args)

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

