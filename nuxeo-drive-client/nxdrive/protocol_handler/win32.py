'''
Created on Feb 6, 2013

@author: mconstantin
'''

from nxdrive.logging_config import get_logger
from nxdrive.utils import find_exe_path
from nxdrive.utils import update_win32_reg_key
from nxdrive import Constants

log = get_logger(__name__)


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
    update_win32_reg_key(
        reg, 'Software\\%s\\%s' % (Constants.COMPANY_NAME, Constants.APP_NAME),
        [('', _winreg.REG_SZ, Constants.SHORT_APP_NAME)],
    )
    # TODO: add an icon for Nuxeo Drive too
    update_win32_reg_key(
        reg, 'Software\\%s\\%s\\Protocols\\%s' % (Constants.COMPANY_NAME, Constants.APP_NAME, Constants.SHORT_APP_NAME),
        [('URL Protocol', _winreg.REG_SZ, '')],
    )
    # TODO: add an icon for the nxdrive protocol too
    update_win32_reg_key(
        reg,
        'Software\\%s\\%s\\Protocols\\%s\\shell\\open\\command' % (Constants.COMPANY_NAME, Constants.APP_NAME, Constants.SHORT_APP_NAME),
        [('', _winreg.REG_SZ, command)],
    )
    # Create the nxdrive protocol key
    nxdrive_class_path = 'Software\\Classes\\nxdrive'
    update_win32_reg_key(
        reg, nxdrive_class_path,
        [
            ('EditFlags', _winreg.REG_DWORD, 2),
            ('', _winreg.REG_SZ, 'URL:%s Protocol' % Constants.SHORT_APP_NAME),
            ('URL Protocol', _winreg.REG_SZ, ''),
        ],
    )
    # Create the nxdrive command key
    command_path = nxdrive_class_path + '\\shell\\open\\command'
    update_win32_reg_key(
        reg, command_path,
        [('', _winreg.REG_SZ, command)],
    )
