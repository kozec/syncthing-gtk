#!/usr/bin/env python2
"""
Syncthing-GTK - DaemonSettingsDialog

Universal dialog handler for all Syncthing settings and editing
"""
from __future__ import unicode_literals
from gi.repository import Gtk, Gdk
from syncthing_gtk import EditorDialog
from syncthing_gtk import Notifications, HAS_DESKTOP_NOTIFY
from syncthing_gtk.tools import *
from syncthing_gtk.configuration import LONG_AGO
import os

_ = lambda (a) : a

VALUES = [ "vautostart_daemon", "vautokill_daemon", "vminimize_on_start",
		"vautostart", "vuse_old_header", "vicons_in_menu",
		"vnotification_for_update", "vnotification_for_folder",
		"vnotification_for_error", "vst_autoupdate", "vsyncthing_binary",
	]

class UISettingsDialog(EditorDialog):
	def __init__(self, app):
		EditorDialog.__init__(self, app, "ui-settings.glade",
			_("UI Settings"))
		self.app = app
	
	def run(self):
		return self["dialog"].run()
	
	def cb_btBrowse_clicked(self, *a):
		""" Display file browser dialog to browse for syncthing binary """
		browse_for_binary(self["editor"], self, "vsyncthing_binary")
	
	#@Overrides
	def load_data(self):
		# Don't load data from syncthing daemon, it knows nothing...
		copy = { k : self.app.config[k] for k in self.app.config }
		if IS_UNITY or IS_GNOME:
			self["vuse_old_header"].set_visible(False)
			self["vuse_old_header"].set_no_show_all(True)
			self["vicons_in_menu"].set_visible(False)
			self["vicons_in_menu"].set_no_show_all(True)
		if not HAS_DESKTOP_NOTIFY:
			# Disable notifications settings if required
			# library is not available
			self["lblNotifications"].set_sensitive(False)
			self["vnotification_for_update"].set_sensitive(False)
			self["vnotification_for_folder"].set_sensitive(False)
			self["vnotification_for_error"].set_sensitive(False)
		if IS_WINDOWS:
			# Leave daemon running causes weird bugs on Windows,
			# so only one option is enabled there
			self["rbOnExitLeave"].set_sensitive(False)
			self["rbOnExitAsk"].set_sensitive(False)
			self["rbOnExitTerminate"].set_active(True)
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
		elif key == "vst_autoupdate":
			# Reset updatecheck timer when autoupdate is turned on
			if self["vst_autoupdate"].get_active():
				self.values["last_updatecheck"] = LONG_AGO
			return EditorDialog.store_value(self, key, w)
		else:
			return EditorDialog.store_value(self, key, w)
	
	#@Overrides
	def set_value(self, key, value):
		if key == "autostart":
			set_run_on_startup(value, "Syncthing-GTK", get_executable(),
				"/usr/share/syncthing-gtk/icons/st-logo-128.png",
				"GUI for Syncthing")
		else:
			return EditorDialog.set_value(self, key, value)
	
	#@Overrides
	def get_value(self, key):
		if key == "autostart":
			return is_ran_on_startup("Syncthing-GTK")
		else:
			return EditorDialog.get_value(self, key)
	
	#@Overrides
	def on_data_loaded(self):
		self.values = self.config
		self.checks = {
			"vsyncthing_binary" : lambda p : os.path.isfile(p) and os.access(p, os.X_OK)
		}
		return self.display_values(VALUES)
	
	#@Overrides
	def update_special_widgets(self, *a):
		if self["vuse_old_header"].get_active():
			self["vicons_in_menu"].set_sensitive(False)
			self["vicons_in_menu"].set_active(True)
		else:
			self["vicons_in_menu"].set_sensitive(True)
	
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
		# Restart or cancel updatecheck
		self.app.check_for_upgrade()

def browse_for_binary(parent_window, settings_dialog, value):
	"""
	Display file browser dialog to browse for syncthing binary.
	Used here and by FindDaemonDialog as well.
	"""
	# Prepare dialog
	d = Gtk.FileChooserDialog(
		_("Browse for Syncthing binary"),
		parent_window,
		Gtk.FileChooserAction.OPEN,
		(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
		Gtk.STOCK_OK, Gtk.ResponseType.OK))
	# Prepare filter
	f = Gtk.FileFilter()
	if IS_WINDOWS:
		f.set_name("Executables")
		f.add_pattern("*.exe")
	else:
		f.set_name("Binaries")
		f.add_mime_type("application/x-executable")
		f.add_mime_type("application/x-shellscript")
	d.add_filter(f)
	# Set default path
	confdir = os.path.join(get_config_dir(), "syncthing")
	prevvalue = str(settings_dialog[value].get_text()).strip()
	if prevvalue and os.path.exists(os.path.split(prevvalue)[0]):
		d.set_current_folder(os.path.split(prevvalue)[0])
	elif os.path.exists(confdir):
		d.set_current_folder(confdir)
	elif IS_WINDOWS:
		if "CommonProgramFiles" in os.environ:
			d.set_current_folder(os.environ["CommonProgramFiles"])
		elif os.path.exists("C:\\Program Files"):
			d.set_current_folder("C:\\Program Files")
		# Else nothing, just start whatever you like
	else:
		d.set_current_folder("/usr/bin")
	
	# Get response
	if d.run() == Gtk.ResponseType.OK:
		settings_dialog[value].set_text(d.get_filename())
	d.destroy()
