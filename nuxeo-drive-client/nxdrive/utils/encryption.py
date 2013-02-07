'''
Created on Feb 6, 2013

@author: mconstantin
'''

import sys
from nxdrive import Constants
from nxdrive.logging_config import get_logger

log = get_logger(__name__)
# Utilities for encrypting the password stored in the local database
try:
    from Crypto.Cipher import AES
    import hashlib
    import base64
    import getpass
    if sys.platform == 'win32':
        import win32crypt
    elif sys.platform == 'darwin':
        import keyring

    log.debug("Crypto.Cipher, etc. successfully imported")
    def encrypt_password(pwd):
        key = hashlib.md5(getpass.getuser()).digest()
        mode = AES.MODE_ECB
        encryptor = AES.new(key, mode)
        pwd = pad_to_multiple_of_16(pwd)
        encpwd = encryptor.encrypt(pwd)
        if sys.platform == 'win32':
            pwdhash = win32crypt.CryptProtectData(key, Constants.SHORT_APP_NAME, None, None, None, 0)
        elif sys.platform == 'darwin':
            keyring.set_password(Constants.SHORT_APP_NAME, getpass.getuser(), key)
            pwdhash = Constants.SHORT_APP_NAME
        else:
            pwdhash = key
        return base64.standard_b64encode(encpwd), base64.standard_b64encode(pwdhash)

    def decrypt_password(encpwd, pwdhash = ''):
        pwdhash = base64.standard_b64decode(pwdhash)
        if sys.platform == 'win32':
            desc = ''
            key = win32crypt.CryptUnprotectData(pwdhash, desc, None, None, 0)[1]
        elif sys.platform == 'darwin':
            key = keyring.get_password(Constants.SHORT_APP_NAME, getpass.getuser())
        else:
            key = pwdhash
        mode = AES.MODE_ECB
        decryptor = AES.new(key, mode)
        encpwd = base64.standard_b64decode(encpwd)
        encpwd = pad_to_multiple_of_16(encpwd)
        pwd = decryptor.decrypt(encpwd)
        pwd = remove_pad(pwd)
        return pwd

except ImportError as e:
    log.warning("module is not installed (%s): password will not be encrypted", str(e))
    def encrypt_password(pwd):
        return pwd

    def decrypt_password(encpwd, pwdhash = ''):
        return encpwd


def pad_to_multiple_of_16(indata):
    if len(indata) % 16 != 0:
        diff = 16 - len(indata) % 16
        indata += ' ' * diff

    return indata

def remove_pad(indata):
    pos = indata.find(' ')
    if pos != -1:
        indata = indata[0:pos]

    return indata
