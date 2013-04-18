"""Global debug flag"""
DEBUG = False

def isDebug():
    return DEBUG

"""Global maintenance/upgrade service flag"""
USE_LOCAL_SERVICE = False
"""Flag for simulating a quota exception"""
DEBUG_QUOTA_EXCEPTION = False
"""Flag for simulating a maintenance exception"""
DEBUG_MAINTENANCE_EXCEPTION = False
"""Flag for simulating a 503 error"""
DEBUG_UNAVAILABLE = False
"""Flag for checking maintenance and upgrade services every loop (iteration)"""
NAG_EVERY_LOOP = False
"""Synchronize 'conflicted' state"""
DEBUG_SYNC_CONFLICTED = True
"""Use a global cookiejar"""
USE_SINGLE_COOKIEJAR = True

"""Setup i18n"""
import gettext
gettext.install('cpodesktop')
