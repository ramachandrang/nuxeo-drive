'''
Created on Jan 30, 2013

@author: constantinm
'''

import os.path
import re

VERSIONFILE = r"nuxeo-drive-client/nxdrive/_version.py"

def get_version():
    VERSIONPATH = os.path.join(os.path.dirname(__file__), VERSIONFILE)
    verstr = "unknown"
    try:
        with open(VERSIONPATH, "rt") as f:
            verstrline = f.read()
    except EnvironmentError:
        # Okay, there is no version file.
        raise RuntimeError("there is no version file %s" % VERSIONFILE)
    else:
        VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
        mo = re.search(VSRE, verstrline, re.M)
        if mo:
            verstr = mo.group(1)
            return verstr
        else:
            raise RuntimeError("if %s.py exists, it is required to be well-formed" % (VERSIONFILE,))

def inc_build_number():
    try:
        oldver = get_version()
        __version_info__ = tuple([ num for num in oldver.split('.')])
        build = int(__version_info__[2])
        buildstr = str(build + 1)
        __version_info__ = (__version_info__[0], __version_info__[1], buildstr)
        ver = '.'.join(__version_info__)

        VERSIONPATH = os.path.join(os.path.dirname(__file__), VERSIONFILE)
        verstr = "__version__ = '%s'" % ver

        with open(VERSIONPATH, "wt") as f:
            f.write(verstr)
    except EnvironmentError:
        # Okay, there is no version file.
        raise RuntimeError("there is no version file %s" % VERSIONFILE)


if __name__ == '__main__':
    print get_version()
    inc_build_number()
    print get_version()

