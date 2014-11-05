#!/usr/bin/env python2
"""
Syncthing-GTK - DaemonSettingsDialog

Universal dialog handler for all Syncthing settings and editing
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk
from syncthing_gtk import EditorDialog
from syncthing_gtk import Notifications, HAS_DESKTOP_NOTIFY, THE_HELL
_ = lambda (a) : a

VALUES = [ "vautostart_daemon", "vautokill_daemon", "vminimize_on_start",
		"vnotification_for_update", "vuse_old_header", "vnotification_for_folder",
		"vnotification_for_error"
	]

class UISettingsDialog(EditorDialog):
	def __init__(self, app):
		EditorDialog.__init__(self, app, "ui-settings.glade",
			_("UI Settings"))
		self.app = app
	
	def run(self):
		return self["dialog"].run()
	
	#@Overrides
	def load_data(self):
		# Don't load data from syncthing daemon, it knows nothing...
		copy = { k : self.app.config[k] for k in self.app.config }
		if THE_HELL:
			self["vuse_old_header"].set_visible(False)
			self["vuse_old_header"].set_no_show_all(True)
		self.cb_data_loaded(copy)
		self.cb_check_value()
	
	#@Overrides
	def display_value(self, key, w):
		if key == "vautostart_daemon":
			value = self.get_value(key[1:])
			if   value == 0: self["rbOnStartWait"].set_active(True)
			elif value == 1: self["rbOnStartRun"].set_active(True)
			else: self["rbOnStartAsk"].set_active(True)
		elif key == "vautokill_daemon":
			value = self.get_value(key[1:])
			if   value == 1: self["rbOnExitTerminate"].set_active(True)
			elif value == 0: self["rbOnExitLeave"].set_active(True)
			else: self["rbOnExitAsk"].set_active(True)
		else:
			return EditorDialog.display_value(self, key, w)
	
	#@Overrides
	def store_value(self, key, w):
		if key == "vautostart_daemon":
			if   self["rbOnStartWait"].get_active() : self.set_value(key[1:], 0)
			elif self["rbOnStartRun"].get_active() : self.set_value(key[1:], 1)
			else: return self.set_value(key[1:], 2)	# vOnStartAsk
		elif key == "vautokill_daemon":
			if self["rbOnExitTerminate"].get_active() : return self.set_value(key[1:], 1)
			elif self["rbOnExitLeave"].get_active() : return self.set_value(key[1:], 0)
			else: return self.set_value(key[1:], 2)	# vOnExitAsk
		else:
			return EditorDialog.store_value(self, key, w)
	
	#@Overrides
	def on_data_loaded(self):
		self.values = self.config
		self.checks = {}
		return self.display_values(VALUES)
	
	#@Overrides
	def update_special_widgets(self, *a):
		pass
	
	#@Overrides
	def on_save_reuqested(self):
		self.store_values(VALUES)
		# Save data to configuration file
		for k in self.values:
			self.app.config[k] = self.values[k]
		# Report work done
		self.syncthing_cb_post_config()
	
	#@Overrides
	def on_saved(self):
		self.close()
		# Recreate Notifications object if needed
		if HAS_DESKTOP_NOTIFY:
			if not self.app.notifications is None:
				self.app.notifications.kill()
				self.app.notifications = None
			if self.app.config["notification_for_update"] or self.app.config["notification_for_error"]:
				self.app.notifications = Notifications(self.app, self.app.daemon)
