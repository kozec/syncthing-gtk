#!/usr/bin/env python2
"""
Syncthing-GTK - DaemonSettingsDialog

Universal dialog handler for all Syncthing settings and editing
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk
from syncthing_gtk import EditorDialog
_ = lambda (a) : a

VALUES = [ "vOnStart", "vOnExit", "vauto_minimize", "vuse_old_header" ]


class UISettingsDialog(EditorDialog):
	def __init__(self, app):
		EditorDialog.__init__(self, app, "ui-settings.glade",
			"UI Settings")
	
	#@Overrides
	def load_data(self):
		# Don't load data from syncthing daemon, it knows nothing...
		print self.app.config
		for k in self.app.config:
			print k
		copy = { k : self.app.config[k] for k in self.app.config }
		self.cb_data_loaded(copy)
		self.cb_check_value()
	
	#@Overrides
	def get_value(self, key):
		if key == "vOnStart":
			if   self["vOnStartWait"].get_active() : return 0
			elif self["vOnStartRun"].get_active() : return 1
			else: return 2	# vOnStartAsk
		elif key == "vOnExit":
			if self["vOnExitTerminate"].get_active() : return 0
			elif self["vOnExitLeave"].get_active() : return 1
			else: return 2	# vOnExitAsk
		else:
			return EditorDialog.get_value(self, key)
	
	#@Overrides
	def set_value(self, key, value):
		if key == "vOnStart":
			if   value == 0: self["vOnStartWait"].set_active(True)
			elif value == 1: self["vOnStartRun"].set_active(True)
			else: self["vOnStartAsk"].set_active(True)
		elif key == "vOnExit":
			if   value == 0: self["vOnExitTerminate"].set_active(True)
			elif value == 1: self["vOnExitLeave"].set_active(True)
			else: self["vOnExitAsk"].set_active(True)
		else:
			return EditorDialog.set_value(self, key, value)

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
