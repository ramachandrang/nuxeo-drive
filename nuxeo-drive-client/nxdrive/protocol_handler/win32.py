import os
import sys
import pythoncom
from win32com.client import Dispatch
from win32com.shell import shell

from nxdrive.logging_config import get_logger
from nxdrive import Constants
log = get_logger(__name__)

# COM Errors
FILE_NOT_FOUND = 0x80070002


def find_exe_path():
    """Introspect the Python runtime to find the frozen Windows exe"""
    import nxdrive
    nxdrive_path = os.path.dirname(nxdrive.__file__)
    frozen_suffix = os.path.join('library.zip', 'nxdrive')
    if nxdrive_path.endswith(frozen_suffix):
        exe_path = nxdrive_path.replace(frozen_suffix, Constants.SHORT_APP_NAME + '.exe')
        if os.path.exists(exe_path):
            return exe_path
    # TODO: handle the python.exe + python script as sys.argv[0] case as well
    return None


def update_key(reg, path, attributes=()):
    """Helper function to create / set a key with attribute values"""
    import _winreg
    key = _winreg.CreateKey(reg, path)
    _winreg.CloseKey(key)
    key = _winreg.OpenKey(reg, path, 0, _winreg.KEY_WRITE)
    for attribute, type_, value in attributes:
        _winreg.SetValueEx(key, attribute, 0, type_, value)
    _winreg.CloseKey(key)


def register_protocol_handlers(controller):
    """Register ndrive as a protocol handler in the Registry"""
    import _winreg

    exe_path = find_exe_path()
    if exe_path is None:
        log.warning('Not a frozen windows exe: '
                 'skipping protocol handler registration')
        return

    log.debug("Registering 'nxdrive' protocol handler to: %s", exe_path)
    reg = _winreg.ConnectRegistry(None, _winreg.HKEY_CURRENT_USER)

    # Register Nuxeo Drive as a software as a protocol command provider
    command = '"' + exe_path + '" "%1"'
    update_key(
        reg, 'Software\\%s\\%s' % (Constants.COMPANY_NAME, Constants.APP_NAME),
        [('', _winreg.REG_SZ, Constants.SHORT_APP_NAME)],
    )
    # TODO: add an icon for Nuxeo Drive too
    update_key(
        reg, 'Software\\%s\\%s\\Protocols\\%s' % (Constants.COMPANY_NAME, Constants.APP_NAME, Constants.SHORT_APP_NAME),
        [('URL Protocol', _winreg.REG_SZ, '')],
    )
    # TODO: add an icon for the nxdrive protocol too
    update_key(
        reg,
        'Software\\%s\\%s\\Protocols\\%s\\shell\\open\\command' % (Constants.COMPANY_NAME, Constants.APP_NAME, Constants.SHORT_APP_NAME),
        [('', _winreg.REG_SZ, command)],
    )
    # Create the nxdrive protocol key
    nxdrive_class_path = 'Software\\Classes\\%s' % Constants.SHORT_APP_NAME
    update_key(
        reg, nxdrive_class_path,
        [
            ('EditFlags', _winreg.REG_DWORD, 2),
            ('', _winreg.REG_SZ, 'URL:%s Protocol' % Constants.SHORT_APP_NAME),
            ('URL Protocol', _winreg.REG_SZ, ''),
        ],
    )
    # Create the nxdrive command key
    command_path = nxdrive_class_path + '\\shell\\open\\command'
    update_key(
        reg, command_path,
        [('', _winreg.REG_SZ, command)],
    )
    
def create_shortcut(path, target, wDir='', icon=''):
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(path)
    shortcut.Targetpath = target
    shortcut.WorkingDirectory = wDir
    if icon == '':
        pass
    else:
        shortcut.iconLocation = icon
    shortcut.save()
    
def create_or_replace_shortcut(shortcut, target):
    win_version = sys.getwindowsversion()
    if win_version.major == 6 and win_version.minor == 1:
        # check if the link already exists
        shlink = pythoncom.CoCreateInstance(shell.CLSID_ShellLink, None, 
                                              pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink)
        try:
            shlink.QueryInterface(pythoncom.IID_IPersistFile).Load(shortcut)
            if shlink.GetPath(shell.SLGP_RAWPATH)[0] != target:
                shlink.SetPath(target)
                shlink.QueryInterface(pythoncom.IID_IPersistFile).Save(None, True)
        except pythoncom.com_error as e:
            exe_path = find_exe_path()
            if exe_path is None:
                # FOR TESTING
                exe_path = 'C:\\Program Files (x86)\\%s\\%s.exe' % (Constants.APP_NAME, Constants.SHORT_APP_NAME)
                create_shortcut(shortcut, target, icon=exe_path)
    else:
        # TODO find the Favorites location for other Windows versions
        pass
    
def create_shortcut_if_not_exists(shortcut, target):
    win_version = sys.getwindowsversion()
    if win_version.major == 6 and win_version.minor == 1:
        # check if the link already exists
        shlink = pythoncom.CoCreateInstance(shell.CLSID_ShellLink, None, 
                                              pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink)
        try:
            shlink.QueryInterface(pythoncom.IID_IPersistFile).Load(shortcut)
        except pythoncom.com_error as e:
            exe_path = find_exe_path()
            if exe_path is None:
                # FOR TESTING
                exe_path = 'C:\\Program Files (x86)\\%s\\%s.exe' % (Constants.APP_NAME, Constants.SHORT_APP_NAME)
                create_shortcut(shortcut, target, icon=exe_path)
    else:
        # TODO find the Favorites location for other Windows versions
        pass    
    
    