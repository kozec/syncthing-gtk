#!/usr/bin/env python2
from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, Gio, GLib, Pango
from xml.dom import minidom
import json, os, webbrowser, datetime, urlparse
import sys, time, pprint
_ = lambda (a) : a

COLOR_NODE				= "#9246B1"
COLOR_NODE_SYNCING		= "#2A89C8"
COLOR_NODE_CONNECTED	= "#2AAB61"
COLOR_OWN_NODE			= "#C0C0C0"
COLOR_REPO				= "#9246B1"
COLOR_REPO_SYNCING		= "#2A89C8"
COLOR_REPO_IDLE			= "#2AAB61"
DEBUG = False

class App(object):
	def __init__(self):
		self.builder = None
		self.refresh_rate = 1 # seconds
		self.my_id = None
		self.webui_url = None
		self.rightclick_box = None
		# Epoch is incereased when restart() method is called; It is
		# used to discard responses for old REST requests
		self.epoch = 1	
		# connect_dialog may be displayed durring initial communication
		# or if daemon shuts down.
		self.connect_dialog = None
		self.widgets = {}
		self.repos = {}
		self.nodes = {}
		self.setup_widgets()
		self.setup_connection()
		GLib.idle_add(self.request_config)
	
	def setup_widgets(self):
		# Load glade file
		self.builder = Gtk.Builder()
		self.builder.add_from_file("app.glade")
		self.builder.connect_signals(self)
		# Setup window
		self["window"].set_title(_("Syncthing GTK"))
		self["edit-menu"].set_sensitive(False)
	
	def setup_connection(self):
		# Read syncthing config to get connection url
		confdir = GLib.get_user_config_dir()
		if confdir is None:
			confdir = os.path.expanduser("~/.config")
		configxml = os.path.join(confdir, "syncthing", "config.xml")
		try:
			config = file(configxml, "r").read()
		except Exception, e:
			self.fatal_error("Failed to read daemon configuration: %s" % e)
		try:
			xml = minidom.parseString(config)
		except Exception, e:
			self.fatal_error("Failed to parse daemon configuration: %s" % e)
		try:
			address = xml.getElementsByTagName("configuration")[0] \
						.getElementsByTagName("gui")[0] \
						.getElementsByTagName("address")[0] \
						.firstChild.nodeValue
			self.webui_url = "http://%s" % address
			self.last_id = 0
			# TODO: https
		except Exception, e:
			self.fatal_error("Required configuration node not found in daemon config file")
	
	def rest_request(self, command, callback, error_callback=None, callback_data=None):
		"""
		Requests response from server. After response is recieved,
		callback with parsed json data is called.
		If requests fails and error_callback is set, error_callback is
		called. If error_callback is None, request is repeated.
		
		Callback signatures:
		if callback_data is set:
			callback(json_data, callback_data)
			error_callback(exception, command, callback_data)
		if callback_data is null:
			callback(json_data)
			error_callback(exception, command)
		"""
		uri = "%s/rest/%s" % (self.webui_url, command)
		io = Gio.file_new_for_uri(uri)
		io.load_contents_async(None, self.rest_response, command, self.epoch, callback, error_callback, callback_data)
	
	def rest_response(self, io, results, command, epoch, callback, error_callback, callback_data):
		"""
		Recieves and parses REST response. Calls callback if successfull.
		See rest_request for more info.
		"""
		if epoch < self.epoch :
			# Requested before restart() call; Data may be nonactual, discard it.
			if DEBUG : print "Discarded old response for", command
			return
		try:
			ok, contents, etag = io.load_contents_finish(results)
		except Exception, e:
			self.rest_error(e, command, epoch, callback, error_callback, callback_data)
			return
		if ok:
			data = json.loads(contents) if "{" in contents else {'data' : contents}
			if callback_data:
				callback(data, callback_data)
			else:
				callback(data)
		else:
			self.rest_error(Exception("not ok"), command, epoch, callback, error_callback, callback_data)
	
	def rest_error(self, error, command, epoch, callback, error_callback, callback_data):
		""" Error handler for rest_response method """
		if error_callback:
			if callback_data:
				error_callback(error, command, callback_data)
			else:
				error_callback(error, command)
		else:
			print >>sys.stderr, "Request '%s' failed (%s) Repeating..." % (command, error)
			GLib.timeout_add_seconds(1, self.rest_request, command, callback, error_callback, callback_data)
	
	def request_config(self, *a):
		""" Request settings from syncthing daemon """
		self.rest_request("config", self.syncthing_cb_config, self.syncthing_cb_config_error)
	
	def request_repo_data(self, repo_id):
		self.rest_request("model?repo=%s" % (repo_id,), self.syncthing_cb_repo_data, callback_data=repo_id)
	
	def request_completion(self, node_id, repo_id=None):
		""" Requests completion data from syncthing daemon """
		if repo_id is None:
			node = self.nodes[node_id]
			for repo in self.repos.values():
				if node in repo["nodes"]:
					self.request_completion(node_id, repo["id"])
			return
		self.rest_request("completion?node=%s&repo=%s" % (node_id, repo_id), self.syncthing_cb_completion, callback_data=(node_id, repo_id))
	
	def request_events(self, *a):
		""" Request new events from syncthing daemon """
		self.rest_request("events?since=%s" % self.last_id, self.syncthing_cb_events, self.syncthing_cb_events_error)
	
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
			self.connect_dialog = Gtk.MessageDialog(
				self["window"],
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.INFO, 0, "-")
			self.connect_dialog.add_button("gtk-quit", 1)
			self.connect_dialog.connect("response", self.cb_exit) # Only one response available so far
			self.connect_dialog.show_all()
		def set_label(d, message):
			""" Small, recursive helper function to set label somehwere deep in dialog """
			for c in d.get_children():
				if isinstance(c, Gtk.Container):
					if set_label(c, message):
						return True
				elif isinstance(c, Gtk.Label):
					c.set_markup(message)
					return True
			return False
		set_label(self.connect_dialog.get_content_area(), message)
	
	def close_connect_dialog(self):
		if self.connect_dialog != None:
			self.connect_dialog.destroy()
			self.connect_dialog = None
	
	def show_popup_menu(self, box, event):
		self.rightclick_box = box
		self["popup-menu"].popup(None, None, None, None, event.button, event.time)
	
	def show_repo(self, id, name, path, is_master, ignore_perms, shared):
		""" Shared is expected to be list """
		# title = name if len(name) < 20 else "...%s" % name[-20:]
		box = InfoBox(self, name, Gtk.Image.new_from_icon_name("drive-harddisk", Gtk.IconSize.LARGE_TOOLBAR))
		box.add_value("id",			"icons/version.png",	_("Repository ID"),			id)
		box.add_value("folder",		"icons/folder.png",		_("Folder"),				path)
		box.add_value("global",		"icons/global.png",		_("Global Repository"),		"? items, ?B")
		box.add_value("local",		"icons/home.png",		_("Local Repository"),		"? items, ?B")
		box.add_value("oos",		"icons/dl_rate.png",	_("Out Of Sync"),			"? items, ?B")
		box.add_value("master",		"icons/lock.png",		_("Master Repo"),			_("Yes") if is_master else _("No"))
		box.add_value("ignore",		"icons/ignore.png",		_("Ignore Permissions"),	_("Yes") if ignore_perms else _("No"))
		box.add_value("shared",		"icons/shared.png",		_("Shared With"),			", ".join([ n.get_title() for n in shared ]))
		box.add_hidden_value("id", id)
		box.add_hidden_value("needs_update", True)
		box.add_hidden_value("nodes", shared)
		box.set_status("Unknown")
		box.set_color_hex(COLOR_REPO)
		self["repolist"].pack_start(box, False, False, 3)
		box.set_vexpand(False)
		self["repolist"].show_all()
		self.repos[id] = box
		return box
	
	def show_node(self, id, name, use_compression):
		box = InfoBox(self, name, Gtk.Image.new_from_icon_name("computer", Gtk.IconSize.LARGE_TOOLBAR))
		box.add_value("address",	"icons/address.png",	_("Address"),			"?")
		box.add_value("sync",		"icons/sync.png",		_("Synchronization"),	"0%")
		box.add_value("compress",	"icons/compress.png",	_("Use Compression"),	_("Yes") if use_compression else _("No"))
		box.add_value("dl.rate",	"icons/dl_rate.png",	_("Download Rate"),		"0 bps (0 B)")
		box.add_value("up.rate",	"icons/up_rate.png",	_("Upload Rate"),		"0 bps (0 B)")
		box.add_value("version",	"icons/version.png",	_("Version"),			"?")
		box.add_hidden_value("id", id)
		box.add_hidden_value("connected", False)
		box.add_hidden_value("completion", {})
		box.add_hidden_value("bytes_in", 0)
		box.add_hidden_value("bytes_out", 0)
		box.add_hidden_value("time", 0)
		box.set_color_hex(COLOR_NODE)
		self["nodelist"].pack_start(box, False, False, 3)
		box.set_vexpand(False)
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
		self.epoch += 1
		self.my_id = None
		self["edit-menu"].set_sensitive(False)
		self.request_config()
	
	def update_completion(self, node_id):
		node = self.nodes[node_id]
		total = 100.0 * len(node["completion"])
		sync = sum(node["completion"].values())
		node["sync"] = "%3.f%%" % (sync / total * 100.0)
		if not node["connected"]:
			node.set_color_hex(COLOR_NODE)
			node.set_status(_("Disconnected"))
		elif sync < total:
			node.set_color_hex(COLOR_NODE_SYNCING)
			node.set_status(_("Syncing"), total, sync)
		else:
			node.set_color_hex(COLOR_NODE_CONNECTED)
			node.set_status(_("Up to Date"))
	
	# --- Callbacks ---
	def cb_exit(self, event, *a):
		Gtk.main_quit()
	
	def cb_menu_add_repo(self, event, *a):
		pass
	
	def cb_menu_popup_edit(self, *a):
		if self.rightclick_box in self.repos.values():
			# Editing repository
			e = EditorDialog(self, "repo-edit", False, self.rightclick_box["id"])
			e.show(self["window"])
	
	def syncthing_cb_events(self, events):
		""" Called when event list is pulled from syncthing daemon """
		if len(events) > 0:
			for e in events:
				self.on_event(e)
			self.last_id = events[-1]["id"]
		for rid in self.repos:
			if self.repos[rid]["needs_update"]:
				self.repos[rid]["needs_update"] = False
				self.rest_request("model?repo=%s" % (rid,), self.syncthing_cb_repo_data, callback_data=rid)
		GLib.timeout_add_seconds(self.refresh_rate, self.request_events)
	
	def syncthing_cb_events_error(self, exception, command):
		"""
		As most frequent request, "event" request is used to detect when
		daemon stops to respond. "Please wait" message is displayed in
		that case, UI is restarted and waits until daemon respawns.
		"""
		if isinstance(exception, GLib.GError):
			print ">>>", exception.code, exception.message
			if exception.code in (34, 39):	# Connection terminated unexpectedly, Connection Refused
				self.display_connect_dialog("%s %s" % (
					_("Connecting to Syncthing daemon lost."),
					_("Syncthing is probably restarting or has been shut down.")
					))
				self.restart()
				return
		# Other errors are ignored and events are pulled again after prolonged delay
		GLib.timeout_add_seconds(self.refresh_rate * 5, self.request_events)
	
	def syncthing_cb_connections(self, connections):
		current_time = time.time()
		totals = {"dl.rate" : 0.0, "up.rate" : 0.0, "InBytesTotal" : 0.0, "OutBytesTotal" : 0.0} # Total up/down rate, total bytes transfered
		for nid in connections:
			if nid != "total":
				try:
					node = self.nodes[nid]
					# Update easy stuff
					node["address"] = connections[nid]["Address"]
					node["version"] = connections[nid]["ClientVersion"]
					# Compute transfer rate
					for key, ui_key, data_key in ( ("bytes_in", "dl.rate", "InBytesTotal"), ("bytes_out", "up.rate", "OutBytesTotal") ):
						if node[key] != 0:
							time_delta = current_time - node["time"]
							if time_delta > 0: # Don't divide by zero even if time wraps
								bytes_delta = connections[nid][data_key] - node[key]
								bps = float(bytes_delta) / time_delta  # B/s
								node[ui_key] = "%sps (%s)" % (sizeof_fmt(bps), sizeof_fmt(connections[nid][data_key]))
								totals[ui_key] += bps
								totals[data_key] += connections[nid][data_key]
						node[key] = connections[nid][data_key]
					node["time"] = current_time
					# Update color & header if node changed state just now
					if not node["connected"]:
						node.set_status(_("Connected"))
						node["connected"] = True
						node.set_color_hex(COLOR_NODE_SYNCING)
					# Requeste additional data
					self.request_completion(nid)
				except KeyError: # Unknown node
					print >>sys.stderr, "Warning: Unknown node recieved in connection list:", e["data"]["id"]
		if self.my_id in self.nodes:
			# If my node is already known, update down/upload rate
			node = self.nodes[self.my_id]
			for ui_key, data_key in ( ("dl.rate", "InBytesTotal"), ("up.rate", "OutBytesTotal") ):
				node[ui_key] = "%sps (%s)" % (sizeof_fmt(totals[ui_key]), sizeof_fmt(totals[data_key]))
			# TODO: Results differ from webui :(
		GLib.timeout_add_seconds(self.refresh_rate * 5, self.rest_request, "connections", self.syncthing_cb_connections)
	
	def syncthing_cb_completion(self, data, (node_id, repo_id)):
		if not node_id in self.nodes : return	# Shouldn't be possible
		self.nodes[node_id]["completion"][repo_id] = float(data["completion"])
		self.update_completion(node_id)
	
	def syncthing_cb_system(self, data):
		if self.my_id != data["myID"]:
			if self.my_id != None:
				# Can myID be ever changed? Do full restart in that case
				self.restart()
				return
			self.my_id = data["myID"]
			node = self.nodes[self.my_id]
			# Move my node to top
			self["nodelist"].reorder_child(node, 0)
			# Modify header & color
			node.set_status("")
			node.set_icon(Gtk.Image.new_from_icon_name("user-home", Gtk.IconSize.LARGE_TOOLBAR))
			node.invert_header(True)
			node.set_color_hex(COLOR_OWN_NODE)
			self["header"].set_subtitle(node.get_title())
			# Modify values
			node.clear_values()
			node.add_value("ram",		"icons/ram.png",	_("RAM Utilization"), "")
			node.add_value("cpu",		"icons/cpu.png",	_("CPU Utilization"), "")
			node.add_value("dl.rate",	"icons/dl_rate.png",	_("Download Rate"),			"0 bps (0 B)")
			node.add_value("up.rate",	"icons/up_rate.png",	_("Upload Rate"),			"0 bps (0 B)")
			node.add_value("announce",	"icons/announce.png",	_("Announce Server"),		"")
			node.add_value("version",	"icons/version.png",	_("Version"),				"?")
			node.show_all()
			self.rest_request("version", self.syncthing_cb_version)
		
		# Update my node display
		node = self.nodes[self.my_id]
		node["ram"] = sizeof_fmt(data["sys"])
		node["cpu"] = "%3.2f%%" % (data["cpuPercent"],)
		if not "extAnnounceOK" in data:
			node["announce"] = _("disabled")
		elif data["extAnnounceOK"]:
			node["announce"] = _("Online") 
		else:
			node["announce"] = _("offline")
		
		GLib.timeout_add_seconds(self.refresh_rate * 5, self.rest_request, "system", self.syncthing_cb_system)
	
	def syncthing_cb_version(self, data):
		node = self.nodes[self.my_id]
		if node is None : return
		node["version"] = data["data"]
	
	def syncthing_cb_repo_data(self, data, repo_id):
		if not repo_id in self.repos: return	# Shouldn't be possible
		repo = self.repos[repo_id]
		repo["global"] = "%s %s, %s" % (data["globalFiles"], _("Files"), sizeof_fmt(data["globalBytes"]))
		repo["local"]	 = "%s %s, %s" % (data["localFiles"], _("Files"), sizeof_fmt(data["localBytes"]))
		repo["oos"]	 = "%s %s, %s" % (data["needFiles"], _("Files"), sizeof_fmt(data["needBytes"]))
		repo.set_status(_(data['state'].capitalize()), float(data["globalBytes"]), float(data["inSyncBytes"]))
		
		if data['state'] == 'idle':
			repo.set_color_hex(COLOR_REPO_IDLE)
		else:
			# Repo is being synchronized, request data again to keep UI updated
			GLib.timeout_add_seconds(self.refresh_rate, self.request_repo_data, repo_id)
			repo.set_color_hex(COLOR_REPO_SYNCING)
	
	def syncthing_cb_config(self, config):
		"""
		Called when configuration is loaded from syncthing daemon.
		After configuraion is sucessfully parsed, app starts quering for events
		"""
		self.clear()
		# Parse nodes
		for n in sorted(config["Nodes"], key=lambda x : x["Name"].lower()):
			self.show_node(n["NodeID"], n["Name"], n["Compression"])
		# Parse repos
		for r in config["Repositories"]:
			rid = r["ID"]
			self.show_repo(
				rid, r["Directory"], r["Directory"],
				r["ReadOnly"], r["IgnorePerms"], 
				sorted([ self.nodes[n["NodeID"]] for n in r["Nodes"] ], key=lambda x : x.get_title().lower())
				)
			self.request_repo_data(rid)
			
		self.close_connect_dialog()
		self["edit-menu"].set_sensitive(True)
		self.rest_request("events?limit=1", self.syncthing_cb_events)	# Requests most recent event only
		self.rest_request("connections", self.syncthing_cb_connections)
		self.rest_request("system", self.syncthing_cb_system)
	
	def syncthing_cb_config_error(self, exception, command):
		if isinstance(exception, GLib.GError):
			if exception.code == 39:	# Connection Refused, I can't find constant for it in GLib
				# Connection refused is only error code with good way to handle.
				# It usualy means that daemon is not yet fully started or not running at all.
				# For now, handler just displays dialog with "please wait" message tries it again
				if self.connect_dialog == None:
					self.display_connect_dialog("%s\n%s" % (
						_("Connecting to Syncthing daemon at %s...") % (self.webui_url,),
						_("If daemon is not running, it may be good idea to start it now.")
						))
				GLib.timeout_add_seconds(self.refresh_rate, self.rest_request, "config", self.syncthing_cb_config, self.syncthing_cb_config_error)
				return
		# All other errors are fatal for now. Error dialog is displayed and program exits.
		d = Gtk.MessageDialog(
				self["window"],
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
				"%s\n\n%s %s" % (
					_("Connection to daemon failed. Check your configuration and try again."),
					_("Error message:"), str(exception)
					)
				)
		d.run()
		Gtk.main_quit()
	
	def on_event(self, e):
		eType = e["type"]
		if eType in ("Ping", "Starting", "StartupComplete"):
			# Let's ignore ignore those
			pass
		elif eType == "StateChanged":
			try:
				box = self.repos[e["data"]["repo"]]
				box.set_status(_(e["data"]["to"].capitalize()))
				if e["data"]["to"] == "idle":
					box.set_color_hex(COLOR_REPO_IDLE)
				else:
					box.set_color_hex(COLOR_REPO_SYNCING)
				box["needs_update"] = True
			except KeyError: # Unknown repo
				print >>sys.stderr, "Warning: Unknown repo recieved for StateChanged event:", e["data"]["repo"]
		elif eType in ("LocalIndexUpdated", "RemoteIndexUpdated"):
			try:
				self.repos[e["data"]["repo"]]["needs_update"] = True
			except KeyError: # Unknown repo
				print >>sys.stderr, "Warning: Unknown repo recieved for %s event:" % eType, e["data"]["repo"]
		elif eType == "NodeConnected":
			try:
				node = self.nodes[e["data"]["id"]]
				node["address"] = e["data"]["addr"]
				node.set_status(_("Connected"))
				node["connected"] = True
				node.set_color_hex(COLOR_NODE_SYNCING)
				self.request_completion(e["data"]["id"], None)
			except KeyError: # Unknown node
				print >>sys.stderr, "Warning: Unknown node recieved for NodeConnected event:", e["data"]["id"]
		elif eType == "NodeDisconnected":
			try:
				node = self.nodes[e["data"]["id"]]
				node.set_status(_("Disconnected"))
				node["address"] = "?"
				node["connected"] = False
				node.set_color_hex(COLOR_NODE)
			except KeyError: # Unknown node
				print >>sys.stderr, "Warning: Unknown node recieved for NodeDisconnected event:", e["data"]["id"]
				print self.nodes
		else:
			print "Unhandled event type:", e

class InfoBox(Gtk.Container):
	""" Box with informations about node or repository """
	__gtype_name__ = "InfoBox"
	
	### Initialization
	def __init__(self, app, title, icon):
		# Variables
		self.app = app
		self.child = None
		self.header = None
		self.str_title = None
		self.header_inverted = False
		self.values = {}
		self.value_widgets = {}
		self.icon = icon
		self.color = (1, 0, 1, 1)		# rgba
		self.background = (1, 1, 1, 1)	# rgba
		self.border_width = 2
		self.children = [self.header, self.child]
		# Initialization
		Gtk.Container.__init__(self)
		self.init_header()
		self.init_grid()
		# Settings
		self.set_title(title)
		self.set_status(_("Disconnected"))
	
	def set_icon(self, icon):
		self.header_box.remove(self.icon)
		self.header_box.pack_start(icon, False, False, 0)
		self.header_box.reorder_child(icon, 0)
		self.header_box.show_all()
		self.icon = icon
	
	def init_header(self):
		# Create widgets
		eb = Gtk.EventBox()
		self.title = Gtk.Label()
		self.status = Gtk.Label()
		hbox = Gtk.HBox()
		# Set values
		self.title.set_alignment(0.0, 0.5)
		self.status.set_alignment(1.0, 0.5)
		self.title.set_ellipsize(Pango.EllipsizeMode.START)
		hbox.set_spacing(4)
		# Connect signals
		eb.connect("realize", self.set_header_cursor)
		eb.connect("button-release-event", self.on_header_click)
		# Pack together
		hbox.pack_start(self.icon, False, False, 0)
		hbox.pack_start(self.title, True, True, 0)
		hbox.pack_start(self.status, False, False, 0)
		eb.add(hbox)
		# Update stuff
		self.header_box = hbox
		self.header = eb
		self.header.set_parent(self)
		self.children = [self.header, self.child]
	
	def init_grid(self):
		# Create widgets
		self.grid = Gtk.Grid()
		self.rev = Gtk.Revealer()
		align = Gtk.Alignment()
		eb = Gtk.EventBox()
		# Set values
		self.grid.set_row_spacing(1)
		self.grid.set_column_spacing(3)
		self.rev.set_reveal_child(False)
		align.set_padding(2, 2, 5, 5)
		# Connect signals
		eb.connect("button-release-event", self.on_grid_click)
		# Pack together
		align.add(self.grid)
		eb.add(align)
		self.rev.add(eb)
		self.add(self.rev)
	
	### GtkWidget-related stuff
	def do_add(self, widget):
		if not widget is None:
			if self.child is None:
				self.child = widget
				self.children = [self.header, self.child]
				widget.set_parent(self)
 
	def do_remove(self, widget):
		if self.child == widget:
			self.child = None
			self.children = [self.header, self.child]
			widget.unparent()
 
	def do_child_type(self):
		return(Gtk.Widget.get_type())
 
	def do_forall(self, include_internals, callback, *callback_parameters):
		if not callback is None:
			if hasattr(self, 'children'): # No idea why this happens...
				for c in self.children:
					if not c is None:
						callback(c, *callback_parameters)
 
	def do_get_request_mode(self):
		return(Gtk.SizeRequestMode.CONSTANT_SIZE)
 
	def do_get_preferred_height(self):
		mw, nw, mh, nh = self.get_prefered_size()
		return(mh, nh)
 
	def do_get_preferred_width(self):
		mw, nw, mh, nh = self.get_prefered_size()
		return(mw, nw)
	
	def get_prefered_size(self):
		""" Returns (min_width, nat_width, min_height, nat_height) """
		min_width, nat_width = 0, 0
		min_height, nat_height = 0, 0
		# Use max of prefered widths from children;
		# Use sum of predered height from children.
		for c in self.children:
			if not c is None:
				mw, nw = c.get_preferred_width()
				mh, nh = c.get_preferred_height()
				min_width = max(min_width, mw)
				nat_width = max(nat_width, nw)
				min_height = min_height + mh
				nat_height = nat_height + nh
		# Add border size
		min_width += self.border_width * 2	# Left + right border
		nat_width += self.border_width * 2
		min_height += self.border_width * 3	# Top + bellow header + bottom
		nat_height += self.border_width * 3
		return(min_width, nat_width, min_height, nat_height)
 
	def do_size_allocate(self, allocation):
		child_allocation = Gdk.Rectangle()
		child_allocation.x = self.border_width
		child_allocation.y = self.border_width
 
		self.set_allocation(allocation)
 
		if self.get_has_window():
			if self.get_realized():
				self.get_window().move_resize(allocation.x, allocation.y, allocation.width, allocation.height)
		
		# Allocate childrens as VBox does, always use all available width
		for c in self.children:
			if not c is None:
				if c.get_visible():
					min_size, nat_size = c.get_preferred_size()
					child_allocation.width = allocation.width - (self.border_width * 2)
					child_allocation.height = min_size.height
					# TODO: Handle child that has window (where whould i get it?)
					c.size_allocate(child_allocation)
					child_allocation.y += child_allocation.height + self.border_width
 
	def do_realize(self):
		allocation = self.get_allocation()
 
		attr = Gdk.WindowAttr()
		attr.window_type = Gdk.WindowType.CHILD
		attr.x = allocation.x
		attr.y = allocation.y
		attr.width = allocation.width
		attr.height = allocation.height
		attr.visual = self.get_visual()
		attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK
 
		WAT = Gdk.WindowAttributesType
		mask = WAT.X | WAT.Y | WAT.VISUAL
 
		window = Gdk.Window(self.get_parent_window(), attr, mask);
		window.set_decorations(0)
		self.set_window(window)
		self.register_window(window)
		self.set_realized(True)
 
	def do_draw(self, cr):
		allocation = self.get_allocation()
		
		if self.background is None:
			# Use default window background
			Gtk.render_background(self.get_style_context(), cr,
					self.border_width,
					self.border_width,
					allocation.width - (2 * self.border_width),
					allocation.height - (2 * self.border_width)
					)
		
		header_al = self.children[0].get_allocation()
		
		# Border
		cr.set_source_rgba(*self.color)
		cr.move_to(0, self.border_width / 2.0)
		cr.line_to(0, allocation.height)
		cr.line_to(allocation.width, allocation.height)
		cr.line_to(allocation.width, self.border_width / 2.0)
		cr.set_line_width(self.border_width * 2) # Half of border is rendered outside of widget
		cr.stroke()
		
		# Background
		if not self.background is None:
			# Use set background color
			cr.set_source_rgba(*self.background)
			cr.rectangle(self.border_width,
					self.border_width,
					allocation.width - (2 * self.border_width),
					allocation.height - (2 * self.border_width)
					)
			cr.fill()
		
		# Header
		cr.set_source_rgba(*self.color)
		cr.rectangle(self.border_width / 2.0, 0, allocation.width - self.border_width, header_al.height + (2 * self.border_width))
		cr.fill()
		
		for c in self.children:
			if not c is None:
				self.propagate_draw(c, cr)
            
	### InfoBox logic
	def set_header_cursor(self, eb, *a):
		""" Sets cursor over top part of infobox to hand """
		eb.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND1))
	
	def on_header_click(self, eventbox, event):
		"""
		Hides or reveals everything bellow header
		Displays popup menu on right click
		"""
		if event.button == 1:	# left
			self.rev.set_reveal_child(not self.rev.get_reveal_child())
		elif event.button == 3:	# right
			self.app.show_popup_menu(self, event)
	
	def on_grid_click(self, eventbox, event):
		""" Displays popup menu on right click """
		if event.button == 3:	# right
			self.app.show_popup_menu(self, event)
	
	### Methods
	def set_title(self, t):
		self.str_title = t
		if self.header_inverted:
			self.title.set_markup('<span font_weight="bold" font_size="large" color="black">%s</span>' % t)
		else:
			self.title.set_markup('<span font_weight="bold" font_size="large" color="white">%s</span>' % t)
	
	def get_title(self):
		return self.str_title
	
	def invert_header(self, e):
		self.header_inverted = e
		self.set_title(self.str_title)
	
	def set_status(self, t, percentage_base=0.0, percentage_value=0.0):
		if percentage_base > 0.0 and percentage_base != percentage_value :
			percent = percentage_value / percentage_base * 100.0
			self.status.set_markup('<span font_weight="bold" font_size="large" color="white">%s (%.f%%)</span>' % (t, percent))
			if DEBUG : print "%s state changed to %s (%s%%)" % (self.str_title, t, percent)
		else:
			self.status.set_markup('<span font_weight="bold" font_size="large" color="white">%s</span>' % t)
			if DEBUG : print "%s state changed to %s" % (self.str_title, t)
	
	def set_color_hex(self, hx):
		""" Expects AABBCC or #AABBCC format """
		hx = hx.lstrip('#')
		l = len(hx)
		color = [ float(int(hx[i:i+l/3], 16)) / 255.0 for i in range(0, l, l/3) ]
		while len(color) < 4:
			color.append(1.0)
		self.set_color(*color)
		
	def set_color(self, r, g, b, a):
		""" Expects floats """
		self.color = (r, g, b, a)
		self.queue_draw()
	
	def set_border(self, width):
		self.border_width = width
		self.queue_resize()
	
	def add_value(self, key, icon, title, value):
		""" Adds new line with provided properties """
		wIcon, wTitle, wValue = Gtk.Image.new_from_file(icon), Gtk.Label(), Gtk.Label()
		self.value_widgets[key] = wValue
		self.set_value(key, value)
		wTitle.set_text(title)
		wTitle.set_alignment(0.0, 0.5)
		wValue.set_alignment(1.0, 0.5)
		wValue.set_ellipsize(Pango.EllipsizeMode.START)
		wTitle.set_property("expand", True)
		line = len(self.value_widgets)
		self.grid.attach(wIcon, 0, line, 1, 1)
		self.grid.attach_next_to(wTitle, wIcon, Gtk.PositionType.RIGHT, 1, 1)
		self.grid.attach_next_to(wValue, wTitle, Gtk.PositionType.RIGHT, 1, 1)
	
	def clear_values(self):
		""" Removes all lines from UI, efectively making all values hidden """
		for ch in [ ] + self.grid.get_children():
			self.grid.remove(ch)
		self.value_widgets = {}
	
	def add_hidden_value(self, key, value):
		""" Adds value that is saved, but not shown on UI """
		self.set_value(key, value)
	
	def set_value(self, key, value):
		""" Updates already existing value """
		self.values[key] = value
		if key in self.value_widgets:
			self.value_widgets[key].set_text(value)
	
	def get_value(self, key):
		return self.values[key]
	
	def __getitem__(self, key):
		""" Shortcut to get_value """
		return self.values[key]
	
	def __setitem__(self, key, value):
		""" Shortcut to set_value. Creates new hidden_value if key doesn't exist """
		self.set_value(key, value)

class EditorDialog(object):
	""" Universal handler for all Syncthing settings and editing """
	VALUES = {
		# Dict with lists of all editable values, indexed by editor mode
		"repo-edit" : ["vID", "vDirectory", "vReadOnly", "vIgnorePerms", "vVersioning", "vKeepVersions", "vNodes" ],
	}
	
	def __init__(self, app, mode, is_new, id):
		self.app = app
		self.mode = mode
		self.id = id
		self.is_new = is_new
		self.config = None
		self.values = None
		self.setup_widgets()
		self.load_data()
	
	def __getitem__(self, name):
		""" Convince method that allows widgets to be accessed via self["widget"] """
		return self.builder.get_object(name)
	
	def __contains__(self, name):
		""" Returns true if there is such widget """
		return self.builder.get_object(name) != None
	
	def find_widget_by_id(self, id, parent=None):
		""" Recursively searchs for widget with specified ID """
		if parent == None:
			if id in self: return self[id] # Do things fast if possible
			parent = self["editor"]
		for c in parent.get_children():
			if c.get_id() == id:
				return c
			if isinstance(c, Gtk.Container):
				r = self.find_widget_by_id(id, c)
				if not r is None:
					return r
		return None
	
	def show(self, parent=None):
		if not parent is None:
			self["editor"].set_transient_for(parent)
		self["editor"].show_all()
	
	def close(self):
		self["editor"].hide()
		self["editor"].destroy()
	
	def setup_widgets(self):
		# Load glade file
		self.builder = Gtk.Builder()
		self.builder.add_from_file("%s.glade" % self.mode)
		self.builder.connect_signals(self)
		# Set title stored in glade file in "Edit Title|Save Title" format
		self["editor"].set_title(self["editor"].get_title().split("|")[ 1 if self.is_new else 0 ])
		# Disable everything until configuration is loaded
		self["editor"].set_sensitive(False)
	
	def get_value(self, key):
		"""
		Returns value from configuration.
		Usualy returns self.values[key], but can handle some special cases
		"""
		if key == "KeepVersions":
			# Number
			return self.values["Versioning"]["Params"]["keep"] # oww...
		elif key == "Versioning":
			# Boool
			return self.values["Versioning"]["Type"] != ""
		elif key in self.values:
			return self.values[key]
		else:
			raise KeyError(key)
	
	def load_data(self):
		self.app.rest_request("config", self.cb_data_loaded, self.cb_data_failed)
	
	def cb_data_loaded(self, config):
		self.config = config
		try:
			if self.mode == "repo-edit":
				self.values = [ x for x in self.config["Repositories"] if x["ID"] == self.id ][0]
		except KeyError:
			# ID not found in configuration. This is practicaly impossible,
			# so it's handled only by self-closing dialog.
			self.close()
			return
		# Iterate over all known configuration values and set UI elements using unholy method
		for key in self.VALUES[self.mode]:
			w = self.find_widget_by_id(key)
			if not key is None:
				if isinstance(w, Gtk.Entry):
					w.set_text(self.get_value(key.strip("v")))
				elif isinstance(w, Gtk.CheckButton):
					w.set_active(self.get_value(key.strip("v")))
				elif key == "vNodes":
					# Very special case
					nids = [ n["NodeID"] for n in self.get_value("Nodes") ]
					for node in self.app.nodes.values():
						if node["id"] != self.app.my_id:
							b = Gtk.CheckButton(node.get_title(), False)
							self["vNodes"].pack_end(b, False, False, 0)
							b.set_active(node["id"] in nids)
					self["vNodes"].show_all()
				else:
					print w
		# Disable ID editing if neede
		self["vID"].set_sensitive(self.is_new)
		# Enable dialog
		self["editor"].set_sensitive(True)
	
	def cb_data_failed(self, exception, *a):
		"""
		Failed to load configuration. This shouldn't happen unless daemon
		dies exactly when user clicks to edit menu.
		Handled by simple error message.
		"""
		# All other errors are fatal for now. Error dialog is displayed and program exits.
		d = Gtk.MessageDialog(
				self["editor"],
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
				"%s %s\n\n%s %s" % (
					_("Failed to load configuration from daemon."),
					_("Try again."),
					_("Error message:"), str(exception)
					)
				)
		d.run()
		self.close()

def sizeof_fmt(size):
	for x in ('B','kB','MB','GB','TB'):
		if size < 1024.0:
			if x in ('B', 'kB'):
				return "%3.0f %s" % (size, x)
			return "%3.2f %s" % (size, x)
		size /= 1024.0

if __name__ == "__main__":
	App().show()
	Gtk.main()

