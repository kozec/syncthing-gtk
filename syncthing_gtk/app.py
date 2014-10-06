#!/usr/bin/env python2
"""
Syncthing-GTK - App

Main application window
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gio
from syncthing_gtk import *
from syncthing_gtk.tools import *
import os, webbrowser, sys, pprint, re

_ = lambda (a) : a

COLOR_DEVICE			= "#9246B1"
COLOR_DEVICE_SYNCING	= "#2A89C8"
COLOR_DEVICE_CONNECTED	= "#2A89C8"
COLOR_OWN_DEVICE		= "#C0C0C0"
COLOR_REPO				= "#9246B1"
COLOR_REPO_SYNCING		= "#2A89C8"
COLOR_REPO_SCANNING		= "#2A89C8"
COLOR_REPO_IDLE			= "#2AAB61"
COLOR_REPO_STOPPED		= "#87000B"
COLOR_NEW				= "#A0A0A0"
SI_FRAMES				= 4 # Number of animation frames for status icon

# Infobar position
RIBAR_POSITION = 0 if not THE_HELL else 1

# Regexps used to extract meaningfull data from error messages
FIX_EXTRACT_REPOID = re.compile(r'[a-zA-Z ]+"([-\._a-zA-Z0-9]+)"[a-zA-Z ]+"([-A-Z0-9]+)".*')

# Response IDs
RESPONSE_RESTART		= 256
RESPONSE_FIX_REPOID		= 257
RESPONSE_FIX_NEW_device	= 258
RESPONSE_QUIT			= 260
RESPONSE_START_DAEMON	= 271
RESPONSE_SLAIN_DAEMON	= 272
RESPONSE_SPARE_DAEMON	= 273

# RI's
REFRESH_INTERVAL_DEFAULT	= 1
REFRESH_INTERVAL_TRAY		= 5

class App(Gtk.Application, TimerManager):
	"""
	Main application / window.
	Hide parameter controlls if app should be minimized to status icon
	after start.
	"""
	def __init__(self, hide=True, use_headerbar=True,
						gladepath="/usr/share/syncthing-gtk",
						iconpath="/usr/share/syncthing-gtk/icons"):
		Gtk.Application.__init__(self,
				application_id="me.kozec.syncthingtk",
				flags=Gio.ApplicationFlags.FLAGS_NONE)
		TimerManager.__init__(self)
		self.gladepath = gladepath
		self.iconpath = iconpath
		self.builder = None
		self.rightclick_box = None
		self.config = Configuration()
		self.first_activation = hide and self.config["minimize_on_start"]
		self.process = None
		self.use_headerbar = use_headerbar and not self.config["use_old_header"]
		self.watcher = None
		self.notifications = None
		# connect_dialog may be displayed durring initial communication
		# or if daemon shuts down.
		self.connect_dialog = None
		self.widgets = {}
		self.error_boxes = []
		self.error_messages = set([])	# Holds set of already displayed error messages
		self.folders = {}
		self.devices = {}
		self.open_boxes = set([])		# Holds set of expanded device/folder boxes
		self.sync_animation = 0
	
	def do_startup(self, *a):
		Gtk.Application.do_startup(self, *a)
		self.setup_widgets()
		self.setup_statusicon()
		self.setup_connection()
		self.daemon.reconnect()
	
	def do_activate(self, *a):
		if not self.first_activation or (THE_HELL and not HAS_INDICATOR):
			# Show main window
			self.show()
		elif self.first_activation:
			print
			print _("Syncthing-GTK started and running in notification area")
			self.daemon.set_refresh_interval(REFRESH_INTERVAL_TRAY)
		self.first_activation = False
	
	def setup_widgets(self):
		# Load glade file
		self.builder = Gtk.Builder()
		self.builder.add_from_file(os.path.join(self.gladepath, "app.glade"))
		self.builder.connect_signals(self)
		# Setup window
		self["edit-menu"].set_sensitive(False)
		if THE_HELL or not self.use_headerbar:
			# Modify window if running under Ubuntu; Ubuntu default GTK
			# engine handles windows with header in... weird way.
			# This can be also forced by -s parameter in command line.
			
			# Unparent some stuff
			for u in ("content", "window-menu-icon"):
				self[u].get_parent().remove(self[u])
			
			# Create window
			w = Gtk.Window()
			w.set_size_request(*self["window"].get_size_request())
			w.set_default_size(*self["window"].get_default_size())
			w.set_icon(self["window"].get_icon())
			w.set_has_resize_grip(True)
			w.set_resizable(True)
			
			# Create toolbar
			bar = Gtk.Toolbar()
			bar.get_style_context().add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)
			window_menu = Gtk.ToolButton()
			window_menu.set_icon_widget(self["window-menu-icon"])
			window_menu.connect("clicked", self.cb_menu_popup, self["window-menu-menu"])
			middle_item = Gtk.ToolItem()
			middle_label = Gtk.Label()
			middle_item.set_expand(True)
			middle_label.set_label("")
			middle_item.add(middle_label)
			edit_menu = Gtk.ToolButton.new(Gtk.Image.new_from_icon_name("emblem-system-symbolic", 1))
			edit_menu.connect("clicked", self.cb_menu_popup, self["edit-menu-menu"])
			self["server-name"] = middle_label
			
			# Pack & set
			bar.add(window_menu)
			bar.add(middle_item)
			bar.add(edit_menu)
			self["content"].pack_start(bar, False, False, 0)
			self["content"].reorder_child(bar, 0)
			self["content"].show_all()
			w.add(self["content"])			
			self["window"].destroy()
			self["window"] = w
			self["window"].connect("delete-event", self.cb_delete_event)
		
		self["window"].set_title(_("Syncthing GTK"))
		self.add_window(self["window"])
	
	def setup_statusicon(self):
		self.statusicon = StatusIcon(self.iconpath, self["si-menu"])
		self.statusicon.connect("clicked", self.cb_statusicon_click)
		if THE_HELL and HAS_INDICATOR:
			self["menu-si-show"].set_visible(True)
	
	def setup_connection(self):
		# Create Daemon instance (loads and parses config)
		try:
			self.daemon = Daemon()
		except TLSUnsupportedException, e:
			self.fatal_error("%s\n%s" % (
				_("Sorry, connecting to HTTPS is not supported."),
				_("Disable HTTPS in WebUI and try again.")
				))
			sys.exit(1)
		except InvalidConfigurationException, e:
			self.fatal_error(str(e))
			sys.exit(1)
		# Enable filesystem watching and desktop notifications,
		# if desired and possible
		if HAS_INOTIFY:
			self.watcher = Watcher(self, self.daemon)
		if HAS_DESKTOP_NOTIFY:
			self.notifications = Notifications(self, self.daemon)
		# Connect signals
		self.daemon.connect("config-out-of-sync", self.cb_syncthing_config_oos)
		self.daemon.connect("config-saved", self.cb_syncthing_config_saved)
		self.daemon.connect("connected", self.cb_syncthing_connected)
		self.daemon.connect("connection-error", self.cb_syncthing_con_error)
		self.daemon.connect("disconnected", self.cb_syncthing_disconnected)
		self.daemon.connect("error", self.cb_syncthing_error)
		self.daemon.connect("folder-rejected", self.cb_syncthing_folder_rejected)
		self.daemon.connect("device-rejected", self.cb_syncthing_device_rejected)
		self.daemon.connect("my-id-changed", self.cb_syncthing_my_id_changed)
		self.daemon.connect("device-added", self.cb_syncthing_device_added)
		self.daemon.connect("device-data-changed", self.cb_syncthing_device_data_changed)
		self.daemon.connect("last-seen-changed", self.cb_syncthing_last_seen_changed)
		self.daemon.connect("device-connected", self.cb_syncthing_device_state_changed, True)
		self.daemon.connect("device-disconnected", self.cb_syncthing_device_state_changed, False)
		self.daemon.connect("device-sync-started", self.cb_syncthing_device_sync_progress)
		self.daemon.connect("device-sync-progress", self.cb_syncthing_device_sync_progress)
		self.daemon.connect("device-sync-finished", self.cb_syncthing_device_sync_progress, 1.0)
		self.daemon.connect("folder-added", self.cb_syncthing_folder_added)
		self.daemon.connect("folder-data-changed", self.cb_syncthing_folder_data_changed)
		self.daemon.connect("folder-data-failed", self.cb_syncthing_folder_state_changed, 0.0, COLOR_NEW, "")
		self.daemon.connect("folder-sync-started", self.cb_syncthing_folder_state_changed, 0.0, COLOR_REPO_SYNCING, _("Syncing"))
		self.daemon.connect("folder-sync-progress", self.cb_syncthing_folder_state_changed, COLOR_REPO_SYNCING, _("Syncing"))
		self.daemon.connect("folder-sync-finished", self.cb_syncthing_folder_state_changed, 1.0, COLOR_REPO_IDLE, _("Idle"))
		self.daemon.connect("folder-scan-started", self.cb_syncthing_folder_state_changed, 1.0, COLOR_REPO_SCANNING, _("Scanning"))
		self.daemon.connect("folder-scan-finished", self.cb_syncthing_folder_state_changed, 1.0, COLOR_REPO_IDLE, _("Idle"))
		self.daemon.connect("folder-stopped", self.cb_syncthing_folder_stopped) 
		self.daemon.connect("system-data-updated", self.cb_syncthing_system_data)
	
	def start_deamon(self):
		if self.process == None:
			self.process = DaemonProcess(["syncthing"])
			self.process.connect('exit', self.cb_daemon_exit)
			self["menu-daemon-output"].set_sensitive(True)
	
	def cb_syncthing_connected(self, *a):
		self.clear()
		self.close_connect_dialog()
		self.set_status(True)
		self["edit-menu"].set_sensitive(True)
		self["menu-si-shutdown"].set_sensitive(True)
		self["menu-si-show-id"].set_sensitive(True)
		self["menu-si-restart"].set_sensitive(True)
	
	def cb_syncthing_disconnected(self, daemon, reason, message):
		# if reason == Daemon.UNEXPECTED
		message = "%s %s" % (
				_("Connection to Syncthing daemon lost."),
				_("Syncthing is probably restarting or has been shut down."))
		if reason == Daemon.SHUTDOWN:
			message = _("Syncthing has been shut down.")
		elif reason == Daemon.RESTART:
			message = "%s %s..." % (_("Syncthing is restarting."), _("Please wait"))
		self.display_connect_dialog(message)
		self.set_status(False)
		self.restart()
	
	def cb_syncthing_con_error(self, daemon, reason, message):
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
						self.start_deamon()
					else:
						self.display_run_daemon_dialog()
			self.set_status(False)
		else: # Daemon.UNKNOWN, Daemon.NOT_AUTHORIZED
			# All other errors are fatal for now. Error dialog is displayed and program exits.
			if reason == Daemon.NOT_AUTHORIZED:
				message = _("Cannot authorize with daemon failed. Please, use WebUI to generate API key or disable password authentication.")
			elif reason == Daemon.OLD_VERSION:
				message = _("Your syncthing daemon is too old.\nPlease, upgrade syncthing package at least to version %s and try again.") % (self.daemon.get_min_version(),)
			else: # Daemon.UNKNOWN
				message = "%s\n\n%s %s" % (
						_("Connection to daemon failed. Check your configuration and try again."),
						_("Error message:"), str(message)
						)
			d = Gtk.MessageDialog(
					self["window"],
					Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
					Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
					message
					)
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
			self["content"].pack_start(r, False, False, 0)
			self["content"].reorder_child(r, RIBAR_POSITION)
			r.connect("close", self.cb_infobar_close)
			r.connect("response", self.cb_infobar_response)
			r.show()
			r.set_reveal_child(True)
	
	def cb_syncthing_config_saved(self, *a):
		# Ask daemon to reconnect and reload entire UI
		self.cancel_all() # timers
		if not self.watcher is None:
			self.watcher.clear()
		self.daemon.reconnect()
	
	def cb_syncthing_error(self, daemon, message):
		if message in self.error_messages:
			# Same error is already displayed
			print >>sys.stderr, "(repeated)", message
			return
		print >>sys.stderr, message
		if "Unexpected folder ID" in message:
			# Handled by event, don't display twice
			return
		severity = Gtk.MessageType.WARNING
		if "Stopping folder" in message:
			severity = Gtk.MessageType.ERROR
		self.error_messages.add(message)
		self.show_error_box(RIBar(message, severity))
	
	def cb_syncthing_folder_rejected(self, daemon, nid, rid):
		if (nid, rid) in self.error_messages:
			# Store as error message and don't display twice
			return
		self.error_messages.add((nid, rid))
		device, can_fix = nid, False
		if nid in self.devices:
			device = self.devices[nid].get_title()
			can_fix = True
		markup = _('Unexpected folder ID "<b>%s</b>" sent from device "<b>%s</b>"; ensure that the '
					'folder exists and that  this device is selected under "Share With" in the '
					'folder configuration.') % (rid, device)
		r = RIBar("", Gtk.MessageType.WARNING,)
		r.get_label().set_markup(markup)
		if can_fix:
			r.add_button(RIBar.build_button(_("_Fix")), RESPONSE_FIX_REPOID)
		self.show_error_box(r, {"nid" : nid, "rid" : rid} )
	
	def cb_syncthing_device_rejected(self, daemon, nid, address):
		address = address.split(":")[0]	# Remove port from address, it's random by default anyway
		if (nid, address) in self.error_messages:
			# Store as error message and don't display twice
			return
		self.error_messages.add((nid, address))
		markup = _('Unknown device "<b>%s</b>" is trying to connect from IP "<b>%s</b>"; '
					'If you just configured this remote device, you can click \'fix\' '
					'to open Add device dialog.') % (nid, address)
		r = RIBar("", Gtk.MessageType.WARNING,)
		r.get_label().set_markup(markup)
		r.add_button(RIBar.build_button(_("_Fix")), RESPONSE_FIX_NEW_device)
		self.show_error_box(r, {"nid" : nid, "address" : address} )
	
	def cb_syncthing_my_id_changed(self, daemon, device_id):
		if device_id in self.devices:
			device = self.devices[device_id]
			# Move my device to top
			self["devicelist"].reorder_child(device, 0)
			# Modify header & color
			device.set_status("")
			device.set_icon(Gtk.Image.new_from_icon_name("user-home", Gtk.IconSize.LARGE_TOOLBAR))
			device.invert_header(True)
			device.set_color_hex(COLOR_OWN_DEVICE)
			self["header"].set_subtitle(device.get_title())
			if "server-name" in self:
				self["server-name"].set_markup("<b>%s</b>" % (device.get_title(),))
			# Modify values
			device.clear_values()
			device.add_value("ram",		"ram.png",		_("RAM Utilization"),	"")
			device.add_value("cpu",		"cpu.png",		_("CPU Utilization"),	"")
			device.add_value("dl_rate",	"dl_rate.png",	_("Download Rate"),		"0 bps (0 B)")
			device.add_value("up_rate",	"up_rate.png",	_("Upload Rate"),		"0 bps (0 B)")
			device.add_value("announce",	"announce.png",	_("Announce Server"),	"")
			device.add_value("version",	"version.png",	_("Version"),			"?")
			device.show_all()
	
	def cb_syncthing_system_data(self, daemon, mem, cpu, announce):
		if self.daemon.get_my_id() in self.devices:
			# Update my device display
			device = self.devices[self.daemon.get_my_id()]
			device["ram"] = sizeof_fmt(mem)
			device["cpu"] = "%3.2f%%" % (cpu)
			if announce == -1:
				device["announce"] = _("disabled")
			elif announce == 1:
				device["announce"] = _("Online") 
			else:
				device["announce"] = _("offline")
	
	def cb_syncthing_device_added(self, daemon, nid, name, data):
		self.show_device(nid, name,
			data["Compression"],
			data["Introducer"] if "Introducer" in data else False
		)
	
	def cb_syncthing_device_data_changed(self, daemon, nid, address, client_version,
			dl_rate, up_rate, bytes_in, bytes_out):
		if nid in self.devices:	# Should be always
			device = self.devices[nid]
			# Update strings
			device["address"] = address
			device["version"] = client_version
			# Update rates
			device['dl_rate'] = "%sps (%s)" % (sizeof_fmt(dl_rate), sizeof_fmt(bytes_in))
			device['up_rate'] = "%sps (%s)" % (sizeof_fmt(up_rate), sizeof_fmt(bytes_out))
	
	def cb_syncthing_last_seen_changed(self, daemon, nid, dt):
		if nid in self.devices:	# Should be always
			device = self.devices[nid]
			if dt is None:
				device['last-seen'] = _("Never")
			else:
				dtf = dt.strftime("%Y-%m-%d %H:%M")
				device['last-seen'] = str(dtf)
	
	def cb_syncthing_device_state_changed(self, daemon, nid, connected):
		if nid in self.devices:	# Should be always
			device = self.devices[nid]
			if device["connected"] != connected:
				device["connected"] = connected
				if connected:
					# Update color & header
					device.set_status(_("Connected"))
					device.set_color_hex(COLOR_DEVICE_CONNECTED)
					# Update visible values
					device.show_values("sync", "dl.rate", "up.rate", "version")
					device.hide_values("last-seen")
				else:
					# Update color & header
					device.set_status(_("Disconnected"))
					device.set_color_hex(COLOR_DEVICE)
					# Update visible values
					device.hide_values("sync", "dl.rate", "up.rate", "version")
					device.show_values("last-seen")
	
	def cb_syncthing_device_sync_progress(self, daemon, device_id, sync):
		if device_id in self.devices:
			device = self.devices[device_id]
			device["sync"] = "%3.f%%" % (sync * 100.0)
			if not device["connected"]:
				device.set_color_hex(COLOR_DEVICE)
				device.set_status(_("Disconnected"))
			elif sync >= 0.0 and sync < 0.99:
				device.set_color_hex(COLOR_DEVICE_SYNCING)
				device.set_status(_("Syncing"), sync)
			else:
				device.set_color_hex(COLOR_DEVICE_CONNECTED)
				device.set_status(_("Up to Date"))
	
	def cb_syncthing_folder_added(self, daemon, rid, r):
		box = self.show_folder(
			rid, r["Path"], r["Path"],
			r["ReadOnly"], r["IgnorePerms"], 
			r["RescanIntervalS"],
			sorted(
				[ self.devices[n["DeviceID"]] for n in r["Devices"] ],
				key=lambda x : x.get_title().lower()
				)
			)
		if not self.watcher is None:
			if rid in self.config["use_inotify"]:
				self.watcher.watch(box["norm_path"])
	
	def cb_syncthing_folder_data_changed(self, daemon, rid, data):
		if rid in self.folders:	# Should be always
			folder = self.folders[rid]
			folder["global"] = "%s %s, %s" % (data["globalFiles"], _("Files"), sizeof_fmt(data["globalBytes"]))
			folder["local"]	 = "%s %s, %s" % (data["localFiles"], _("Files"), sizeof_fmt(data["localBytes"]))
			folder["oos"]	 = "%s %s, %s" % (data["needFiles"], _("Files"), sizeof_fmt(data["needBytes"]))
			if float(data["globalBytes"]) > 0.0:
				sync = float(data["inSyncBytes"]) / float(data["globalBytes"]),
			else:
				sync = 0.0
			# folder.set_status(_(data['state'].capitalize()), sync)
	
	def cb_syncthing_folder_state_changed(self, daemon, rid, percentage, color, text):
		if rid in self.folders:	# Should be always
			folder = self.folders[rid]
			folder.set_color_hex(color)
			folder.set_status(text, percentage)
			self.set_status(True)
	
	def cb_syncthing_folder_stopped(self, daemon, rid, message):
		if rid in self.folders:	# Should be always
			folder = self.folders[rid]
			folder.set_color_hex(COLOR_REPO_STOPPED)
			folder.set_status(_("Stopped"), 0)
			# Color, theme-based icon is used here. It's intentional and
			# supposed to draw attention
			folder.add_value("error", "dialog-error", _("Error"), message)
			folder.show_value('error')
	
	def set_status(self, is_connected):
		""" Sets icon and text on first line of popup menu """
		if is_connected:
			if self.daemon.syncing():
				sr = self.daemon.get_syncing_list()
				if len(sr) == 1:
					self["menu-si-status"].set_label(_("Synchronizing '%s'") % (sr[0],))
				else:
					self["menu-si-status"].set_label(_("Synchronizing %s folders") % (len(sr),))
				self.animate_status()
			else:
				self.statusicon.set("si-idle", _("Idle"))
				self["menu-si-status"].set_label(_("Idle"))
				self.cancel_timer("icon")
		else:
			self.statusicon.set("si-unknown", _("Connecting to Syncthing daemon..."))
			self["menu-si-status"].set_label(_("Connecting to Syncthing daemon..."))
			self.cancel_timer("icon")
	
	def show_error_box(self, ribar, additional_data={}):
		self["content"].pack_start(ribar, False, False, 0)
		self["content"].reorder_child(ribar, RIBAR_POSITION)
		ribar.connect("close", self.cb_infobar_close)
		ribar.connect("response", self.cb_infobar_response, additional_data)
		ribar.show()
		ribar.set_reveal_child(True)
		self.error_boxes.append(ribar)
	
	def animate_status(self):
		""" Handles icon animation """
		if self.timer_active("icon"):
			# Already animating
			return
		self.statusicon.set("si-syncing-%s" % (self.sync_animation,))
		self.sync_animation += 1
		if self.sync_animation >= SI_FRAMES:
			self.sync_animation = 0
		self.timer("icon", 1, self.animate_status)
	
	def fatal_error(self, text):
		# TODO: Better way to handle this
		print >>sys.stderr, text
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
	
	def is_visible(self):
		""" Returns True if main window is visible """
		return self["window"].is_visible()
	
	def show(self):
		"""
		Shows main window or brings it to front, if is already visible.
		If connection to daemon is not established, shows 'Connecting'
		dialog as well.
		"""
		
		self.daemon.set_refresh_interval(REFRESH_INTERVAL_DEFAULT)
		self.daemon.request_events()
		if not self["window"].is_visible():
			# self["window"].show_all()
			self["window"].show()
			if self.connect_dialog != None:
				self.connect_dialog.show()
		else:
			self["window"].present()
	
	def hide(self):
		""" Hides main windows and 'Connecting' dialog, if displayed """
		if self.connect_dialog != None:
			self.connect_dialog.hide()
		self["window"].hide()
		self.daemon.set_refresh_interval(REFRESH_INTERVAL_TRAY)
	
	def display_connect_dialog(self, message):
		"""
		Displays 'Be patient, i'm trying to connect here' dialog, or updates
		it's message if said dialog is already displayed.
		"""
		if self.connect_dialog == None:
			if DEBUG: print "Creating connect_dialog"
			self.connect_dialog = Gtk.MessageDialog(
				self["window"],
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.INFO, 0, "-")
			self.connect_dialog.add_button("gtk-quit", RESPONSE_QUIT)
			# There is only one response available on this dialog
			self.connect_dialog.connect("response", self.cb_exit)
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
		if DEBUG: print "Settinig connect_dialog label", message[0:15]
		set_label(self.connect_dialog.get_content_area(), message)
	
	def display_run_daemon_dialog(self):
		"""
		Displays 'Syncthing is not running, should I start it for you?'
		dialog.
		"""
		if self.connect_dialog == None: # Don't override already existing dialog
			if DEBUG: print "Creating run_daemon_dialog"
			self.connect_dialog = Gtk.MessageDialog(
				self["window"],
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.INFO, 0,
				"%s\n%s" % (
					_("Syncthing daemon doesn't appear to be running."),
					_("Start it now?")
					)
				)
			cb = Gtk.CheckButton(_("Always start daemon automaticaly"))
			self.connect_dialog.get_content_area().pack_end(cb, False, False, 2)
			self.connect_dialog.add_button("_Start",   RESPONSE_START_DAEMON)
			self.connect_dialog.add_button("gtk-quit", RESPONSE_QUIT)
			# There is only one response available on this dialog
			self.connect_dialog.connect("response", self.cb_run_daemon_response, cb)
			if self.is_visible():
				self.connect_dialog.show_all()
			else:
				cb.show()	# Keep this one visible, even if dialog is not
	
	def close_connect_dialog(self):
		if self.connect_dialog != None:
			self.connect_dialog.hide()
			self.connect_dialog.destroy()
			self.connect_dialog = None
	
	def show_folder(self, id, name, path, is_master, ignore_perms, rescan_interval, shared):
		""" Shared is expected to be list """
		# title = name if len(name) < 20 else "...%s" % name[-20:]
		box = InfoBox(self, name, Gtk.Image.new_from_icon_name("drive-harddisk", Gtk.IconSize.LARGE_TOOLBAR))
		box.add_value("id",			"version.png",	_("Repository ID"),			id)
		box.add_value("path",		"folder.png",	_("Path"),					path)
		box.add_value("global",		"global.png",	_("Global Repository"),		"? items, ?B")
		box.add_value("local",		"home.png",		_("Local Repository"),		"? items, ?B")
		box.add_value("oos",		"dl_rate.png",	_("Out Of Sync"),			"? items, ?B")
		box.add_value("master",		"lock.png",		_("Master Repo"),			_("Yes") if is_master else _("No"))
		box.add_value("ignore",		"ignore.png",	_("Ignore Permissions"),	_("Yes") if ignore_perms else _("No"))
		box.add_value("rescan",		"restart.png",	_("Rescan Interval"),		"%s s" % (rescan_interval,))
		box.add_value("shared",		"shared.png",	_("Shared With"),			", ".join([ n.get_title() for n in shared ]))
		box.add_hidden_value("id", id)
		box.add_hidden_value("devices", shared)
		box.add_hidden_value("norm_path", os.path.abspath(os.path.expanduser(path)))
		box.set_status("Unknown")
		box.set_color_hex(COLOR_REPO)
		box.connect('right-click', self.cb_popup_menu_folder)
		self["folderlist"].pack_start(box, False, False, 3)
		box.set_vexpand(False)
		box.set_open(id in self.open_boxes)
		self["folderlist"].show_all()
		self.folders[id] = box
		return box
	
	def show_device(self, id, name, use_compression, introducer):
		if name in (None, ""):
			# Show first block from ID if name is unset
			name = id.split("-")[0]
		box = InfoBox(self, name, Gtk.Image.new_from_icon_name("computer", Gtk.IconSize.LARGE_TOOLBAR))
		box.add_value("address",	"address.png",	_("Address"),			"?")
		box.add_value("sync",		"sync.png",		_("Synchronization"),	"0%", visible=False)
		box.add_value("compress",	"compress.png",	_("Use Compression"),	_("Yes") if use_compression else _("No"))
		box.add_value("dl.rate",	"dl_rate.png",	_("Download Rate"),		"0 bps (0 B)", visible=False)
		box.add_value("up.rate",	"up_rate.png",	_("Upload Rate"),		"0 bps (0 B)", visible=False)
		box.add_value("introducer",	"thumb_up.png",	_("Introducer"),		_("Yes") if introducer else _("No"))
		box.add_value("version",	"version.png",	_("Version"),			"?", visible=False)
		box.add_value('last-seen',	"clock.png",	_("Last Seen"),			_("Never"))
		box.add_hidden_value("id", id)
		box.add_hidden_value("connected", False)
		box.add_hidden_value("completion", {})
		box.add_hidden_value("bytes_in", 0)
		box.add_hidden_value("bytes_out", 0)
		box.add_hidden_value("time", 0)
		box.set_color_hex(COLOR_DEVICE)
		box.connect('right-click', self.cb_popup_menu_device)
		self["devicelist"].pack_start(box, False, False, 3)
		box.set_vexpand(False)
		box.set_open(id in self.open_boxes)
		self["devicelist"].show_all()
		self.devices[id] = box
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
		self["edit-menu"].set_sensitive(False)
		self["menu-si-shutdown"].set_sensitive(False)
		self["menu-si-show-id"].set_sensitive(False)
		self["menu-si-restart"].set_sensitive(False)
		if not self["infobar"] is None:
			self.cb_infobar_close(self["infobar"])
		for r in self.error_boxes:
			r.get_parent().remove(r)
			r.destroy()
		self.error_boxes = []
		self.error_messages = set([])
		self.cancel_all() # timers
		if not self.watcher is None:
			self.watcher.clear()
		self.daemon.reconnect()
	
	# --- Callbacks ---
	def cb_exit(self, *a):
		if self.process != None:
			if self.config["autokill_daemon"] == 2:	# Ask
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
				self.process.kill()
		self.quit()
	
	def cb_about(self, *a):
		AboutDialog(self).show(self["window"])
	
	def cb_delete_event(self, *e):
		# Hide main window
		self.hide()
		return True
	
	def cb_menu_show_id(self, *a):
		d = IDDialog(self, self.daemon.get_my_id())
		d.show(self["window"])
	
	def cb_menu_add_folder(self, event, *a):
		""" Handler for 'Add folder' menu item """
		e = FolderEditorDialog(self, True)
		e.load()
		e.show(self["window"])
	
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
	
	def cb_popup_menu_folder(self, box, button, time):
		self.rightclick_box = box
		self["popup-menu-folder"].popup(None, None, None, None, button, time)
	
	def cb_popup_menu_device(self, box, button, time):
		self.rightclick_box = box
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
		path = os.path.expanduser(self.rightclick_box["path"])
		# Try to use any of following, known commands to display directory contents
		for x in ('xdg-open', 'gnome-open', 'kde-open'):
			if os.path.exists("/usr/bin/%s" % x):
				os.system("/usr/bin/%s '%s' &" % (x, path))
				break
	
	def cb_menu_popup_delete_folder(self, *a):
		""" Handler for 'delete' folder context menu item """
		# Editing folder
		self.check_delete("folder", self.rightclick_box["id"], self.rightclick_box.get_title())

	def cb_menu_popup_rescan_folder(self, *a):
		""" Handler for 'rescan' context menu item """
		# Editing folder
		self.daemon.rescan(self.rightclick_box["id"])
	
	def cb_menu_popup_delete_device(self, *a):
		""" Handler for other 'edit' context menu item """
		# Editing device
		self.check_delete("device", self.rightclick_box["id"], self.rightclick_box.get_title())
	
	def check_delete(self, mode, id, name):
		"""
		Asks user if he really wants to do what he just asked to do
		"""
		print mode, id
		d = Gtk.MessageDialog(
				self["window"],
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.QUESTION,
				Gtk.ButtonsType.YES_NO,
				"%s %s\n'%s'?" % (
					_("Do you really want do delete"),
					_("folder") if mode == "folder" else _("device"),
					name
					)
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
			config["Folders"] = [ x for x in config["Folders"] if x["ID"] != id ]
			if id in self.folders:
				self.folders[id].get_parent().remove(self.folders[id])
		else: # device
			config["Devices"] = [ x for x in config["Devices"] if x["DeviceID"] != id ]
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
	
	def cb_menu_webui(self, *a):
		""" Handler for 'Open WebUI' menu item """
		print "Opening '%s' in browser" % (self.daemon.get_webui_url(),)
		webbrowser.open(self.daemon.get_webui_url())
	
	def cb_menu_daemon_output(self, *a):
		if self.process != None:
			d = DaemonOutputDialog(self, self.process)
			d.show(self["window"])
	
	def cb_statusicon_click(self, *a):
		""" Called when user clicks on status icon """
		# Hide / show main window
		if self.is_visible():
			self.hide()
		else:
			self.show()
	
	def cb_infobar_close(self, bar):
		if bar == self["infobar"]:
			self["infobar"] = None
		bar.close()
		if bar in self.error_boxes:
			self.error_boxes.remove(bar)
	
	def cb_infobar_response(self, bar, response_id, additional_data={}):
		if response_id == RESPONSE_RESTART:
			# Restart
			self.daemon.restart()
		elif response_id == RESPONSE_FIX_REPOID:
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
					e.load()
					e.show(self["window"])
		elif response_id == RESPONSE_FIX_NEW_device:
			e = DeviceEditorDialog(self, True, additional_data["nid"])
			e.load()
			e.show(self["window"])
		self.cb_infobar_close(bar)
	
	def cb_open_closed(self, box):
		"""
		Called from InfoBox when user opens or closes bottom part
		"""
		if box.is_open():
			self.open_boxes.add(box["id"])
		else:
			self.open_boxes.discard(box["id"])
	
	def cb_run_daemon_response(self, dialog, response, checkbox):
		if response == RESPONSE_START_DAEMON:
			self.start_deamon()
			self.close_connect_dialog()
			self.display_connect_dialog(_("Starting Syncthing daemon"))
			if checkbox.get_active():
				self.config["autostart_daemon"] = 1
		else: # if response <= 0 or response == RESPONSE_QUIT:
			self.cb_exit()
	
	def cb_kill_daemon_response(self, dialog, response, checkbox):
		if response == RESPONSE_SLAIN_DAEMON:
			if not self.process is None:
				self.process.terminate()
		if checkbox.get_active():
			self.config["autokill_daemon"] = (1 if response == RESPONSE_SLAIN_DAEMON else 0)
		self.process = None
		self.cb_exit()
	
	def cb_daemon_exit(self, proc, error_code):
		if not self.process is None:
			# Whatever happens, if daemon dies while it shouldn't,
			# restart it
			self.process = DaemonProcess(["syncthing"])
			self.process.connect('exit', self.cb_daemon_exit)
