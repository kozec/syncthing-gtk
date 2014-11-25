#!/usr/bin/env python2
"""
Syncthing-GTK - FolderEditorDialog

Universal dialog handler for all Syncthing settings and editing
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk
from syncthing_gtk.tools import check_device_id
from syncthing_gtk import EditorDialog, HAS_INOTIFY
import os, sys, re
_ = lambda (a) : a

COLOR_NEW				= "#A0A0A0"
# Regexp to check if folder id is valid
RE_FOLDER_ID = re.compile("^([a-zA-Z0-9\-\._]{1,64})$")
# Regexp to generate folder id from filename
RE_GEN_ID = re.compile("([a-zA-Z0-9\-\._]{1,64}).*")
VALUES = [ "vID", "vPath", "vReadOnly", "vIgnorePerms", "vDevices",
	"vVersioning", "vKeepVersions", "vRescanIntervalS", "vMaxAge",
	"vVersionsPath", "vINotify"
	]

class FolderEditorDialog(EditorDialog):
	MESSAGES = {
		# Displayed when folder id is invalid
		"vID" : _("The Folder ID must be a short, unique identifier"
			" (64 characters or less) consisting of letters, numbers "
			"and the the dot (.), dash (-) and underscode (_) "
			"characters only"),
	}
	
	def __init__(self, app, is_new, id=None):
		EditorDialog.__init__(self, app,
			"folder-edit.glade",
			"New Shared Folder" if is_new else "Edit Shared Folder"
			)
		self.id = id
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
			self["vPath"].set_text(d.get_filename())
			if len(self["vID"].get_text().strip()) == 0:
				# ID is empty, fill it with last path element
				try:
					lpl = os.path.split(d.get_filename())[-1]
					id = RE_GEN_ID.search(lpl).group(0).lower()
					self["vID"].set_text(id)
				except AttributeError:
					# Can't regexp anything
					pass
		d.destroy()
	
	#@Overrides
	def get_value(self, key):
		if key == "KeepVersions":
			return self.get_burried_value("Versioning/Params/keep", self.values, 0, int)
		elif key == "MaxAge":
			return self.get_burried_value("Versioning/Params/maxAge", self.values, 0, int) / 86400 # seconds to days
		elif key == "VersionsPath":
			return self.get_burried_value("Versioning/Params/versionsPath", self.values, "")
		elif key == "Versioning":
			return self.get_burried_value("Versioning/Type", self.values, "")
		elif key == "INotify":
			return self.id in self.app.config["use_inotify"]
		else:
			return EditorDialog.get_value(self, key)
	
	#@Overrides
	def set_value(self, key, value):
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
		elif key == "INotify":
			l = self.app.config["use_inotify"]
			if value:
				if not self.id in l:
					l.append(self.id)
			else:
				while self.id in l:
					l.remove(self.id)
			self.app.config["use_inotify"] = l
		else:
			EditorDialog.set_value(self, key, value)
	
	#@Overrides
	def on_data_loaded(self):
		try:
			if self.is_new:
				self.values = { x.lstrip("v") : "" for x in VALUES }
				self.checks = {
					"vID" : self.check_folder_id,
					"vPath" : self.check_path
					}
				if self.id != None:
					try:
						v = [ x for x in self.config["Folders"] if x["ID"] == self.id ][0]
						self.values = v
						self.is_new = False
					except IndexError:
						pass
				self.set_value("Versioning", "simple")
				self.set_value("RescanIntervalS", 30)
				self.set_value("KeepVersions", 10)
			else:
				self.values = [ x for x in self.config["Folders"] if x["ID"] == self.id ][0]
				self.checks = {}
				self["vPath"].set_sensitive(False)
				self["btBrowse"].set_sensitive(False)
		except KeyError, e:
			# ID not found in configuration. This is practicaly impossible,
			# so it's handled only by self-closing dialog.
			print >>sys.stderr, e
			self.close()
			return False
		if not HAS_INOTIFY:
			self["vINotify"].set_sensitive(False)
			self["lblINotify"].set_sensitive(False)
			self["vINotify"].set_tooltip_text(_("Please, install pyinotify package to use this feature"))
			self["lblINotify"].set_tooltip_text(_("Please, install pyinotify package to use this feature"))
		return self.display_values(VALUES)
	
	#@Overrides
	def display_value(self, key, w):
		if key == "vDevices":
			# Very special case
			nids = [ n["DeviceID"] for n in self.get_value("Devices") ]
			for device in self.app.devices.values():
				if device["id"] != self.app.daemon.get_my_id():
					b = Gtk.CheckButton(device.get_title(), False)
					b.set_tooltip_text(device["id"])
					self["vDevices"].pack_end(b, False, False, 0)
					b.set_active(device["id"] in nids)
			self["vDevices"].show_all()
		else:
			EditorDialog.display_value(self, key, w)
	
	#@Overrides
	def update_special_widgets(self, *a):
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
	
	#@Overrides
	def on_save_reuqested(self):
		self.store_values(VALUES)
		if self.is_new:
			# Add new dict to configuration (edited dict is already there)
			self.config["Folders"].append(self.values)
		# Post configuration back to daemon
		self.post_config()
	
	#@Overrides
	def store_value(self, key, w):
		if key == "vDevices":	# Still very special case
			devices = [ {
					   "Addresses" : None,
					   "DeviceID" : b.get_tooltip_text(),
					   "Name" : "",
					   "CertName" : "",
					   "Compression" : False
						}
						for b in self["vDevices"].get_children()
						if b.get_active()
					]
			self.set_value("Devices", devices)
		else:
			EditorDialog.store_value(self, key, w)
	
	#@Overrides
	def on_saved(self):
		self.close()
		# If new folder/device was added, show dummy item UI, so user will
		# see that something happen even before daemon gets restarted
		if self.is_new:
			box = self.app.show_folder(
				self.get_value("ID"), self.get_value("Path"), self.get_value("Path"),
				self.get_value("ReadOnly"), self.get_value("IgnorePerms"),
				self.get_value("RescanIntervalS"),
				sorted(
					[ self.app.devices[n["DeviceID"]] for n in self.get_value("Devices") ],
					key=lambda x : x.get_title().lower()
				))
			box.set_color_hex(COLOR_NEW)
	
	def check_folder_id(self, value):
		if value in self.app.folders:
			# Duplicate folder id
			return False
		if RE_FOLDER_ID.match(value) is None:
			# Invalid string
			return False
		return True
	
	def check_path(self, value):
		# Any non-empty path is OK
		return True
	
	def fill_folder_id(self, rid):
		""" Pre-fills folder Id for new-folder dialog """
		self["vID"].set_text(rid)
		self.id = rid
		self.update_special_widgets()
	
	def mark_device(self, nid):
		""" Marks (checks) checkbox for specified device """
		if "vDevices" in self:	# ... only if there are checkboxes here
			for child in self["vDevices"].get_children():
				if child.get_tooltip_text() == nid:
					l = child.get_children()[0]	# Label in checkbox
					l.set_markup("<b>%s</b>" % (l.get_label()))
					child.set_active(True)
