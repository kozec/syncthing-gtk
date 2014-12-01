#!/usr/bin/env python2
"""
Syncthing-GTK - DaemonSettingsDialog

Universal dialog handler for all Syncthing settings and editing
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk
from syncthing_gtk import EditorDialog
_ = lambda (a) : a

VALUES = [ "vListenAddress", "vLocalAnnEnabled", "vUPnPEnabled",
		"vStartBrowser", "vMaxSendKbpsEnabled", "vMaxSendKbps",
		"vMaxRecvKbpsEnabled", "vMaxRecvKbps", "vURAccepted",
		"vLocalAnnPort", "vGlobalAnnEnabled", "vGlobalAnnServers"
		]


class DaemonSettingsDialog(EditorDialog):
	def __init__(self, app):
		EditorDialog.__init__(self, app, "daemon-settings.glade",
			"Syncthing Daemon Settings")
	
	#@Overrides
	def get_value(self, key):
		if key == "ListenAddress":
			return ", ".join([ x.strip() for x in self.values[key]])
		elif key == "GlobalAnnServers":
			if "GlobalAnnServer" in self.values:
				# For Syncthing < 0.9.10
				return self.values["GlobalAnnServer"]
			return ", ".join([ x.strip() for x in self.values["GlobalAnnServers"]])
		elif key == "URAccepted":
			return (self.values["URAccepted"] == 1)
		elif key == "MaxSendKbpsEnabled":
			return (self.values["MaxSendKbps"] != 0)
		elif key == "MaxRecvKbpsEnabled":
			return (self.values["MaxRecvKbps"] != 0)
		else:
			return EditorDialog.get_value(self, key)
	
	#@Overrides
	def set_value(self, key, value):
		if key == "ListenAddress":
			self.values[key] = [ x.strip() for x in value.split(",") ]
		elif key == "GlobalAnnServers":
			self.values[key] = [ x.strip() for x in value.split(",") ]
			if "GlobalAnnServer" in self.values:
				# For Syncthing < 0.9.10
				if len(self.values[key]) > 0:
					self.values["GlobalAnnServer"] = self.values[key][0]
				else:
					self.values["GlobalAnnServer"] = ""
		elif key == "URAccepted":
			self.values[key] = 1 if value else -1
		elif key == "MaxSendKbpsEnabled":
			if value:
				if self.values["MaxSendKbps"] <= 0:
					self.values["MaxSendKbps"] = 1
					self.find_widget_by_id("vMaxSendKbps").get_adjustment().set_value(self.values["MaxSendKbps"])
			else:
				self.values["MaxSendKbps"] = 0
				print "MaxSendKbpsEnabled : MaxSendKbps zeroed"
				self.find_widget_by_id("vMaxSendKbps").get_adjustment().set_value(self.values["MaxSendKbps"])
		elif key == "MaxRecvKbpsEnabled":
			if value:
				if self.values["MaxRecvKbps"] <= 0:
					self.values["MaxRecvKbps"] = 1
					self.find_widget_by_id("vMaxRecvKbps").get_adjustment().set_value(self.values["MaxRecvKbps"])
			else:
				self.values["MaxRecvKbps"] = 0
				self.find_widget_by_id("vMaxRecvKbps").get_adjustment().set_value(self.values["MaxRecvKbps"])
		else:
			return EditorDialog.set_value(self, key, value)

	#@Overrides
	def on_data_loaded(self):
		self.values = self.config["Options"]
		self.checks = {}
		return self.display_values(VALUES)
	
	#@Overrides
	def update_special_widgets(self, *a):
		self["vMaxSendKbps"].set_sensitive(self.get_value("MaxSendKbpsEnabled"))
		self["vMaxRecvKbps"].set_sensitive(self.get_value("MaxRecvKbpsEnabled"))
		self["lblvLocalAnnPort"].set_sensitive(self.get_value("LocalAnnEnabled"))
		self["vLocalAnnPort"].set_sensitive(self.get_value("LocalAnnEnabled"))
		self["lblvGlobalAnnServers"].set_sensitive(self.get_value("GlobalAnnEnabled"))
		self["vGlobalAnnServers"].set_sensitive(self.get_value("GlobalAnnEnabled"))
	
	#@Overrides
	def on_save_reuqested(self):
		self.store_values(VALUES)
		# Post configuration back to daemon
		self.post_config()
	
	#@Overrides
	def on_saved(self):
		self.close()
