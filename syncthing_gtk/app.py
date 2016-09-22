#!/usr/bin/env python2
"""
Syncthing-GTK - App

Main application window
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gio, Gdk
from syncthing_gtk import *
from syncthing_gtk.tools import *
from syncthing_gtk.tools import _ # gettext function
from datetime import datetime
import os, webbrowser, sys, time, logging, shutil, re
log = logging.getLogger("App")

# Internal version used by updater (if enabled)
INTERNAL_VERSION		= "v0.9.1"
# Minimal Syncthing version supported by App
MIN_ST_VERSION			= "0.13.0"

COLOR_DEVICE			= "#707070"					# Dark-gray
COLOR_DEVICE_SYNCING	= "#2A89C8"					# Blue
COLOR_DEVICE_CONNECTED	= "#2AAB61"					# Green
COLOR_DEVICE_OFFLINE	= COLOR_DEVICE				# Dark-gray
COLOR_DEVICE_ERROR		= "#87000B"					# Red
COLOR_OWN_DEVICE		= "#C0C0C0"					# Light-gray
COLOR_FOLDER			= "#9246B1"					# Dark-purbple
COLOR_FOLDER_SYNCING	= COLOR_DEVICE_SYNCING		# Blue
COLOR_FOLDER_SCANNING	= COLOR_DEVICE_SYNCING		# Blue
COLOR_FOLDER_IDLE		= COLOR_DEVICE_CONNECTED	# Green
COLOR_FOLDER_STOPPED	= COLOR_DEVICE_ERROR		# Red
COLOR_FOLDER_OFFLINE	= COLOR_DEVICE_OFFLINE		# Dark-gray
COLOR_NEW				= COLOR_OWN_DEVICE			# Light-gray
SI_FRAMES				= 12 # Number of animation frames for status icon

# Response IDs
RESPONSE_RESTART		= 256
RESPONSE_FIX_FOLDER_ID	= 257
RESPONSE_FIX_NEW_DEVICE	= 258
RESPONSE_FIX_IGNORE		= 259
RESPONSE_QUIT			= 260
RESPONSE_START_DAEMON	= 271
RESPONSE_SLAIN_DAEMON	= 272
RESPONSE_SPARE_DAEMON	= 273
RESPONSE_UR_ALLOW		= 274
RESPONSE_UR_FORBID		= 275

# RI's
REFRESH_INTERVAL_DEFAULT	= 1
REFRESH_INTERVAL_TRAY		= 5

# If daemon dies twice in this interval, broken settings are assumed
RESTART_TOO_FREQUENT_INTERVAL = 5

UPDATE_CHECK_INTERVAL = 12 * 60 * 60

# Speed values in outcoming/incoming speed limit menus
SPEED_LIMIT_VALUES = [ 10, 25, 50, 75, 100, 200, 500, 750, 1000, 2000, 5000 ]

class App(Gtk.Application, TimerManager):
	"""
	Main application / window.
	Hide parameter controlls if app should be minimized to status icon
	after start.
	"""
	def __init__(self, gladepath="/usr/share/syncthing-gtk",
						iconpath="/usr/share/syncthing-gtk/icons"):
		Gtk.Application.__init__(self,
				application_id="me.kozec.syncthingtk",
				flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
		TimerManager.__init__(self)
		# Setup Gtk.Application
		self.setup_commandline()
		# Set variables
		self.gladepath = gladepath
		self.iconpath = iconpath
		self.builder = None
		self.rightclick_box = None
		self.config = Configuration()
		self.process = None
		self.hide_window = self.config["minimize_on_start"]
		self.exit_after_wizard = False
		self.last_restart_time = 0.0
		# Can be changed by --force-update=vX.Y.Z argument
		self.force_update_version = None
		# Determine if header bar should be shown
		# User setting is not visible under Unity/Gnome
		self.use_headerbar = \
			not IS_UNITY and (not self.config["use_old_header"] or IS_GNOME) \
			and (Gtk.get_major_version(), Gtk.get_minor_version()) >= (3, 10)
		
		self.watcher = None
		self.daemon = None	# Created by setup_connection method
		self.notifications = None
		# connect_dialog may be displayed durring initial communication
		# or if daemon shuts down.
		self.connect_dialog = None
		# Used when upgrading from incompatibile version
		self.restart_after_update = None
		self.dark_color = None			# RGBA. None by default, changes with dark themes
		self.recv_limit = -1			# Used mainly to prevent menu handlers from recursing
		self.send_limit = -1			# -//-
		self.ur_question_shown = False	# Used to prevent showing 'Do you wan't usage reporting'
										# question more than once until ST-GTK is restarted.
		self.home_dir_override = None	# If set by '--home'
		self.wizard = None
		self.widgets = {}
		self.error_boxes = []
		self.error_messages = set([])	# Holds set of already displayed error messages
		self.folders = {}
		self.devices = {}
		self.open_boxes = set([])		# Holds set of expanded device/folder boxes
		self.devices_never_loaded = True
		self.folders_never_loaded = True
		self.sync_animation = 0
	
	
	def do_startup(self, *a):
		Gtk.Application.do_startup(self, *a)
		self.setup_widgets()
		self.setup_actions()
		self.setup_statusicon()
	
	def do_local_options(self, trash, lo):
		self.parse_local_options(lo.contains)
		return -1
	
	def parse_local_options(self, is_option):
		""" Test for expected options using specified method """
		set_logging_level(is_option("verbose"), is_option("debug") )
		if is_option("header"): self.use_headerbar = False
		if is_option("window"): self.hide_window = False
		if is_option("minimized"): self.hide_window = True
		if is_option("wizard"):
			self.exit_after_wizard = True
			self.show_wizard()
		elif is_option("about"):
			ad = AboutDialog(self, self.gladepath)
			ad.run([])
			sys.exit(0)
		
	def do_command_line(self, cl):
		Gtk.Application.do_command_line(self, cl)
		new_glib = GLib.glib_version >= (2, 40, 0)
		if new_glib:
			if cl.get_options_dict().contains("quit"):
				self.cb_exit()
				return 0
			if cl.get_options_dict().contains("home"):
				self.home_dir_override = cl.get_options_dict().lookup_value("home").get_string()
			if not StDownloader is None:
				if cl.get_options_dict().contains("force-update"):
					self.force_update_version = \
						cl.get_options_dict().lookup_value("force-update").get_string()
					if not self.force_update_version.startswith("v"):
						self.force_update_version = "v%s" % (self.force_update_version,)
			if cl.get_options_dict().contains("add-repo"):
				path = os.path.abspath(os.path.expanduser(
					cl.get_options_dict().lookup_value("add-repo").get_string()))
				self.show_add_folder_dialog(path)
			if cl.get_options_dict().contains("remove-repo"):
				path = os.path.abspath(os.path.expanduser(
					cl.get_options_dict().lookup_value("remove-repo").get_string()))
				self.show_remove_folder_dialog(path)
		else:
			# Fallback for old GTK without option parsing
			if "-h" in sys.argv or "--help" in sys.argv:
				print "Usage:"
				print "  %s [arguments]" % (sys.argv[0],)
				print "Arguments:"
				for o in self.arguments:
					# Don't display hidden and unsupported parameters
					if not o.long_name in ("force-update", "quit"):
						print "  -%s, --%s %s" % (
							chr(o.short_name),
							o.long_name.ljust(10),
							o.description)
				sys.exit(0)
			def is_option(name):
				# Emulating Gtk.Application.do_local_options
				for o in self.arguments:
					if o.long_name == name:
						if "-%s" % (chr(o.short_name),) in sys.argv:
							return True
						if "--%s" % (o.long_name,) in sys.argv:
							return True
				return False
			self.parse_local_options(is_option)
		
		if self.daemon == None:
			if self.wizard == None:
				if self.setup_connection():
					self.daemon.reconnect()
		self.activate()
		return 0
	
	def do_activate(self, *a):
		if self.hide_window:
			log.info("")
			log.info(_("Syncthing-GTK started and running in notification area"))
			if not self.daemon is None:
				self.daemon.set_refresh_interval(REFRESH_INTERVAL_TRAY)
		else:
			if self.wizard is None:
				# Show main window
				self.cb_statusicon_click()
		self.hide_window = False
	
	def setup_commandline(self):
		new_glib = GLib.glib_version >= (2, 40, 0)
		def aso(long_name, short_name, description,
				arg=GLib.OptionArg.NONE,
				flags=GLib.OptionFlags.IN_MAIN):
			""" add_simple_option, adds program argument in simple way """
			o = GLib.OptionEntry()
			o.long_name = long_name
			o.short_name = short_name
			o.description = description
			o.flags = flags
			o.arg = arg
			if new_glib:
				self.add_main_option_entries([o])
			else:
				self.arguments.append(o)

		if new_glib:
			# Guess who doesn't support option parsing...
			self.connect('handle-local-options', self.do_local_options)
		else:
			self.arguments = []
		aso("window",	b"w", "Display window (don't start minimized)")
		aso("minimized",b"m", "Hide window (start minimized)")
		aso("header",	b"s", "Use classic window header")
		aso("quit",		b"q", "Quit running instance (if any)")
		aso("verbose",	b"v", "Be verbose")
		aso("debug",	b"d", "Be more verbose (debug mode)")
		aso("wizard",	b"1", "Run 'first start wizard' and exit")
		aso("about",	b"a", "Display about dialog and exit")
		aso("home", 0, "Overrides default syncthing configuration directory",
				GLib.OptionArg.STRING)
		aso("add-repo", 0,    "Opens 'add repository' dialog with specified path prefilled",
				GLib.OptionArg.STRING)
		aso("remove-repo", 0, "If there is repository assigned with specified path, opens 'remove repository' dialog",
				GLib.OptionArg.STRING)
		if not StDownloader is None:
			aso("force-update", 0,
					"Force updater to download specific daemon version",
					GLib.OptionArg.STRING, GLib.OptionFlags.HIDDEN)
	
	def setup_actions(self):
		def add_simple_action(name, callback):
			action = Gio.SimpleAction.new(name, None)
			action.connect('activate', callback)
			self.add_action(action)
			return action
		add_simple_action('webui', self.cb_menu_webui)
		add_simple_action('daemon_output', self.cb_menu_daemon_output).set_enabled(False)
		add_simple_action('inotify_output', self.cb_menu_inotify_output).set_enabled(False)
		add_simple_action('preferences', self.cb_menu_ui_settings)
		add_simple_action('about', self.cb_about)
		add_simple_action('quit', self.cb_exit)

		add_simple_action('add_folder', self.cb_menu_add_folder)
		add_simple_action('add_device', self.cb_menu_add_device)
		add_simple_action('daemon_preferences', self.cb_menu_daemon_settings)
		add_simple_action('show_id', self.cb_menu_show_id)
		add_simple_action('daemon_shutdown', self.cb_menu_shutdown)
		add_simple_action('daemon_restart', self.cb_menu_restart)
	
	
	def setup_widgets(self):
		self.builder = UIBuilder()
		# Set conditions for UIBuilder
		old_gtk = ((Gtk.get_major_version(), Gtk.get_minor_version()) < (3, 12)) and not IS_WINDOWS
		icons_in_menu = self.config["icons_in_menu"]
		if self.use_headerbar: 		self.builder.enable_condition("header_bar")
		if not self.use_headerbar:	self.builder.enable_condition("traditional_header")
		if IS_WINDOWS: 				self.builder.enable_condition("is_windows")
		if IS_GNOME:  				self.builder.enable_condition("is_gnome")
		if old_gtk:					self.builder.enable_condition("old_gtk")
		if icons_in_menu:			self.builder.enable_condition("icons_in_menu")
		# Fix icon path
		self.builder.replace_icon_path("icons/", self.iconpath)
		# Load glade file
		self.builder.add_from_file(os.path.join(self.gladepath, "app.glade"))
		self.builder.connect_signals(self)
		# Dunno how to do this from glade
		if self.use_headerbar and IS_GNOME:
			self.set_app_menu(self["app-menu"])
		
		# Create speedlimit submenus for incoming and outcoming speeds
		L_MEH = [("menu-si-sendlimit", self.cb_menu_sendlimit),
				 ("menu-si-recvlimit", self.cb_menu_recvlimit)]
		for limitmenu, eventhandler in L_MEH:
			submenu = self["%s-sub" % (limitmenu,)]
			for speed in SPEED_LIMIT_VALUES:
				menuitem = Gtk.CheckMenuItem(_("%s kB/s") % (speed,))
				item_id = "%s-%s" % (limitmenu, speed)
				menuitem.connect('activate', eventhandler, speed)
				self[item_id] = menuitem
				submenu.add(menuitem)
			self[limitmenu].show_all()
		
		if not old_gtk:
			if not self["edit-menu-icon"] is None:
				if not Gtk.IconTheme.get_default().has_icon(self["edit-menu-icon"].get_icon_name()[0]):
					# If requested icon is not found in default theme, replace it with emblem-system-symbolic
					self["edit-menu-icon"].set_from_icon_name("emblem-system-symbolic", self["edit-menu-icon"].get_icon_name()[1])
		
		# Set window title in way that even Gnome can understand
		self["window"].set_title(_("Syncthing-GTK"))
		self["window"].set_wmclass("Syncthing GTK", "Syncthing GTK")
		self.add_window(self["window"])
	
	def setup_statusicon(self):
		self.statusicon = get_status_icon(self.iconpath, self["si-menu"])
		self.statusicon.connect("clicked",        self.cb_statusicon_click)
		self.statusicon.connect("notify::active", self.cb_statusicon_notify_active)
		self.cb_statusicon_notify_active()
	
	def setup_connection(self):
		# Create Daemon instance (loads and parses config)
		try:
			if self.home_dir_override:
				self.daemon = Daemon(os.path.join(self.home_dir_override, "config.xml"))
			else:
				self.daemon = Daemon(self.home_dir_override)
		except InvalidConfigurationException, e:
			# Syncthing is not configured, most likely never launched.
			# Run wizard.
			if IS_XP:
				# Wizard can't run on old Windows versions. Instead of
				# it, 'Give me daemon executable' dialog is shown
				self.cb_daemon_startup_failed(None, "Syncthing is not configured or configuration file cannot be found.")
				return False
			self.hide()
			self.show_wizard()
			return False
		except TLSErrorException, e:
			# This is pretty-much fatal. Display error message and bail out.
			self.cb_syncthing_con_error(daemon, Daemon.UNKNOWN, str(e), e)
			return False
		# Enable filesystem watching and desktop notifications,
		# if desired and possible
		if not Watcher is None:
			self.watcher = Watcher(self, self.daemon)
		if HAS_DESKTOP_NOTIFY:
			if self.config["notification_for_update"] or self.config["notification_for_error"]:
				self.notifications = Notifications(self, self.daemon)
		# Connect signals
		self.daemon.connect("config-out-of-sync", self.cb_syncthing_config_oos)
		self.daemon.connect("config-saved", self.cb_syncthing_config_saved)
		self.daemon.connect("connected", self.cb_syncthing_connected)
		self.daemon.connect("connection-error", self.cb_syncthing_con_error)
		self.daemon.connect("disconnected", self.cb_syncthing_disconnected)
		self.daemon.connect("error", self.cb_syncthing_error)
		self.daemon.connect("config-loaded", self.cb_config_loaded)
		self.daemon.connect("folder-rejected", self.cb_syncthing_folder_rejected)
		self.daemon.connect("device-rejected", self.cb_syncthing_device_rejected)
		self.daemon.connect("my-id-changed", self.cb_syncthing_my_id_changed)
		self.daemon.connect("device-added", self.cb_syncthing_device_added)
		self.daemon.connect("device-data-changed", self.cb_syncthing_device_data_changed)
		self.daemon.connect("last-seen-changed", self.cb_syncthing_last_seen_changed)
		self.daemon.connect("device-connected", self.cb_syncthing_device_state_changed, True)
		self.daemon.connect("device-disconnected", self.cb_syncthing_device_state_changed, False)
		self.daemon.connect("device-paused", self.cb_syncthing_device_paused_resumed, True)
		self.daemon.connect("device-resumed", self.cb_syncthing_device_paused_resumed, False)
		self.daemon.connect("device-sync-started", self.cb_syncthing_device_sync_progress)
		self.daemon.connect("device-sync-progress", self.cb_syncthing_device_sync_progress)
		self.daemon.connect("device-sync-finished", self.cb_syncthing_device_sync_progress, 1.0)
		self.daemon.connect("folder-added", self.cb_syncthing_folder_added)
		self.daemon.connect("folder-error", self.cb_syncthing_folder_error)
		self.daemon.connect("folder-data-changed", self.cb_syncthing_folder_data_changed)
		self.daemon.connect("folder-data-failed", self.cb_syncthing_folder_state_changed, 0.0, COLOR_NEW, "")
		self.daemon.connect("folder-sync-started", self.cb_syncthing_folder_state_changed, 0.0, COLOR_FOLDER_SYNCING, _("Syncing"))
		self.daemon.connect("folder-sync-progress", self.cb_syncthing_folder_state_changed, COLOR_FOLDER_SYNCING, _("Syncing"))
		self.daemon.connect("folder-sync-finished", self.cb_syncthing_folder_up_to_date)
		self.daemon.connect("folder-scan-started", self.cb_syncthing_folder_state_changed, 1.0, COLOR_FOLDER_SCANNING, _("Scanning"))
		self.daemon.connect("folder-scan-progress", self.cb_syncthing_folder_state_changed, COLOR_FOLDER_SCANNING, _("Scanning"))
		self.daemon.connect("folder-scan-finished", self.cb_syncthing_folder_up_to_date)
		self.daemon.connect("folder-stopped", self.cb_syncthing_folder_stopped) 
		self.daemon.connect("system-data-updated", self.cb_syncthing_system_data)
		return True
	
	def show_wizard(self):
		self.wizard = Wizard(self.gladepath, self.iconpath, self.config)
		self.wizard.connect('cancel', self.cb_wizard_finished)
		self.wizard.connect('close', self.cb_wizard_finished)
		self.wizard.show()
	
	def start_daemon_ui(self):
		"""
		Does same thing as start_daemon.
		Additionaly displays 'Starting Daemon' message and swaps
		menu items in notification icon menu.
		"""
		# Swap menu items in notification menu
		self["menu-si-shutdown"].set_visible(True)
		self["menu-si-resume"].set_visible(False)
		# Display message
		self.close_connect_dialog()
		self.display_connect_dialog(_("Starting Syncthing daemon"))
		# Start daemon
		self.start_daemon()

	def start_daemon(self):
		if self.process is None:
			if IS_WINDOWS:
				from syncthing_gtk import windows
				if windows.is_shutting_down():
					log.warning("Not starting daemon: System shutdown detected")
					return
			self.ct_process()
			self.lookup_action('daemon_output').set_enabled(True)
			self["menu-si-daemon-output"].set_sensitive(True)
	
	def ct_process(self):
		"""
		Sets self.process, adds related handlers and starts daemon.
		Just so I don't have to write same code all over the place.
		"""
		cmdline = [self.config["syncthing_binary"], "-no-browser"]
		vars, preargs, args = parse_config_arguments(self.config["syncthing_arguments"])
		cmdline = preargs + cmdline + args
		if self.home_dir_override:
			cmdline += [ "-home" , self.home_dir_override ]
		
		self.process = DaemonProcess(cmdline, self.config["daemon_priority"], self.config["max_cpus"], env=vars)
		self.process.connect('failed', self.cb_daemon_startup_failed)
		self.process.connect('exit', self.cb_daemon_exit)
		self.process.start()
	
	def ask_for_ur(self, *a):
		if self.ur_question_shown:
			# Don't ask twice until ST-GTK restart
			return
		markup = "".join([
			"<b>%s</b>" % (_("Allow Anonymous Usage Reporting?"),),
			"\n",
			_("The encrypted usage report is sent daily."), " ",
			_("It is used to track common platforms, folder sizes and app versions."), " ",
			_("If the reported data set is changed you will be prompted with this dialog again."),
			"\n",
			_("The aggregated statistics are publicly available at"), " ",
			"<a href='https://data.syncthing.net'>https://data.syncthing.net.</a>",
			"."
		])
		r = RIBar(markup, Gtk.MessageType.QUESTION)
		r.add_button(RIBar.build_button("gtk-yes", use_stock=True), RESPONSE_UR_ALLOW)
		r.add_button(RIBar.build_button("gtk-no", use_stock=True), RESPONSE_UR_FORBID)
		self.show_info_box(r)
		
		self.ur_question_shown = True
		# User response is handled in App.cb_infobar_response
	
	def check_for_upgrade(self, *a):
		if StDownloader is None:
			# Can't, someone stole my updater module :(
			return
		self.cancel_timer("updatecheck")
		if not self.config["st_autoupdate"]:
			# Disabled, don't even bother
			log.info("updatecheck: disabled")
			return
		if self.process == None:
			# Upgrading if executable is not launched by Syncthing-GTK
			# may fail in too many ways.
			log.warning("Skiping updatecheck: Daemon not launched by me")
			return
		if self.force_update_version is None:
			if (datetime.now() - self.config["last_updatecheck"]).total_seconds() < UPDATE_CHECK_INTERVAL:
				# Too soon, check again in 10 minutes
				self.timer("updatecheck", 60 * 10, self.check_for_upgrade)
				log.info("updatecheck: too soon")
				return
		log.info("Checking for updates...")
		# Prepare
		target = "%s.new" % (self.config["syncthing_binary"],)
		target_dir = os.path.split(target)[0]
		# Check for write access to parent directory
		if not can_upgrade_binary(self.config["syncthing_binary"]):
			self.cb_syncthing_error(None, "Warning: No write access to daemon binary; Skipping update check.")
			return
		# Determine platform
		suffix, tag = StDownloader.determine_platform()
		if suffix is None or tag is None:
			# Shouldn't really happen at this point
			log.warning("Cannot update: Unsupported platform")
			return
		
		# Define callbacks
		def cb_cu_error(*a):
			# Version check failed. Try it again later
			self.timer("updatecheck", 1 * 60 * 60, self.check_for_upgrade)
		
		def cb_cu_progress(sd, progress, pb):
			pb.set_fraction(progress)
		
		def cb_cu_extract_start(sd, l, pb):
			l.set_text(_("Extracting update..."))
			pb.set_fraction(0.0)
		
		def cb_cu_extract_finished(sd, r, l, pb):
			pb.hide()
			l.set_text(_("Restarting daemon..."))
			if self.daemon.is_connected():
				self.daemon.restart()
			else:
				# Happens when updating from unsupported version
				if not self.process is None:
					self.process.kill()
				else:
					self.start_daemon()
					self.set_status(False)
					self.restart()
			self.timer(None, 2, r.close)
		
		def cb_cu_download_fail(sd, exception, message, r):
			log.error("Download failed: %s", exception)
			r.close()
			self.cb_syncthing_error(None, _("Failed to download upgrade: %s") % (message))
			return cb_cu_error()
		
		def cb_cu_version(sd, version):
			needs_upgrade = False
			try:
				needs_upgrade = not compare_version(self.daemon.get_version(), version)
			except Exception:
				# May happen if connection to daemon is lost while version
				# check is running
				return cb_cu_error()
			if not self.force_update_version is None:
				needs_upgrade = True
				self.force_update_version = None
			log.info("Updatecheck: needs_upgrade = %s", needs_upgrade)
			self.config["last_updatecheck"] = datetime.now()
			if needs_upgrade:
				pb = Gtk.ProgressBar()
				l = Gtk.Label(_("Downloading Syncthing %s") % (version,))
				l.set_alignment(0, 0.5)
				box = Gtk.VBox()
				box.pack_start(l, True, True, 0)
				box.pack_start(pb, False, True, 1)
				box.show_all()
				r = RIBar(box, Gtk.MessageType.INFO)
				r.disable_close_button()
				self.show_info_box(r)
				sd.connect("error", cb_cu_download_fail, r)
				sd.connect("download-progress", cb_cu_progress, pb)
				sd.connect("extraction-progress", cb_cu_progress, pb)
				sd.connect("download-finished", cb_cu_extract_start, l, pb)
				sd.connect("extraction-finished", cb_cu_extract_finished, r, l, pb)
				sd.download()
			else:
				# No upgrade is needed. Schedule another check on later time
				self.timer("updatecheck", UPDATE_CHECK_INTERVAL, self.check_for_upgrade)
		
		# Check version
		sd = StDownloader(target, tag)
		sd.connect("error", cb_cu_error)
		sd.connect("version", cb_cu_version)
		if self.force_update_version is None:
			sd.get_version()
		else:
			sd.force_version(self.force_update_version)
	
	def swap_updated_binary(self):
		"""
		Switches newly downloaded binary with old one.
		Called while daemon is restarting after upgrade is downloaded.
		"""
		log.info("Found .new file, updating daemon binary")
		bin = self.config["syncthing_binary"]
		old_bin = bin + ".old"
		new_bin = bin + ".new"
		# Move old from way
		try:
			shutil.move(bin, old_bin)
		except Exception, e:
			log.warning("Failed to upgrade daemon binary: Failed to rename old binary")
			log.warning(e)
			return
		# Place new
		try:
			shutil.move(new_bin, bin)
		except Exception, e:
			log.warning("Failed to upgrade daemon binary: Failed to rename new binary")
			log.warning(e)
			# Return old back to place
			try:
				shutil.move(old_bin, bin)
			except Exception, e:
				# This really shouldn't happen, in more than one sense
				log.error("Failed to upgrade daemon binary: Failed to rename backup")
				log.exception(e)
			return
		# Remove old
		try:
			os.unlink(old_bin)
		except Exception, e:
			# Not exactly fatal
			log.warning("Failed to remove backup binary durring backup")
			log.warning(e)
	
	def cb_syncthing_connected(self, *a):
		self.clear()
		self.close_connect_dialog()
		self.set_status(True)
		self["edit-menu-button"].set_sensitive(True)
		self["menu-si-shutdown"].set_sensitive(True)
		self["menu-si-show-id"].set_sensitive(True)
		self["menu-si-recvlimit"].set_sensitive(True)
		self["menu-si-sendlimit"].set_sensitive(True)
		if IS_WINDOWS and not self.use_headerbar:
			# Stupid way to reconfigure window content and keep windows
			# decorations visible on Windows
			r = RIBar(
				_("Connected to Syncthing daemon"),
				Gtk.MessageType.INFO
				)
			self.show_info_box(r)
			self.cb_infobar_close(r)
	
	def cb_syncthing_disconnected(self, daemon, reason, message):
		# if reason == Daemon.UNEXPECTED
		message = "%s %s" % (
				_("Connection to Syncthing daemon lost."),
				_("Syncthing is probably restarting or has been shut down."))
		if reason == Daemon.SHUTDOWN:
			message = _("Syncthing has been shut down.")
			self["menu-si-shutdown"].set_visible(False)
			self["menu-si-resume"].set_visible(True)			
		elif reason == Daemon.RESTART:
			message = "%s %s..." % (_("Syncthing is restarting."), _("Please wait"))
		self.display_connect_dialog(message, quit_button = reason != Daemon.RESTART)
		if reason == Daemon.SHUTDOWN:
			# Add 'Start daemon again' button to dialog
			self.connect_dialog.add_button("Start Again", RESPONSE_START_DAEMON)
		elif reason == Daemon.RESTART:
			# Nothing, just preventing next branch from running
			pass
		elif IS_WINDOWS and not self.process is None:
			# Restart daemon process if connection is lost on Windows
			self.process.kill()
			self.process = None
			self.start_daemon()
		self.set_status(False)
		self.restart()
	
	def cb_syncthing_con_error(self, daemon, reason, message, exception):
		if reason == Daemon.REFUSED:
			# If connection is refused, handler just displays dialog with "please wait" message
			# and lets Daemon object to retry connection
			if self.connect_dialog == None:
				if check_daemon_running():
					# Daemon is running, wait for it
					self.display_connect_dialog(_("Connecting to Syncthing daemon at %s...") % (self.daemon.get_webui_url(),))
				else:
					# Daemon is probably not there, give user option to start it
					if self.config["autostart_daemon"] == 0:
						# ... unless he already decided once forever ...
						self.display_connect_dialog(_("Waiting for Syncthing daemon at %s...") % (self.daemon.get_webui_url(),))
					elif self.config["autostart_daemon"] == 1:
						# ... or already gave persmission ...
						self.display_connect_dialog(_("Starting Syncthing daemon"))
						self.start_daemon()
					else:
						self.display_run_daemon_dialog()
			self.set_status(False)
		elif reason == Daemon.OLD_VERSION and self.config["st_autoupdate"] and not self.process is None and not StDownloader is None:
			# Daemon is too old, but autoupdater is enabled and I have control of deamon.
			# Try to update.
			from configuration import LONG_AGO
			self.config["last_updatecheck"] = LONG_AGO
			self.restart_after_update = True
			self.close_connect_dialog()
			self.display_connect_dialog(_("Your syncthing daemon is too old.") + "\n" + _("Attempting to download recent, please wait..."))
			self.set_status(False)
			self.check_for_upgrade()
		else:
			# All other errors are fatal for now. Error dialog is displayed and program exits.
			if reason == Daemon.NOT_AUTHORIZED:
				message = _("Cannot authorize with daemon. Please, use WebUI to generate API key or disable password authentication.")
			elif reason == Daemon.OLD_VERSION:
				message = _("Your syncthing daemon is too old.\nPlease, upgrade syncthing package at least to version %s and try again.") % (self.daemon.get_min_version(),)
			elif reason == Daemon.TLS_UNSUPPORTED:
				message = _("Sorry, connecting to HTTPS is not supported on this platform.\nPlease, use WebUI to disable HTTPS try again.")
			else: # Daemon.UNKNOWN
				message = "%s\n\n%s %s" % (
						_("Connection to daemon failed. Check your configuration and try again."),
						_("Error message:"), str(message)
						)
				if "Not found" in str(message):
					# Special case that has usual explanation
					message = "%s\n%s" % (
						message,
						_("Possible cause: Is there another web server running on Syncthing port?")
					)
			d = Gtk.MessageDialog(
					self["window"],
					Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
					Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
					message
					)
			if not exception is None and hasattr(exception, 'full_response'):
				# Anything derived from HTTPError, where full server
				# response is attached
				ex = Gtk.Expander(label=_("More info"))
				tbuf = Gtk.TextBuffer()
				try:
					tbuf.set_text(u'Server response:\n\'%s\'' % (exception.full_response,))
				except Exception:
					# May happen when full_response can't be decoded
					try:
						tbuf.set_text(u'Server response:\n\'%s\'' % ((exception.full_response,),))
					except Exception:
						# Shouldn't really happen
						tbuf.set_text("<unparsable mess of data>")
				tview = Gtk.TextView(buffer=tbuf)
				swin = Gtk.ScrolledWindow()
				swin.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
				swin.add_with_viewport(tview)
				swin.set_size_request(300, 400)
				ex.add(swin)
				d.get_message_area().pack_end(ex, True, True, 1)
				ex.show_all()
			d.run()
			d.hide()
			d.destroy()
			self.quit()
	
	def cb_syncthing_config_oos(self, *a):
		if self["infobar"] == None:
			r = RIBar(
				_("The configuration has been saved but not activated.\nSyncthing must restart to activate the new configuration."),
				Gtk.MessageType.WARNING,
				( RIBar.build_button(_("_Restart"), "view-refresh"), RESPONSE_RESTART)
				)
			self["infobar"] = r
			self.show_info_box(r)
	
	def cb_syncthing_config_saved(self, *a):
		# Refresh daemon data from UI
		log.debug("Config saved")
		self.refresh()
	
	def cb_config_loaded(self, daemon, config):
		# Called after connection to daemon is initialized;
		# Used to change indicating UI components
		self.recv_limit = config["options"]["maxRecvKbps"]
		self.send_limit = config["options"]["maxSendKbps"]
		L_MEV = [("menu-si-sendlimit", self.send_limit),
				 ("menu-si-recvlimit", self.recv_limit)]
		
		for limitmenu, value in L_MEV:
			other = True
			for speed in [0] + SPEED_LIMIT_VALUES:
				menuitem = self["%s-%s" % (limitmenu, speed)]
				menuitem.set_active(speed == value)
				if speed == value:
					other = False
			self["%s-other" % (limitmenu,)].set_active(other)
		
		if config["options"]["urAccepted"] == 0:
			# User did not responded to usage reporting yet. Ask
			self.ask_for_ur()
		
		if not self.watcher is None:
			self.watcher.start()
	
	def cb_syncthing_error(self, daemon, message):
		""" Handles errors reported by syncthing daemon """
		# Daemon argument is not used
		RE_IP_PORT = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+):([0-9]+)")
		if "remote device speaks an older version of the protocol" in message:
			# This one needs special treatement because remote port changes
			# every time when this is reported.
			id = re.search("to ([-0-9A-Za-z]+)", message)
			version = re.search("protocol \(([^\)]+)\)", message)
			if not id or not version:
				# Invalid format
				return
			id = display_id = id.group(1)
			version = version.group(1)
			if id in self.devices:
				device = self.devices[id]
				display_id = device.get_title()
				device.set_color_hex(COLOR_DEVICE_ERROR)
				device.set_status(_("Incompatible"), 0)
				device.show_value("version")
				device["version"] = version
			
			message = _("Connecting to <b>%s</b> failed; the remote device speaks an older version of the protocol (%s) not compatible with this version") % (
					display_id, version)
		while RE_IP_PORT.search(message):
			# Strip any IP:port pairs in message to only IP. Port usually
			# changes with each error message
			ip, port = RE_IP_PORT.search(message).groups()
			message = message.replace("%s:%s" % (ip, port), ip)
		if message in self.error_messages:
			# Same error is already displayed
			log.info("(repeated) %s", message)
			return
		log.info(message)
		if "Unexpected folder ID" in message:
			# Handled by event, don't display twice
			return
		severity = Gtk.MessageType.WARNING
		if "Stopping folder" in message:
			severity = Gtk.MessageType.ERROR
		self.error_messages.add(message)
		bar = RIBar(message, severity)
		bar.connect("response", self.cb_error_response, message)
		self.show_error_box(bar)
	
	def cb_error_response(self, bar, response, message):
		# Remove closed error message from self.error_messages list,
		# so it can re-appear
		if message in self.error_messages:
			self.error_messages.remove(message)
	
	def cb_syncthing_folder_rejected(self, daemon, nid, rid, label):
		if (nid, rid) in self.error_messages:
			# Store as error message and don't display twice
			return
		self.error_messages.add((nid, rid))
		device, can_fix = nid, False
		if nid in self.devices:
			device = self.devices[nid].get_title()
			can_fix = True
		markup = _('%(device)s wants to share folder "%(folder)s". Add new folder?') % {
			'device' : "<b>%s</b>" % device,
			'folder' : "<b>%s</b>" % (label or rid)
			}
		r = RIBar("", Gtk.MessageType.WARNING,)
		r.get_label().set_markup(markup)
		if can_fix:
			r.add_button(RIBar.build_button(_("_Add")), RESPONSE_FIX_FOLDER_ID)
		self.show_error_box(r, {"nid" : nid, "rid" : rid, "label" : label } )
	
	def cb_syncthing_device_rejected(self, daemon, nid, name, address):
		# Remove port from address, it's random by default anyway
		if "[" in address:
			# IPv6 address
			address = address.split("]:")[0] + "]"
		else:
			# IPv4
			address = address.split(":")[0]
		if (nid, address) in self.error_messages:
			# Store as error message and don't display twice
			return
		self.error_messages.add((nid, address))
		markup = _('Device "<b>%(name)s</b>" (%(device)s) at IP "<b>%(ip)s</b>" wants to connect. Add new device?') % {
			'name' : name,
			'device' : "<b>%s</b>" % nid,
			'ip' : "<b>%s</b>" % address
			}
		r = RIBar("", Gtk.MessageType.WARNING,)
		r.get_label().set_markup(markup)
		r.add_button(RIBar.build_button(_("_Add")), RESPONSE_FIX_NEW_DEVICE)
		r.add_button(RIBar.build_button(_("_Ignore")), RESPONSE_FIX_IGNORE)
		self.show_error_box(r, {"nid" : nid, "name" : name, "address" : address} )
	
	def cb_syncthing_my_id_changed(self, daemon, device_id):
		if device_id in self.devices:
			device = self.devices[device_id]
			# Move my device to top
			self["devicelist"].reorder_child(device, 0)
			# Modify header & color
			device.set_status("")
			device.invert_header(True)
			device.set_color_hex(COLOR_OWN_DEVICE)
			if self.use_headerbar:
				self["header"].set_subtitle(device.get_title())
			else:
				self["server-name"].set_markup("<b>%s</b>" % (device.get_title(),))
			# Modify values
			device.clear_values()
			device.add_value("ram",		"ram.svg",		_("RAM Utilization"),	"")
			device.add_value("cpu",		"cpu.svg",		_("CPU Utilization"),	"")
			device.add_value("inbps",	"dl_rate.svg",	_("Download Rate"),		"0 B/s (0 B)")
			device.add_value("outbps",	"up_rate.svg",	_("Upload Rate"),		"0 B/s (0 B)")
			device.add_value("announce",	"announce.svg",	_("Announce Server"),	"")
			device.add_value("version",	"version.svg",	_("Version"),			None)
			device.show_all()
			# Expand my own device box right after startup
			if self.devices_never_loaded:
				self.open_boxes.add(device["id"])
				device.set_open(True)
				self.devices_never_loaded = True
			# Remove my own device from "Shared with" value in all shared directories
			# ( https://github.com/syncthing/syncthing/issues/915 )
			for folder in self.folders:
				f = self.folders[folder]
				if device in f["devices"]:
					f["shared"] = ", ".join([ n.get_title() for n in f["devices"] if n != device ])
			# Check for new version, if enabled
			self.check_for_upgrade()
	
	def cb_syncthing_system_data(self, daemon, mem, cpu, d_failed, d_total):
		if self.daemon.get_my_id() in self.devices:
			# Update my device display
			device = self.devices[self.daemon.get_my_id()]
			device["ram"] = sizeof_fmt(mem)
			device["cpu"] = "%3.2f%%" % (cpu)
			if d_total == 0:
				device["announce"] = _("disabled")
			else:			
				device["announce"] = "%s/%s" % (d_total - d_failed, d_total)
	
	def cb_syncthing_device_added(self, daemon, nid, name, used, data):
		self.show_device(nid, name,
			data["compression"],
			data["introducer"] if "introducer" in data else False,
			used
		)
	
	def cb_syncthing_device_data_changed(self, daemon, nid, address, client_version,
			inbps, outbps, inbytes, outbytes):
		if nid in self.devices:	# Should be always
			device = self.devices[nid]
			# Update strings
			device["address"] = address
			if client_version not in ("?", None):
				device["version"] = client_version
			# Update rates
			device['inbps'] = "%s/s (%s)" % (sizeof_fmt(inbps), sizeof_fmt(inbytes))
			device['outbps'] = "%s/s (%s)" % (sizeof_fmt(outbps), sizeof_fmt(outbytes))
	
	def cb_syncthing_last_seen_changed(self, daemon, nid, dt):
		if nid in self.devices:	# Should be always
			device = self.devices[nid]
			if dt is None:
				device['last-seen'] = _("Never")
			else:
				dtf = dt.strftime("%Y-%m-%d %H:%M")
				device['last-seen'] = str(dtf)
	
	def cb_syncthing_device_paused_resumed(self, daemon, nid, paused):
		if nid in self.devices:	# Should be always
			device = self.devices[nid]
			device.set_status(_("Paused") if paused else _("Disconnected"))
			device.set_color_hex(COLOR_DEVICE_OFFLINE)
			device["online"] = False
			device["connected"] = False
			# Update visible values
			device.hide_values("sync", "inbps", "outbps", "version")
			device.show_values("last-seen")
		self.update_folders()
		self.set_status(True)
	
	def cb_syncthing_device_state_changed(self, daemon, nid, connected):
		if nid in self.devices:	# Should be always
			device = self.devices[nid]
			if device["connected"] != connected:
				device["connected"] = connected
				if connected:
					# Update color & header
					device.set_status(_("Connected"))
					device.set_color_hex(COLOR_DEVICE_CONNECTED)
					device["online"] = True
					# Update visible values
					device.show_values("sync", "inbps", "oubps", "version")
					device.hide_values("last-seen")
				else:
					# Update color & header
					device.set_status(_("Disconnected"))
					device.set_color_hex(COLOR_DEVICE_OFFLINE)
					device["online"] = False
					# Update visible values
					device.hide_values("sync", "inbps", "outbps", "version")
					device.show_values("last-seen")
		self.update_folders()
		self.set_status(True)
	
	def cb_syncthing_device_sync_progress(self, daemon, device_id, sync):
		if device_id in self.devices:
			device = self.devices[device_id]
			device["sync"] = "%3.f%%" % (sync * 100.0)
			if not device["connected"]:
				device.set_color_hex(COLOR_DEVICE_OFFLINE)
				device.set_status(_("Disconnected"))
			elif sync >= 0.0 and sync < 0.99:
				device.set_color_hex(COLOR_DEVICE_SYNCING)
				device.set_status(_("Syncing"), sync)
			else:
				device.set_color_hex(COLOR_DEVICE_CONNECTED)
				device.set_status(_("Up to Date"))
	
	def cb_syncthing_folder_added(self, daemon, rid, r):
		box = self.show_folder(
			rid, r["label"], r["path"],
			r["type"] == "readonly",
			r["ignorePerms"], 
			r["rescanIntervalS"],
			sorted(
				[ self.devices[n["deviceID"]] for n in r["devices"] if n["deviceID"] in self.devices ],
				key=lambda x : x.get_title().lower()
				)
			)
		if not self.watcher is None:
			if rid in self.config["use_inotify"]:
				self.watcher.watch(box["id"], box["norm_path"])
				if IS_WINDOWS:
					self.lookup_action('inotify_output').set_enabled(True)
	
	def cb_syncthing_folder_data_changed(self, daemon, rid, data):
		if rid in self.folders:	# Should be always
			folder = self.folders[rid]
			folder["global"] = "%s %s, %s" % (data["globalFiles"], _("Files"), sizeof_fmt(data["globalBytes"]))
			folder["local"]	 = "%s %s, %s" % (data["localFiles"], _("Files"), sizeof_fmt(data["localBytes"]))
			folder["oos"]	 = "%s %s, %s" % (data["needFiles"], _("Files"), sizeof_fmt(data["needBytes"]))
			if folder["b_master"]:
				can_override = (data["needFiles"] > 0)
				if can_override != folder["can_override"]:
					folder["can_override"] = can_override
					self.cb_syncthing_folder_up_to_date(None, rid)
	
	def cb_syncthing_folder_up_to_date(self, daemon, rid):
		if rid in self.folders:	# Should be always
			folder = self.folders[rid]
			self.cb_syncthing_folder_state_changed(daemon, rid, 1.0,
				COLOR_FOLDER_IDLE,
				_("Cluster out of sync") if folder["can_override"] else _("Up to Date")
			)
		
	def cb_syncthing_folder_state_changed(self, daemon, rid, percentage, color, text):
		if rid in self.folders:	# Should be always
			folder = self.folders[rid]
			folder.set_color_hex(color)
			folder.set_status(text, percentage)
			self.update_folders()
			self.set_status(True)
	
	def cb_syncthing_folder_stopped(self, daemon, rid, message):
		if rid in self.folders:	# Should be always
			folder = self.folders[rid]
			folder.set_color_hex(COLOR_FOLDER_STOPPED)
			folder.set_status(_("Stopped"), 0)
			# Color, theme-based icon is used here. It's intentional and
			# supposed to draw attention
			folder.add_value("error", "dialog-error", _("Error"), message)
			folder.show_value('error')
	
	def cb_syncthing_folder_error(self, daemon, rid, errors):
		if rid in self.folders:	# Should be always
			folder = self.folders[rid]
			message = "%(path)s: %(error)s" % errors[-1]
			folder.add_value("error", "dialog-error", _("Error"), message)
			folder.show_value('error')
	
	def any_device_online(self):
		"""
		Returns True if there is at least one device connected to daemon
		"""
		for box in self.devices.values():
			if box["online"] and box["id"] != self.daemon.get_my_id():
				return True
		return False
	
	def set_status(self, is_connected):
		""" Sets icon and text on first line of popup menu """
		if is_connected:
			if self.daemon.syncing():
				# Daemon is online and at work
				sr = self.daemon.get_syncing_list()
				if len(sr) == 1:
					self["menu-si-status"].set_label(_("Synchronizing '%s'") % (sr[0],))
				else:
					self["menu-si-status"].set_label(_("Synchronizing %s folders") % (len(sr),))
				self.animate_status()
			elif self.any_device_online():
				# Daemon is online and idle
				self.statusicon.set("si-%s-idle" % (self.config['icon_theme'],), _("Up to Date"))
				self["menu-si-status"].set_label(_("Up to Date"))
				self.cancel_timer("icon")
			else:
				# Daemon is online, but there is no remote device connected
				self.statusicon.set("si-%s-unknown" % (self.config['icon_theme'],), _("All devices offline"))
				self["menu-si-status"].set_label(_("All devices offline"))
				self.cancel_timer("icon")
		else:
			# Still connecting to syncthing daemon
			self.statusicon.set("si-%s-unknown" % (self.config['icon_theme'],), _("Connecting to Syncthing daemon..."))
			self["menu-si-status"].set_label(_("Connecting to Syncthing daemon..."))
			self.cancel_timer("icon")
	
	def animate_status(self):
		""" Handles icon animation """
		if self.timer_active("icon"):
			# Already animating
			return
		self.statusicon.set("si-%s-%s" % (self.config['icon_theme'], self.sync_animation,))
		self.sync_animation += 1
		if self.sync_animation >= SI_FRAMES:
			self.sync_animation = 0
		self.timer("icon", 0.1, self.animate_status)
	
	def update_folders(self):
		"""
		Sets status of any 'idle' folder that has no devices online to
		'offline' and back if one of devices got connected.
		"""
		for rid in self.folders:
			online = False
			folder = self.folders[rid]
			for device in folder["devices"]:
				online = online or device["online"]
			if online and folder.compare_color_hex(COLOR_FOLDER_OFFLINE):
				# Folder was marked as offline but is back online now
				if folder["can_override"]:
					folder.set_status(_("Cluster out of sync"))
				else:
					folder.set_status(_("Up to Date"))
				folder.set_color_hex(COLOR_FOLDER_IDLE)
			elif not online and folder.compare_color_hex(COLOR_FOLDER_SCANNING):
				# Folder is offline and in Scanning state
				folder.set_color_hex(COLOR_FOLDER_OFFLINE)
			elif not online and folder.compare_color_hex(COLOR_FOLDER_IDLE):
				# Folder is offline and in Idle state (not scanning)
				if len([ d for d in folder["devices"] if d["id"] != self.daemon.get_my_id()]) == 0:
					# No device to share folder with
					folder.set_status(_("Unshared"))
				else:
					# Folder is shared, but all devices are offline
					folder.set_status(_("Offline"))
				folder.set_color_hex(COLOR_FOLDER_OFFLINE)
	
	def show_error_box(self, ribar, additional_data={}):
		self.show_info_box(ribar, additional_data)
		self.error_boxes.append(ribar)
	
	def show_info_box(self, ribar, additional_data=None):
		self["content"].pack_start(ribar, False, False, 0)
		self["content"].reorder_child(ribar, 0 if self.use_headerbar else 1)
		ribar.connect("close", self.cb_infobar_close)
		ribar.connect("response", self.cb_infobar_response, additional_data)
		ribar.show()
		ribar.set_reveal_child(True)
	
	def fatal_error(self, text):
		# TODO: Better way to handle this
		log.error(text)
		d = Gtk.MessageDialog(
				None,
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
				text
				)
		d.run()
		d.hide()
		d.destroy()
		self.quit()
	
	def get_folder_n_path(self, path):
		"""
		Returns tuple of ID of folder containign specified path and
		relative path in that folder, or (None, None) if specified path
		doesn't belongs anywhere
		"""
		for folder_id in self.folders:
			f = self.folders[folder_id]
			relpath = os.path.relpath(path, f["norm_path"])
			if not relpath.startswith("../") and relpath != "..":
				return (folder_id, relpath)
		return (None, None)
	
	def __getitem__(self, name):
		""" Convince method that allows widgets to be accessed via self["widget"] """
		if name in self.widgets:
			return self.widgets[name]
		return self.builder.get_object(name)
	
	def __setitem__(self, name, item):
		""" Convince method that allows widgets to be accessed via self["widget"] """
		self.widgets[name] = item
	
	def __contains__(self, name):
		""" Returns True if there is such widget """
		if name in self.widgets: return True
		return self.builder.get_object(name) != None
	
	def hilight(self, boxes):
		to_hilight = set([])
		for box in boxes:
			if box["id"] in self.folders:
				for d in box["devices"]:
					if d["id"] != self.daemon.get_my_id():
						to_hilight.add(d)
				to_hilight.add(box)
			if box["id"] in self.devices and box["id"] != self.daemon.get_my_id():
				for f in self.folders.values():
					if box in f["devices"]:
						to_hilight.add(f)
				to_hilight.add(box)
		for box in [] + self.devices.values() + self.folders.values():
			box.set_hilight(box in to_hilight)
	
	def is_visible(self):
		""" Returns True if main window is visible """
		return self["window"].is_visible()
	
	def show(self):
		"""
		Shows main window or brings it to front, if is already visible.
		If connection to daemon is not established, shows 'Connecting'
		dialog as well.
		"""
		if not self.daemon is None:
			self.daemon.set_refresh_interval(REFRESH_INTERVAL_DEFAULT)
			self.daemon.request_events()
		if not self["window"].is_visible():
			self["window"].show()
			if IS_WINDOWS and not self.config["window_position"] is None:
				scr = Gdk.Screen.get_default()
				self.config["window_position"] = (
					min(self.config["window_position"][0], scr.width() - 300),
					min(self.config["window_position"][1], scr.height() - 100)
				)
				self["window"].move(*self.config["window_position"] )
			if self.connect_dialog != None:
				self.connect_dialog.show()
		else:
			self["window"].present()
		self["menu-si-show"].set_label(_("Hide Window"))
	
	def hide(self):
		""" Hides main windows and 'Connecting' dialog, if displayed """
		if self.connect_dialog != None:
			self.connect_dialog.hide()
		if IS_WINDOWS:
			x, y = self["window"].get_position()
			if x < 0 : x = 0
			if y < 0 : y = 0
			# Yes, it is possible for window to have negative position
			# on Windows...
			self.config["window_position"] = (x, y)
		self["window"].hide()
		self["menu-si-show"].set_label(_("Show Window"))
		if not self.daemon is None:
			self.daemon.set_refresh_interval(REFRESH_INTERVAL_TRAY)
	
	def display_connect_dialog(self, message, quit_button=True):
		"""
		Displays 'Be patient, i'm trying to connect here' dialog, or updates
		it's message if said dialog is already displayed.
		"""
		if self.connect_dialog == None:
			log.debug("Creating connect_dialog")
			self.connect_dialog = Gtk.MessageDialog(
				self["window"],
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.INFO, 0, "-")
			if quit_button:
				self.connect_dialog.add_button("gtk-quit", RESPONSE_QUIT)
			# There is only one response available on this dialog
			self.connect_dialog.connect("response", self.cb_connect_dialog_response, None)
			if self.is_visible():
				self.connect_dialog.show_all()
		def set_label(d, message):
			"""
			Small, recursive helper function to set label somehwere
			deep in dialog
			"""
			for c in d.get_children():
				if isinstance(c, Gtk.Container):
					if set_label(c, message):
						return True
				elif isinstance(c, Gtk.Label):
					c.set_markup(message)
					return True
			return False
		log.verbose("Settinig connect_dialog label %s" % message[0:15])
		set_label(self.connect_dialog.get_content_area(), message)
	
	def display_run_daemon_dialog(self):
		"""
		Displays 'Syncthing is not running, should I start it for you?'
		dialog.
		"""
		if self.connect_dialog == None: # Don't override already existing dialog
			log.debug("Creating run_daemon_dialog")
			self.connect_dialog = Gtk.MessageDialog(
				self["window"],
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.INFO, 0,
				"%s\n%s" % (
					_("Syncthing daemon doesn't appear to be running."),
					_("Start it now?")
					)
				)
			cb = Gtk.CheckButton(_("Always start daemon automatically"))
			self.connect_dialog.get_content_area().pack_end(cb, False, False, 2)
			self.connect_dialog.add_button("_Start",   RESPONSE_START_DAEMON)
			self.connect_dialog.add_button("gtk-quit", RESPONSE_QUIT)
			# There is only one response available on this dialog
			self.connect_dialog.connect("response", self.cb_connect_dialog_response, cb)
			if self.is_visible():
				self.connect_dialog.show_all()
			else:
				cb.show()	# Keep this one visible, even if dialog is not
			# Update notification icon menu so user can start daemon from there
			self["menu-si-shutdown"].set_visible(False)
			self["menu-si-resume"].set_visible(True)
	
	def close_connect_dialog(self):
		if self.connect_dialog != None:
			self.connect_dialog.hide()
			self.connect_dialog.destroy()
			self.connect_dialog = None
			
			if IS_WINDOWS:
				# Force windows position on Windows - GTK 3.18 moves
				# window to corner when connect_dialog disappears for
				# some unexplainable reason
				x, y = self["window"].get_position()
				
				def move_back():
					self["window"].move(x, y)
				GLib.idle_add(move_back)
	
	def show_folder(self, id, label, path, is_master, ignore_perms, rescan_interval, shared):
		""" Shared is expected to be list """
		display_path = path
		if IS_WINDOWS:
			if display_path.lower().replace("\\", "/").startswith(os.path.expanduser("~").lower()):
				display_path = "~%s" % display_path[len(os.path.expanduser("~")):]
		title = id
		if self.config["folder_as_path"]:
			title = display_path
		if label not in (None, ""):
			title = label
		if id in self.folders:
			# Reuse existing box
			box = self.folders[id]
			box.set_title(title)
		else:
			# Create new box
			box = InfoBox(self, title, Gtk.Image.new_from_icon_name("drive-harddisk", Gtk.IconSize.LARGE_TOOLBAR))
			# Add visible lines
			box.add_value("id",			"version.svg",	_("Folder ID"),			id)
			box.add_value("path",		"folder.svg",	_("Path"))
			box.add_value("global",		"global.svg",	_("Global State"),		"? items, ?B")
			box.add_value("local",		"home.svg",		_("Local State"),		"? items, ?B")
			box.add_value("oos",		"dl_rate.svg",	_("Out Of Sync"),		"? items, ?B")
			box.add_value("master",		"lock.svg",		_("Folder Master"))
			box.add_value("ignore",		"ignore.svg",	_("Ignore Permissions"))
			box.add_value("rescan",		"rescan.svg",	_("Rescan Interval"))
			box.add_value("shared",		"shared.svg",	_("Shared With"))
			# Add hidden stuff
			box.add_hidden_value("b_master", is_master)
			box.add_hidden_value("can_override", False)
			box.add_hidden_value("devices", shared)
			box.add_hidden_value("norm_path", os.path.abspath(os.path.expanduser(path)))
			box.add_hidden_value("label", label)
			# Setup display & signal
			box.set_status("Unknown")
			if not self.dark_color is None:
				box.set_dark_color(*self.dark_color)
			box.set_color_hex(COLOR_FOLDER)
			box.set_vexpand(False)
			GLib.idle_add(box.show_all)	# Window border will dissapear without this on Windows
			self["folderlist"].pack_start(box, False, False, 3)
			box.set_open(id in self.open_boxes or self.folders_never_loaded)
			box.connect('right-click', self.cb_popup_menu_folder)
			box.connect('doubleclick', self.cb_browse_folder)
			box.connect('enter-notify-event', self.cb_box_mouse_enter)
			box.connect('leave-notify-event', self.cb_box_mouse_leave)
			self.folders[id] = box
			self.folders_never_loaded = False
		# Set values
		box.set_value("id",		id)
		box.set_value("path",	display_path)
		box.set_value("master",	_("Yes") if is_master else _("No"))
		box.set_value("ignore",	_("Yes") if ignore_perms else _("No"))
		box.set_value("rescan",	"%s s%s" % (
			rescan_interval, " " + _("(watch)") if id in self.config["use_inotify"] else "" ))
		box.set_value("shared",	", ".join([ n.get_title() for n in shared ]))
		box.set_value("b_master", is_master)
		box.set_value("can_override", False)
		box.set_visible("id",		self.config["folder_as_path"] or label not in (None, ""))
		box.set_visible("master",	is_master)
		box.set_visible("ignore",	ignore_perms)
		return box
	
	def show_device(self, id, name, compression, introducer, used):
		if name in (None, ""):
			# Show first block from ID if name is unset
			name = id.split("-")[0]
		if not used:
			name = "%s (%s)" % (name, _("Unused"))
		if id in self.devices:
			# Reuse existing box
			box = self.devices[id]
			box.set_title(name)
		else:
			# Create new box
			box = InfoBox(self, name, IdentIcon(id))
			# Add visible lines
			box.add_value("address",	"address.svg",	_("Address"),			None)
			box.add_value("sync",		"sync.svg",		_("Synchronization"),	"0%", visible=False)
			box.add_value("compress",	"compress.svg",	_("Compression"))
			box.add_value("inbps",		"dl_rate.svg",	_("Download Rate"),		"0 B/s (0 B)", visible=False)
			box.add_value("outbps",		"up_rate.svg",	_("Upload Rate"),		"0 B/s (0 B)", visible=False)
			box.add_value("introducer",	"thumb_up.svg",	_("Introducer"))
			box.add_value("version",	"version.svg",	_("Version"),			None, visible=False)
			box.add_value('last-seen',	"clock.svg",	_("Last Seen"),			_("Never"))
			# Add hidden stuff
			box.add_hidden_value("id", id)
			box.add_hidden_value("connected", False)
			box.add_hidden_value("completion", {})
			box.add_hidden_value("time", 0)
			box.add_hidden_value("online", False)
			# Setup display & signal
			if not self.dark_color is None:
				box.set_dark_color(*self.dark_color)
			box.set_color_hex(COLOR_DEVICE)
			box.set_vexpand(False)
			box.set_open(id in self.open_boxes)
			box.get_icon().set_size_request(22, 22)
			GLib.idle_add(box.show_all)	# Window border will dissapear without this on Windows
			self["devicelist"].pack_start(box, False, False, 3)
			box.connect('right-click', self.cb_popup_menu_device)
			box.connect('enter-notify-event', self.cb_box_mouse_enter)
			box.connect('leave-notify-event', self.cb_box_mouse_leave)
			self.devices[id] = box
		# Set values
		if compression in (True, "always"): box.set_value("compress", _("All Data"))
		elif compression in (False, "never"): box.set_value("compress", _("Off"))
		else: box.set_value("compress", _("Metadata Only"))
		box.set_value("introducer",	_("Yes") if introducer else _("No"))
		box.set_value('last-seen',	_("Never"))
		return box
	
	def clear(self):
		""" Clears folder and device lists. """
		for i in ('devicelist', 'folderlist'):
			for c in [] + self[i].get_children():
				self[i].remove(c)
				c.destroy()
		self.devices = {}
		self.folders = {}
	
	def restart(self):
		"""
		Removes everything, restets all data and reconnects
		to daemon.
		"""
		self["edit-menu-button"].set_sensitive(False)
		self["menu-si-shutdown"].set_sensitive(False)
		self["menu-si-show-id"].set_sensitive(False)
		self["menu-si-recvlimit"].set_sensitive(False)
		self["menu-si-sendlimit"].set_sensitive(False)
		if not self["infobar"] is None:
			self.cb_infobar_close(self["infobar"])
		for r in self.error_boxes:
			r.get_parent().remove(r)
			r.destroy()
		self.error_boxes = []
		self.error_messages = set([])
		self.cancel_all() # timers
		if not self.watcher is None:
			self.watcher.kill()
		self.daemon.reconnect()
	
	def refresh(self):
		"""
		Similar to restart().
		Re-requests all data from daemon, without disconnecting.
		Then refreshes all UI widgets.
		Looks cleaner & prevents UI from blinking.
		"""
		log.debug("Reloading config...")
		if not self.watcher is None:
			self.watcher.kill()
			self.lookup_action('inotify_output').set_enabled(False)
		def callback(*a):
			if not self.watcher is None:
				GLib.timeout_add_seconds(1, self.watcher.start)
		self.daemon.reload_config(callback)
	
	def change_setting_async(self, setting_name, value, retry_on_error=False, restart=True):
		"""
		Asynchronously changes one value in daemon configuration and
		optionaly restarts daemon.
		
		This will:
		 - call daemon.read_config() to read configuration from daemon
		 - change value in recieved YAML document
		 - call daemon.write_config() to post configuration back
		 - call daemon.restart()
		Everthing will be done asynchronously and will be repeated
		until succeed, if retry_on_error is set to True.
		Even if retry_on_error is False, error in write_config will
		be only logged.
		
		It is possible to change nested setting using '/' as separator.
		That may cause error if parent setting node is not present and
		this error will not cause retrying process as well.
		
		If value is callable, it's called instead of setting it.
		In such case, callable is called as:
		   value(config_node_as_dict, setting_name)
		"""
		# ^^ Longest comment in entire project
		
		# Callbacks
		def csnr_error(e, trash, setting_name, value, retry_on_error):
			"""
			Error handler for change_setting_async method
			"""
			log.error("change_setting_async: Failed to read configuration: %s", e)
			if retry_on_error:
				log.error("Retrying...")
				change_setting_async(setting_name, value, retry_on_error, restart)
			else:
				log.error("Giving up.")
		
		def csnr_save_error(e, *a):
			"""
			Another error handler for change_setting_async method.
			This one just reports failure.
			"""
			log.error("change_setting_async: Failed to store configuration: %s", e)
			log.error("Giving up.")
		
		def csnr_config_read(config, setting_name, value, retry_on_error):
			"""
			Handler for change_setting_async
			Modifies recieved config and post it back.
			"""
			c, setting = config, setting_name
			while "/" in setting:
				key, setting = setting.split("/", 1)
				c = c[key]
			if hasattr(value, '__call__'):
				value(c, setting)
			else:
				c[setting] = value
			self.daemon.write_config(config, csnr_config_saved, csnr_save_error, setting_name, value)
		
		def csnr_config_saved(setting_name, value):
			"""
			Handler for change_setting_async
			Reports good stuff and restarts daemon.
			"""
			log.verbose("Configuration value '%s' set to '%s'", setting_name, value)
			if restart:
				message = "%s %s..." % (_("Syncthing is restarting."), _("Please wait"))
				self.display_connect_dialog(message)
				self.set_status(False)
				self.restart()
				GLib.idle_add(self.daemon.restart)
		
		# Call
		self.daemon.read_config(csnr_config_read, csnr_error, setting_name, value, retry_on_error)
	
	def quit(self, *a):
		if self.process != None:
			if IS_WINDOWS:
				# Always kill subprocess on windows
				self.process.kill()
				self.process = None
				if not self.watcher is None:
					self.watcher.kill()
			elif self.config["autokill_daemon"] == 2:	# Ask
				d = Gtk.MessageDialog(
					self["window"],
					Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
					Gtk.MessageType.INFO, 0,
					"%s\n%s" % (
						_("Exiting."),
						_("Shutdown Syncthing daemon as well?")
						)
					)
				d.add_button("gtk-yes",	RESPONSE_SLAIN_DAEMON)
				d.add_button("gtk-no",	RESPONSE_SPARE_DAEMON)
				cb = Gtk.CheckButton(_("Always do same; Don't show this window again"))
				d.get_content_area().pack_end(cb, False, False, 2)
				d.connect("response", self.cb_kill_daemon_response, cb)
				d.show_all()
				return
			elif self.config["autokill_daemon"] == 1: # Yes
				self.process.terminate()
				self.process = None
		Gtk.Application.quit(self)
	
	def show_add_folder_dialog(self, path=None):
		"""
		Waits for daemon to connect and shows 'add folder' dialog,
		optionaly with pre-filled path entry.
		"""
		handler_id = None
		def have_config(*a):
			""" One-time handler for config-loaded signal """
			if not handler_id is None:
				self.daemon.handler_disconnect(handler_id)
			self.show()
			e = FolderEditorDialog(self, True, None, path)
			e.call_after_loaded(e.fill_folder_id, generate_folder_id(), False)
			e.load()
			e.show(self["window"])
		
		if self.daemon.is_connected():
			have_config()
		else:
			handler_id = self.daemon.connect("config-loaded", have_config)
	
	def show_remove_folder_dialog(self, path):
		"""
		Waits for daemon to connect, then searchs for folder id assigned
		with specified path and shows 'remove folder' dialog, it such
		id is found.
		If id is not found, does nothing.
		"""
		handler_id = None
		def have_config(*a):
			""" One-time handler for config-loaded signal """
			if not handler_id is None:
				self.daemon.handler_disconnect(handler_id)
			for rid in self.folders:
				if self.folders[rid]["path"] == path:
					name = self.folders[rid].get_title()
					self.show()
					self.check_delete("folder", rid, name)
					return
			log.warning("Failed to remove directory for path '%s': No such folder", path)
		
		if self.daemon.is_connected():
			have_config()
		else:
			handler_id = self.daemon.connect("config-loaded", have_config)
	
	# --- Callbacks ---
	def cb_exit(self, *a):
		self.statusicon.hide()
		self.quit()
	
	def cb_about(self, *a):
		AboutDialog(self, self.gladepath).show(self["window"])
	
	def cb_delete_event(self, *e):
		# Hide main window
		self.hide()
		return True
	
	def cb_realized(self, widget, *a):
		context = widget.get_style_context()
		color = context.get_background_color(Gtk.StateFlags.SELECTED)
		# Dark color: Gdk.RGBA(red=0.223529, green=0.247059, blue=0.247059, alpha=1.000000)
		# Light color: Gdk.RGBA(red=0.929412, green=0.929412, blue=0.929412, alpha=1.000000)
		light_color = False
		for c in list(color)[0:3]:
			if c > 0.75: light_color = True
		if not light_color:
			# Set dark color based on current window background
			self.dark_color = (color.red, color.green, color.blue, 1.0)
			# Recolor all boxes
			for box in self.folders.values():
				box.set_dark_color(*self.dark_color)
			for box in self.devices.values():
				box.set_dark_color(*self.dark_color)
	
	def cb_box_mouse_enter(self, box, *a):
		self.hilight([box])

	def cb_box_mouse_leave(self, *a):
		self.hilight([])
	
	def cb_menu_show_id(self, *a):
		d = IDDialog(self, self.daemon.get_my_id())
		d.show(self["window"])
	
	def cb_menu_add_folder(self, event, *a):
		""" Handler for 'Add folder' menu item """
		self.show_add_folder_dialog()
	
	def cb_menu_add_device(self, event, *a):
		""" Handler for 'Add device' menu item """
		e = DeviceEditorDialog(self, True)
		e.load()
		e.show(self["window"])
	
	def cb_menu_daemon_settings(self, event, *a):
		""" Handler for 'Daemon Settings' menu item """
		e = DaemonSettingsDialog(self)
		e.load()
		e.show(self["window"])
	
	def cb_menu_ui_settings(self, event, *a):
		""" Handler for 'UI Settings' menu item """
		e = UISettingsDialog(self)
		e.load()
		e.show(self["window"])
	
	def cb_menu_recvlimit(self, menuitem, speed=0):
		if menuitem.get_active() and self.recv_limit != speed:
			self.change_setting_async("options/maxRecvKbps", speed)
	
	def cb_menu_sendlimit(self, menuitem, speed=0):
		if menuitem.get_active() and self.send_limit != speed:
			self.change_setting_async("options/maxSendKbps", speed)
	
	def cb_menu_recvlimit_other(self, menuitem):
		return self.cb_menu_limit_other(menuitem, self.recv_limit)
	
	def cb_menu_sendlimit_other(self, menuitem):
		return self.cb_menu_limit_other(menuitem, self.send_limit)
	
	def cb_menu_limit_other(self, menuitem, speed):
		# Common for cb_menu_recvlimit_other and cb_menu_sendlimit_other
		#
		# Removes checkbox, if speed is not considered as 'other'
		# Displays configuration dialog
		# Detect if checkbox was changed by user
		checked_by_user = (
			(speed in [0] + SPEED_LIMIT_VALUES 
				and menuitem.get_active())
			or
			(not speed in [0] + SPEED_LIMIT_VALUES 
				and not menuitem.get_active())
			)
		if checked_by_user:
			# Display daemon settings dialog and (un)check box back to
			# its correct state
			self.cb_menu_daemon_settings(None)
			menuitem.set_active(not menuitem.get_active())
	
	def cb_popup_menu_folder(self, box, button, time):
		self.rightclick_box = box
		self["menu-popup-override"].set_visible(box["can_override"])
		self["menu-separator-override"].set_visible(box["can_override"])
		self["popup-menu-folder"].popup(None, None, None, None, button, time)
	
	def cb_popup_menu_device(self, box, button, time):
		self.rightclick_box = box
		# Display 'edit device' and 'delete device' menu items on
		# everything but my own node
		b = box["id"] != self.daemon.get_my_id()
		self["menu-popup-edit-device"].set_visible(b)
		self["menu-popup-delete-device"].set_visible(b)
		self["menu-popup-pause-device"].set_visible(box.get_status() != _("Paused"))
		self["menu-popup-resume-device"].set_visible(box.get_status() == _("Paused"))
		self["popup-menu-device"].popup(None, None, None, None, button, time)
	
	def cb_menu_popup(self, source, menu):
		""" Handler for ubuntu-only toolbar buttons """
		menu.popup(None, None, None, None, 0, 0)
	
	def cb_menu_popup_edit_folder(self, *a):
		""" Handler for 'edit' context menu item """
		# Editing folder
		self.open_editor(FolderEditorDialog, self.rightclick_box["id"])
	
	def cb_menu_popup_edit_ignored(self, *a):
		""" Handler for 'edit ignore patterns' context menu item """
		e = IgnoreEditor(self,
			self.rightclick_box["id"],
			self.rightclick_box["path"],
			)
		e.load()
		e.show(self["window"])
	
	def cb_menu_popup_edit_device(self, *a):
		""" Handler for other 'edit' context menu item """
		# Editing device
		self.open_editor(DeviceEditorDialog, self.rightclick_box["id"])
	
	def cb_menu_popup_browse_folder(self, *a):
		""" Handler for 'browse' folder context menu item """
		self.cb_browse_folder(self.rightclick_box)
		
	def cb_browse_folder(self, box, *a):
		""" Handler for 'browse' action """
		path = os.path.expanduser(box["path"])
		if IS_WINDOWS:
			# Don't attempt anything, use Windows Explorer on Windows
			path = path.replace("/", "\\")
			os.startfile(path, 'explore')
		else:
			# Try to use any of following, known commands to
			# display directory contents
			for x in ('xdg-open', 'gnome-open', 'kde-open'):
				if os.path.exists("/usr/bin/%s" % x):
					os.system( ("/usr/bin/%s '%s' &" % (x, path)).encode('utf-8') )
					break
	
	def cb_menu_popup_delete_folder(self, *a):
		""" Handler for 'delete' folder context menu item """
		# Editing folder
		self.check_delete("folder", self.rightclick_box["id"], self.rightclick_box.get_title())

	def cb_menu_popup_rescan_folder(self, *a):
		""" Handler for 'rescan' context menu item """
		log.info("Rescan folder %s", self.rightclick_box["id"])
		self.daemon.rescan(self.rightclick_box["id"])
	
	def cb_menu_popup_override(self, *a):
		""" Handler for 'override' context menu item """
		log.info("Override folder %s", self.rightclick_box["id"])
		self.daemon.override(self.rightclick_box["id"])
	
	def cb_menu_popup_delete_device(self, *a):
		""" Handler for other 'edit' context menu item """
		self.check_delete("device", self.rightclick_box["id"], self.rightclick_box.get_title())
	
	def cb_menu_popup_pause_device(self, *a):
		""" Handler for 'resume device' context menu item """
		self.daemon.pause(self.rightclick_box["id"])
	
	def cb_menu_popup_resume_device(self, *a):
		""" Handler for 'resume device' context menu item """
		self.daemon.resume(self.rightclick_box["id"])
	
	def check_delete(self, mode, id, name):
		"""
		Asks user if he really wants to do what he just asked to do
		"""
		msg = _("Do you really want to permanently stop synchronizing directory '%s'?")
		if mode == "device":
			msg = _("Do you really want remove device '%s' from Syncthing?")
		d = Gtk.MessageDialog(
				self["window"],
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.QUESTION,
				Gtk.ButtonsType.YES_NO,
				msg % name
				)
		r = d.run()
		d.hide()
		d.destroy()
		if r == Gtk.ResponseType.YES:
			# Load config from server (to have something to delete from)
			self.daemon.read_config(self.cb_delete_config_loaded, None, mode, id)
	
	def cb_delete_config_loaded(self, config, mode, id):
		"""
		Callback called when user decides to _really_ delete something and
		configuration is loaded from server.
		"""
		if mode == "folder":
			config["folders"] = [ x for x in config["folders"] if x["id"] != id ]
			if id in self.folders:
				self.folders[id].get_parent().remove(self.folders[id])
		else: # device
			config["devices"] = [ x for x in config["devices"] if x["deviceID"] != id ]
			if id in self.devices:
				self.devices[id].get_parent().remove(self.devices[id])
		self.daemon.write_config(config, lambda *a: a)
	
	def open_editor(self, cls, id):
		e = cls(self, False, id)
		e.load()
		e.show(self["window"])
	
	def cb_menu_popup_show_id(self, *a):
		""" Handler for 'show id' context menu item """
		# Available only for devices
		d = IDDialog(self, self.rightclick_box["id"])
		d.show(self["window"])
	
	def cb_menu_restart(self, event, *a):
		""" Handler for 'Restart' menu item """
		self.daemon.restart()
	
	def cb_menu_shutdown(self, event, *a):
		""" Handler for 'Shutdown' menu item """
		self.process = None	# Prevent app from restarting daemon
		self.daemon.shutdown()
	
	def cb_menu_resume(self, event, *a):
		""" Handler for 'Resume' menu item """
		self.start_daemon_ui()
	
	def cb_menu_webui(self, *a):
		""" Handler for 'Open WebUI' menu item """
		log.info("Opening '%s' in browser", self.daemon.get_webui_url())
		webbrowser.open(self.daemon.get_webui_url())
	
	def cb_menu_daemon_output(self, *a):
		if self.process != None:
			d = DaemonOutputDialog(self, self.process)
			d.show(None)
	
	def cb_menu_inotify_output(self, *a):
		# Available & called only on Windows
		if hasattr(self.watcher, "proc") and not self.watcher.proc is None:
			d = DaemonOutputDialog(self, self.watcher.proc)
			d.show(None, _("Syncthing-Inotify Output"))
		else:
			d = Gtk.MessageDialog(
					self["window"],
					Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
					Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
					_("Syncthing-Inotify is unavailable or failed to start")
				)
			r = d.run()
			d.hide()
			d.destroy()
	
	def cb_statusicon_click(self, *a):
		""" Called when user clicks on status icon """
		# Hide / show main window
		if self.is_visible():
			self.hide()
		else:
			self.show()
	
	def cb_statusicon_notify_active(self, *a):
		""" Called when the status icon changes its "inaccessible for sure" state """
		# Show main window if the status icon thinks that no icon is visible to the user
		if not self.statusicon.get_active():
			if not (IS_GNOME or IS_I3 or IS_MATE or IS_XFCE):
				# Gnome sometimes lag on this, but always ends displaying icon later
				# ... and i3 as well
				# ... oh gods :'(
				self.show()
	
	def cb_infobar_close(self, bar):
		if bar == self["infobar"]:
			self["infobar"] = None
		bar.close()
		if bar in self.error_boxes:
			self.error_boxes.remove(bar)
	
	def cb_infobar_response(self, bar, response_id, additional_data={}):
		# TODO: Split this, I don't like handling different things in
		# one method
		if response_id == RESPONSE_RESTART:
			# Restart
			self.daemon.restart()
		elif response_id == RESPONSE_FIX_FOLDER_ID:
			# Give up if there is no device with matching ID
			if additional_data["nid"] in self.devices:
				# Find folder with matching ID ...
				if additional_data["rid"] in self.folders:
					# ... if found, show edit dialog and pre-select
					# matching device
					e = FolderEditorDialog(self, False, additional_data["rid"])
					e.call_after_loaded(e.mark_device, additional_data["nid"])
					e.load()
					e.show(self["window"])
				else:
					# If there is no matching folder, prefill 'new folder'
					# dialog and let user to save it
					e = FolderEditorDialog(self, True, additional_data["rid"])
					e.call_after_loaded(e.mark_device, additional_data["nid"])
					e.call_after_loaded(e.fill_folder_id, additional_data["rid"])
					if additional_data["label"]:
						e.call_after_loaded(e["vlabel"].set_text, additional_data["label"])
					e.load()
					e.show(self["window"])
		elif response_id == RESPONSE_FIX_NEW_DEVICE:
			e = DeviceEditorDialog(self, True, additional_data["nid"])
			if additional_data["name"]:
				e.call_after_loaded(e["vname"].set_text, additional_data["name"])
			e.load()
			e.show(self["window"])
		elif response_id == RESPONSE_FIX_IGNORE:
			# Ignore unknown device
			def add_ignored(target, trash):
				if not "ignoredDevices" in target:
					target["ignoredDevices"] = []
				target["ignoredDevices"].append(additional_data["nid"])
			self.change_setting_async("ignoredDevices", add_ignored, restart=False)
		elif response_id == RESPONSE_UR_ALLOW:
			# Allow Usage reporting
			self.change_setting_async("options/urAccepted", 1)
		elif response_id == RESPONSE_UR_FORBID:
			# Allow Usage reporting
			self.change_setting_async("options/urAccepted", -1)
		self.cb_infobar_close(bar)
	
	def cb_open_closed(self, box):
		"""
		Called from InfoBox when user opens or closes bottom part
		"""
		if box.is_open():
			self.open_boxes.add(box["id"])
		else:
			self.open_boxes.discard(box["id"])
	
	def cb_connect_dialog_response(self, dialog, response, checkbox):
		# Common for 'Daemon is not running' and 'Connecting to daemon...'
		if response == RESPONSE_START_DAEMON:
			self.start_daemon_ui()
			if not checkbox is None and checkbox.get_active():
				self.config["autostart_daemon"] = 1
		else: # if response <= 0 or response == RESPONSE_QUIT:
			self.cb_exit()
	
	def cb_kill_daemon_response(self, dialog, response, checkbox):
		if response == RESPONSE_SLAIN_DAEMON:
			if not self.process is None:
				self.process.terminate()
				self.process = None
		if checkbox.get_active():
			self.config["autokill_daemon"] = (1 if response == RESPONSE_SLAIN_DAEMON else 0)
		self.process = None
		self.cb_exit()
	
	def cb_wizard_finished(self, wizard, *a):
		self.wizard = None
		if wizard.is_finished() and not self.exit_after_wizard:
			# Good, try connecting again
			wizard.hide()
			wizard.destroy()
			self.show()
			if self.setup_connection():
				self.daemon.reconnect()
		else:
			self.quit()
	
	def cb_daemon_exit(self, proc, error_code):
		if proc == self.process:
			# Whatever happens, if daemon dies while it shouldn't,
			# restart it...
			if time.time() - self.last_restart_time < RESTART_TOO_FREQUENT_INTERVAL:
				# ... unless it keeps restarting
				self.cb_daemon_startup_failed(proc, "Daemon exits too fast")
				return
			self.last_restart_time = time.time()
			if not StDownloader is None and self.config["st_autoupdate"] and os.path.exists(self.config["syncthing_binary"] + ".new"):
				# New daemon version is downloaded and ready to use.
				# Switch to this version before restarting
				self.swap_updated_binary()
				if self.restart_after_update:
					self.restart_after_update = False
					self.restart()
			self.ct_process()
	
	def cb_daemon_startup_failed(self, proc, exception):
		"""
		Check if daemon binary exists.
		If not, ask user where did he put it
		"""
		# Prepare FindDaemonDialog instance where user can
		# set new path for syncthing_binary
		d = FindDaemonDialog(self)
		d.load()
		d.set_transient_for(self["window"] if self.connect_dialog is None
				else self.connect_dialog)
		# If binary exists, assume that something is completly wrong,
		# and change error message
		if os.path.exists(self.config["syncthing_binary"]):
			d.set_message("%s\n%s %s\n\n%s" % (
					_("Failed to start Syncthing daemon."),
					_("Error message:"), str(exception),
					_("Please, check your installation or set new path to Syncthing daemon binary."),
			))
			d.hide_download_button()
		# Let dialog run and try running syncthing again if new
		# syncthing_binary is acquired
		r = d.run()
		d.destroy()
		if r == FindDaemonDialog.RESPONSE_SAVED:
			self.cb_daemon_exit(self.process, -1)
		else:
			self.quit()
