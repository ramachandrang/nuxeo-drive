# !/usr/bin/env python
"""Commandline interface for launching the wizard from the installer"""

import sys
from nxdrive.commandline import main

argv = ['some_file', 'wizard']
sys.exit(main(argv))


