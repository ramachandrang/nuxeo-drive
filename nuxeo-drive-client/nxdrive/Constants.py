'''
Created on Oct 28, 2012

@author: mconstantin
'''
import sys
from nxdrive import USE_LOCAL_SERVICE

try:
    import _version
    __version__ = _version.__version__
except ImportError:
    __version__ = '0.0.0.0'

COMPANY_NAME = 'Sharp'
PRODUCT_NAME = _('Cloud Portal Office')
APP_NAME = PRODUCT_NAME + _(' Desktop')
SHORT_APP_NAME = 'CpoDesktop'
OSX_APP_NAME = APP_NAME

APP_STATE_RUNNING = 'running'
APP_STATE_STOPPED = 'stopped'
APP_STATE_QUITTING = 'quitting'
APP_SUBSTATE_AVAILABLE = 'available'
APP_SUBSTATE_MAINTENANCE = 'maintenance'

INFO_STATE_NONE = 'none'
INFO_STATE_MAINTENANCE_SCHEDULE = 'maint_schedule'
INFO_STATE_QUOTA = 'quota'
INFO_STATE_UPGRADE = 'upgrade'
INFO_STATE_INVALID_CREDENTIALS = 'invalid_cred'
INFO_STATE_INVALID_PROXY = 'invalid_proxy'

DEFAULT_NXDRIVE_FOLDER = PRODUCT_NAME
CONFIG_FILE = 'nxdrive.cfg'

# TODO replace with CloudDesk url and admin(?) account
CLOUDDESK_URL = u'https://qadm.sharpb2bcloud.com/app1'
ACCOUNT = ''
# CLOUDDESK_URL = r'http://localhost:8080/nuxeo'
SERVICE_NAME = 'Cloud Portal Office'

if USE_LOCAL_SERVICE:
    MAINTENANCE_SERVICE_URL = u'http://hbdisdlw7.enet.sharplabs.com/Maintenance/MaintenanceSchedule.svc/json/'
    UPGRADE_SERVICE_URL = u'http://hbdisdlw7.enet.sharplabs.com/Maintenance/SoftwareUpdates.svc/json/'
    #UPGRADE_SERVICE_URL = r'http://localhost:8000/upgrade/default/upgrade.json/'
else:
    MAINTENANCE_SERVICE_URL = u'https://dev-mgmt.sharpb2bcloud.com/Maintenance/MaintenanceSchedule.svc/json/'
    UPGRADE_SERVICE_URL = u'https://dev-mgmt.sharpb2bcloud.com/Maintenance/SoftwareUpdates.svc/json/'

INTERNAL_HTTP_PORT = 63111
CLOUDDESK_UID = '0da71bd4-4aff-11e2-9c64-3c075442cb05'
CLOUDDESK_REMOTE_NAME = "Nuxeo Drive"
APP_ID = CLOUDDESK_UID
MY_DOCS = r'My Documents'
OTHERS_DOCS = r'Other Documents'
GUEST_FOLDER = r'Guest Folder'
OTHERS_DOCS_UID = '3910c811-4977-11e2-8a7d-3c075442cb05'
ROOT_CLOUDDESK = 0
ROOT_MYDOCS = 1
ROOT_OTHERS_DOCS = 2
RECENT_FILES_COUNT = 5

ICON_ANIMATION_DELAY = 200
ICON_ANIMATION_START_DELAY = 100
NOTIFICATION_MESSAGE_DELAY = 3  # in seconds
SERVICE_NOTIFICATION_INTERVAL = 6 * 3600  # six hours
FDTOKEN_DURATION = 15 * 60
SYNC_STATUS_STOP = 1
SYNC_STATUS_START = 2
APP_ICON_DIALOG = ':/icon_dlg.png'
APP_ICON_ENABLED = ':/indicator_icon_enabled.png'
APP_ICON_DISABLED = ':/indicator_icon_disabled.png'
APP_ICON_SYNCED = ':/indicator_icon_synced.png'
APP_ICON_PAUSED = ':/indicator_icon_paused.png'
APP_ICON_STOPPING = ':/indicator_icon_paused.png'
APP_ICON_SYNCED = ':/indicator_icon_synced.png'
APP_ICON_PATTERN = ':/indicator_icon_%s.png'
APP_ICON_PATTERN_ANIMATION = ':/indicator_icon_%s_%s.png'
APP_ICON_ABOUT = ':/about_icon.png'
APP_ICON_TAB_GENERAL = ':/general.png'
APP_ICON_TAB_ACCOUNT = ':/account.png'
APP_ICON_TAB_NETWORK = ':/network.png'
APP_ICON_TAB_ADVANCED = ':/advanced.png'
APP_ICON_WIZARD_RB = ':/rb_icon.png'
APP_ICON_MENU_QUOTA = ':/menu_quota_exceeded.png'
APP_ICON_MENU_MAINT = ':/menu_maint_mode.png'
APP_ICON_MENU_UNAVAILABLE = APP_ICON_MENU_QUOTA

if sys.platform == 'darwin':
    APP_IMG_WIZARD_FINDER_FOLDERS = ':/finder_folders.png'
    APP_IMG_WIZARD_ACCESS_FILES = ':/access_files_darwin.png'
    APP_IMG_WIZARD_APPBAR = ':/appbar.png'
    APP_IMG_WIZARD_FINAL = ':/final_page_darwin.png'
    APP_IMG_WIZARD_BKGRND = ':/bkgrnd.png'
    APP_IMG_WIZARD_BANNER = ':/banner.png'
elif sys.platform == 'win32':
    APP_IMG_WIZARD_FINDER_FOLDERS = ':/explorer_folders.png'
    APP_IMG_WIZARD_ACCESS_FILES = ':/access_files_win32.png'
    APP_IMG_WIZARD_APPBAR = ':/systray.png'
    APP_IMG_WIZARD_FINAL = ':/final_page_win32.png'
    APP_IMG_WIZARD_WATERMARK = ':/watermark.png'
    APP_IMG_WIZARD_BANNER = ':/banner.png'

COPYRIGHT_FILE = r'CloudDesk_EULA.txt'
HELP_FILE = r'Cloud_Portal_Office_Help.pdf'
ICON_OVERLAY_SYNC = r'nxdrive/data/icons/cpo-sync.ico'
ICON_APP_ENABLED = r'CP_Red_Office_16x16_Online.png'
ICON_APP_DISABLED = r'CP_Red_Office_16x16_Offline.png'


