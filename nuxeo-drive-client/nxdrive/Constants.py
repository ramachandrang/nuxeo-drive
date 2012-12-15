'''
Created on Oct 28, 2012

@author: mconstantin
'''

APP_STATE_RUNNING = 'running'
APP_STATE_STOPPED = 'stopped'
APP_STATE_QUITTING = 'quitting'

DEFAULT_NXDRIVE_FOLDER = "CloudDesk"
DEFAULT_CLOUDDESK_URL = "http://ec2-50-112-198-72.us-west-2.compute.amazonaws.com:8080/app1"
DEFAULT_ACCOUNT = "user@shiro.com"

MY_DOCS = 'My Docs'
OTHERS_DOCS = 'Others Docs'

ICON_ANIMATION_DELAY = 200
ICON_ANIMATION_START_DELAY = 100
NOTIFICATION_MESSAGE_DELAY = 2 #in seconds
FDTOKEN_DURATION = 15 * 60
SYNC_STATUS_STOP = 1
SYNC_STATUS_START = 2
APP_ICON_ENABLED = ':/indicator_icon_enabled.png'
APP_ICON_DISABLED = ':/indicator_icon_disabled.png'
APP_ICON_STOPPING = ':/indicator_icon_stopping.png'
APP_ICON_PATTERN = ':/indicator_icon_%s.png'
APP_ICON_PATTERN_ANIMATION = ':/indicator_icon_%s_%s.png'
APP_ICON_ABOUT = ':/about_icon.png'

COPYRIGHT_FILE = 'nxdrive/data/COPYING.txt'

__version__ = '1.0.0'

