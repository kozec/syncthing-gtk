#!/usr/bin/env python2
"""
Syncthing-GTK - EditorDialog

Universal dialog handler for all Syncthing settings and editing
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, Gio, GLib, Pango
from syncthing_gtk.tools import check_node_id, ints
import re
_ = lambda (a) : a

class EditorDialog(object):
	""" Universal dialog handler for all Syncthing settings and editing """
	VALUES = {
		# Dict with lists of all editable values, indexed by editor mode
		"repo-edit" : [
			"vID", "vDirectory", "vReadOnly", "vIgnorePerms", "vNodes",
			"vVersioning", "vKeepVersions"
			],
		"node-edit" : [
			"vNodeID", "vName", "vAddresses", "vCompression"
			],
		"daemon-settings" : [
			"vListenAddress", "vLocalAnnEnabled", "vUPnPEnabled",
			"vStartBrowser", "vMaxSendKbpsEnabled", "vMaxSendKbps",
			"vRescanIntervalS", "vURAccepted", "vLocalAnnPort",
			"vGlobalAnnEnabled", "vGlobalAnnServer"
			]
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
		# Stores original label  value while error message is displayed.
		self.original_labels={}
		# Used by get_widget_id
		self.widget_to_id = {}
		self.setup_widgets()
		self.load_data()
	
	def __getitem__(self, name):
		""" Convince method that allows widgets to be accessed via self["widget"] """
		return self.builder.get_object(name)
	
	def __contains__(self, name):
		""" Returns true if there is such widget """
		return self.builder.get_object(name) != None
	
	def get_widget_id(self, w):
		"""
		Returns glade file ID for specified widget or None, if widget
		is not known.
		"""
		if not w in self.widget_to_id:
			return None
		return self.widget_to_id[w]
	
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
		if "|" in self["editor"].get_title():
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
		elif key in ("Addresses", "ListenAddress"):
			return ",".join([ x.strip() for x in self.values[key]])
		elif key == "MaxSendKbpsEnabled":
			return (self.values["MaxSendKbps"] != 0)
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
		#elif key  in ("LocalAnnPort", "RescanIntervalS"):
		#	self.values[key] = ints(value)
		elif key == "URAccepted":
			self.values[key] = 1 if value else 0
		elif key in ("Addresses", "ListenAddress"):
			self.values[key] = [ x.strip() for x in value.split(",") ]
		elif key == "MaxSendKbpsEnabled":
			if value:
				if self.values["MaxSendKbps"] <= 0:
					self.values["MaxSendKbps"] = 1
			else:
				self.values["MaxSendKbps"] = 0
			self.find_widget_by_id("vMaxSendKbps").get_adjustment().set_value(self.values["MaxSendKbps"])
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
		self.app.daemon.read_config(self.cb_data_loaded, self.cb_data_failed)
	
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
						"vNodeID" : check_node_id,
						}
			else:
				if self.mode == "repo-edit":
					self.values = [ x for x in self.config["Repositories"] if x["ID"] == self.id ][0]
					self.checks = {
						"vDirectory" : self.check_path
						}
				elif self.mode == "node-edit":
					self.values = [ x for x in self.config["Nodes"] if x["NodeID"] == self.id ][0]
				elif self.mode == "daemon-settings":
					self.values = self.config["Options"]
					self.checks = {}
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
			self.widget_to_id[w] = key
			if not key is None:
				if isinstance(w, Gtk.SpinButton):
					w.get_adjustment().set_value(ints(self.get_value(key.lstrip("v"))))
				elif isinstance(w, Gtk.Entry):
					w.set_text(str(self.get_value(key.lstrip("v"))))
				elif isinstance(w, Gtk.CheckButton):
					w.set_active(self.get_value(key.lstrip("v")))
				elif key == "vNodes":
					# Very special case
					nids = [ n["NodeID"] for n in self.get_value("Nodes") ]
					for node in self.app.nodes.values():
						if node["id"] != self.app.daemon.get_my_id():
							b = Gtk.CheckButton(node.get_title(), False)
							b.set_tooltip_text(node["id"])
							self["vNodes"].pack_end(b, False, False, 0)
							b.set_active(node["id"] in nids)
					self["vNodes"].show_all()
				else:
					print w
		self.update_special_widgets()
		# Enable dialog
		self["editor"].set_sensitive(True)
	
	def ui_value_changed(self, w, *a):
		key = self.get_widget_id(w)
		if key != None:
			if isinstance(w, Gtk.CheckButton):
				self.set_value(key.lstrip("v"), w.get_active())
				self.update_special_widgets()
	
	def update_special_widgets(self, *a):
		""" Enables/disables some widgets """
		if self.mode == "repo-edit":
			self["vID"].set_sensitive(self.is_new)
			self["rvVersioning"].set_reveal_child(self.get_value("Versioning"))
		elif self.mode == "node-edit":
			self["vNodeID"].set_sensitive(self.is_new)
			self["vAddresses"].set_sensitive(self.id != self.app.daemon.get_my_id())
		elif self.mode == "daemon-settings":
			self["vMaxSendKbps"].set_sensitive(self.get_value("MaxSendKbpsEnabled"))
			self["lblvLocalAnnPort"].set_sensitive(self.get_value("LocalAnnEnabled"))
			self["vLocalAnnPort"].set_sensitive(self.get_value("LocalAnnEnabled"))
			self["lblvGlobalAnnServer"].set_sensitive(self.get_value("GlobalAnnEnabled"))
			self["vGlobalAnnServer"].set_sensitive(self.get_value("GlobalAnnEnabled"))

	
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
				if isinstance(w, Gtk.SpinButton):
					self.set_value(key.strip("v"), int(w.get_adjustment().get_value()))
				elif isinstance(w, Gtk.Entry):
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
		# Show some changes directly
		if self.mode == "node-edit" and self.id in self.app.nodes:
			name = self.values["Name"]
			node = self.app.nodes[self.id]
			if name in (None, ""):
				# Show first block from ID if name is unset
				name = self.id.split("-")[0]
			node.set_title(name)
			node.set_value("compress", _("Yes") if self.values["Compression"] else _("No"))
	
	def check_repo_id(self, value):
		return not self.RE_REPO_ID.match(value) is None
	
	def check_path(self, value):
		# Any non-empty path is OK
		return True
	
	def post_config(self):
		""" Posts edited configuration back to daemon """
		self.app.daemon.write_config(self.config, self.syncthing_cb_post_config, self.syncthing_cb_post_error)
	
	def syncthing_cb_post_config(self, *a):
		# No return value for this call, let's hope for the best
		print "Configuration (probably) saved"
		self["editor"].set_sensitive(True)
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

