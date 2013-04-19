import os
import sys

from nxdrive import Constants
from nxdrive.utils import win32utils
try:
    from exceptions import WindowsError
except ImportError:
    # This will never be raised under unix
    pass
from nxdrive.logging_config import get_logger
from nxdrive.utils.helpers import find_exe_path

log = get_logger(__name__)

def register_startup(register):
    if sys.platform == 'win32':
        if register:
            register_startup_win32()
        else:
            unregister_startup_win32()
    elif sys.platform == 'darwin':
        if register:
            register_startup_darwin()
        else:
            unregister_startup_darwin()    
    
def register_startup_win32():
    target = find_exe_path()
    startup_folder = os.path.expanduser('~/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup')
    startup_folder = os.path.normpath(startup_folder)
    shortcut_path = os.path.join(startup_folder, Constants.SHORT_APP_NAME + '.lnk')
    log.debug("Registering '%s' for startup in: '%s'", target, startup_folder)
    args = ['gui', '--start']
    if os.path.splitext(target)[1] == '.py':
        # FOR TESTING
        args.insert(0, target)
        target = sys.executable
        
    try:
        win32utils.create_or_replace_shortcut(shortcut_path, target, ' '.join(args))
    except Exception as e:
        log.debug("Failed to register '%s' for startup in '%s' (%s)", target, startup_folder, e)
        
def unregister_startup_win32():
    target = find_exe_path()
    startup_folder = os.path.expanduser('~/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup')
    startup_folder = os.path.normpath(startup_folder)
    shortcut_path = os.path.join(startup_folder, Constants.SHORT_APP_NAME + '.lnk')
    log.debug("Unregistering '%s' for startup in: '%s'", target, startup_folder)
    try:
        os.unlink(shortcut_path)
    except WindowsError as e:
        log.debug("Failed to unregister '%s' for startup in: '%s'. Cannot delete shortcut (%s)", target, startup_folder, e)
    except Exception as e:
        log.debug("Failed to unregister '%s' for startup in: '%s' (%s)", target, startup_folder, e)
                    
                    
NDRIVE_AGENT_FILENAME = "com.sharp.cpodesktop.plist"
NDRIVE_AGENT_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.sharp.cpodesktop.agentlauncher</string>
  <key>RunAtLoad</key>
  <true/>
  <key>Program</key>
  <string>%s</string>
</dict>
</plist>
"""


def register_startup_darwin():
    """Register the Nuxeo Drive.app as a user Launch Agent

    http://developer.apple.com/library/mac/#documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html

    """
    agents_folder = os.path.expanduser('~/Library/LaunchAgents')
    agent_filepath = os.path.join(agents_folder, NDRIVE_AGENT_FILENAME)
    exe_path = find_exe_path()
    log.debug("Registering '%s' for startup in: '%s'", exe_path, agent_filepath)

    if not os.path.exists(agents_folder):
        os.makedirs(agents_folder)

    with open(agent_filepath, 'wb') as f:
        f.write(NDRIVE_AGENT_TEMPLATE % exe_path)

def unregister_startup_darwin():
    agents_folder = os.path.expanduser('~/Library/LaunchAgents')
    agent_filepath = os.path.join(agents_folder, NDRIVE_AGENT_FILENAME)
    exe_path = find_exe_path()
    log.debug("Unregistering '%s' for startup in: '%s'", exe_path, agent_filepath)
    if os.path.exists(agent_filepath):
        try:
            os.unlink(agent_filepath)  
        except OSError as e:
            log.debug("Failed to unregister '%s' for startup in: '%s'. Cannot delete file (%s)", exe_path, agent_filepath, e)
        except Exception as e:
            log.debug("Failed to unregister '%s' for startup in: '%s' (%s)", exe_path, agent_filepath, e)
        
