'''
Created on Oct 28, 2012

@author: mconstantin
'''
import sys

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

APP_STATE_RUNNING = _('running')
APP_STATE_STOPPED = _('stopped')
APP_STATE_QUITTING = _('quitting')
APP_SUBSTATE_AVAILABLE = _('available')
APP_SUBSTATE_MAINTENANCE = _('maintenance')

INFO_STATE_NONE = 'none'
INFO_STATE_MAINTENANCE_SCHEDULE = 'maint_schedule'
INFO_STATE_QUOTA = 'quota'
INFO_STATE_UPGRADE = 'upgrade'
INFO_STATE_INVALID_CREDENTIALS = 'invalid_cred'
INFO_STATE_INVALID_PROXY = 'invalid_proxy'

DEFAULT_NXDRIVE_FOLDER = PRODUCT_NAME
# TODO replace with CloudDesk url and admin(?) account
DEFAULT_CLOUDDESK_URL = r'https://qadm.sharpb2bcloud.com/app1'
DEFAULT_ACCOUNT = "user4@qt1.com"
# DEFAULT_CLOUDDESK_URL = r'http://localhost:8080/nuxeo'
# DEFAULT_ACCOUNT = "user@shiro.com"
SERVICE_NAME = 'Cloud Portal Office'
#MAINTENANCE_SERVICE_URL = r'http://hbdisdlw7.enet.sharplabs.com/Maintenance/MaintenanceSchedule.svc/json/'
MAINTENANCE_SERVICE_URL = r'https://qa-mgmt.sharpb2bcloud.com/Maintenance/MaintenanceSchedule.svc/qadm.sharpb2bcloud.com'
#UPGRADE_SERVICE_URL = r'http://localhost:8000/upgrade/default/upgrade.json/'
UPGRADE_SERVICE_URL = r'http://HBDISDLW7.enet.sharplabs.com/Maintenance/SoftwareUpdates.svc/json/'
INTERNAL_HTTP_PORT = 63111

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
NOTIFICATION_MESSAGE_DELAY = 3  # in seconds
SERVICE_NOTIFICATION_INTERVAL = 6 * 3600  # six hours
FDTOKEN_DURATION = 15 * 60
SYNC_STATUS_STOP = 1
SYNC_STATUS_START = 2
APP_ICON_DIALOG = ':/icon_dlg.png'
APP_ICON_ENABLED = ':/indicator_icon_enabled.png'
APP_ICON_DISABLED = ':/indicator_icon_disabled.png'
APP_ICON_PAUSED = ':/indicator_icon_paused.png'
APP_ICON_STOPPING = ':/indicator_icon_paused.png'
APP_ICON_PATTERN = ':/indicator_icon_%s.png'
APP_ICON_PATTERN_ANIMATION = ':/indicator_icon_%s_%s.png'
APP_ICON_ABOUT = ':/about_icon.png'
APP_ICON_TAB_GENERAL = ':/general.png'
APP_ICON_TAB_ACCOUNT = ':/account.png'
APP_ICON_TAB_NETWORK = ':/network.png'
APP_ICON_TAB_ADVANCED = ':/advanced.png'
APP_ICON_WIZARD_RB = ':/rb_icon.png'

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

COPYRIGHT_FILE = r'nxdrive/data/CloudDesk_EULA.txt'
ICON_OVERLAY_SYNC = r'nxdrive/data/icons/cpo-sync.ico'
ICON_APP_ENABLED = R'nuxeo_drive_icon_16_enabled.png'
ICON_APP_DISABLED = R'nuxeo_drive_icon_16_disabled.png'


