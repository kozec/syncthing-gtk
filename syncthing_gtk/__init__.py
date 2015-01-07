#!/usr/bin/env python2
import tools
from daemonprocess		import DaemonProcess
from configuration		import Configuration
from daemonoutputdialog	import DaemonOutputDialog
from stdownloader		import StDownloader
from wizard				import Wizard

# Internal version used by updater (if enabled)
INTERNAL_VERSION		= "v0.5.2"
# Minimal Syncthing version supported by App
MIN_ST_VERSION			= "0.10.3"
