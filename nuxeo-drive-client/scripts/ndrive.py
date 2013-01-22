#!/usr/bin/env python
"""Commandline interface for the Nuxeo Drive filesystem synchronizer"""

import sys
import os.path
from nxdrive.commandline import main

#import pdb
#pdb.set_trace()

base = os.path.split(os.path.split(__file__)[0])[0]
script = os.path.join(base, 'nxdrive', 'commandline.py')
argv = [script, sys.argv[1]]
sys.exit(main(argv))


