#!/usr/bin/env python
"""Commandline interface for the Nuxeo Drive filesystem synchronizer"""

import sys
from nxdrive.commandline import main
sys.exit(main())
#sys.exit(main('commandline.py gui --log-level-file DEBUG --stop-on-error False'.split()))
