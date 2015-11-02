#!/usr/bin/env python2
import tools
import os
from timermanager		import TimerManager
from daemonprocess		import DaemonProcess
from daemon				import Daemon, InvalidConfigurationException, \
					TLSUnsupportedException, ConnectionRestarted, \
					TLSErrorException
if not "GTK2APP" in os.environ:
	# Condition above prevents __init__ from loading stuff that
	# depends on GTK3-only features, allowing GTK2 apps to use
	# Daemon object to interact with Syncthing
	from watcher			import Watcher
	from uibuilder			import UIBuilder
	from notifications		import Notifications, HAS_DESKTOP_NOTIFY
	from infobox			import InfoBox
	from editordialog		import EditorDialog
	from deviceeditor		import DeviceEditorDialog
	from foldereditor		import FolderEditorDialog
	from daemonsettings		import DaemonSettingsDialog
	from statusicon			import get_status_icon
	from configuration		import Configuration
	from iddialog			import IDDialog
	from aboutdialog		import AboutDialog
	from ignoreeditor		import IgnoreEditor
	from ribar				import RIBar
	from identicon			import IdentIcon
	from daemonoutputdialog	import DaemonOutputDialog
	try:
		# May fail if stdownloader is removed from distribution
		from stdownloader		import StDownloader
	except ImportError:
		StDownloader = None
	from uisettingsdialog	import UISettingsDialog
	from wizard				import Wizard
	from finddaemondialog	import FindDaemonDialog
	from app				import App
