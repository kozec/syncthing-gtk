#!/usr/bin/env python2
"""
Syncthing-GTK - DeviceEditorDialog

Universal dialog handler for all Syncthing settings and editing
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk
from syncthing_gtk.tools import check_device_id
from syncthing_gtk import EditorDialog
import sys
_ = lambda (a) : a

COLOR_NEW				= "#A0A0A0"
VALUES = [ "vDeviceID", "vName", "vAddresses", "vCompression",
	"vFolders", "vIntroducer"
	]

class DeviceEditorDialog(EditorDialog):
	MESSAGES = {
		# Displayed when device id is invalid
		"vDeviceID" : _("The entered device ID does not look valid. It "
			"should be a 52 character string consisting of letters and "
			"numbers, with spaces and dashes being optional."),
	}
	
	def __init__(self, app, is_new, id=None):
		EditorDialog.__init__(self, app,
			"device-edit.glade",
			"New Device" if is_new else "Edit Device"
			)
		self.id = id
		self.is_new = is_new
	
	#@Overrides
	def get_value(self, key):
		if key == "Addresses":
			return ",".join([ x.strip() for x in self.values[key]])
		else:
			return EditorDialog.get_value(self, key)
	
	#@Overrides
	def set_value(self, key, value):
		if key == "Addresses":
			self.values[key] = [ x.strip() for x in value.split(",") ]
		else:
			return EditorDialog.set_value(self, key, value)
	
	#@Overrides
	def on_data_loaded(self):
		try:
			if self.is_new:
				self.values = { x.lstrip("v") : "" for x in VALUES }
				self.set_value("Addresses", "dynamic")
				self.set_value("Compression", True)
				self.checks = {
					"vDeviceID" : check_device_id,
					}
				if self.id != None:
					# Pre-fill device id, if provided
					self.set_value("DeviceID", self.id)
			else:
				self.values = [ x for x in self.config["Devices"] if x["DeviceID"] == self.id ][0]
		except KeyError:
			# ID not found in configuration. This is practicaly impossible,
			# so it's handled only by self-closing dialog.
			print >>sys.stderr, e
			self.close()
			return
		return self.display_values(VALUES)
	
	#@Overrides
	def display_value(self, key, w):
		if key == "vFolders":
			# Even more special case
			rids = [ ]
			# Get list of folders that share this device
			for r in self.config["Folders"]:
				for n in r["Devices"]:
					if n["DeviceID"] == self.id:
						rids.append(r["ID"])
			# Create CheckButtons
			for folder in reversed(sorted(self.app.folders.values(), key=lambda x : x["id"])):
				b = Gtk.CheckButton(folder["path"], False)
				b.set_tooltip_text(folder["id"])
				self["vFolders"].pack_end(b, False, False, 0)
				b.set_active(folder["id"] in rids)
			self["vFolders"].show_all()
		else:
			EditorDialog.display_value(self, key, w)
	
	#@Overrides
	def update_special_widgets(self, *a):
		self["vDeviceID"].set_sensitive(self.is_new)
		self["vAddresses"].set_sensitive(self.id != self.app.daemon.get_my_id())
	
	#@Overrides
	def on_save_reuqested(self):
		self.store_values(VALUES)
		if self.is_new:
			# Add new dict to configuration (edited dict is already there)
			self.config["Devices"].append(self.values)
		# Post configuration back to daemon
		self.post_config()
	
	#@Overrides
	def store_value(self, key, w):
		if key == "vFolders":	# And this one is special too
			# Generate dict of { folder_id : bool } where bool is True if
			# folder should be shared with this device
			folders = {}
			for b in self["vFolders"].get_children():
				folders[b.get_tooltip_text()] = b.get_active()
			# Go over all Folders/<folder>/Devices/<device> keys in config
			# and set them as needed
			nid = self.get_value("DeviceID")
			for r in self.config["Folders"]:
				rid = r["ID"]
				found = False
				for n in r["Devices"]:
					if n["DeviceID"] == nid:
						if not rid in folders or not folders[rid]:
							# Remove this /<device> key (unshare folder with device)
							r["Devices"].remove(n)
							break
						found = True
				if (not found) and (rid in folders) and folders[rid]:
					# Add new /<device> key (share folder with device)
					r["Devices"].append({
					   "Addresses" : None,
					   "DeviceID" : nid,
					   "Name" : "",
					   "CertName" : "",
					   "Compression" : False
						})
		else:
			EditorDialog.store_value(self, key, w)
	
	#@Overrides
	def on_saved(self):
		self.close()
		# If new folder/device was added, show dummy item UI, so user will
		# see that something happen even before daemon gets restarted
		if self.is_new:
			box = self.app.show_device(self.get_value("DeviceID"), self.get_value("Name"),
				self.get_value("Compression"), self.get_value("Introducer"))
			box.set_color_hex(COLOR_NEW)
