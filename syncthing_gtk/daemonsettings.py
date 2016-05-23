#!/usr/bin/env python2
"""
Syncthing-GTK - DaemonSettingsDialog

Universal dialog handler for all Syncthing settings and editing
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk
from syncthing_gtk.editordialog import EditorDialog, strip_v
from syncthing_gtk.tools import _ # gettext function

VALUES = [ "vlistenAddresses", "vlocalAnnounceEnabled", "vupnpEnabled",
		"vstartBrowser", "vmaxSendKbpsEnabled", "vmaxSendKbps",
		"vmaxRecvKbpsEnabled", "vmaxRecvKbps", "vurAccepted",
		"vlocalAnnouncePort", "vglobalAnnounceEnabled",
		"vglobalAnnounceServers"
		]


class DaemonSettingsDialog(EditorDialog):
	def __init__(self, app):
		EditorDialog.__init__(self, app, "daemon-settings.glade",
			_("Syncthing Daemon Settings"))
	
	#@Overrides
	def get_value(self, key):
		if key == "listenAddresses":
			return ", ".join([ strip_v(x) for x in self.values[key]])
		elif key == "globalAnnounceServers":
			return ", ".join([ strip_v(x) for x in self.values["globalAnnounceServers"]])
		elif key == "urAccepted":
			return (self.values["urAccepted"] == 1)
		elif key == "maxSendKbpsEnabled":
			return (self.values["maxSendKbps"] != 0)
		elif key == "maxRecvKbpsEnabled":
			return (self.values["maxRecvKbps"] != 0)
		else:
			return EditorDialog.get_value(self, key)
	
	#@Overrides
	def set_value(self, key, value):
		if key == "listenAddresses":
			self.values[key] = [ x.strip(" \t") for x in value.split(",") ]
		elif key == "globalAnnounceServers":
			self.values[key] = [ x.strip(" \t") for x in value.split(",") ]
		elif key == "urAccepted":
			self.values[key] = 1 if value else -1
		elif key == "maxSendKbpsEnabled":
			if value:
				if self.values["maxSendKbps"] <= 0:
					self.values["maxSendKbps"] = 1
					self.find_widget_by_id("vmaxSendKbps").get_adjustment().set_value(self.values["maxSendKbps"])
			else:
				self.values["maxSendKbps"] = 0
				self.find_widget_by_id("vmaxSendKbps").get_adjustment().set_value(self.values["maxSendKbps"])
		elif key == "maxRecvKbpsEnabled":
			if value:
				if self.values["maxRecvKbps"] <= 0:
					self.values["maxRecvKbps"] = 1
					self.find_widget_by_id("vmaxRecvKbps").get_adjustment().set_value(self.values["maxRecvKbps"])
			else:
				self.values["maxRecvKbps"] = 0
				self.find_widget_by_id("vmaxRecvKbps").get_adjustment().set_value(self.values["maxRecvKbps"])
		else:
			return EditorDialog.set_value(self, key, value)
	
	#@Overrides
	def on_data_loaded(self):
		self.values = self.config["options"]
		self.checks = {}
		return self.display_values(VALUES)
	
	#@Overrides
	def update_special_widgets(self, *a):
		self["vmaxSendKbps"].set_sensitive(self.get_value("maxSendKbpsEnabled"))
		self["vmaxRecvKbps"].set_sensitive(self.get_value("maxRecvKbpsEnabled"))
		self["lblvlocalAnnouncePort"].set_sensitive(self.get_value("localAnnounceEnabled"))
		self["vlocalAnnouncePort"].set_sensitive(self.get_value("localAnnounceEnabled"))
		self["lblvglobalAnnounceServers"].set_sensitive(self.get_value("globalAnnounceEnabled"))
		self["lblvglobalAnnounceServers"].set_sensitive(self.get_value("globalAnnounceEnabled"))
	
	#@Overrides
	def on_save_reuqested(self):
		self.store_values(VALUES)
		# Post configuration back to daemon
		self.post_config()
	
	#@Overrides
	def on_saved(self):
		self.close()
