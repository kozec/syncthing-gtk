#!/usr/bin/env python2
"""
Syncthing-GTK - DeviceEditorDialog

Universal dialog handler for all Syncthing settings and editing
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk
from syncthing_gtk.tools import check_device_id
from syncthing_gtk.tools import _ # gettext function
from syncthing_gtk.editordialog import EditorDialog, strip_v
import sys, logging
log = logging.getLogger("DeviceEditor")

COLOR_NEW				= "#A0A0A0"
VALUES = [ "vdeviceID", "vname", "vaddresses", "vcompression",
	"vfolders", "vintroducer"
	]

class DeviceEditorDialog(EditorDialog):
	MESSAGES = {
		# Displayed when device id is invalid
		"vdeviceID" : _("The entered device ID does not look valid. It "
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
		if key == "addresses":
			return ",".join([ strip_v(x) for x in self.values[key]])
		elif key == "compression":
			val = EditorDialog.get_value(self, key)
			# For syncthing <= 0.10.25
			if val in (True, "true"):
				return "always"
			elif val in (False, "false"):
				return "never"
			else:
				return val
		else:
			return EditorDialog.get_value(self, key)
	
	#@Overrides
	def set_value(self, key, value):
		if key == "addresses":
			self.values[key] = [ strip_v(x) for x in value.split(",") ]
		else:
			return EditorDialog.set_value(self, key, value)
	
	#@Overrides
	def on_data_loaded(self):
		try:
			if self.is_new:
				self.values = { strip_v(x) : "" for x in VALUES }
				self.set_value("addresses", "dynamic")
				self.set_value("compression", "metadata")
				self.checks = {
					"vdeviceID" : check_device_id,
					}
				if self.id != None:
					# Pre-fill device id, if provided
					self.set_value("deviceID", self.id)
			else:
				self.values = [ x for x in self.config["devices"] if x["deviceID"] == self.id ][0]
		except KeyError, e:
			# ID not found in configuration. This is practicaly impossible,
			# so it's handled only by self-closing dialog.
			log.exception(e)
			self.close()
			return
		return self.display_values(VALUES)
	
	#@Overrides
	def display_value(self, key, w):
		if key == "vfolders":
			# Even more special case
			rids = [ ]
			# Get list of folders that share this device
			for r in self.config["folders"]:
				for n in r["devices"]:
					if n["deviceID"] == self.id:
						rids.append(r["id"])
			# Create CheckButtons
			for folder in reversed(sorted(self.app.folders.values(), key=lambda x : x["id"])):
				b = Gtk.CheckButton(folder["path"], False)
				b.set_tooltip_text(folder["id"])
				self["vfolders"].pack_end(b, False, False, 0)
				b.set_active(folder["id"] in rids)
			self["vfolders"].show_all()
		else:
			EditorDialog.display_value(self, key, w)
	
	#@Overrides
	def update_special_widgets(self, *a):
		self["vdeviceID"].set_sensitive(self.is_new)
	
	#@Overrides
	def on_save_reuqested(self):
		self.store_values(VALUES)
		if self.is_new:
			# Add new dict to configuration (edited dict is already there)
			self.config["devices"].append(self.values)
		# Post configuration back to daemon
		self.post_config()
	
	#@Overrides
	def store_value(self, key, w):
		if key == "vaddresses":
			addresses = w.get_text().strip()
			if addresses == "dynamic":
				# Special case
				self.set_value("addresses", "dynamic")
			else:
				addresses = [
					x.strip() if "://" in x else "tcp://%s" % (x.strip(),)
					for x in addresses.split(",") ]
				self.set_value("addresses", ",".join(addresses))
		elif key == "vfolders":
			# Generate dict of { folder_id : bool } where bool is True if
			# folder should be shared with this device
			folders = {}
			for b in self["vfolders"].get_children():
				folders[b.get_tooltip_text()] = b.get_active()
			# Go over all Folders/<folder>/Devices/<device> keys in config
			# and set them as needed
			nid = self.get_value("deviceID")
			for r in self.config["folders"]:
				rid = r["id"]
				found = False
				for n in r["devices"]:
					if n["deviceID"] == nid:
						if not rid in folders or not folders[rid]:
							# Remove this /<device> key (unshare folder with device)
							r["devices"].remove(n)
							break
						found = True
				if (not found) and (rid in folders) and folders[rid]:
					# Add new /<device> key (share folder with device)
					r["devices"].append({
					   "addresses" : None,
					   "deviceID" : nid,
					   "name" : "",
					   "certName" : "",
					   "compression" : "metadata"
						})
		else:
			EditorDialog.store_value(self, key, w)
	
	#@Overrides
	def on_saved(self):
		self.close()
