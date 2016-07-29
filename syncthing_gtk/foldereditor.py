#!/usr/bin/env python2
"""
Syncthing-GTK - FolderEditorDialog

Universal dialog handler for all Syncthing settings and editing
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk
from syncthing_gtk.tools import _ # gettext function
from syncthing_gtk.tools import generate_folder_id
from syncthing_gtk.editordialog import EditorDialog, strip_v
from syncthing_gtk import EditorDialog, Watcher
import os, sys, re, logging
log = logging.getLogger("FolderEditor")

COLOR_NEW				= "#A0A0A0"
# Regexp to generate folder id from filename
RE_GEN_ID = re.compile("([a-zA-Z0-9\-\._]{1,64}).*")
VALUES = [ "vlabel", "vid", "vpath", "vreadOnly", "vignorePerms", "vdevices",
	"vversioning", "vkeepVersions", "vrescanIntervalS", "vmaxAge",
	"vversionsPath", "vinotify", "vcleanoutDays", "vcommand", "vorder",
	"vminDiskFreePct"
	]
VERSIONING_TYPES = set(['simple', 'staggered', 'trashcan', 'external'])

class FolderEditorDialog(EditorDialog):
	def __init__(self, app, is_new, id=None, path=None):
		EditorDialog.__init__(self, app,
			"folder-edit.glade",
			"New Shared Folder" if is_new else "Edit Shared Folder"
			)
		self.id = id
		self.path = path
		self.is_new = is_new
	
	def on_btBrowse_clicked(self, *a):
		"""
		Display folder browser dialog to browse for folder... folder.
		Oh god, this new terminology sucks...
		"""
		if not self.is_new: return
		# Prepare dialog
		d = Gtk.FileChooserDialog(
			_("Select Folder for new Folder"),	# fuck me...
			self["editor"],
			Gtk.FileChooserAction.SELECT_FOLDER,
			(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
			Gtk.STOCK_OK, Gtk.ResponseType.OK))
		# Set default path to home directory
		d.set_current_folder(os.path.expanduser("~"))
		# Get response
		if d.run() == Gtk.ResponseType.OK:
			self["vpath"].set_text(d.get_filename())
			if len(self["vid"].get_text().strip()) == 0:
				# ID is empty, fill it with last path element
				try:
					lpl = os.path.split(d.get_filename())[-1]
					id = RE_GEN_ID.search(lpl).group(0).lower()
					self["vid"].set_text(id)
				except AttributeError:
					# Can't regexp anything
					pass
		d.destroy()
	
	def on_vid_icon_press(self, *a):
		if self["vid"].get_sensitive():
			self["vid"].set_text(generate_folder_id())
	
	#@Overrides
	def get_value(self, key):
		if key == "keepVersions":
			return self.get_burried_value("versioning/params/keep", self.values, 0, int)
		elif key == "maxAge":
			return self.get_burried_value("versioning/params/maxAge", self.values, 0, int) / 86400 # seconds to days
		elif key == "cleanoutDays":
			return self.get_burried_value("versioning/params/cleanoutDays", self.values, 0, int)
		elif key == "command":
			return self.get_burried_value("versioning/params/command", self.values, "")
		elif key == "versionsPath":
			return self.get_burried_value("versioning/params/versionsPath", self.values, "")
		elif key == "readOnly":
			return self.get_burried_value("type", self.values, "") == "readonly"
		elif key == "versioning":
			return self.get_burried_value("versioning/type", self.values, "")
		elif key == "inotify":
			return self.id in self.app.config["use_inotify"]
		else:
			return EditorDialog.get_value(self, key)
	
	#@Overrides
	def set_value(self, key, value):
		if key == "versioning":
			# Create structure if needed
			self.create_dicts(self.values, ("versioning", "type"))
			self.values["versioning"]["type"] = value
		elif key == "keepVersions":
			# Create structure if needed
			self.create_dicts(self.values, ("versioning", "params", "keep"))
			self.values["versioning"]["params"]["keep"] = str(int(value))
		elif key == "cleanoutDays":
			# Create structure if needed
			self.create_dicts(self.values, ("versioning", "params", "cleanoutDays"))
			self.values["versioning"]["params"]["cleanoutDays"] = str(int(value))
		elif key == "maxAge":
			# Create structure if needed
			self.create_dicts(self.values, ("versioning", "params", "maxAge"))
			self.values["versioning"]["params"]["maxAge"] = str(int(value) * 86400) # days to seconds
		elif key == "command":
			# Create structure if needed
			self.create_dicts(self.values, ("versioning", "params", "command"))
			self.values["versioning"]["params"]["command"] = value
		elif key == "versionsPath":
			# Create structure if needed
			self.create_dicts(self.values, ("versioning", "params", "versionsPath"))
			self.values["versioning"]["params"]["versionsPath"] = value
		elif key == "readOnly":
			self.values["type"] = "readonly" if value else "readwrite"
		elif key == "inotify":
			id = self.id
			if id is None:
				# Happens when saving new folder
				id = self["vid"].get_text().strip()
			l = self.app.config["use_inotify"]
			if value:
				if not id in l:
					l.append(id)
			else:
				while id in l:
					l.remove(id)
			self.app.config["use_inotify"] = l
		else:
			EditorDialog.set_value(self, key, value)
	
	#@Overrides
	def on_data_loaded(self):
		try:
			if self.is_new:
				self.values = { strip_v(x) : "" for x in VALUES }
				self.checks = {
					"vid" : self.check_folder_id,
					"vpath" : self.check_path,
					"vcommand" : self.check_command,
				}
				if self.id != None:
					try:
						v = [ x for x in self.config["folders"] if x["id"] == self.id ][0]
						self.values = v
						self.is_new = False
					except IndexError:
						pass
				if not self.path is None:
					self.set_value("path", self.path)
					self["vpath"].set_sensitive(False)
				self.set_value("versioning", "simple")
				self.set_value("rescanIntervalS", 30)
				self.set_value("keepVersions", 10)
			else:
				self.values = [ x for x in self.config["folders"] if x["id"] == self.id ][0]
				self.checks = {
					"vcommand" : self.check_command,
				}
				self["vpath"].set_sensitive(False)
				self["btBrowse"].set_sensitive(False)
		except KeyError, e:
			# ID not found in configuration. This is practicaly impossible,
			# so it's handled only by self-closing dialog.
			log.exception(e)
			self.close()
			return False
		if Watcher is None:
			self["vinotify"].set_sensitive(False)
			self["lblinotify"].set_sensitive(False)
			self["vinotify"].set_tooltip_text(_("Please, install pyinotify package to use this feature"))
			self["lblinotify"].set_tooltip_text(_("Please, install pyinotify package to use this feature"))
		return self.display_values(VALUES)
	
	#@Overrides
	def display_value(self, key, w):
		if key == "vdevices":
			# Very special case
			nids = [ n["deviceID"] for n in self.get_value("devices") ]
			for device in self.app.devices.values():
				if device["id"] != self.app.daemon.get_my_id():
					b = Gtk.CheckButton(device.get_title(), False)
					b.set_tooltip_text(device["id"])
					self["vdevices"].pack_end(b, False, False, 0)
					b.set_active(device["id"] in nids)
			self["vdevices"].show_all()
		else:
			EditorDialog.display_value(self, key, w)
	
	#@Overrides
	def update_special_widgets(self, *a):
		self["vid"].set_sensitive(self.id is None)
		v = self.get_value("versioning")
		if v == "":
			if self["rvversioning"].get_reveal_child():
				self["rvversioning"].set_reveal_child(False)
		else:
			for x in VERSIONING_TYPES:
				self["bxVersioning_" + x].set_visible(self.get_value("versioning") == x)
			if not self["rvversioning"].get_reveal_child():
				self["rvversioning"].set_reveal_child(True)
	
	#@Overrides
	def on_save_reuqested(self):
		self.store_values(VALUES)
		print self.values
		if self.is_new:
			# Add new dict to configuration (edited dict is already there)
			self.config["folders"].append(self.values)
		# Post configuration back to daemon
		self.post_config()
	
	#@Overrides
	def store_value(self, key, w):
		if key == "vdevices":	# Still very special case
			devices = [ {
						"deviceID" : b.get_tooltip_text(),
						} for b in self["vdevices"].get_children()
						if b.get_active()
					]
			self.set_value("devices", devices)
		else:
			EditorDialog.store_value(self, key, w)
	
	#@Overrides
	def on_saved(self):
		self.close()
		# If new folder/device was added, show dummy item UI, so user will
		# see that something happen even before daemon gets restarted
		if self.is_new:
			box = self.app.show_folder(
				self.get_value("id"), self.get_value("label"), self.get_value("path"),
				self.get_value("readOnly"), self.get_value("ignorePerms"),
				self.get_value("rescanIntervalS"),
				sorted(
					[ self.app.devices[n["deviceID"]] for n in self.get_value("devices") ],
					key=lambda x : x.get_title().lower()
				))
			box.set_color_hex(COLOR_NEW)
	
	#@Overrides
	def ui_value_changed(self, w, *a):
		EditorDialog.ui_value_changed(self, w, *a)
		self.cb_check_value(w, *a)
	
	def check_folder_id(self, value):
		if len(value.strip()) == 0:
			# Empty value
			return False
		if value in self.app.folders:
			# Duplicate folder id
			return False
		return True
	
	def check_path(self, value):
		# Any non-empty path is OK
		return len(value.strip()) > 0
	
	def check_command(self, value):
		# Any non-empty command is OK
		return self.get_value("versioning") != "external" or len(value.strip()) > 0
	
	def fill_folder_id(self, rid, readonly=True):
		""" Pre-fills folder Id for new-folder dialog """
		self["vid"].set_text(rid)
		self.id = rid
		self.update_special_widgets()
		self["vid"].set_sensitive(not readonly)
	
	def mark_device(self, nid):
		""" Marks (checks) checkbox for specified device """
		if "vdevices" in self:	# ... only if there are checkboxes here
			for child in self["vdevices"].get_children():
				if child.get_tooltip_text() == nid:
					l = child.get_children()[0]	# Label in checkbox
					l.set_markup("<b>%s</b>" % (l.get_label()))
					child.set_active(True)
