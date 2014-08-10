#!/usr/bin/env python2
from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, Gio, GLib, Pango
from xml.dom import minidom
from base64 import b32decode
import json, re, os, webbrowser, datetime, urlparse, tempfile
import sys, time, pprint
_ = lambda (a) : a

COLOR_NODE				= "#9246B1"
COLOR_NODE_SYNCING		= "#2A89C8"
COLOR_NODE_CONNECTED	= "#2AAB61"
COLOR_OWN_NODE			= "#C0C0C0"
COLOR_REPO				= "#9246B1"
COLOR_REPO_SYNCING		= "#2A89C8"
COLOR_REPO_IDLE			= "#2AAB61"
SI_FRAMES				= 4 # Number of animation frames for status icon
LUHN_ALPHABET			= "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" # Characters valid in node id
DEBUG = False

class App(object):
	def __init__(self):
		self.builder = None
		self.refresh_rate = 1 # seconds
		self.my_id = None
		self.webui_url = None
		self.rightclick_box = None
		self.address = None
		self.CSRFtoken = None
		# Epoch is incereased when restart() method is called; It is
		# used to discard responses for old REST requests
		self.epoch = 1	
		# connect_dialog may be displayed durring initial communication
		# or if daemon shuts down.
		self.connect_dialog = None
		self.widgets = {}
		self.repos = {}
		self.nodes = {}
		self.timers = {}			# see timer() method
		self.open_boxes = set([])	# Holds set of expanded node/repo boxes
		self.syncing_repos = set([])# Holds set of repos that are being synchronized
		self.sync_animation = 0
		self.setup_widgets()
		self.setup_statusicon()
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
	
	def setup_statusicon(self):
		self.statusicon = Gtk.StatusIcon.new_from_file("icons/si-unknown.png")
		self.statusicon.set_title(_("Syncthing GTK"))
		self.statusicon.connect("activate", self.cb_statusicon_click)
		self.statusicon.connect("popup-menu", self.cb_statusicon_popup)
		self.set_status(False)
	
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
			self.address = xml.getElementsByTagName("configuration")[0] \
							.getElementsByTagName("gui")[0] \
							.getElementsByTagName("address")[0] \
							.firstChild.nodeValue
			self.webui_url = "http://%s" % self.address
			self.last_id = 0
			# TODO: https
		except Exception, e:
			self.fatal_error("Required configuration node not found in daemon config file")
	
	def set_status(self, is_connected):
		""" Sets icon and text on first line of popup menu """
		if is_connected:
			if len(self.syncing_repos) == 0:
				self.statusicon.set_from_file("icons/si-idle.png")
				self["menu-si-status"].set_label(_("Idle"))
				self.timer_cancel("icon")
			else:
				if len(self.syncing_repos) == 1:
					self["menu-si-status"].set_label(_("Synchronizing '%s'") % (list(self.syncing_repos)[0]["id"],))
				else:
					self["menu-si-status"].set_label(_("Synchronizing %s repos") % (len(self.syncing_repos),))
				self.animate_status()
		else:
			self.statusicon.set_from_file("icons/si-unknown.png")
			self["menu-si-status"].set_label(_("Connecting to daemon..."))
			self.timer_cancel("icon")
	
	def animate_status(self):
		""" Handles icon animation """
		if "icon" in self.timers:
			# Already animating
			return
		self.statusicon.set_from_file("icons/si-syncing-%s.png" % (self.sync_animation,))
		self.sync_animation += 1
		if self.sync_animation >= SI_FRAMES:
			self.sync_animation = 0
		self.timer("icon", 1, self.animate_status)
	
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
			self.rest_error(e, command, callback, error_callback, callback_data)
			return
		finally:
			del io	# Prevents leaking fd's in gvfsd-http daemon if program crashes
		if ok:
			try:
				data = json.loads(contents)
			except ValueError: # Not a JSON
				data = {'data' : contents }
			if callback_data:
				callback(data, callback_data)
			else:
				callback(data)
		else:
			self.rest_error(Exception("not ok"), command, callback, error_callback, callback_data)
	
	def rest_error(self, exception, command, callback, error_callback, callback_data):
		""" Error handler for rest_response method """
		if error_callback:
			if callback_data:
				error_callback(exception, command, callback_data)
			else:
				error_callback(exception, command)
		else:
			print >>sys.stderr, "Request '%s' failed (%s) Repeating..." % (command, exception)
			self.timer(None, 1, self.rest_request, command, callback, error_callback, callback_data)
	
	def rest_post(self, command, data, callback, error_callback=None, callback_data=None):
		""" POSTs data (formated with json) to daemon. Works like rest_request """
		uri = "/rest/%s" % ( "restart",)
		sc = Gio.SocketClient()
		sc.connect_to_host_async(self.address, 0, None, self.rest_post_connected,
			command, data, self.epoch, callback, error_callback, callback_data)
	
	def rest_post_connected(self, sc, results, command, data, epoch, callback, error_callback, callback_data):
		""" Second part of rest_post, called after HTTP connection is initiated """
		try:
			con = sc.connect_to_service_finish(results)
			if con == None:
				raise Exception("Unknown error")
		except Exception, e:
			self.rest_post_error(e, command, data, callback, error_callback, callback_data)
			return
		post_str = None
		if self.CSRFtoken == None:
			# Request CSRF token first
			if DEBUG: print "Requesting cookie"
			post_str = "\r\n".join([
				"GET / HTTP/1.0",
				"Host: %s" % self.address,
				"Connection: close",
				"",
				"",
				]).encode("utf-8")
		else:
			# Build POST request
			json_str = json.dumps(data)
			post_str = "\r\n".join([
				"POST /rest/%s HTTP/1.0" % command,
				"Connection: close",
				"Cookie: CSRF-Token=%s" % self.CSRFtoken,
				"X-CSRF-Token: %s" % self.CSRFtoken,
				"Content-Length: %s" % len(json_str),
				"Content-Type: application/json",
				"",
				json_str
				]).encode("utf-8")
		# Send it out and wait for response
		con.get_output_stream().write_all(post_str)
		con.get_input_stream().read_bytes_async(102400, 1, None, self.rest_post_response,
			sc, command, data, callback, error_callback, callback_data)
	
	def rest_post_response(self, con, results, sc, command, data, callback, error_callback, callback_data):
		try:
			response = con.read_bytes_finish(results)
			if response == None:
				raise Exception("No data recieved")
		except Exception, e:
			self.rest_post_error(e, command, data, callback, error_callback, callback_data)
			return
		finally:
			con.close()
			del con
		response = response.get_data()
		if self.CSRFtoken == None:
			# I wanna cookie!
			response = response.split("\n")
			for d in response:
				if d.startswith("Set-Cookie:"):
					for c in d.split(":", 1)[1].split(";"):
						if c.strip().startswith("CSRF-Token="):
							self.CSRFtoken = c.split("=", 1)[1].strip(" \r\n")
							if DEBUG: print "Got new cookie:", self.CSRFtoken
							break
					if self.CSRFtoken != None:
						break
			if self.CSRFtoken == None:
				# This is pretty fatal and likely to fail again,
				# so request is not repeated automaticaly
				if error_callback == None:
					print >>sys.stderr, ""
					print >>sys.stderr, "Error: Request '%s' failed: Error: failed to get CSRF cookie from daemon" % (command,)
				else:
					self.rest_post_error(Exception("Failed to get CSRF cookie"))
				return
			# Repeat request with acqiured cookie
			self.rest_post(command, data, callback, error_callback, callback_data)
			return
		# Extract response code
		try:
			code = response.split("\n")[0].strip("\r\n").split(" ")[1]
			if int(code) != 200:
				self.rest_post_error(Exception("HTTP error %s" % (code,)), command, data, callback, error_callback, callback_data)
				return
		except Exception:
			# That probably wasn't HTTP
			self.rest_post_error(Exception("Invalid HTTP response"), command, data, callback, error_callback, callback_data)
			return
		if "CSRF Error" in response:
			# My cookie is too old; Throw it away and try again
			if DEBUG: print "Throwing away my cookie :("
			self.CSRFtoken = None
			self.rest_post(command, data, callback, error_callback, callback_data)
			return
		
		# Parse response and call callback
		try:
			response = response.split("\r\n\r\n", 1)[1]
			rdata = json.loads(response)
		except IndexError: # No data
			rdata = { }
		except ValueError: # Not a JSON
			rdata = {'data' : response }
		if callback_data:
			callback(rdata, callback_data)
		else:
			callback(rdata)
	
	def rest_post_error(self, exception, command, data, callback, error_callback, callback_data):
		""" Error handler for rest_post_response method """
		if error_callback:
			if callback_data:
				error_callback(exception, command, data, callback_data)
			else:
				error_callback(exception, command, data)
		else:
			print >>sys.stderr, "Post '%s' failed (%s) Repeating..." % (command, exception)
			self.timer(None, 1, self.rest_post, command, data, callback, error_callback, callback_data)
	
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
			if DEBUG: print "Creating connect_dialog"
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
		if DEBUG: print "Settinig connect_dialog label", message[0:15]
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
		box.set_open(id in self.open_boxes)
		self["repolist"].show_all()
		self.repos[id] = box
		return box
	
	def show_node(self, id, name, use_compression):
		if name in (None, ""):
			# Show first block from ID if name is unset
			name = id.split("-")[0]
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
		self.epoch += 1
		self.my_id = None
		self["info-revealer"].set_reveal_child(False)
		self["edit-menu"].set_sensitive(False)
		self["menu-si-shutdown"].set_sensitive(False)
		self["menu-si-show-id"].set_sensitive(False)
		self["menu-si-restart"].set_sensitive(False)
		for x in self.timers:
			GLib.source_remove(self.timers[x])
		self.timers = {}
		self.request_config()
	
	def timer(self, name, delay, callback, *data):
		"""
		Runs callback after specified number of seconds. Uses
		GLib.timeout_add_seconds with small wrapping to allow named
		timers to be canceled by reset() call
		"""
		if name is None:
			# No wrapping is needed, call GLib directly
			GLib.timeout_add_seconds(delay, callback, *data)
		else:
			if name in self.timers:
				# Cancel old timer
				GLib.source_remove(self.timers[name])
			# Create new one
			self.timers[name] = GLib.timeout_add_seconds(delay, self.cb_timer, name, callback, *data)
	
	def timer_cancel(self, name):
		""" Cancels named timer """
		if name in self.timers:
			GLib.source_remove(self.timers[name])
			del self.timers[name]
	
	def update_completion(self, node_id):
		node = self.nodes[node_id]
		total = 100.0 * len(node["completion"])
		sync = sum(node["completion"].values())
		node["sync"] = "%3.f%%" % (sync / total * 100.0) if total > 0 else "0%"
		if not node["connected"]:
			node.set_color_hex(COLOR_NODE)
			node.set_status(_("Disconnected"))
		elif sync < total:
			node.set_color_hex(COLOR_NODE_SYNCING)
			node.set_status(_("Syncing"), total, sync)
		else:
			node.set_color_hex(COLOR_NODE_CONNECTED)
			node.set_status(_("Up to Date"))
	
	def config_updated(self, *a):
		""" Check if configuration is out of sync """
		self.rest_request("config/sync", self.syncthing_cb_config_in_sync)
	
	# --- Callbacks ---
	def cb_exit(self, event, *a):
		Gtk.main_quit()
	
	def cb_menu_show_id(self, *a):
		d = MyIDDialog(self)
		d.show(self["window"])
	
	def cb_menu_add_repo(self, event, *a):
		""" Handler for 'Add repository' menu item """
		e = EditorDialog(self, "repo-edit", True)
		e.show(self["window"])
	
	def cb_menu_add_node(self, event, *a):
		""" Handler for 'Add node' menu item """
		e = EditorDialog(self, "node-edit", True)
		e.show(self["window"])
	
	def cb_menu_popup_edit(self, *a):
		if self.rightclick_box in self.repos.values():
			# Editing repository
			e = EditorDialog(self, "repo-edit", False, self.rightclick_box["id"])
			e.show(self["window"])
		elif self.rightclick_box in self.nodes.values():
			# Editing node
			e = EditorDialog(self, "node-edit", False, self.rightclick_box["id"])
			e.show(self["window"])
	
	def cb_menu_restart(self, event, *a):
		self.rest_post("restart",  {}, self.syncthing_cb_shutdown, None,
			"%s %s..." % (_("Syncthing is restarting."), _("Please wait")))
	
	def cb_menu_shutdown(self, event, *a):
		self.rest_post("shutdown", {}, self.syncthing_cb_shutdown, None,
			_("Syncthing has been shut down."))
	
	def cb_statusicon_click(self, *a):
		""" Called when user clicks on status icon """
		# Hide / show main window
		if self["window"].is_visible():
			self["window"].hide()
		else:
			self["window"].show()
	
	def cb_statusicon_popup(self, si, button, time):
		""" Called when user right-clicks on status icon """
		self["si-menu"].popup(None, None, None, None, button, time)
	
	def cb_infobar_close(self, *a):
		self["info-revealer"].set_reveal_child(False)
	
	def cb_open_closed(self, box):
		"""
		Called from InfoBox when user opens or closes bottom part
		"""
		if box.is_open():
			self.open_boxes.add(box["id"])
		else:
			self.open_boxes.discard(box["id"])
	
	def cb_timer(self, name, callback, *data):
		"""
		Removes name from list of active timers and calls real callback.
		"""
		del self.timers[name]
		callback(*data)
		return False
	
	def syncthing_cb_shutdown(self, data, message):
		""" Callback for 'shutdown' AND 'restart' request """
		if 'ok' in data:
			self.set_status(False)
			self.display_connect_dialog(message)
			self.restart()
		else:
			# TODO: display error message here
			pass
	
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
		self.timer("event", self.refresh_rate, self.request_events)
	
	def syncthing_cb_events_error(self, exception, command):
		"""
		As most frequent request, "event" request is used to detect when
		daemon stops to respond. "Please wait" message is displayed in
		that case, UI is restarted and waits until daemon respawns.
		"""
		if isinstance(exception, GLib.GError):
			if exception.code in (34, 39):	# Connection terminated unexpectedly, Connection Refused
				if self.connect_dialog == None:
					self.display_connect_dialog("%s %s" % (
						_("Connection to Syncthing daemon lost."),
						_("Syncthing is probably restarting or has been shut down.")
						))
				self.set_status(False)
				self.restart()
				return
		# Other errors are ignored and events are pulled again after prolonged delay
		self.timer("event", self.refresh_rate * 5, self.request_events)
	
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
		self.timer("conns", self.refresh_rate * 5, self.rest_request, "connections", self.syncthing_cb_connections)
	
	def syncthing_cb_completion(self, data, (node_id, repo_id)):
		if node_id in self.nodes:	# Should be always
			if "completion" in data:
				self.nodes[node_id]["completion"][repo_id] = float(data["completion"])
			self.update_completion(node_id)
	
	def syncthing_cb_system(self, data):
		if self.my_id != data["myID"]:
			if self.my_id != None:
				# Can myID be ever changed? Do full restart in that case
				print >>sys.stderr, "Warning: My ID was changed"
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
		
		self.timer("system", self.refresh_rate * 5, self.rest_request, "system", self.syncthing_cb_system)
	
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
			self.syncing_repos.discard(repo)
			self.set_status(True)
		else:
			# Repo is being synchronized, request data again to keep UI updated
			self.timer("repo_%s" % repo_id, self.refresh_rate, self.request_repo_data, repo_id)
			repo.set_color_hex(COLOR_REPO_SYNCING)
			self.syncing_repos.add(repo)
			self.set_status(True)
	
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
		self.set_status(True)
		self["edit-menu"].set_sensitive(True)
		self["menu-si-shutdown"].set_sensitive(True)
		self["menu-si-show-id"].set_sensitive(True)
		self["menu-si-restart"].set_sensitive(True)
		self.rest_request("events?limit=1", self.syncthing_cb_events)	# Requests most recent event only
		self.rest_request("config/sync", self.syncthing_cb_config_in_sync)
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
				self.set_status(False)
				self.timer("config", self.refresh_rate, self.rest_request, "config", self.syncthing_cb_config, self.syncthing_cb_config_error)
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
	
	def syncthing_cb_config_in_sync(self, data):
		"""
		Handler for config/sync response. Displays infobox if
		configuration is not in sync.
		"""
		if "configInSync" in data:
			if not data["configInSync"]:
				# Not in sync...
				self["info-revealer"].set_reveal_child(True)
	
	def on_event(self, e):
		eType = e["type"]
		if eType in ("Ping", "Starting", "StartupComplete"):
			# Let's ignore ignore those
			pass
		elif eType == "StateChanged":
			try:
				to = e["data"]["to"]
				box = self.repos[e["data"]["repo"]]
				box.set_status(_(e["data"]["to"].capitalize()))
				if to == "idle":
					box.set_color_hex(COLOR_REPO_IDLE)
					self.syncing_repos.discard(box)
				elif to == "syncing":
					box.set_color_hex(COLOR_REPO_SYNCING)
					self.syncing_repos.add(box)
				else:
					box.set_color_hex(COLOR_REPO_SYNCING)
					self.syncing_repos.discard(box)
				self.set_status(True)
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
			self.app.cb_open_closed(self)
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
	
	def set_open(self, b):
		self.rev.set_reveal_child(b)
	
	def is_open(self):
		""" Returns True if box is open """
		return self.rev.get_reveal_child()
	
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


class MyIDDialog(object):
	""" Display ID of this node """
	def __init__(self, app):
		self.app = app
		self.setup_widgets()
		self.load_data()
	
	def __getitem__(self, name):
		""" Convince method that allows widgets to be accessed via self["widget"] """
		return self.builder.get_object(name)
	
	def show(self, parent=None):
		if not parent is None:
			self["dialog"].set_transient_for(parent)
		self["dialog"].show_all()
	
	def close(self):
		self["dialog"].hide()
		self["dialog"].destroy()
	
	def setup_widgets(self):
		# Load glade file
		self.builder = Gtk.Builder()
		self.builder.add_from_file("node-id.glade")
		self.builder.connect_signals(self)
		self["vID"].set_text(self.app.my_id)

	def load_data(self):
		""" Loads QR code from Syncthing daemon """
		uri = "%s/qr/%s" % (self.app.webui_url, self.app.my_id)
		io = Gio.file_new_for_uri(uri)
		io.load_contents_async(None, self.cb_syncthing_qr)
	
	def cb_btClose_clicked(self, *a):
		self.close()
	
	def cb_syncthing_qr(self, io, results):
		"""
		Called when QR code is loaded or operation fails. Image is then
		displayed in dialog, failure is silently ignored.
		"""
		try:
			ok, contents, etag = io.load_contents_finish(results)
			if ok:
				# QR is loaded, save it to temp file and let GTK to handle
				# rest
				tf = tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False)
				tf.write(contents)
				tf.close()
				self["vQR"].set_from_file(tf.name)
				os.unlink(tf.name)
		except Exception, e:
			return
		finally:
			del io


class EditorDialog(object):
	""" Universal handler for all Syncthing settings and editing """
	VALUES = {
		# Dict with lists of all editable values, indexed by editor mode
		"repo-edit" : ["vID", "vDirectory", "vReadOnly", "vIgnorePerms",
							"vVersioning", "vKeepVersions", "vNodes" ],
		"node-edit" : ["vNodeID", "vName", "vAddresses", "vCompression" ],
	}
	# Regexp to check if repository id is valid
	RE_REPO_ID = re.compile("^([a-zA-Z0-9\-\._]{1,64})$")
	# Invalid Value Messages.
	# Messages displayed when value in field is invalid
	IV_MESSAGES = {
		"vNodeID" : _("The entered node ID does not look valid. It "
			"should be a 52 character string consisting of letters and "
			"numbers, with spaces and dashes being optional."),
		"vID" : _("The repository ID must be a short identifier (64 "
			"characters or less) consisting of letters, numbers and "
			"the the dot (.), dash (-) and underscode (_) characters "
			"only"),
	}
	
	def __init__(self, app, mode, is_new, id=None):
		self.app = app
		self.mode = mode
		self.id = id
		self.is_new = is_new
		self.config = None
		self.values = None
		self.checks = {}
		self.valid_ids = []		# Used as cache for repository ID checking
		self.original_labels={}	# Stores original value while error message
								# is displayed on label.
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
			try:
				return self.values["Versioning"]["Params"]["keep"] # oww...
			except (KeyError, TypeError):
				# Node not found
				return 0
		elif key == "Versioning":
			# Boool
			try:
				return self.values["Versioning"]["Type"] != ""
			except (KeyError, TypeError):
				# Node not found
				return False
		elif key == "Addresses":
			return ",".join([ x.strip() for x in self.values["Addresses"]])
		elif key in self.values:
			return self.values[key]
		else:
			raise KeyError(key)
	
	def set_value(self, key, value):
		""" Stores value to configuration, handling some special cases """
		if key == "KeepVersions":
			# Create structure if needed
			self.create_dicts(self.values, ("Versioning", "Params", "keep"))
			self.values["Versioning"]["Params"]["keep"] = str(int(value))
		elif key == "Versioning":
			# Create structure if needed
			self.create_dicts(self.values, ("Versioning", "Type"))
			self.values["Versioning"]["Type"] = "simple" if value else ""
		elif key == "Addresses":
			self.values["Addresses"] = [ x.strip() for x in value.split(",") ]
		elif key in self.values:
			self.values[key] = value
		else:
			raise KeyError(key)	
	
	def create_dicts(self, parent, keys):
		"""
		Creates structure of nested dicts, if they are not in place already.
		"""
		if not type(keys) == list: keys = list(keys)
		if len(keys) == 0 : return	# Done
		key, rest = keys[0], keys[1:]
		if not key in parent :
			parent[key] = {}
		if parent[key] in ("", None ):
			parent[key] = {}
		self.create_dicts(parent[key], rest)
	
	def load_data(self):
		self.app.rest_request("config", self.cb_data_loaded, self.cb_data_failed)
	
	def display_error_message(self, value_id):
		""" Changes text on associated label to error message """
		wid = "lbl%s" % (value_id,) # widget id
		if value_id in self.original_labels:
			# Already done
			return
		if not value_id in self.IV_MESSAGES:
			# Nothing to show
			return
		self.original_labels[value_id] = self[wid].get_label()
		self[wid].set_markup('<span color="red">%s</span>' % (self.IV_MESSAGES[value_id],))
	
	def hide_error_message(self, value_id):
		""" Changes text on associated label back to normal text """
		wid = "lbl%s" % (value_id,) # widget id
		if value_id in self.original_labels:
			self[wid].set_label(self.original_labels[value_id])
			del self.original_labels[value_id]
	
	def cb_data_loaded(self, config):
		self.config = config
		try:
			if self.is_new:
				self.values = { x.lstrip("v") : "" for x in self.VALUES[self.mode] }
				if self.mode == "repo-edit":
					self.checks = {
						"vID" : self.check_repo_id,
						"vDirectory" : self.check_path
						}
				elif self.mode == "node-edit":
					self.set_value("Addresses", "dynamic")
					self.set_value("Compression", True)
					self.checks = {
						"vNodeID" : self.check_node_id,
						}
			else:
				if self.mode == "repo-edit":
					self.values = [ x for x in self.config["Repositories"] if x["ID"] == self.id ][0]
					self.checks = {
						"vDirectory" : self.check_path
						}
				elif self.mode == "node-edit":
					self.values = [ x for x in self.config["Nodes"] if x["NodeID"] == self.id ][0]
				else:
					# Invalid mode. Shouldn't be possible
					self.close()
					return
		except KeyError:
			# ID not found in configuration. This is practicaly impossible,
			# so it's handled only by self-closing dialog.
			self.close()
			return
		# Iterate over all known configuration values and set UI elements using unholy method
		for key in self.VALUES[self.mode]:
			w = self.find_widget_by_id(key)
			if not key is None:
				if isinstance(w, Gtk.SpinButton):
					w.get_adjustment().set_value(int(self.get_value(key.lstrip("v"))))
				elif isinstance(w, Gtk.Entry):
					w.set_text(str(self.get_value(key.strip("v"))))
				elif isinstance(w, Gtk.CheckButton):
					w.set_active(self.get_value(key.strip("v")))
				elif key == "vNodes":
					# Very special case
					nids = [ n["NodeID"] for n in self.get_value("Nodes") ]
					for node in self.app.nodes.values():
						if node["id"] != self.app.my_id:
							b = Gtk.CheckButton(node.get_title(), False)
							b.set_tooltip_text(node["id"])
							self["vNodes"].pack_end(b, False, False, 0)
							b.set_active(node["id"] in nids)
					self["vNodes"].show_all()
				else:
					print w
		# Update special widgets
		if "vID" in self:
			self["vID"].set_sensitive(self.is_new)
		if "vNodeID" in self:
			self["vNodeID"].set_sensitive(self.is_new)
		if "vVersioning" in self:
			self.cb_vVersioning_toggled(self["vVersioning"])

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
	
	def cb_vVersioning_toggled(self, cb, *a):
		self["rvVersioning"].set_reveal_child(cb.get_active())
	
	def cb_btClose_clicked(self, *a):
		self.close()
	
	def cb_check_value(self, *a):
		self["btSave"].set_sensitive(True)
		for x in self.checks:
			value = self[x].get_text().strip()
			if len(value) == 0:
				# Empty value in field
				self["btSave"].set_sensitive(False)
				self.hide_error_message(x)
			elif not self.checks[x](value):
				# Invalid value in any field
				self["btSave"].set_sensitive(False)
				self.display_error_message(x)
			else:
				self.hide_error_message(x)
	
	def cb_btSave_clicked(self, *a):
		# Saving data... Iterate over same values as load does and put
		# stuff back to self.values dict
		for key in self.VALUES[self.mode]:
			w = self.find_widget_by_id(key)
			if not key is None:
				if isinstance(w, Gtk.Entry):
					self.set_value(key.strip("v"), w.get_text())
				elif isinstance(w, Gtk.CheckButton):
					self.set_value(key.strip("v"), w.get_active())
				elif key == "vNodes":
					# Still very special case
					nodes = [ {
							   "Addresses" : None,
							   "NodeID" : b.get_tooltip_text(),
							   "Name" : "",
							   "CertName" : "",
							   "Compression" : False
								}
								for b in self["vNodes"].get_children()
								if b.get_active()
							]
					self.set_value("Nodes", nodes)
		# Add new dict to configuration (edited dict is already there)
		if self.is_new:
			if self.mode == "repo-edit":
				self.config["Repositories"].append(self.values)
			elif self.mode == "node-edit":
				self.config["Nodes"].append(self.values)
		# Post configuration back to daemon
		self["editor"].set_sensitive(False)
		self.post_config()
	
	def check_node_id(self, value):
		return check_node_id(value)
	
	def check_repo_id(self, value):
		return not self.RE_REPO_ID.match(value) is None
	
	def check_path(self, value):
		# Any non-empty path is OK
		return True
	
	def post_config(self):
		""" Posts edited configuration back to daemon """
		self.app.rest_post("config", self.config, self.syncthing_cb_post_config, self.syncthing_cb_post_error)
	
	def syncthing_cb_post_config(self, *a):
		# No return value for this call, let's hope for the best
		print "Configuration (probably) saved"
		self["editor"].set_sensitive(True)
		self.app.config_updated()
		self.close()
	
	def syncthing_cb_post_error(self, *a):
		# TODO: Unified error message
		d = Gtk.MessageDialog(
			self["editor"],
			Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
			Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE,
			_("Failed to save configuration."))
		d.run()
		d.hide()
		d.destroy()
		self["editor"].set_sensitive(True)

def luhn_b32generate(s):
	"""
	Returns a check digit for the string s which should be composed of
	characters from LUHN_ALPHABET
	"""
	factor, sum, n = 1, 0, len(LUHN_ALPHABET)
	for c in s:
		try:
			codepoint = LUHN_ALPHABET.index(c)
		except ValueError:
			raise ValueError("Digit %s is not valid" % (c,))
		addend = factor * codepoint
		factor = 1 if factor == 2 else 2
		addend = (addend / n) + (addend % n)
		sum += addend
	remainder = sum % n
	checkcodepoint = (n - remainder) % n
	return LUHN_ALPHABET[checkcodepoint]

def check_node_id(nid):
	""" Returns True if node id is valid """
	# Based on nodeid.go
	nid = nid.strip("== \t").upper() \
		.replace("0", "O") \
		.replace("1", "I") \
		.replace("8", "B") \
		.replace("-", "") \
		.replace(" ", "")
	if len(nid) == 56:
		for i in xrange(0, 4):
			p = nid[i*14:((i+1)*14)-1]
			try:
				l = luhn_b32generate(p)
			except Exception, e:
				print e
				return False
			g = "%s%s" % (p, l)
			if g != nid[i*14:(i+1)*14]:
				return False
		return True
	elif len(nid) == 52:
		try:
			b32decode("%s====" % (nid,))
			return True
		except Exception:
			return False
	else:
		# Wrong length
		return False

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
