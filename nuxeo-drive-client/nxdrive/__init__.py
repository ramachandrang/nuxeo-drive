"""Global debug flag"""
DEBUG = True

"""Global maintenance/upgrade service flag"""
USE_LOCAL_SERVICE = True
"""Flag for simulating a quota exception"""
DEBUG_QUOTA_EXCEPTION = False
"""Flag for simulating a maintenance exception"""
DEBUG_MAINTENANCE_EXCEPTION = False

"""Setup i18n"""
import gettext
gettext.install('cpodesktop')
