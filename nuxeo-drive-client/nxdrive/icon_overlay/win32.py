'''
Created on Jan 9, 2013

@author: constantinm
'''

import os
import sys
import pythoncom
import winerror
from win32com.client import Dispatch
from win32com.shell import shell, shellcon

from nxdrive import Constants


def get_icon_path():
    import nxdrive
    nxdrive_path = os.path.dirname(nxdrive.__file__)
    exe_path = os.path.join(os.path.dirname(nxdrive_path), Constants.APP_NAME)
    if os.path.exists(exe_path):
        return os.path.join(os.path.dirname(nxdrive_path), 'icons')
    else:
        return os.path.join(os.path.dirname(nxdrive_path), 'data', 'icons')

ICON_PATH = get_icon_path()


class IconOverlay:
    _reg_clsctx_ = pythoncom.CLSCTX_INPROC_SERVER
    _reg_clsid_ = '{197965c0-5a86-11e2-b951-0026b9891aeb}'
    _reg_progid_ = '%s.%sOverlayHandler' % (Constants.COMPANY_NAME, Constants.SHORT_APP_NAME)
    _reg_desc_ = 'Icon Overlay Handler for %s' % Constants.APP_NAME
    _public_methods_ = ['GetOverlayInfo', 'GetPriority', 'IsMemberOf']
    _com_interfaces_ = [shell.IID_IShellIconOverlayIdentifier, pythoncom.IID_IDispatch]
    if hasattr(sys, 'importers'):
        # running as py2exe-packed executable
        _reg_class_spec_ = 'icon_overlay.win32.IconOverlay'
  
    def GetOverlayInfo(self):
        return (os.path.join(ICON_PATH, Constants.ICON_OVERLAY_SYNC), 0, shellcon.ISIOI_ICONFILE)
    
    def GetPriority(self):
        return 0
    
    def IsMemberOf(self, fname, attributes):
        # TODO use a proper membership test
        if os.path.isfile(fname) and os.path.dirname(fname) == r'C:\\cpo\\CLOUD PORTAL OFFICE\\My Docs':
            return winerror.S_OK
        return winerror.E_FAIL
    
