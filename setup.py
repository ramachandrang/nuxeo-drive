#! /usr/bin/env python
#
# Copyright (C) 2012 Nuxeo
#

import sys
import os
import platform
import subprocess
from datetime import datetime

from distutils.core import setup
if sys.platform == 'win32':
    import py2exe

PRODUCT_NAME = 'Cloud Portal Office'
APP_NAME = PRODUCT_NAME + ' Desktop'
WIZARD_NAME = PRODUCT_NAME + ' Wizard'
SHORT_APP_NAME = 'CpoDesktop'
SHORT_WIZARD_NAME = 'CpoWizard'
DEFAULT_ROOT_FOLDER = PRODUCT_NAME
version = '0.1.2'

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
    
def default_nuxeo_drive_folder():
    """Find a reasonable location for the root Nuxeo Drive folder
    This folder is user specific, typically under the home folder.
    """
    path = None
    if sys.platform == "win32":
        if os.path.exists(os.path.expanduser(r'~\My Documents')):
            # Compat for Windows XP
            path = os.path.join(r'~\My Documents', PRODUCT_NAME)
        else:
            # Default Documents folder with navigation shortcuts in Windows 7
            # and up.
            path = os.path.join(r'~\Documents', PRODUCT_NAME)
    else:
        path = os.path.join('~', PRODUCT_NAME)
        
    return os.path.expanduser(path)
    
script = 'nuxeo-drive-client/scripts/ndrive.py'
scriptwzd = 'nuxeo-drive-client/scripts/ndrivewzd.py'
scripts = [script, scriptwzd]

freeze_options = {}

packages = [
    'nxdrive',
    'nxdrive.tests',
    'nxdrive.gui',
    'nxdrive.protocol_handler',
    'nxdrive.data',
    'nxdrive.data.icons',
    'nxdrive.async',
    'nxdrive.utils',
]
package_data = {
    'nxdrive.data.icons': ['*.png', '*.svg', '*.ico', '*.icns'],
    'nxdrive.data': ['*.txt', '*.xml'],
}

# TODO: icons are already copied into 'icons' subfolder - investigate this
icons_home = 'nuxeo-drive-client/nxdrive/data/icons'
images_home = 'nuxeo-drive-client/nxdrive/data/images'

win_icon = os.path.join(icons_home, 'nuxeo_drive_icon_64.ico')
png_icon = os.path.join(icons_home, 'nuxeo_drive_icon_64.png')
osx_icon = os.path.join(icons_home, 'nuxeo_drive_app_icon_128.icns')

if sys.platform == 'win32':
    icon = win_icon
elif sys.platform == 'darwin':
    icon = png_icon
else:
    icon = png_icon
    
icons_files = []
for filename in os.listdir(icons_home):
    filepath = os.path.join(icons_home, filename)
    if os.path.isfile(filepath):
        icons_files.append(filepath)
        
images_files = []
for filename in os.listdir(images_home):
    filepath = os.path.join(images_home, filename)
    if os.path.isfile(filepath):
        images_files.append(filepath)
        
others_home = 'nuxeo-drive-client/nxdrive/data'
others_files = []
for filename in os.listdir(others_home):
    filepath = os.path.join(others_home, filename)
    if os.path.isfile(filepath) and os.path.splitext(filename)[1] not in ['.py', '.pyc', '.pyd']:
        others_files.append(filepath)
        
if sys.platform == 'win32':
    bin_files = []
    arch = '64bit' if 'PROGRAMFILES(X86)' in os.environ else '32bit'
    bin_home = os.path.join('nuxeo-drive-client/nxdrive/data/bin/', arch)
    for filename in os.listdir(bin_home):
        filepath = os.path.normpath(os.path.join(bin_home, filename))
        if os.path.isfile(filepath) and os.path.splitext(filepath)[1] == '.dll':
            bin_files.append(filepath)
    

if '--dev' in sys.argv:
    # timestamp the dev artifacts for continuous integration
    # distutils only accepts "b" + digit
    sys.argv.remove('--dev')
    timestamp = datetime.utcnow().isoformat()
    timestamp = timestamp.replace(":", "")
    timestamp = timestamp.replace(".", "")
    timestamp = timestamp.replace("T", "")
    timestamp = timestamp.replace("-", "")
    version += "b" + timestamp

includes = [
    "PySide",
    "PySide.QtCore",
    "PySide.QtNetwork",
    "PySide.QtGui",
    "atexit",  # implicitly required by PySide
    "sqlalchemy.dialects.sqlite",
]


if '--freeze' in sys.argv:
    print "Building standalone executable..."
    sys.argv.remove('--freeze')
    from cx_Freeze import setup, Executable

    # build_exe does not seem to take the package_dir info into account
    sys.path.append('nuxeo-drive-client')

#    executables = [Executable(script, base=None)]
    executables = []
    
    if sys.platform == "win32":
        # Windows GUI program that can be launched without a cmd console
        executables.append(
            Executable(script, targetName=SHORT_APP_NAME + '.exe', base="Win32GUI",
                       icon=icon, shortcutDir="ProgramMenuFolder",
                       shortcutName=APP_NAME))

        executables.append(
            Executable(scriptwzd, targetName=SHORT_WIZARD_NAME + '.exe', base="Win32GUI",
                       icon=icon, shortcutDir="ProgramMenuFolder",
                       shortcutName=WIZARD_NAME))

    # special handling for data files
    packages.remove('nxdrive.data')
    packages.remove('nxdrive.data.icons')
    package_data = {}

    include_files = [
                    icons_home + "/nuxeo_drive_icon_%d.png" % i
                        for i in [16, 32, 48, 64]
    ]
    
    includes = [
                "PySide",
                "PySide.QtCore",
                "PySide.QtNetwork",
                "PySide.QtGui",
                "atexit",  # implicitly required by PySide
                "sqlalchemy.dialects.sqlite",
                ]
    freeze_options = dict(
        executables=executables,
        data_files=[('icons', icons_files), 
                    ('data', others_files),
                    ('bin', bin_files),
                    ('images', images_files),
                    ],
        options={
            "build_exe": {
                "includes": includes,
                "packages": packages + [
                    "nose",
                    "icemac.truncatetext",
                ],
                "excludes": [
                    "ipdb",
                    "clf",
                    "IronPython",
                    "pydoc",
                    "tkinter",
                ],
                "include_files": include_files,
            },
            "bdist_msi": {
                "add_to_path": True,
                "upgrade_code": '{800B7778-1B71-11E2-9D65-A0FD6088709B}',
            },
        },
    )
    # TODO: investigate with esky to get an auto-updateable version but
    # then make sure that we can still have .msi and .dmg packages
    # instead of simple zip files.
elif sys.platform == 'darwin':
    # Under OSX we use py2app instead of cx_Freeze because we need:
    # - argv_emulation=True for nxdrive:// URL scheme handling
    # - easy Info.plit customization
    import py2app  # install the py2app command

    freeze_options = dict(
        app=[script],
        data_files=[('icons', icons_files), 
                    ('nxdrive/data', others_files)],
        options=dict(
            py2app=dict(
                iconfile=png_icon,
                argv_emulation=False,  # We use QT for URL scheme handling
                plist=dict(
                    CFBundleDisplayName=APP_NAME,
                    CFBundleName=APP_NAME,
                    CFBundleIdentifier="com.sharpb2bcloud.cpo.desktop",
                    LSUIElement=True,  # Do not launch as a Dock application
                    CFBundleURLTypes=[
                        dict(
                            CFBundleURLName='%s URL' % APP_NAME,
                            CFBundleURLSchemes=[SHORT_APP_NAME],
                        )
                    ]
                ),
                includes=includes,
            )
        )
    )


setup(
    name=APP_NAME,
    version=version,
    description="Desktop synchronization client for %s." % PRODUCT_NAME,
    author="SHARP",
    author_email="contact@sharplabs.com",
    url='https://github.com/SharpCD/clouddesk_drive.git',
    packages=packages,
    package_dir={'nxdrive': 'nuxeo-drive-client/nxdrive'},
    package_data=package_data,
    scripts=scripts,
    long_description=open('README.rst').read(),
    **freeze_options
)


