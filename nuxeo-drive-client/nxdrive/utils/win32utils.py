'''
Created on Feb 6, 2013

@author: mconstantin
'''

import sys
import os

from nxdrive.logging_config import get_logger
from nxdrive.utils.helpers import find_exe_path
from nxdrive import Constants

log = get_logger(__name__)

if sys.platform == 'win32':
    try:
        import pythoncom
    except ImportError:
        log.warning("pythoncom package is not installed:"
                        " skipping favorite link creation")
    try:
        from win32com.client import Dispatch
        from win32com.shell import shell
    except ImportError:
        log.warning("win32com package is not installed:"
                        " skipping favorite link creation")

# COM Errors
FILE_NOT_FOUND = 0x80070002
# Windows versions
SUPPORTED_WINVER_MAJOR = 6
SUPPORTED_WINVER_MINOR = 1

def update_win32_reg_key(reg, path, attributes = ()):
    """Helper function to create / set a key with attribute values"""
    import _winreg
    key = _winreg.CreateKey(reg, path)
    _winreg.CloseKey(key)
    key = _winreg.OpenKey(reg, path, 0, _winreg.KEY_WRITE)
    for attribute, type_, value in attributes:
        _winreg.SetValueEx(key, attribute, 0, type_, value)
    _winreg.CloseKey(key)

def create_shortcut(path, target, wDir = '', args = None, icon = None):
    try:
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.TargetPath = target
        shortcut.WorkingDirectory = wDir
        if args:
            shortcut.Arguments = args
        if icon:
            shortcut.iconLocation = icon
        shortcut.save()
    except Exception, e:
        log.debug('error creating shortcut %s for %s: %s', path, target, e)

def create_or_replace_shortcut(shortcut, target, args = None):
    win_version = sys.getwindowsversion()
    if win_version.major >= SUPPORTED_WINVER_MAJOR and win_version.minor >= SUPPORTED_WINVER_MINOR:
        # check if the link already exists
        shlink = pythoncom.CoCreateInstance(shell.CLSID_ShellLink, None,
                                              pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink)
        try:
            shlink.QueryInterface(pythoncom.IID_IPersistFile).Load(shortcut)
            if shlink.GetPath(shell.SLGP_RAWPATH)[0].lower() != target.lower():
                shlink.SetPath(target)
                if args:
                    shlink.SetArguments(args)
                shlink.QueryInterface(pythoncom.IID_IPersistFile).Save(None, True)
        except pythoncom.com_error as e:
            exe_path = icon = find_exe_path()
            if os.path.splitext(exe_path)[1] == '.py':
                # FOR TESTING
                icon = None
            create_shortcut(shortcut, target, args = args, icon = icon)
    else:
        # TODO find the Favorites location for other Windows versions
        log.debug("failed to create shortcut. Windows version lower than %d.%d",
                  SUPPORTED_WINVER_MAJOR, SUPPORTED_WINVER_MINOR)


