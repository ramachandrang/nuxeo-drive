'''
Created on Feb 6, 2013

@author: mconstantin
'''

import sys

from nxdrive.logging_config import get_logger
from nxdrive.utils import find_exe_path
from nxdrive import Constants

if sys.platform == 'win32':
    import pythoncom
    from win32com.client import Dispatch
    from win32com.shell import shell

log = get_logger(__name__)

# COM Errors
FILE_NOT_FOUND = 0x80070002


def update_win32_reg_key(reg, path, attributes=()):
    """Helper function to create / set a key with attribute values"""
    import _winreg
    key = _winreg.CreateKey(reg, path)
    _winreg.CloseKey(key)
    key = _winreg.OpenKey(reg, path, 0, _winreg.KEY_WRITE)
    for attribute, type_, value in attributes:
        _winreg.SetValueEx(key, attribute, 0, type_, value)
    _winreg.CloseKey(key)

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
    
    