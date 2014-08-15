#!/usr/bin/env python2
"""
Syncthing-GTK - App

Main window of application
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gio
from syncthing_gtk import *
from syncthing_gtk.tools import *
from syncthing_gtk.statusicon import THE_HELL, HAS_INDICATOR
import os, webbrowser, sys, pprint, re

_ = lambda (a) : a

COLOR_NODE				= "#9246B1"
COLOR_NODE_SYNCING		= "#2A89C8"
COLOR_NODE_CONNECTED	= "#2A89C8"
COLOR_OWN_NODE			= "#C0C0C0"
COLOR_REPO				= "#9246B1"
COLOR_REPO_SYNCING		= "#2A89C8"
COLOR_REPO_SCANNING		= "#2A89C8"
COLOR_REPO_IDLE			= "#2AAB61"
SI_FRAMES				= 4 # Number of animation frames for status icon

# Regexps used to extract meaningfull data from error messages
FIX_EXTRACT_REPOID = re.compile(r'[a-zA-Z ]+"([-\._a-zA-Z0-9]+)"[a-zA-Z ]+"([-A-Z0-9]+)".*')

# Response IDs
RESPONSE_RESTART		= 256
RESPONSE_FIX_REPOID		= 257
RESPONSE_QUIT			= 258
RESPONSE_START_DAEMON	= 259
RESPONSE_SLAIN_DAEMON	= 260
RESPONSE_SPARE_DAEMON	= 261

class App(Gtk.Application, TimerManager):
	"""
	Main application / window.
	Hide parameter controlls if app should be minimized to status icon
	after start.
	"""
	def __init__(self, hide=True, gladepath="/usr/share/syncthing-gtk",
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
		self.first_activation = hide
		self.process = None
		# connect_dialog may be displayed durring initial communication
		# or if daemon shuts down.
		self.connect_dialog = None
		self.widgets = {}
		self.error_boxes = []
		self.repos = {}
		self.nodes = {}
		self.open_boxes = set([])	# Holds set of expanded node/repo boxes
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
			if not self["window"].is_visible():
				self["window"].show()
				if self.connect_dialog != None:
					self.connect_dialog.show()
			else:
				self["window"].present()
		elif self.first_activation:
			print
			print _("Syncthing-GTK started and running in notification area")
		self.first_activation = False
	
	def setup_widgets(self):
		# Load glade file
		self.builder = Gtk.Builder()
		self.builder.add_from_file(os.path.join(self.gladepath, "app.glade"))
		self.builder.connect_signals(self)
		# Setup window
		self["edit-menu"].set_sensitive(False)
		if THE_HELL:
			# Modify window if running under Ubuntu; Ubuntu default GTK
			# engine handles windows with header in... weird way.
			
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
			middle_label.set_label("Ahoj")
			middle_item.add(middle_label)
			edit_menu = Gtk.ToolButton.new_from_stock(Gtk.STOCK_EDIT)
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
		except InvalidConfigurationException, e:
			print >>sys.stderr, e
			sys.exit(1)
		# Connect signals
		self.daemon.connect("config-out-of-sync", self.cb_syncthing_config_oos)
		self.daemon.connect("connected", self.cb_syncthing_connected)
		self.daemon.connect("connection-error", self.cb_syncthing_con_error)
		self.daemon.connect("disconnected", self.cb_syncthing_disconnected)
		self.daemon.connect("error", self.cb_syncthing_error)
		self.daemon.connect("my-id-changed", self.cb_syncthing_my_id_changed)
		self.daemon.connect("node-added", self.cb_syncthing_node_added)
		self.daemon.connect("node-data-changed", self.cb_syncthing_node_data_changed)
		self.daemon.connect("node-connected", self.cb_syncthing_node_state_changed, True)
		self.daemon.connect("node-disconnected", self.cb_syncthing_node_state_changed, False)
		self.daemon.connect("node-sync-started", self.cb_syncthing_node_sync_progress)
		self.daemon.connect("node-sync-progress", self.cb_syncthing_node_sync_progress)
		self.daemon.connect("node-sync-finished", self.cb_syncthing_node_sync_progress, 1.0)
		self.daemon.connect("repo-added", self.cb_syncthing_repo_added)
		self.daemon.connect("repo-data-changed", self.cb_syncthing_repo_data_changed)
		self.daemon.connect("repo-sync-started", self.cb_syncthing_repo_state_changed, 0.0, COLOR_REPO_SYNCING, _("Syncing"))
		self.daemon.connect("repo-sync-progress", self.cb_syncthing_repo_state_changed, COLOR_REPO_SYNCING, _("Syncing"))
		self.daemon.connect("repo-sync-finished", self.cb_syncthing_repo_state_changed, 1.0, COLOR_REPO_IDLE, _("Idle"))
		self.daemon.connect("repo-scan-started", self.cb_syncthing_repo_state_changed, 1.0, COLOR_REPO_SCANNING, _("Scanning"))
		self.daemon.connect("repo-scan-finished", self.cb_syncthing_repo_state_changed, 1.0, COLOR_REPO_IDLE, _("Idle"))
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
					if self.config["autostart_daemon"]:
						# ... unless he already decided once forever
						self.display_connect_dialog(_("Starting Syncthing daemon"))
						self.start_deamon()
					else:
						self.display_run_daemon_dialog()
			self.set_status(False)
		else: # Daemon.UNKNOWN
			# All other errors are fatal for now. Error dialog is displayed and program exits.
			d = Gtk.MessageDialog(
					self["window"],
					Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
					Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
					"%s\n\n%s %s" % (
						_("Connection to daemon failed. Check your configuration and try again."),
						_("Error message:"), str(message)
						)
					)
			d.run()
			Gtk.main_quit()
	
	def cb_syncthing_config_oos(self, *a):
		if self["infobar"] == None:
			r = RIBar(
				_("The configuration has been saved but not activated.\nSyncthing must restart to activate the new configuration."),
				Gtk.MessageType.WARNING,
				( RIBar.build_button(_("_Restart"), "view-refresh"), RESPONSE_RESTART)
				)
			self["infobar"] = r
			self["content"].pack_start(r, False, False, 1)
			self["content"].reorder_child(r, 0)
			r.connect("close", self.cb_infobar_close)
			r.connect("response", self.cb_infobar_response)
			r.show()
			r.set_reveal_child(True)
	
	def cb_syncthing_error(self, daemon, message):
		print >>sys.stderr, message
		r = RIBar(
			message, Gtk.MessageType.WARNING,
			)
		self["content"].pack_start(r, False, False, 1)
		self["content"].reorder_child(r, 0)
		r.connect("close", self.cb_infobar_close)
		r.connect("response", self.cb_infobar_response)
		r.show()
		r.set_reveal_child(True)
		if "Unexpected repository ID" in message:
			match = FIX_EXTRACT_REPOID.match(message)
			if len(match.groups()) == 2:
				r["rid"], r["nid"] = match.groups()
				if r["nid"] in self.nodes:
					r.add_button(RIBar.build_button(_("_Fix")), RESPONSE_FIX_REPOID)
					l = r.get_label()
					# Replace that nasty looking, long node id with label assigned by user
					# and make important things bold
					l.set_markup(l.get_text(). \
						replace('"%s"' % (r["nid"],), '<b>"%s"</b>' % (self.nodes[r["nid"]].get_title(),)). \
						replace('"%s"' % (r["rid"],), '<b>"%s"</b>' % (r["rid"],))
					)
		self.error_boxes.append(r)
	
	def cb_syncthing_my_id_changed(self, daemon, node_id):
		if node_id in self.nodes:
			node = self.nodes[node_id]
			# Move my node to top
			self["nodelist"].reorder_child(node, 0)
			# Modify header & color
			node.set_status("")
			node.set_icon(Gtk.Image.new_from_icon_name("user-home", Gtk.IconSize.LARGE_TOOLBAR))
			node.invert_header(True)
			node.set_color_hex(COLOR_OWN_NODE)
			self["header"].set_subtitle(node.get_title())
			if "server-name" in self:
				self["server-name"].set_markup("<b>%s</b>" % (node.get_title(),))
			# Modify values
			node.clear_values()
			node.add_value("ram",		"ram.png",		_("RAM Utilization"),	"")
			node.add_value("cpu",		"cpu.png",		_("CPU Utilization"),	"")
			node.add_value("dl_rate",	"dl_rate.png",	_("Download Rate"),		"0 bps (0 B)")
			node.add_value("up_rate",	"up_rate.png",	_("Upload Rate"),		"0 bps (0 B)")
			node.add_value("announce",	"announce.png",	_("Announce Server"),	"")
			node.add_value("version",	"version.png",	_("Version"),			"?")
			node.show_all()
	
	def cb_syncthing_system_data(self, daemon, mem, cpu, announce):
		if self.daemon.get_my_id() in self.nodes:
			# Update my node display
			node = self.nodes[self.daemon.get_my_id()]
			node["ram"] = sizeof_fmt(mem)
			node["cpu"] = "%3.2f%%" % (cpu)
			if announce == -1:
				node["announce"] = _("disabled")
			elif announce == 1:
				node["announce"] = _("Online") 
			else:
				node["announce"] = _("offline")
	
	def cb_syncthing_node_added(self, daemon, nid, name, data):
		self.show_node(nid, name, data["Compression"])
	
	def cb_syncthing_node_data_changed(self, daemon, nid, address, client_version,
			dl_rate, up_rate, bytes_in, bytes_out):
		if nid in self.nodes:	# Should be always
			node = self.nodes[nid]
			# Update strings
			node["address"] = address
			node["version"] = client_version
			# Update rates
			node['dl_rate'] = "%sps (%s)" % (sizeof_fmt(dl_rate), sizeof_fmt(bytes_in))
			node['up_rate'] = "%sps (%s)" % (sizeof_fmt(up_rate), sizeof_fmt(bytes_out))
	
	def cb_syncthing_node_state_changed(self, daemon, nid, connected):
		# Update color & header
		if nid in self.nodes:	# Should be always
			node = self.nodes[nid]
			if node["connected"] != connected:
				node["connected"] = connected
				if connected:
					node.set_status(_("Connected"))
					node.set_color_hex(COLOR_NODE_CONNECTED)
				else:
					node.set_status(_("Disconnected"))
					node.set_color_hex(COLOR_NODE)
	
	def cb_syncthing_node_sync_progress(self, daemon, node_id, sync):
		if node_id in self.nodes:
			node = self.nodes[node_id]
			node["sync"] = "%3.f%%" % (sync * 100.0)
			if not node["connected"]:
				node.set_color_hex(COLOR_NODE)
				node.set_status(_("Disconnected"))
			elif sync >= 0.0 and sync < 0.99:
				node.set_color_hex(COLOR_NODE_SYNCING)
				node.set_status(_("Syncing"), sync)
			else:
				node.set_color_hex(COLOR_NODE_CONNECTED)
				node.set_status(_("Up to Date"))
	
	def cb_syncthing_repo_added(self, daemon, rid, r):
		self.show_repo(
			rid, r["Directory"], r["Directory"],
			r["ReadOnly"], r["IgnorePerms"], 
			sorted(
				[ self.nodes[n["NodeID"]] for n in r["Nodes"] ],
				key=lambda x : x.get_title().lower()
				)
			)
	
	def cb_syncthing_repo_data_changed(self, daemon, rid, data):
		if rid in self.repos:	# Should be always
			repo = self.repos[rid]
			repo["global"] = "%s %s, %s" % (data["globalFiles"], _("Files"), sizeof_fmt(data["globalBytes"]))
			repo["local"]	 = "%s %s, %s" % (data["localFiles"], _("Files"), sizeof_fmt(data["localBytes"]))
			repo["oos"]	 = "%s %s, %s" % (data["needFiles"], _("Files"), sizeof_fmt(data["needBytes"]))
			if float(data["globalBytes"]) > 0.0:
				sync = float(data["inSyncBytes"]) / float(data["globalBytes"]),
			else:
				sync = 0.0
			# repo.set_status(_(data['state'].capitalize()), sync)
	
	def cb_syncthing_repo_state_changed(self, daemon, rid, percentage, color, text):
		if rid in self.repos:	# Should be always
			repo = self.repos[rid]
			repo.set_color_hex(color)
			repo.set_status(text, percentage)
			self.set_status(True)
	
	def set_status(self, is_connected):
		""" Sets icon and text on first line of popup menu """
		if is_connected:
			if self.daemon.syncing():
				sr = self.daemon.get_syncing_list()
				if len(sr) == 1:
					self["menu-si-status"].set_label(_("Synchronizing '%s'") % (sr[0],))
				else:
					self["menu-si-status"].set_label(_("Synchronizing %s repos") % (len(sr),))
				self.animate_status()
			else:
				self.statusicon.set("si-idle", _("Idle"))
				self["menu-si-status"].set_label(_("Idle"))
				self.cancel_timer("icon")
		else:
			self.statusicon.set("si-unknown", _("Connecting to Syncthing daemon..."))
			self["menu-si-status"].set_label(_("Connecting to Syncthing daemon..."))
			self.cancel_timer("icon")
	
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
		sys.exit(1)
	
	def __getitem__(self, name):
		""" Convince method that allows widgets to be accessed via self["widget"] """
		if name in self.widgets:
			return self.widgets[name]
		return self.builder.get_object(name)
	
	def __setitem__(self, name, item):
		""" Convince method that allows widgets to be accessed via self["widget"] """
		self.widgets[name] = item
	
	def __contains__(self, name):
		""" Returns true if there is such widget """
		if name in self.widgets: return True
		return self.builder.get_object(name) != None
	
	def show(self):
		self["window"].show_all()
	
	def hide(self):
		self["window"].hide()
	
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
			if self["window"].is_visible():
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
			if self["window"].is_visible():
				self.connect_dialog.show_all()
	
	def close_connect_dialog(self):
		if self.connect_dialog != None:
			self.connect_dialog.hide()
			self.connect_dialog.destroy()
			self.connect_dialog = None
	
	def show_repo(self, id, name, path, is_master, ignore_perms, shared):
		""" Shared is expected to be list """
		# title = name if len(name) < 20 else "...%s" % name[-20:]
		box = InfoBox(self, name, Gtk.Image.new_from_icon_name("drive-harddisk", Gtk.IconSize.LARGE_TOOLBAR))
		box.add_value("id",			"version.png",	_("Repository ID"),			id)
		box.add_value("folder",		"folder.png",	_("Folder"),				path)
		box.add_value("global",		"global.png",	_("Global Repository"),		"? items, ?B")
		box.add_value("local",		"home.png",		_("Local Repository"),		"? items, ?B")
		box.add_value("oos",		"dl_rate.png",	_("Out Of Sync"),			"? items, ?B")
		box.add_value("master",		"lock.png",		_("Master Repo"),			_("Yes") if is_master else _("No"))
		box.add_value("ignore",		"ignore.png",	_("Ignore Permissions"),	_("Yes") if ignore_perms else _("No"))
		box.add_value("shared",		"shared.png",	_("Shared With"),			", ".join([ n.get_title() for n in shared ]))
		box.add_hidden_value("id", id)
		box.add_hidden_value("nodes", shared)
		box.set_status("Unknown")
		box.set_color_hex(COLOR_REPO)
		box.connect('right-click', self.cb_popup_menu_repo)
		self["repolist"].pack_start(box, False, False, 3)
		box.set_vexpand(False)
		box.set_open(id in self.open_boxes)
		self["repolist"].show_all()
		self.repos[id] = box
		return box
	
	def show_node(self, id, name, use_compression):
		if name in (None, ""):
			# Show first block from ID if name is unset
			name = id.split("-")[0]
		box = InfoBox(self, name, Gtk.Image.new_from_icon_name("computer", Gtk.IconSize.LARGE_TOOLBAR))
		box.add_value("address",	"address.png",	_("Address"),			"?")
		box.add_value("sync",		"sync.png",		_("Synchronization"),	"0%")
		box.add_value("compress",	"compress.png",	_("Use Compression"),	_("Yes") if use_compression else _("No"))
		box.add_value("dl.rate",	"dl_rate.png",	_("Download Rate"),		"0 bps (0 B)")
		box.add_value("up.rate",	"up_rate.png",	_("Upload Rate"),		"0 bps (0 B)")
		box.add_value("version",	"version.png",	_("Version"),			"?")
		box.add_hidden_value("id", id)
		box.add_hidden_value("connected", False)
		box.add_hidden_value("completion", {})
		box.add_hidden_value("bytes_in", 0)
		box.add_hidden_value("bytes_out", 0)
		box.add_hidden_value("time", 0)
		box.set_color_hex(COLOR_NODE)
		box.connect('right-click', self.cb_popup_menu_node)
		self["nodelist"].pack_start(box, False, False, 3)
		box.set_vexpand(False)
		box.set_open(id in self.open_boxes)
		self["nodelist"].show_all()
		self.nodes[id] = box
		return box
	
	def clear(self):
		""" Clears repo and node lists. """
		for i in ('nodelist', 'repolist'):
			for c in [] + self[i].get_children():
				self[i].remove(c)
				c.destroy()
		self.nodes = {}
		self.repos = {}
	
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
		self.cancel_all() # timers
		self.daemon.reconnect()
	
	# --- Callbacks ---
	def cb_exit(self, *a):
		if self.process != None:
			if self.config["autokill_daemon"] == 0:
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
			elif self.config["autokill_daemon"] == 1:
				self.process.kill()
		self.quit()
	
	def cb_delete_event(self, *e):
		# Hide main window
		if self.connect_dialog != None:
			self.connect_dialog.hide()
		self["window"].hide()
		return True
	
	def cb_menu_show_id(self, *a):
		d = IDDialog(self, self.daemon.get_my_id())
		d.show(self["window"])
	
	def cb_menu_add_repo(self, event, *a):
		""" Handler for 'Add repository' menu item """
		e = EditorDialog(self, "repo-edit", True)
		e.load()
		e.show(self["window"])
	
	def cb_menu_add_node(self, event, *a):
		""" Handler for 'Add node' menu item """
		e = EditorDialog(self, "node-edit", True)
		e.load()
		e.show(self["window"])
	
	def cb_menu_daemon_settings(self, event, *a):
		""" Handler for 'Daemon Settings' menu item """
		e = EditorDialog(self, "daemon-settings", False)
		e.load()
		e.show(self["window"])
	
	def cb_popup_menu_repo(self, box, button, time):
		self.rightclick_box = box
		self["popup-menu-repo"].popup(None, None, None, None, button, time)
	
	def cb_popup_menu_node(self, box, button, time):
		self.rightclick_box = box
		self["popup-menu-node"].popup(None, None, None, None, button, time)
	
	def cb_menu_popup(self, source, menu):
		""" Handler for ubuntu-only toolbar buttons """
		menu.popup(None, None, None, None, 0, 0)
	
	def cb_menu_popup_edit_repo(self, *a):
		""" Handler for 'edit' context menu item """
		# Editing repository
		e = EditorDialog(self, "repo-edit", False, self.rightclick_box["id"])
		e.load()
		e.show(self["window"])
	
	def cb_menu_popup_edit_node(self, *a):
		""" Handler for other 'edit' context menu item """
		# Editing node
		e = EditorDialog(self, "node-edit", False, self.rightclick_box["id"])
		e.load()
		e.show(self["window"])
	
	def cb_menu_popup_show_id(self, *a):
		""" Handler for 'show id' context menu item """
		# Available only for nodes
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
		if self["window"].is_visible():
			if self.connect_dialog != None:
				self.connect_dialog.hide()
			self["window"].hide()
		else:
			self["window"].show()
			if self.connect_dialog != None:
				self.connect_dialog.show()
	
	def cb_infobar_close(self, bar):
		if bar == self["infobar"]:
			self["infobar"] = None
		bar.close()
		if bar in self.error_boxes:
			self.error_boxes.remove(bar)
	
	def cb_infobar_response(self, bar, response_id):
		if response_id == RESPONSE_RESTART:
			# Restart
			self.daemon.restart()
		if response_id == RESPONSE_FIX_REPOID:
			# Give up if there is no node with matching ID
			if bar["nid"] in self.nodes:
				# Find repository with matching ID ...
				if bar["rid"] in self.repos:
					# ... if found, show edit dialog and pre-select
					# matching node
					e = EditorDialog(self, "repo-edit", False, bar["rid"])
					e.call_after_loaded(e.mark_node, bar["nid"])
					e.load()
					e.show(self["window"])
				else:
					# If there is no matching repository, prefill 'new repo'
					# dialog and let user to save it
					e = EditorDialog(self, "repo-edit", True, bar["rid"])
					e.call_after_loaded(e.mark_node, bar["nid"])
					e.call_after_loaded(e.fill_repo_id, bar["rid"])
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
				self.config["autostart_daemon"] = True
		else: # if response <= 0 or response == RESPONSE_QUIT:
			self.cb_exit()
	
	def cb_kill_daemon_response(self, dialog, response, checkbox):
		if response == RESPONSE_SLAIN_DAEMON:
			if not self.process is None:
				self.process.terminate()
		if checkbox.get_active():
			self.config["autokill_daemon"] = (1 if response == RESPONSE_SLAIN_DAEMON else -1)
		self.process = None
		self.cb_exit()
	
	def cb_daemon_exit(self, proc, error_code):
		if not self.process is None:
			# Whatever happens, if daemon dies while it shouldn't,
			# restart it
			self.process = DaemonProcess(["syncthing"])
			self.process.connect('exit', self.cb_daemon_exit)
