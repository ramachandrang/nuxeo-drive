"""Utilities to operate Nuxeo Drive from the command line"""
import os
import sys
import argparse
from getpass import getpass
import traceback

from nxdrive.controller import Controller
from nxdrive.daemon import daemonize
from nxdrive.logging_config import configure
from nxdrive.logging_config import get_logger
from nxdrive.protocol_handler import parse_protocol_url
from nxdrive.protocol_handler import register_protocol_handlers
from nxdrive.utils import register_startup
from nxdrive.utils import create_settings
from nxdrive import Constants
from nxdrive.controller import default_nuxeo_drive_folder
from sqlalchemy.pool import SingletonThreadPool

try:
    import ipdb
    debugger = ipdb
except ImportError:
    import pdb
    debugger = pdb

if sys.platform == 'win32':
    import win32api
    import win32con

settings = create_settings()

DEFAULT_NX_DRIVE_FOLDER = default_nuxeo_drive_folder()
DEFAULT_DELAY = 5.0
USAGE = """ndrive [command]

If no command is provided, the graphical application is started along with a
synchronization process.

Possible commands:
- version
- console
- start
- stop
- bind-server
- unbind-server
- bind-root
- unbind-root
- gui
- wizard
- com

To get options for a specific command:

  ndrive command --help

"""

PROTOCOL_COMMANDS = {
    'nxdriveedit': 'edit',
    'nxdrivebind': 'bind_server',
}

# FOR DEBUGGING ONLY
DEBUGGING = 1


def make_cli_parser(add_subparsers = True):
    """Parse commandline arguments using a git-like subcommands scheme"""

    common_parser = argparse.ArgumentParser(
        add_help = False,
    )
    
    common_parser.add_argument(
        "--version", "-v",
        action = 'store_true',
        default = False,
        help = _("print the program version.")
    )
        
    common_parser.add_argument(
        "--nxdrive-home",
        default = "~/.nuxeo-drive",
        help = _("Folder to store the %s configuration.") % Constants.APP_NAME
    )
    common_parser.add_argument(
        "--log-level-file",
        default = "DEBUG",
        help = _("Minimum log level for the file log (under NXDRIVE_HOME/logs).")
    )
    common_parser.add_argument(
        "--log-level-console",
        default = "INFO",
        help = _("Minimum log level for the console log.")
    )
    common_parser.add_argument(
        "--log-filename",
        help = _("File used to store the logs, default "
              "NXDRIVE_HOME/logs/nxaudit.logs")
    )
    common_parser.add_argument(
        "--debug", default = False, action = "store_true",
        help = _("Fire a debugger (ipdb or pdb) on uncaught error.")
    )
    common_parser.add_argument(
        "--delay", default = DEFAULT_DELAY, type = float,
        help = _("Delay in seconds between consecutive sync operations.")
    )
    common_parser.add_argument(
        # XXX: Make it true by default as the fault tolerant mode is not yet
        # implemented
        "--stop-on-error", default = True, action = "store_true",
        help = _("Stop the process on first unexpected error."
        "Useful for developers and Continuous Integration.")
    )

    common_parser.add_argument(
        '--start', '-s', action = 'store_true', help = _('start synchronization as soon as the gui starts.'))

    parser = argparse.ArgumentParser(
        parents = [common_parser],
        description = _("Command line interface for %s operations.") % Constants.APP_NAME,
        usage = USAGE,
    )

    if not add_subparsers:
        return parser

    subparsers = parser.add_subparsers(
        title = 'Commands',
    )

    # Link to a remote Nuxeo server
    bind_server_parser = subparsers.add_parser(
        'bind-server', help = 'Attach a local folder to a %s server.' % Constants.PRODUCT_NAME,
        parents = [common_parser],
    )
    bind_server_parser.set_defaults(command = 'bind_server')
    bind_server_parser.add_argument(
        "--password", help = _("Password for the %s account") % Constants.PRODUCT_NAME)
    bind_server_parser.add_argument(
        "--local-folder",
        help = _("Local folder that will host the list of synchronized"
        " workspaces with a remote %s server.") % Constants.PRODUCT_NAME,
        default = DEFAULT_NX_DRIVE_FOLDER,
    )
    bind_server_parser.add_argument(
        "username", help = _("User account to connect to %s") % Constants.PRODUCT_NAME)
    bind_server_parser.add_argument("nuxeo_url",
                                    help = _("URL of the %s server.") % Constants.PRODUCT_NAME)
    bind_server_parser.add_argument(
        "--remote-roots", nargs = "*", default = [],
        help = _("Path synchronization roots (reference or path for"
        " folderish %s documents such as Workspaces or Folders).") % Constants.PRODUCT_NAME)
    bind_server_parser.add_argument(
        "--remote-repo", default = 'default',
        help = _("Name of the remote repository.")
        )

    # Unlink from a remote Nuxeo server
    unbind_server_parser = subparsers.add_parser(
        'unbind-server', help = 'Detach from a remote %s server.' % Constants.PRODUCT_NAME,
        parents = [common_parser],
    )
    unbind_server_parser.set_defaults(command = 'unbind_server')
    unbind_server_parser.add_argument(
        "--local-folder",
        help = _("Local folder that hosts the list of synchronized"
        " workspaces with a remote %s server.") % Constants.PRODUCT_NAME,
        default = DEFAULT_NX_DRIVE_FOLDER,
    )

    # Bind root folders
    bind_root_parser = subparsers.add_parser(
        'bind-root',
        help = _('Attach a local folder as a root for synchronization.'),
        parents = [common_parser],
    )
    bind_root_parser.set_defaults(command = 'bind_root')
    bind_root_parser.add_argument(
        "remote_root",
        help = _("Remote path or id reference of a folder to synchronize.")
    )
    bind_root_parser.add_argument(
        "--local-folder",
        help = _("Local folder that will host the list of synchronized"
        " workspaces with a remote %s server. Must be bound with the"
        " 'bind-server' command.") % Constants.PRODUCT_NAME,
        default = DEFAULT_NX_DRIVE_FOLDER,
    )
    bind_root_parser.add_argument(
        "--remote-repo", default = 'default',
        help = _("Name of the remote repository.")
    )

    # Unlink from a remote Nuxeo root
    unbind_root_parser = subparsers.add_parser(
        'unbind-root', help = 'Detach from a remote %s root.' % Constants.PRODUCT_NAME,
        parents = [common_parser],
    )
    unbind_root_parser.set_defaults(command = 'unbind_root')
    unbind_root_parser.add_argument(
        "local_root", help = _("Local sub-folder to de-synchronize.")
    )

    # Start / Stop the synchronization daemon
    start_parser = subparsers.add_parser(
        'start', help = _('Start the synchronization as a GUI-less daemon'),
        parents = [common_parser],
    )
    start_parser.set_defaults(command = 'start')
    stop_parser = subparsers.add_parser(
        'stop', help = _('Stop the synchronization daemon'),
        parents = [common_parser],
    )
    stop_parser.set_defaults(command = 'stop')
    console_parser = subparsers.add_parser(
        'console',
        help = _('Start a GUI-less synchronization without detaching the process.'),
        parents = [common_parser],
    )
    console_parser.set_defaults(command = 'console')

    status_parser = subparsers.add_parser(
        'status',
        help = _('Fetch the status info of the children of a given folder.'),
        parents = [common_parser],
    )
    status_parser.set_defaults(command = 'status')
    status_parser.add_argument(
        "folder", help = _("Path to a local Nuxeo Drive folder.")
    )

    gui_parser = subparsers.add_parser(
        'gui',
        help = _('Start as a TrayIcon application.'),
        parents = [common_parser],
    )
    gui_parser.set_defaults(command = 'gui')

    com_parser = subparsers.add_parser(
        'com',
        help = _("Register or Unregister the COM Local Server"),
    )

    if sys.platform == 'win32':
        com_parser.set_defaults(command = 'com')
        action = com_parser.add_mutually_exclusive_group(required = True)
        action.add_argument(
            '--register', required = False, action = 'store_true', help = _('Register COM Local Server')
        )
        action.add_argument(
            '--unregister', required = False, action = 'store_true', help = _('Unregister COM Local Server')
        )

    # embedded test runner base on nose:
    test_parser = subparsers.add_parser(
        'test',
        help = _('Run the %s test suite.') % Constants.APP_NAME,
        parents = [common_parser],
    )

    wizard_parser = subparsers.add_parser(
        'wizard',
        help = _('Run the wizard.'),
        parents = [common_parser],
    )
    wizard_parser.set_defaults(command = 'wizard')

    switch_parser = subparsers.add_parser(
        'switch',
        help = _('Switch between wizard and normal mode, when launching the app with no command')
    )
    mode = switch_parser.add_mutually_exclusive_group(required = True)
    switch_parser.set_defaults(command = 'switch')
    mode.add_argument(
        '--wizard', '-w', required = False, action = 'store_true', default = False)
    mode.add_argument(
        '--normal', '-n', required = False, action = 'store_true', default = False)

    test_parser.set_defaults(command = 'test')
    test_parser.add_argument(
        "--with-coverage", default = False, action = "store_true",
        help = _("Compute coverage report.")
    )
    test_parser.add_argument(
        "--with-profile", default = False, action = "store_true",
        help = _("Compute profiling report.")
    )
    return parser


class CliHandler(object):
    """Command Line Interface handler: parse options and execute operation"""


    def parse_cli(self, argv):
        """Parse the command line argument using argparse and protocol URL"""
        # Filter psn argument provided by OSX .app service launcher
        # https://developer.apple.com/library/mac/documentation/Carbon/Reference/LaunchServicesReference/LaunchServicesReference.pdf
        # When run from the .app bundle generated with py2app with
        # argv_emulation=True this is already filtered out but we keep it
        # for running CLI from the source folder in development.
        argv = [a for a in argv if not a.startswith("-psn_")]

        # Preprocess the args to detect protocol handler calls and be more
        # tolerant to missing subcommand
        has_command = False
        protocol_url = None

        filtered_args = []
        for arg in argv[1:]:
            if arg.startswith('nxdrive://'):
                protocol_url = arg
                continue
            if not arg.startswith('-'):
                has_command = True
            filtered_args.append(arg)

        parser = make_cli_parser(add_subparsers = has_command)
        options = parser.parse_args(filtered_args)
        if options.debug:
            # Install Post-Mortem debugger hook

            def info(type, value, tb):
                traceback.print_exception(type, value, tb)
                print
                debugger.pm()

            sys.excepthook = info

        # Merge any protocol info into the other parsed commandline
        # parameters
        if protocol_url is not None:
            protocol_info = parse_protocol_url(protocol_url)
            for k, v in protocol_info.items():
                setattr(options, k, v)

        return options

    def _configure_logger(self, options):
        """Configure the logging framework from the provided options"""
        filename = options.log_filename
        if filename is None:
            filename = os.path.join(
                options.nxdrive_home, 'logs', 'nxdrive.log')

        configure(
            filename,
            file_level = options.log_level_file,
            console_level = options.log_level_console,
            command_name = options.command,
        )

    def looper(self, options = None):
        def wrapper(operation):
            delay = getattr(options, 'delay', DEFAULT_DELAY)
            return self.controller.loop(delay = delay, sync_operation = operation)
        return wrapper

    def handle(self, argv):
        """Parse options, setup logs and controller and dispatch execution."""
        options = self.parse_cli(argv)
        # 'start' is the default command if None is provided
        command = options.command = getattr(options, 'command', 'launch')

        # Configure the logging framework
        self._configure_logger(options)

        # Initialize a controller for this process
        self.controller = Controller.getController(options.nxdrive_home, poolclass = SingletonThreadPool)

        # Find the command to execute based on the
        handler = getattr(self, command, None)
        if handler is None:
            raise NotImplementedError(
                'No handler implemented for command ' + options.command)

        self.log = get_logger(__name__)
        self.log.debug("Command line: " + ' '.join(argv))

        if command == 'launch':
            # Ensure that the protocol handler are registered:
            # this is useful for the edit / open link in the Nuxeo interface
            register_protocol_handlers(self.controller)
            # Ensure that ndrive is registered as a startup application
            register_startup(True)
        try:
            return handler(options)
        except Exception, e:
            if options.debug:
                # Make it possible to use the postmortem debugger
                raise
            else:
                self.log.error("Error executing '%s': %s", command, e,
                          exc_info = True)

    def launch(self, options = None):
        """Launch the QT app in the main thread and sync in another thread."""

        if options.version:
            from nxdrive._version import __version__
            return __version__
        
        # check is in wizard mode
        wizard_mode = settings.value('wizard', 'true')
        if sys.platform == 'win32':
            if wizard_mode.lower() == 'true':
                wizard_mode = True
            elif wizard_mode.lower() == 'false':
                wizard_mode = False
            else:
                wizard_mode = True

        if wizard_mode:
            self.wizard(options)
        else:
            options.start = True
            self.gui(options)

    def gui(self, options = None):
        from nxdrive.gui.menubar import startApp
        result = startApp(self.controller, options)
        return result

    def wizard(self, options = None):
        from nxdrive.gui.wizard import startWizard
        return startWizard(self.controller, options)

    def switch(self, options = None):
        if options.wizard:
            settings.setValue('wizard', True)
        elif options.normal:
            settings.setValue('wizard', False)

    def start(self, options = None):
        """Launch the synchronization in a daemonized process (under POSIX)"""
        # Close DB connections before Daemonization
        self.controller.dispose()
        daemonize()

        self.controller = Controller(options.nxdrive_home)
        self._configure_logger(options)
        self.log.debug("Synchronization daemon started.")
        self.controller.synchronizer.loop(
            delay = getattr(options, 'delay', DEFAULT_DELAY))
        return 0

    def console(self, options):
        fault_tolerant = not getattr(options, 'stop_on_error', True)
        self.controller.synchronizer.loop(delay = getattr(options, 'delay', DEFAULT_DELAY))
        return 0

    def stop(self, options = None):
        self.controller.stop()
        return 0

    def status(self, options):
        states = self.controller.children_states(options.folder)
        for filename, status in states:
            print status + '\t' + filename
        return 0

    def edit(self, options):
        self.controller.launch_file_editor(
            options.server_url, options.item_id)
        return 0

    def bind_server(self, options):
        if options.password is None:
            password = getpass()
        else:
            password = options.password
        self.controller.bind_server(options.local_folder, options.nuxeo_url,
                                    options.username, password)
        for root in options.remote_roots:
            self.controller.bind_root(options.local_folder, root,
                                      repository = options.remote_repo)
        return 0

    def unbind_server(self, options):
        self.controller.unbind_server(options.local_folder)
        return 0

    def bind_root(self, options):
        self.controller.bind_root(options.local_folder, options.remote_root,
                                  repository = options.remote_repo)
        return 0

    def unbind_root(self, options):
        self.controller.unbind_root(options.local_root)
        return 0

    def com(self, options):
        if options.register:
            register_iconovelay_handler()
        elif options.unregister:
            unregister_icon_ovelay_handler()


    def test(self, options):
        import nose
        # Monkeypatch nose usage message as it's complicated to include
        # the missing text resource in the frozen binary package
        nose.core.TestProgram.usage = lambda cls: ""
        argv = [
            '',
            '--verbose',
        ]

        if options.with_coverage:
            argv += [
                '--with-coverage',
                '--cover-package=nxdrive',
                '--cover-html',
                '--cover-html-dir=coverage',
            ]

        if options.with_profile:
            argv += [
                '--with-profile',
                '--profile-restrict=nxdrive',
            ]
        # List the test modules explicitly as recursive discovery is broken
        # when the app is frozen.
        argv += [
            "nxdrive.tests.test_integration_local_client",
            "nxdrive.tests.test_integration_remote_changes",
            "nxdrive.tests.test_integration_remote_document_client",
            "nxdrive.tests.test_integration_remote_file_system_client",
            "nxdrive.tests.test_integration_synchronization",
            "nxdrive.tests.test_integration_versioning",
            "nxdrive.tests.test_synchronizer",
        ]
        return 0 if nose.run(argv = argv) else 1

def register_iconovelay_handler():
    if sys.platform == 'win32':
        import win32com.server.register
        from nxdrive.icon_overlay.win32 import IconOverlay
        win32com.server.register.UseCommandLine(IconOverlay, debug = DEBUGGING)

        keyname = r'Software\Microsoft\Windows\CurrentVersion\Explorer\ShellIconOverlayIdentifiers\%sOverlay' % Constants.SHORT_APP_NAME
        key = win32api.RegCreateKey (win32con.HKEY_LOCAL_MACHINE, keyname)
        win32api.RegSetValue (key, None, win32con.REG_SZ, IconOverlay._reg_clsid_)
    else:
        pass

def unregister_icon_ovelay_handler():
    if sys.platform == 'win32':
        import win32com.server.register
        import pywintypes
        from nxdrive.icon_overlay.win32 import IconOverlay
        win32com.server.register.UseCommandLine(IconOverlay)

        keyname = r'Software\Microsoft\Windows\CurrentVersion\Explorer\ShellIconOverlayIdentifiers'
        key = win32api.RegOpenKey(win32con.HKEY_LOCAL_MACHINE, keyname)
        try:
            win32api.RegDeleteKey(key, '%sOverlay' % Constants.SHORT_APP_NAME)
        except pywintypes.error:
            pass
    else:
        pass


def main(argv = None):
    if argv is None:
        argv = sys.argv
    return CliHandler().handle(argv)

if __name__ == "__main__":
    sys.exit(main())
