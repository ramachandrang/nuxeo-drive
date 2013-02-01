'''
Created on Oct 27, 2012

@author: mconstantin
'''

import sys
import os
import platform
import itertools
import webbrowser
import urllib

import PySide
from PySide import QtGui
from PySide import QtCore
from PySide.QtGui import QDialog, QMessageBox, QImage, QPainter, QIcon
from PySide.QtCore import QTimer

from nxdrive import Constants
from nxdrive.async.operations import SyncOperations
# from utils.helpers import Communicator, ProxyInfo, RecoverableError
from nxdrive.utils.helpers import Communicator, RecoverableError
# this import is flagged erroneously as unused import - do not remove
import nxdrive.gui.qrc_resources
from nxdrive.async.worker import Worker
from nxdrive.controller import default_nuxeo_drive_folder
from nxdrive.logging_config import get_logger
from nxdrive.utils.helpers import create_settings
from nxdrive.model import RecentFiles
from nxdrive.gui.proxy_dlg import ProxyDlg
from nxdrive.gui.preferences_dlg import PreferencesDlg

if sys.platform == 'win32':
    from nxdrive.protocol_handler import win32

settings = create_settings()

def default_expanded_nuxeo_drive_folder():
    return os.path.expanduser(DEFAULT_NX_DRIVE_FOLDER)

DEFAULT_NX_DRIVE_FOLDER = default_nuxeo_drive_folder()
DEFAULT_EX_NX_DRIVE_FOLDER = default_expanded_nuxeo_drive_folder()


log = get_logger(__name__)

def sync_loop(controller, **kwargs):
    """Wrapper to log uncaught exception in the sync thread"""
    try:
        controller.loop(**kwargs)
    except RecoverableError as e:
        frontend = kwargs['frontend']
        if frontend is not None:
            frontend.communicator.error.emit(e.text, e.info, e.buttons)

    except Exception as e:
        log.error("Error in synchronization thread: %s", e, exc_info = True)

        # Clean pid file
        pid = os.getpid()
        pid_filepath = controller._get_sync_pid_filepath()
        try:
            os.unlink(pid_filepath)
        except Exception, e:
            log.warning("Failed to remove stalled pid file: %s"
                    " for stopped process %d: %r",
                    pid_filepath, pid, e)
        # change app state to stopped
        frontend = kwargs['frontend']
        if frontend is not None:
            frontend.notify_sync_stopped()


class BindingInfo(object):
    """Summarize the state of each server connection"""

    _online = False
    _prev_online = False

    @property
    def online(self):
        return self._online

    @online.setter
    def online(self, value):
        self._prev_online = self._online
        self._online = value

    n_pending = 0
    has_more_pending = False

    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.short_name = os.path.basename(folder_path)

    def online_status_change(self):
        return self._online != self._prev_online

    def get_status_message(self):
        # TODO: i18n
        if self.online:
            if self.n_pending != 0:
                return "%d%s pending operations" % (
                    self.n_pending, '+' if self.has_more_pending else '')
            else:
                return "Up-to-date"
        else:
            return "Offline"

    def __str__(self):
        return "%s: %s" % (self.short_name, self.get_status_message())


class CloudDeskTray(QtGui.QSystemTrayIcon):
    def __init__(self, controller, options):
        super(CloudDeskTray, self).__init__()
        # this should be retrieved from persistence storage,
        # i.e. last used connection's local folder
        self.local_folder = DEFAULT_EX_NX_DRIVE_FOLDER
        self.controller = controller
        self.options = options
        self.communicator = Communicator()
        self.state = Constants.APP_STATE_STOPPED
        self.worker = None
        self.opInProgress = None
        self.quit_on_stop = False
        self.binding_info = {}
        self.setupMenu()
        self.setupMisc()
        self.update_running_icon()
        self.setToolTip('%s %s' % (Constants.APP_NAME, Constants.__version__))
        self.preferencesDlg = None
        if options.start:
            self.doWork()

    def setupMenu(self):
        self.menuCloudDesk = QtGui.QMenu()
        self.menuCloudDesk.setObjectName("self.menuCloudDesk")
        self.actionStatus = QtGui.QAction(self.tr("sync status"), self)
        self.actionStatus.setObjectName("actionStatus")
        self.actionCommand = QtGui.QAction(self.tr("action"), self)
        self.actionCommand.setObjectName("actionCommand")
        self.actionOpenCloudDeskFolder = QtGui.QAction(self.tr("Open %s Folder") % Constants.PRODUCT_NAME, self)
        self.actionOpenCloudDeskFolder.setObjectName("actionOpenCloudDeskFolder")
        self.actionShowCloudDeskInfo = QtGui.QAction(self.tr("Open %s Website") % Constants.PRODUCT_NAME, self)
        self.actionShowCloudDeskInfo.setObjectName("actionShowCloudDeskInfo")
        self.menuViewRecentFiles = QtGui.QMenu(self.tr("Recently Changed Files"), self.menuCloudDesk)
        self.menuViewRecentFiles.setObjectName("menuViewRecentFiles")
        self.actionUsername = QtGui.QAction(self.tr("login_name"), self)
        self.actionUsername.setObjectName("actionUsername")
        self.actionUsedStorage = QtGui.QAction(self.tr("used storage"), self)
        self.actionUsedStorage.setObjectName("actionUsedStorage")
        self.actionPreferences = QtGui.QAction(self.tr("Preferences..."), self)
        self.actionPreferences.setObjectName("actionPreferences")
        self.actionHelp = QtGui.QAction(self.tr("Help"), self)
        self.actionHelp.setObjectName("actionHelp")
        self.actionAbout = QtGui.QAction(self.tr("About"), self)
        self.actionAbout.setObjectName("actionAbout")
        # TO BE REMOVED - BEGIN
#        self.actionDebug = QtGui.QAction(self.tr("Debug"),self)
#        self.actionDebug.setObjectName("actionDebug")
        # TO BE REMOVED - END
        self.actionQuit = QtGui.QAction(self.tr("Quit %s") % Constants.APP_NAME, self)
        self.actionQuit.setObjectName("actionQuit")
        self.menuCloudDesk.addAction(self.actionStatus)
        self.menuCloudDesk.addAction(self.actionCommand)
        self.menuCloudDesk.addSeparator()
        self.menuCloudDesk.addAction(self.actionOpenCloudDeskFolder)
        self.menuCloudDesk.addAction(self.actionShowCloudDeskInfo)
        self.menuCloudDesk.addMenu(self.menuViewRecentFiles)
        self.menuCloudDesk.addSeparator()
        self.menuCloudDesk.addAction(self.actionUsername)
        self.menuCloudDesk.addAction(self.actionUsedStorage)
        self.menuCloudDesk.addSeparator()
        self.menuCloudDesk.addAction(self.actionPreferences)
        self.menuCloudDesk.addAction(self.actionHelp)
        self.menuCloudDesk.addAction(self.actionAbout)

        # TO BE REMOVED - BEGIN
#        self.menuCloudDesk.addSeparator()
#        self.menuCloudDesk.addAction(self.actionDebug)
        # TO BE REMOVED - END

        self.menuCloudDesk.addSeparator()
        self.menuCloudDesk.addAction(self.actionQuit)
        # this is just an indicator
        self.actionStatus.setEnabled(False)

    def setupMisc(self):
        self.setContextMenu(self.menuCloudDesk)
        self.actionQuit.triggered.connect(self.quit)
        self.menuCloudDesk.aboutToShow.connect(self.rebuild_menu)
        self.actionPreferences.triggered.connect(self.showPreferences)
        self.actionCommand.triggered.connect(self.doWork)
        self.actionAbout.triggered.connect(self.about)
        self.actionOpenCloudDeskFolder.triggered.connect(self.openLocalFolder)
        self.actionShowCloudDeskInfo.triggered.connect(self.openCloudDesk)
        self.messageClicked.connect(self.handle_message_clicked)

        # TO BE REMOVED - BEGIN
#        self.actionDebug.triggered.connect(self.debug_stuff)

        # copy to local binding
        for sb in self.controller.list_server_bindings():
            self.get_binding_info(sb.local_folder)
        # save current server binding
        self.server_binding = self.controller.get_server_binding(self._get_local_folder())

        # setup communication from worker thread to application
        self.communicator.icon.connect(self.set_icon_state)
        self.communicator.menu.connect(self.update_menu)
        self.communicator.stop.connect(self.handle_stop)
        self.communicator.message.connect(self.handle_message)
        self.communicator.invalid_credentials.connect(self.handle_invalid_credentials)
        self.communicator.invalid_proxy.connect(self.handle_invalid_proxy)
        self.communicator.error.connect(self.handle_recoverable_error)

        # Show 'up-to-date' notification message only once
        self.firsttime_pending_message = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._onTimer)
        self.startDelay = False
        self.stop = False
        self.proxyDlg = None

        if sys.platform == 'win32':
            # create the Favorites shortcut
            shortcut = os.path.join(os.path.expanduser('~'), 'Links', Constants.PRODUCT_NAME + '.lnk')
            win32.create_or_replace_shortcut(shortcut, self.local_folder)

            notifications = settings.value('preferences/notifications', 'true')
            if notifications.lower() == 'true':
                self.notifications = True
            elif notifications.lower() == 'false':
                self.notifications = False
            else:
                self.notifications = True
        else:
            self.notifications = settings.value('preferences/notifications', True)


    def debug_stuff(self):
        # this is not working on OS X
#        self.communicator.message.emit(self.tr("CloudDesk Authentication"),
#                               self.tr('Update credentials'),
#                               QtGui.QSystemTrayIcon.Critical)
        # For TEST ONLY
#        self.controller.get_folders()

        from folders_dlg import SyncFoldersDlg
        dlg = SyncFoldersDlg(frontend = self)
        if dlg.exec_() == QDialog.Rejected:
            return

    def about(self):
        msgbox = QMessageBox()
        msgbox.setText(self.tr("About %s") % Constants.APP_NAME)
        msgbox.setStandardButtons(QMessageBox.Ok)
        msgbox.setInformativeText("""version<b>%s</b>
                <p>Copyright &copy; 2012 SHARP CORPORATION
                All Rights Reserved.
                <p>Platform Details: %s</p>
                <p style="font-size: small">Python %s</p>
                <p style="font-size: small">PySide %s</p>
                <p style="font-size: small">Qt %s</p>""" % (Constants.__version__, platform.system(),
                            platform.python_version(), PySide.__version__, QtCore.__version__))
        icon = QIcon(Constants.APP_ICON_ABOUT)
        msgbox.setIconPixmap(icon.pixmap(48, 48))
        msgbox.setDetailedText(open(Constants.COPYRIGHT_FILE).read())
        msgbox.setDefaultButton(QMessageBox.Ok)
        msgbox.exec_()

    def handle_recoverable_error(self, text, info, buttons):
        mbox = QMessageBox(QMessageBox.Critical, self.tr("CloudDesk Error"), text)
        if buttons is not None:
            mbox.setStandardButtons(buttons)
        mbox.setInformativeText(info)
        mbox.exec_()

    def get_info(self, local_folder):
        info = self.binding_info.get(local_folder, None)
        if info is None:
            info = BindingInfo(local_folder)
            self.binding_info[local_folder] = info
        return info

    def get_binding_info(self, local_folder):
        if local_folder not in self.binding_info:
            self.binding_info[local_folder] = BindingInfo(local_folder)
        return self.binding_info[local_folder]

    def _get_local_folder(self):
        # verify that a binding still exists for the local folder
        binding = self.controller.get_server_binding(self.local_folder, raise_if_missing = False)
        if binding is None:
            # get the 'first' existing binding, if any
            binding = self.controller.get_server_binding()
            self.local_folder = binding.local_folder if binding is not None else DEFAULT_EX_NX_DRIVE_FOLDER

        return self.local_folder

    def openLocalFolder(self):
        self.controller.open_local_file(self._get_local_folder())

    def openCloudDesk(self):
        # TODO Alternative solution to use for opening the site: keep the password (encrypt?)
#        fdtoken = self.controller.get_browser_token(self.local_folder)
#        if fdtoken is None:
#            fdtoken = ''
        server_binding = self.controller.get_server_binding(self.local_folder)
#        pwd = decrypt_password(server_binding.remote_password, server_binding.password_key)
        try:
            new = 2  # open in a new tab if possible
            url = server_binding.server_url
            if url[-1] != '/': url += '/'
#            query_params = {
#                            'user_name': '<SharpToken>',
#                            'user_password': fdtoken,
#                            'language': 'en_US',
#                            'requestedUrl': '',
#                            'form_submitted_marker': '',
#                            'Submit': 'Log in'
#                            }
            query_params = {
                            'user_name': server_binding.remote_user,
                            'user_password': pwd,
                            'language': 'en_US',
                            'requestedUrl': '',
                            'form_submitted_marker': '',
                            'Submit': 'Log in'
                            }

            url += 'nxstartup.faces?' + urllib.urlencode(query_params)
            webbrowser.open(url, new = new)
        except Exception as e:
            log.error('failed to open CloudDesk at %s: %s', server_binding.server_url, str(e))


    @QtCore.Slot(str)
    def set_icon_state(self, state):
        """Execute systray icon change operations triggered by state change
        The synchronization thread can update the state info but cannot
        directly call QtGui widget methods. The should be executed by the main
        thread event loop, hence the delegation to this method that is
        triggered by a signal to allow for message passing between the 2
        threads.
        Return True of the icon has changed state.
        """
        if self.get_icon_state() == state:
            # Nothing to update
            return False

        try:
            handler = getattr(self, '_set_icon_%s' % state, None)
            if handler is None:
                log.warning('Icon not found for: %s', state)
                return False

            handler()
            self._icon_state = state
            return True
        except Exception as ex:
            log.debug("set_icon_state(%s) error: %s" % (state, str(ex)))
            return False

    def get_icon_state(self):
        return getattr(self, '_icon_state', None)

    def _set_icon_enabled(self):
        self.setIcon(QIcon(Constants.APP_ICON_ENABLED))

    def _set_icon_paused(self):
        self.setIcon(QIcon(Constants.APP_ICON_PAUSED))

    def _set_icon_disabled(self):
        self.setIcon(QIcon(Constants.APP_ICON_DISABLED))

    def _set_icon_stopping(self):
        self.setIcon(QIcon(Constants.APP_ICON_STOPPING))

    def _set_icon_enabled_start(self):
        assert not self.startDelay
        assert not self.stop
        QTimer.singleShot(Constants.ICON_ANIMATION_START_DELAY, self._onTimerDelay)
        self.startDelay = True

    def _set_icon_enabled_stop(self):
        if self.startDelay:
            self.stop = True
        else:
            self.timer.stop()
            self._set_icon_enabled()

    def _set_icon_enabled_pause(self):
        if self.startDelay:
            self.stop = True
        else:
            self.timer.stop()
            self._set_icon_paused()

    def _startAnimationDelay(self):
        assert not self.startDelay
        assert not self.stop
        QTimer.singleShot(Constants.ICON_ANIMATION_START_DELAY, self._onTimerDelay)
        self.startDelay = True

    def _startAnimation(self):
        assert not self.startDelay  # this shouldn't happen, delay is reset before
        self.timer.start(Constants.ICON_ANIMATION_DELAY)
        self.iterator = itertools.cycle('2341')

    def _onTimerDelay(self):
        assert self.startDelay
        self.startDelay = False
        if self.stop:
            # stopped before delay elapsed, do not start animation
            self.stop = False
            return

        self._startAnimation()

    def _onTimer(self):
        assert not self.startDelay  # this should not happen, actions are sequential
        assert not self.stop  # this should not happen outside a delay

#        iconBase = QImage(':/menubar_icon.png')
#        iconOverlay = QImage(Constants.APP_ICON_PATTERN % (self.iterator.next()))
#        icon = QIcon(QPixmap.fromImage(self._createImageWithOverlay(iconBase, iconOverlay)))
        # not using overlays
        icon = QIcon(Constants.APP_ICON_PATTERN_ANIMATION % ('transferring', self.iterator.next()))
        self.setIcon(icon)

    def update_running_icon(self):
        if self.state != Constants.APP_STATE_RUNNING:
            self.communicator.icon.emit('disabled')
            return
        infos = self.binding_info.values()
        if len(infos) > 0 and any(i.online for i in infos):
            self.communicator.icon.emit('enabled')
        else:
            self.communicator.icon.emit('disabled')

    def notify_sync_started(self):
        """Called from controller when the sync thread target (controller.loop) starts"""
        log.debug('Synchronization started')
        self.state = Constants.APP_STATE_RUNNING
#        self.communicator.menu.emit()
        self.update_running_icon()

    def notify_sync_stopped(self):
        """Called from controller when the thread target (controller.loop) ends"""
        log.debug('Synchronization stopped')
        self.notify_stop_transfer()
        self.state = Constants.APP_STATE_STOPPED
        self.worker = None
        self.update_running_icon()
#        self.communicator.menu.emit()
        self.communicator.stop.emit()

    def notify_offline(self, local_folder, exception):
        info = self.get_info(local_folder)
        code = getattr(exception, 'code', None)
        if info.online:
            # Mark binding as offline and update UI
            log.debug('Switching to offline mode (code = %r) for: %s',
                      code, local_folder)
            info.online = False
            self.update_running_icon()
            self.communicator.menu.emit()

        if code == 401 or code == 403:
            log.debug('Detected invalid credentials for: %s', local_folder)
            self.communicator.invalid_credentials.emit(local_folder)

        elif code == 61 or code == 600 or code == 601:
            text = getattr(exception, 'text', None)
            msg = 'Detected invalid proxy server settings' + '' if text is None else ': %s' % text
            log.debug(msg)
            self.communicator.invalid_proxy.emit(msg)

    def notify_pending(self, local_folder, n_pending, or_more = False):
        if self.state == Constants.APP_STATE_QUITTING:
            return

        info = self.get_info(local_folder)
        if n_pending != info.n_pending:
            log.debug("%d pending operations for: %s", n_pending, local_folder)
        # Update pending stats
        info.n_pending = n_pending
        info.has_more_pending = or_more

        if not info.online:
            log.debug("Switching to online mode for: %s", local_folder)
            # Mark binding as online and update UI
            info.online = True
            self.update_running_icon()
            self.communicator.menu.emit()

    def notify_pending_details(self, status):
        """NOT USED"""
        if self.state == Constants.APP_STATE_QUITTING:
            return

        local_folder = self._get_local_folder()

        if len(status) == 0: return
        added = filter(lambda (x, y, z): x == local_folder and y == u'locally_created', status)[0][2]
        modified = filter(lambda (x, y, z): x == local_folder and y == u'locally_modified', status)[0][2]
        deleted = filter(lambda (x, y, z): x == local_folder and y == u'locally_deleted', status)[0][2]
        conflicted = filter(lambda (x, y, z): x == local_folder and y == u'conflicted', status)[0][2]

        if modified == 0 and added == 0 and deleted == 0 and conflicted == 0: return

        if modified > 1: msg = '%d files modified' % modified
        elif modified > 0: msg = '%d file modified' % modified
        else: msg = ''

        msg1 = '%d file%s added' if modified == 0 else ', %d added'
        msg += msg1 % added if added > 0 else ''

        msg1 = msg1 = '%d file%s deleted' if modified == 0 and added == 0 else ', %d deleted'
        msg += msg1 % deleted if deleted > 0 else ''

        msg1 = '%d file%s conflicted' if modified == 0 and added == 0 and deleted == 0 else ', %d conflicted'
        msg += msg1 % conflicted if conflicted > 0 else ''

        # show message notification
        self.communicator.message.emit(Constants.APP_NAME,
                                       msg,
                                       QtGui.QSystemTrayIcon.Information)

    def notify_sync_completed(self, status):
        """Update menu and create a notification message"""
        if self.state == Constants.APP_STATE_QUITTING:
            return

        self.communicator.menu.emit()

        if not status: return
        multiple_pattern = {u'remotely_created':'%d%s%s added', u'remotely_modified':'%d%s%s updated', u'remotely_deleted':'%d%s%s deleted', u'conflicted':'%d%s%s conflicted' }
        single_pattern = {u'remotely_created':'%s added', u'remotely_modified':'%s updated', u'remotely_deleted':'%s deleted', u'conflicted':'%s conflicted' }
        msg = ''

#        nonzero_items = dict(filter(lambda (k,v): v[0] > 0, status.iteritems()))
#        allzero_items = [(k,v) for (k,v) in status.iteritems() if v[0] == 0]
        allone_items = [(k, v) for (k, v) in status.iteritems() if len(v) == 1]

#        if len(allzero_items) + len(allone_items) == len(status) and len(allone_items) == 1:
        if len(allone_items) == len(status) and len(allone_items) == 1:
            # only 1 file present
            k, fn = allone_items[0][0], allone_items[0][1][0]
            try:
                msg = single_pattern[k] % fn
            except KeyError:
                return
        else:
            l = []; i = 0
            for k in status.keys():
                try:
                    l.append(multiple_pattern[k] % (len(status[k]), ' file' if i == 0 else '', 's' if i == 0 and len(status[k]) > 1 else ''))
                    i += 1
                except KeyError:
                    continue

            msg = ', '.join(l)

        if len(msg) == 0: return

        # show message notification
        self.communicator.message.emit(Constants.APP_NAME,
                                       msg,
                                       QtGui.QSystemTrayIcon.Information)


    def notify_start_transfer(self):
        if self.state != Constants.APP_STATE_QUITTING:
            self.communicator.icon.emit('enabled_start')

    def notify_stop_transfer(self):
        if self.state != Constants.APP_STATE_QUITTING:
            self.communicator.icon.emit('enabled_stop')

    def notify_pause_transfer(self):
        if self.state != Constants.APP_STATE_QUITTING:
            self.communicator.icon.emit('enabled_pause')

    def notify_local_folders(self, local_folders):
        """Cleanup unbound server bindings if any"""

        if self.state == Constants.APP_STATE_QUITTING:
            return

        refresh = False
        for registered_folder in self.binding_info.keys():
            if registered_folder not in local_folders:
                del self.binding_info[registered_folder]
                refresh = True
        for local_folder in local_folders:
            if local_folder not in self.binding_info:
                self.binding_info[local_folder] = BindingInfo(local_folder)
                refresh = True
        if refresh:
            log.debug(u'Detected changes in the list of local folders: %s',
                      u", ".join(local_folders))
            self.communicator.menu.emit()
            self.update_running_icon()

    def notify_folders_changed(self):
        if self.state != Constants.APP_STATE_QUITTING:
            self.communicator.folders.emit()

    def quit(self):
        if self.state != Constants.APP_STATE_QUITTING:
            self.state = Constants.APP_STATE_QUITTING
            self.quit_on_stop = True
            self.communicator.menu.emit()

        if self.state != Constants.APP_STATE_STOPPED:
            self.communicator.icon.emit('stopping')

        if self.worker is not None and self.worker.isAlive():
            # Ask the controller to stop: the synchronization loop will in turn
            # call notify_sync_stopped and finally handle_stop
            self.controller.stop()
            if self.worker.isPaused():
                self._resumeSync()
        else:
            # quit directly
            QtGui.QApplication.quit()

    def rebuild_menu(self):
        """update when menu is activated"""
        self.actionUsername.setText(self._getUserName())
        # TO DO retrieve storage used
        self.actionUsedStorage.setText("123Mb (0.03%) of 4Gb")

        self.actionShowCloudDeskInfo.setEnabled(len(self.binding_info.values()) > 0)
        self.actionStatus.setText(self._syncStatus())
        self.actionCommand.setText(self._syncCommand())
        self.actionOpenCloudDeskFolder.setText('Open %s Folder' % os.path.basename(self._get_local_folder()))
        self.actionQuit.setEnabled(self.state != Constants.APP_STATE_QUITTING)

        self.menuViewRecentFiles.clear()
        session = self.controller.get_session()
        recent_files = session.query(RecentFiles).all()
        for recent_file in recent_files:
            open_folder = lambda: self.controller.open_local_file(recent_file.local_root)
            file_msg = recent_file.local_name
            open_folder_action = QtGui.QAction(
                file_msg, self.menuViewRecentFiles, triggered = open_folder)
            # TODO setEnabled(False) does not work!!
            if recent_file.pair_state == 'remotely_deleted' or recent_file.pair_state == 'deleted':
                open_folder_action.setVisible(False)
            self.menuViewRecentFiles.addAction(open_folder_action)

    def update_menu(self):
        pass

    def showPreferences(self):
        if self.preferencesDlg is not None:
            return

        self.preferencesDlg = PreferencesDlg(frontend = self)
        if self.preferencesDlg.exec_() == QDialog.Rejected:
            self.preferencesDlg = None
            return

        self.notifications = self.preferencesDlg.notifications
        self.preferencesDlg = None

        # copy to local binding
        self.binding_info.clear()
        for sb in self.controller.list_server_bindings():
            # assume online until connecting to server proves otherwise
            self.get_binding_info(sb.local_folder).online = True


    def setupProcessing(self):
        self.opInProgress = SyncOperations()

        if self.worker is None or not self.worker.isAlive():
            fault_tolerant = not getattr(self.options, 'stop_on_error', True)
            delay = getattr(self.options, 'delay', 5.0)
            # Controller and its database session pool should be thread safe,
            # hence reuse it directly
            self.worker = Worker(self.opInProgress,
                                 target = sync_loop,
                                 args = (self.controller,),
                                 kvargs = {"frontend": self,
                                         "fault_tolerant": fault_tolerant,
                                         "delay": delay})

        self.worker.start()

    def _syncCommand(self):
        infos = self.binding_info.values()
        if len(infos) == 0:
            self.actionCommand.setEnabled(True)
            return self.tr("Start")
        elif self.state == Constants.APP_STATE_STOPPED:
            self.actionCommand.setEnabled(True)
            return self.tr("Start")
        elif self.state == Constants.APP_STATE_QUITTING:
            self.actionCommand.setEnabled(False)
            return self.tr("Start")
        elif self.state == Constants.APP_STATE_RUNNING and self.worker.isPaused():
            self.actionCommand.setEnabled(True)
            return self.tr("Resume")
        elif self.state == Constants.APP_STATE_RUNNING and self.worker.isPausing():
            self.actionCommand.setEnabled(False)
            return self.tr("Resume")
        elif self.state == Constants.APP_STATE_RUNNING:
            self.actionCommand.setEnabled(any(i.online for i in infos))
            return self.tr("Pause")

    def _syncStatus(self):
        infos = self.binding_info.values()
        if len(infos) == 0:
            return self.tr("Not connected")
        if len(infos) > 0 and all(not i.online for i in infos):
            return self.tr("Off-line")
        elif (self.state == Constants.APP_STATE_STOPPED):
            return self.tr("Completed")
        elif self.state == Constants.APP_STATE_RUNNING and self.worker.isPaused():
            return self.tr("Paused")
        elif self.state == Constants.APP_STATE_RUNNING and self.worker.isPausing():
            return self.tr("Pausing")
        elif self.state == Constants.APP_STATE_RUNNING:
            return self.tr("Running")
        elif self.state == Constants.APP_STATE_QUITTING:
            return self.tr('Quitting...')

    def doWork(self):
        if self.state == Constants.APP_STATE_STOPPED:
            self._doSync()
        elif self.state == Constants.APP_STATE_QUITTING:
            return
        elif (not self.worker.isPaused()):
            self._pauseSync()
        else:
            self._resumeSync()


    def _doSync(self):
        if len(self.controller.list_server_bindings()) == 0:
            # Launch the GUI to create a binding
            from nxdrive.gui.authentication import prompt_authentication
            result = prompt_authentication(self.controller, DEFAULT_NX_DRIVE_FOLDER,
                                       url = Constants.DEFAULT_CLOUDDESK_URL,
                                       username = Constants.DEFAULT_ACCOUNT)
            ok = result[0]
            if not ok: return

        self.setupProcessing()

    def started(self):
        self.actionCommand.setText("Pause")
        self.actionStatus.setText("Syncing")

    def finished(self):
        self.opInProgress = None
        self.worker = None
        self.actionCommand.setText("Start")
        self.actionStatus.setText("Completed")

    def _pauseSync(self):
        self.worker.pause()

    def _resumeSync(self):
        self.worker.resume()

    @QtCore.Slot()
    def handle_stop(self):
        if self.quit_on_stop:
            log.info("application quit.")
            self.quit()

    @QtCore.Slot(str)
    def handle_invalid_credentials(self, local_folder):
        sb = self.controller.get_server_binding(local_folder, raise_if_missing = False)
        # menu is updated when is activated
#        self.communicator.menu.emit()
        # show a notification
        for_server = '' if sb is None else ' for server: %s' % sb.server_url
        detail = 'Update credentials%s' % for_server
        self.handle_message(self.tr("%s Authentication") % Constants.APP_NAME,
                           detail,
                           QtGui.QSystemTrayIcon.Critical)

        # clicking on the message notification is not working on the Mac
        if sys.platform == 'darwin':
            if not self.get_binding_info(self.local_folder).online:
                # Launch the GUI to create a binding
                from nxdrive.gui.authentication import prompt_authentication
                server_binding = self.controller.get_server_binding(self.local_folder, raise_if_missing = False)
                success = prompt_authentication(self.controller, self.local_folder,
                                       url = server_binding.server_url,
                                       username = server_binding.remote_user)

                if success:
                    self.doWork()

    @QtCore.Slot()
    def handle_invalid_proxy(self, message):
        self.handle_message(self.tr("%s Configuration") % Constants.APP_NAME,
                           message,
                           QtGui.QSystemTrayIcon.Critical)
        if self.proxyDlg is None:
            self.proxyDlg = ProxyDlg(frontend = self)
            self.proxyDlg.exec_()
            self.proxyDlg = None

    @QtCore.Slot(str, str, QtGui.QSystemTrayIcon.MessageIcon)
    def handle_message(self, title, message, icon_type):
        if self.notifications:
            self.showMessage(title, message, icon_type, Constants.NOTIFICATION_MESSAGE_DELAY * 1000)

    def handle_message_clicked(self):
        # handle only the click for entering credentials
        if not self.get_binding_info(self.local_folder).online:
            # Launch the GUI to create a binding
            from nxdrive.gui.authentication import prompt_authentication
            server_binding = self.controller.get_server_binding(self.local_folder, raise_if_missing = False)
            success = prompt_authentication(self.controller, self.local_folder,
                                   url = server_binding.server_url,
                                   username = server_binding.remote_user)

            if success[0]:
                self.doWork()

    def _getUserName(self):
#        local_folder = default_nuxeo_drive_folder()
#        local_folder = os.path.abspath(os.path.expanduser(local_folder))
        server_binding = self.controller.get_server_binding(self.local_folder, raise_if_missing = False)
        return server_binding.remote_user if not server_binding == None else Constants.DEFAULT_ACCOUNT

    def _createImageWithOverlay(self, baseImage, overlayImage):
        imageWithOverlay = QImage(baseImage.size(), QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(imageWithOverlay)

        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(imageWithOverlay.rect(), QtCore.Qt.transparent)

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(0, 0, baseImage)

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        baseRect = baseImage.rect()
        overlayRect = overlayImage.rect()
        painter.drawImage(baseRect.width() - overlayRect.width(), baseRect.height() - overlayRect.height(), overlayImage)

        painter.end()
        return imageWithOverlay


from nxdrive.utils.helpers import QApplicationSingleton

def startApp(controller, options):
    app = QApplicationSingleton()
    app.setQuitOnLastWindowClosed(False)
    i = CloudDeskTray(controller, options)
    i.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(startApp)
