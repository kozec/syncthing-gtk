#!/usr/bin/env python2
"""
Syncthing-GTK - EditorDialog

Universal dialog handler for all Syncthing settings and editing
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, Gio, GLib, GObject, Pango
from syncthing_gtk.tools import check_node_id, ints
import os, re
_ = lambda (a) : a

COLOR_NEW				= "#A0A0A0"

class EditorDialog(GObject.GObject):
	"""
	Universal dialog handler for all Syncthing settings and editing
	
	Signals:
		close()
			emitted after dialog is closed
		loaded()
			Emitted after dialog loads and parses configurationdata
	"""
	__gsignals__ = {
			b"close"	: (GObject.SIGNAL_RUN_FIRST, None, ()),
			b"loaded"	: (GObject.SIGNAL_RUN_FIRST, None, ()),
		}
	
	VALUES = {
		# Dict with lists of all editable values, indexed by editor mode
		"repo-edit" : [
			"vID", "vDirectory", "vReadOnly", "vIgnorePerms", "vNodes",
			"vVersioning", "vKeepVersions", "vRescanIntervalS",
			"vMaxAge", "vVersionsPath"
			],
		"node-edit" : [
			"vNodeID", "vName", "vAddresses", "vCompression"
			],
		"daemon-settings" : [
			"vListenAddress", "vLocalAnnEnabled", "vUPnPEnabled",
			"vStartBrowser", "vMaxSendKbpsEnabled", "vMaxSendKbps",
			"vURAccepted", "vLocalAnnPort", "vGlobalAnnEnabled",
			"vGlobalAnnServer"
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
		"vID" : _("The repository ID must be a short, unique identifier"
			" (64 characters or less) consisting of letters, numbers "
			"and the the dot (.), dash (-) and underscode (_) "
			"characters only"),
	}
	
	def __init__(self, app, mode, is_new, id=None):
		GObject.GObject.__init__(self)
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
	
	def load(self):
		""" Loads configuration data and pre-fills values to fields """
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
		self["editor"].set_modal(True)
		self["editor"].show_all()
	
	def close(self):
		self.emit("close")
		self["editor"].hide()
		self["editor"].destroy()
	
	def setup_widgets(self):
		# Load glade file
		self.builder = Gtk.Builder()
		self.builder.add_from_file(os.path.join(self.app.gladepath, "%s.glade" % self.mode))
		self.builder.connect_signals(self)
		# Set title stored in glade file in "Edit Title|Save Title" format
		if "|" in self["editor"].get_title():
			self["editor"].set_title(self["editor"].get_title().split("|")[ 1 if self.is_new else 0 ])
		# Disable everything until configuration is loaded
		self["editor"].set_sensitive(False)
	
	def get_burried_value(self, key, vals, default, convert=lambda a:a):
		"""
		Returns value stored deeper in element tree.
		Method is called recursively for every tree level. If value is
		not found, default is returned.
		"""
		if type(key) != list:
			# Parse key, split by '/'
			return self.get_burried_value(key.split("/"), vals, default, convert)
		try:
			if len(key) > 1:
				tkey, key = key[0], key[1:]
				return self.get_burried_value(key, vals[tkey], default, convert)
			return convert(vals[key[0]])
		except Exception:
			return default
	
	def get_value(self, key):
		"""
		Returns value from configuration.
		Usualy returns self.values[key], but can handle some special cases
		"""
		if key == "KeepVersions":
			return self.get_burried_value("Versioning/Params/keep", self.values, 0, int)
		elif key == "MaxAge":
			return self.get_burried_value("Versioning/Params/maxAge", self.values, 0, int) / 86400 # seconds to days
		elif key == "VersionsPath":
			return self.get_burried_value("Versioning/Params/versionsPath", self.values, "")
		elif key == "Versioning":
			return self.get_burried_value("Versioning/Type", self.values, "")
		elif key in ("Addresses", "ListenAddress"):
			return ",".join([ x.strip() for x in self.values[key]])
		elif key == "MaxSendKbpsEnabled":
			return (self.values["MaxSendKbps"] != 0)
		elif key in self.values:
			return self.values[key]
		else:
			print self.values
			raise KeyError(key)
	
	def set_value(self, key, value):
		""" Stores value to configuration, handling some special cases """
		if key == "Versioning":
			# Create structure if needed
			self.create_dicts(self.values, ("Versioning", "Type"))
			self.values["Versioning"]["Type"] = value
		elif key == "KeepVersions":
			# Create structure if needed
			self.create_dicts(self.values, ("Versioning", "Params", "keep"))
			self.values["Versioning"]["Params"]["keep"] = str(int(value))
		elif key == "MaxAge":
			# Create structure if needed
			self.create_dicts(self.values, ("Versioning", "Params", "maxAge"))
			self.values["Versioning"]["Params"]["maxAge"] = str(int(value) * 86400) # days to seconds
		elif key == "VersionsPath":
			# Create structure if needed
			self.create_dicts(self.values, ("Versioning", "Params", "versionsPath"))
			self.values["Versioning"]["Params"]["versionsPath"] = value
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
					if self.id != None:
						try:
							v = [ x for x in self.config["Repositories"] if x["ID"] == self.id ][0]
							self.values = v
							self.is_new = False
						except IndexError:
							pass
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
				elif isinstance(w, Gtk.ComboBox):
					val = self.get_value(key.lstrip("v"))
					m = w.get_model()
					for i in xrange(0, len(m)):
						if val == str(m[i][0]).strip():
							w.set_active(i)
							break
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
		# Brag
		self.emit("loaded")
	
	def ui_value_changed(self, w, *a):
		"""
		Handler for widget that controls state of other widgets
		"""
		key = self.get_widget_id(w)
		if key != None:
			if isinstance(w, Gtk.CheckButton):
				self.set_value(key.lstrip("v"), w.get_active())
				self.update_special_widgets()
			if isinstance(w, Gtk.ComboBox):
				self.set_value(key.strip("v"), str(w.get_model()[w.get_active()][0]).strip())
				self.update_special_widgets()
	
	def update_special_widgets(self, *a):
		""" Enables/disables some widgets """
		if self.mode == "repo-edit":
			self["vID"].set_sensitive(self.id is None)
			v = self.get_value("Versioning")
			if v == "":
				if self["rvVersioning"].get_reveal_child():
					self["rvVersioning"].set_reveal_child(False)
			else:
				self["bxVersioningSimple"].set_visible(self.get_value("Versioning") == "simple")
				self["bxVersioningStaggered"].set_visible(self.get_value("Versioning") == "staggered")
				if not self["rvVersioning"].get_reveal_child():
					self["rvVersioning"].set_reveal_child(True)
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
				elif isinstance(w, Gtk.ComboBox):
					self.set_value(key.strip("v"), str(w.get_model()[w.get_active()][0]).strip())
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
	
	def cb_format_value_s(self, spinner):
		""" Formats spinner value  """
		spinner.get_buffer().set_text(_("%ss") % (int(spinner.get_adjustment().get_value()),), -1);
		return True
	
	def cb_format_value_days(self, spinner):
		""" Formats spinner value  """
		v = int(spinner.get_adjustment().get_value())
		if v == 0:
			spinner.get_buffer().set_text(_("never delete"), -1)
		elif v == 1:
			spinner.get_buffer().set_text(_("%s day") % (v,), -1);
		else:
			spinner.get_buffer().set_text(_("%s days") % (v,), -1);
		return True
	
	def check_repo_id(self, value):
		if value in self.app.repos:
			# Duplicate repo id
			return False
		if self.RE_REPO_ID.match(value) is None:
			# Invalid string
			return False
		return True
	
	def check_path(self, value):
		# Any non-empty path is OK
		return True
	
	def post_config(self):
		""" Posts edited configuration back to daemon """
		self.app.daemon.write_config(self.config, self.syncthing_cb_post_config, self.syncthing_cb_post_error)
	
	def syncthing_cb_post_config(self, *a):
		# No return value for this call, let's hope for the best
		print "Configuration (probably) saved"
		# Close editor
		self["editor"].set_sensitive(True)
		self.close()
		# If new repo/node was added, show dummy item UI, so user will
		# see that something happen even before daemon gets restarted
		if self.is_new:
			box = None
			if self.mode == "repo-edit":
				box = self.app.show_repo(
					self.get_value("ID"), self.get_value("Directory"), self.get_value("Directory"),
					self.get_value("ReadOnly"), self.get_value("IgnorePerms"),
					self.get_value("RescanIntervalS"),
					sorted(
						[ self.app.nodes[n["NodeID"]] for n in self.get_value("Nodes") ],
						key=lambda x : x.get_title().lower()
					))
			elif self.mode == "node-edit":
				box = self.app.show_node(self.get_value("NodeID"), self.get_value("Name"),
					self.get_value("Compression"))
			# Gray background for new stuff
			if not box is None:
				box.set_color_hex(COLOR_NEW)
	
	def syncthing_cb_post_error(self, *a):
		# TODO: Unified error message
		print a
		d = Gtk.MessageDialog(
			self["editor"],
			Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
			Gtk.MessageType.INFO, Gtk.ButtonsType.CLOSE,
			_("Failed to save configuration."))
		d.run()
		d.hide()
		d.destroy()
		self["editor"].set_sensitive(True)
	
	def call_after_loaded(self, callback, *data):
		""" Calls callback whem 'loaded' event is emited """
		self.connect("loaded",
			# lambda bellow throws 'event_source' argument and
			# calls callback with rest of arguments
			lambda obj, callback, *a : callback(*a),
			callback, *data
			)
	
	def fill_repo_id(self, rid):
		""" Pre-fills repository Id for new-repo dialog """
		self["vID"].set_text(rid)
		self.id = rid
		self.update_special_widgets()
	
	def mark_node(self, nid):
		""" Marks (checks) checkbox for specified node """
		if "vNodes" in self:	# ... only if there are checkboxes here
			for child in self["vNodes"].get_children():
				if child.get_tooltip_text() == nid:
					l = child.get_children()[0]	# Label in checkbox
					l.set_markup("<b>%s</b>" % (l.get_label()))
					child.set_active(True)
