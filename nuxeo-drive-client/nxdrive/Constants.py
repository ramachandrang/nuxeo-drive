'''
Created on Oct 28, 2012

@author: mconstantin
'''

COMPANY_NAME = 'SHARP'
PRODUCT_NAME = 'CLOUD PORTAL OFFICE'
APP_NAME = PRODUCT_NAME + ' Desktop'
SHORT_APP_NAME = 'CpoDesktop'
OSX_APP_NAME = APP_NAME

APP_STATE_RUNNING = 'running'
APP_STATE_STOPPED = 'stopped'
APP_STATE_QUITTING = 'quitting'

DEFAULT_NXDRIVE_FOLDER = PRODUCT_NAME
# TODO replace with CloudDesk url and admin(?) account
DEFAULT_CLOUDDESK_URL = "http://ec2-50-112-198-72.us-west-2.compute.amazonaws.com:8080/app1"
DEFAULT_ACCOUNT = "user@shiro.com"

CLOUDDESK_UID = '0da71bd4-4aff-11e2-9c64-3c075442cb05'
MY_DOCS = 'My Docs'
OTHERS_DOCS = 'Others Docs'
OTHERS_DOCS_UID = '3910c811-4977-11e2-8a7d-3c075442cb05'
ROOT_CLOUDDESK = 0
ROOT_MYDOCS = 1
ROOT_OTHERS_DOCS = 2
RECENT_FILES_COUNT = 5

ICON_ANIMATION_DELAY = 200
ICON_ANIMATION_START_DELAY = 100
NOTIFICATION_MESSAGE_DELAY = 3 #in seconds
FDTOKEN_DURATION = 15 * 60
SYNC_STATUS_STOP = 1
SYNC_STATUS_START = 2
APP_ICON_ENABLED = ':/indicator_icon_enabled.png'
APP_ICON_DISABLED = ':/indicator_icon_disabled.png'
APP_ICON_STOPPING = ':/indicator_icon_stopping.png'
APP_ICON_PATTERN = ':/indicator_icon_%s.png'
APP_ICON_PATTERN_ANIMATION = ':/indicator_icon_%s_%s.png'
APP_ICON_ABOUT = ':/about_icon.png'
APP_ICON_TAB_GENERAL = ':/general.png'
APP_ICON_TAB_ACCOUNT = ':/account.png'
APP_ICON_TAB_NETWORK =':/network.png'
APP_ICON_TAB_ADVANCED = ':/advanced.png'

COPYRIGHT_FILE = 'nxdrive/data/CloudDesk_EULA.txt'

__version__ = '1.0.0'

