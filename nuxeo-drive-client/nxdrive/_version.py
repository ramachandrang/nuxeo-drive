__version__ = '0.1.9'

import re

def _is_newer_version(version):
    if version is None:
        return False
    v1=map(int,re.sub('(\.0+)+\Z','',version).split('.'))
    v=map(int,re.sub('(\.0+)+\Z','',__version__).split('.'))
    return cmp(v1, v) > 0
