"""GUI prompt to bind a new server"""
import os
from nxdrive.client import Unauthorized
from nxdrive.gui.resources import find_icon
from nxdrive.logging_config import get_logger
from nxdrive import Constants

log = get_logger(__name__)

# Keep QT an optional dependency for now
QtGui, QDialog = None, object
try:
    from PySide import QtGui
    QDialog = QtGui.QDialog
    log.debug("QT / PySide successfully imported")
except ImportError:
    log.warning("QT / PySide is not installed: GUI is disabled")
    pass


is_dialog_open = False


def find_icon(icon_filename):
    import nxdrive
    nxdrive_path = os.path.dirname(nxdrive.__file__)
    icons_path = os.path.join(nxdrive_path, 'data', 'icons')

    frozen_suffix = os.path.join('library.zip', 'nxdrive')
    if nxdrive_path.endswith(frozen_suffix):
        # Frozen distribution of nxdrive, data is out of the zip
        icons_path = nxdrive_path.replace(frozen_suffix, 'icons')

    if not os.path.exists(icons_path):
        raise IOError("Could not find the icons folder at: " + icons_path)

    icon_filepath = os.path.join(icons_path, icon_filename)
    if not os.path.exists(icon_filepath):
        raise IOError("Could not find icon file: " + icon_filepath)

    return icon_filepath


class Dialog(QDialog):
    """Dialog box to prompt the user for Server Bind credentials"""

    def __init__(self, fields_spec, title=None, fields_title=None,
                 callback=None, parent=None):
        super(Dialog, self).__init__(parent)
        if QtGui is None:
            raise RuntimeError("PySide is not installed.")

        self.setWindowIcon(QtGui.QIcon(Constants.APP_ICON_ENABLED))
        self.create_authentication_box(fields_spec)
        self.callback = callback
        buttonBox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok
                                           | QtGui.QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        mainLayout = QtGui.QVBoxLayout()
        mainLayout.addWidget(self.authentication_group_box)
        self.message_area = QtGui.QLabel()
        self.message_area.setWordWrap(True)
        mainLayout.addWidget(self.message_area)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)
        if title is not None:
            self.setWindowTitle(title)
#        icon = find_icon('nuxeo_drive_icon_64.png')
#        if icon is not None:
#            self.setWindowIcon(QtGui.QIcon(icon))
        self.resize(600, -1)
        self.accepted = False
        self.values = None

    def create_authentication_box(self, fields_spec):
        self.authentication_group_box = QtGui.QGroupBox()
        layout = QtGui.QGridLayout()
        self.fields = {}
        for i, spec in enumerate(fields_spec):
            label = QtGui.QLabel(spec['label'])
            line_edit = QtGui.QLineEdit()
            value = spec.get('value')
            if value is not None:
                line_edit.setText(value)
            if spec.get('is_password', False):
                line_edit.setEchoMode(QtGui.QLineEdit.Password)
            if spec.get('is_readonly', False):
                line_edit.setReadOnly(True)
            line_edit.textChanged.connect(self.clear_message)
            layout.addWidget(label, i + 1, 0)
            layout.addWidget(line_edit, i + 1, 1)
            self.fields[spec['id']] = line_edit

        self.authentication_group_box.setLayout(layout)

    def clear_message(self, *args, **kwargs):
        self.message_area.setText(None)

    def show_message(self, message):
        self.message_area.setText(message)

    def accept(self):
        if self.callback is not None:
            self.values = dict((id_, w.text())
                               for id_, w in self.fields.items())
            if not self.callback(self.values, self):
                return
        self.accepted = True
        super(Dialog, self).accept()

    def reject(self):
        super(Dialog, self).reject()


def prompt_authentication(controller, local_folder, url=None, username=None,
                          is_url_readonly=False, parent=None, app=None, update=True):
    """Prompt a QT dialog to ask for user credentials for binding a server"""
    global is_dialog_open

    if QtGui is None:
        # Qt / PySide is not installed
        log.error("QT / PySide is not installed:"
                  " use commandline options for binding a server.")
        return False

    if is_dialog_open:
        # Do not reopen the dialog multiple times
        return False

    # TODO: learn how to use QT i18n support to handle translation of labels
    fields_spec = [
        {
            'id': 'url',
            'label': 'Nuxeo Server URL:',
            'value': url,
            'is_readonly': is_url_readonly,
        },
        {
            'id': 'username',
            'label': 'Username:',
            'value': username,
        },
        {
            'id': 'password',
            'label': 'Password:',
            'is_password': True,
        },
    ]
    def bind_server(values, dialog):
        try:
            url = values['url']
            if not url:
                dialog.show_message("The Nuxeo server URL is required.")
                return False
            if (not url.startswith("http://")
                and not url.startswith('https://')):
                dialog.show_message("Not a valid HTTP url.")
                return False
            username = values['username']
            if not username:
                dialog.show_message("A user name is required")
                return False
            password = values['password']
            dialog.show_message("Connecting to %s ..." % url)
            if update:
                controller.bind_server(local_folder, url, username, password)
                #get federated token for CloudDesk
                
            else:
                controller.validate_credentials(url, username, password)
            return True
        except Unauthorized:
            dialog.show_message("Invalid credentials.")
            return False
        except:
            msg = "Unable to connect to " + url
            log.debug(msg, exc_info=True)
            # TODO: catch a new ServerUnreachable catching network isssues
            dialog.show_message(msg)
            return False

    if app is None:
        log.debug("Launching QT prompt for server binding.")
        from nxdrive.utils.helpers import QApplicationSingleton
        QApplicationSingleton()
#        QtGui.QApplication([])

    dialog = Dialog(fields_spec, title="%s Authentication" % Constants.APP_NAME,
                    callback=bind_server)
    is_dialog_open = True
    try:
        dialog.exec_()
    except:
        dialog.reject()
        raise
    finally:
        is_dialog_open = False
    return dialog.accepted, dialog.values

if __name__ == '__main__':
    from nxdrive.controller import Controller
    from nxdrive.controller import default_nuxeo_drive_folder
    ctl = Controller('/tmp')
    local_folder = default_nuxeo_drive_folder()
    print prompt_authentication(
        ctl, local_folder,
        url='http://localhost:8080/nuxeo',
        username='Administrator',
    )
