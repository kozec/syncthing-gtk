#!/usr/bin/env python2
"""
Syncthing-GTK - DaemonSettingsDialog

Universal dialog handler for all Syncthing settings and editing
"""
from __future__ import unicode_literals
from gi.repository import Gtk, Gdk
from syncthing_gtk import EditorDialog
from syncthing_gtk import Notifications, StDownloader, HAS_DESKTOP_NOTIFY
from syncthing_gtk.tools import *
from syncthing_gtk.tools import _ # gettext function
from syncthing_gtk.configuration import LONG_AGO
import os, logging

log = logging.getLogger("UISettingsDialog")

VALUES = [ "vautostart_daemon", "vautokill_daemon", "vminimize_on_start",
		"vautostart", "vuse_old_header", "vicons_in_menu",
		"vforce_dark_theme", "vdaemon_priority", "vfolder_as_path",
		"vnotification_for_update", "vnotification_for_folder",
		"vnotification_for_error", "vst_autoupdate", "vsyncthing_binary",
		"vsyncthing_arguments", "vmax_cpus", "vicon_theme", "vlanguage"
	]

# Values for filemanager integration. Key is ID of checkbox widget
FM_DATA = {
	"fmcb_nemo" : (
		"nemo/extensions-3.0/libnemo-python.so",	# python plugin location, relative to /usr/lib
		"Nemo python bindings",						# name or description of required package
		"syncthing-plugin-nemo",					# plugin script filename, without extension
		"nemo-python/extensions",					# script folder, relative to XDG_DATA_HOME
		"Nemo"										# name
	),
	"fmcb_nautilus" : (
		"nautilus/extensions-3.0/libnautilus-python.so",
		"Nautilus python bindings",
		"syncthing-plugin-nautilus",
		"nautilus-python/extensions",
		"Nautilus"
	),
	"fmcb_caja" : (
		"caja/extensions-2.0/libcaja-python.so",
		"Caja python bindings",
		"syncthing-plugin-caja",
		"caja-python/extensions",
		"Caja"
	)
}

class UISettingsDialog(EditorDialog):
	SETTING_NEEDS_RESTART = [
		"vuse_old_header", "vforce_dark_theme", "vicons_in_menu",
		"vicon_theme", "vlanguage"
	]
	
	def __init__(self, app):
		EditorDialog.__init__(self, app, "ui-settings.glade",
			_("UI Settings"))
		self.app = app
	
	def run(self):
		return self["dialog"].run()
	
	def cb_btBrowse_clicked(self, *a):
		""" Display file browser dialog to browse for syncthing binary """
		browse_for_binary(self["editor"], self, "vsyncthing_binary")
	
	def cb_vmax_cpus_value_changed(self, sb):
		if sb.get_adjustment().get_value() == 0:
			sb.set_text(_("Unlimited"))
	
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
			self["vforce_dark_theme"].set_visible(True)
			self["lbl_vlanguage"].set_visible(True)
			self["vlanguage"].set_visible(True)
		# Check for filemanager python bindings current state of plugins
		status = []
		for widget_id in FM_DATA:
			so_file, package, plugin, location, name = FM_DATA[widget_id]
			if not get_fm_source_path(plugin) is None:
				if library_exists(so_file):
					self[widget_id].set_sensitive(True)
					self[widget_id].set_active(
						os.path.exists(get_fm_target_path(plugin, location))
					)
				else:
					log.warning("Cannot find %s required to support %s", so_file, name)
					status.append(_("Install %(package)s package to enable %(feature)s support") % {
						'package' : package,
						'feature' : name
					})
			else:
				log.warning("Cannot find %s.py required to support %s", plugin, name)
		self["fmLblIntegrationStatus"].set_text("\n".join(status))
		if StDownloader is None:
			self["vst_autoupdate"].set_visible(False)
			self["lblAutoupdate"].set_visible(False)
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
		elif key == "daemon_priority":
			return EditorDialog.set_value(self, key, int(value))
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
		pass
	
	#@Overrides
	def on_save_reuqested(self):
		self.store_values(VALUES)
		# Save data to configuration file
		for k in self.values:
			self.app.config[k] = self.values[k]
		# Create / delete fm integration scripts
		for widget_id in FM_DATA:
			so_file, package, plugin, location, name = FM_DATA[widget_id]
			if self[widget_id].get_sensitive() and self[widget_id].get_active():
				# Should be enabled. Check if script is in place and create it if not
				source = get_fm_source_path(plugin)
				target = get_fm_target_path(plugin, location)
				if not source is None and not os.path.exists(target):
					try:
						# Create directory first
						os.makedirs(os.path.dirname(target))
					except Exception, e:
						# Ignore "file already exists" error
						pass
					try:
						if is_file_or_symlink(target):
							os.unlink(target)
						os.symlink(source, target)
						log.info("Created symlink '%s' -> '%s'", source, target)
					except Exception, e:
						log.error("Failed to symlink '%s' -> '%s'", source, target)
						log.error(e)
			else:
				# Should be disabled. Remove redundant scripts
				for extension in ("py", "pyc", "pyo"):
					target = get_fm_target_path(plugin, location, extension)
					if is_file_or_symlink(target):
						try:
							os.unlink(target)
							log.info("Removed '%s'", target)
						except Exception, e:
							log.error("Failed to remove '%s'", target)
							log.error(e)
		
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
		# Update directory boxes to reflect change in 'folder_as_path'
		for rid in self.app.folders:
			box = self.app.folders[rid]
			title = box["path"] if self.app.config["folder_as_path"] else rid
			box.set_visible("id", self.app.config["folder_as_path"])
			box.set_title(title)

def library_exists(name):
	"""
	Checks if there is specified so file installed in one of known prefixes
	"""
	PREFIXES = [
		"/usr/lib64",	# Fedora
		"/usr/lib",
		"/usr/local/lib/",
		"/usr/x86_64-pc-linux-gnu/lib/",
		"/usr/i686-pc-linux-gnu/lib/",
		"/usr/lib/x86_64-linux-gnu/",
		"/usr/lib/i386-linux-gnu/",
	]
	for prefix in PREFIXES:
		if os.path.exists(os.path.join(prefix, name)):
			return True
	return False

def get_fm_target_path(plugin, location, extension="py"):
	"""
	Returns full path to plugin file in filemanager plugins directory
	"""
	datahome = os.path.expanduser("~/.local/share")
	if "XDG_DATA_HOME" in os.environ:
		datahome = os.environ["XDG_DATA_HOME"]
	return os.path.join(datahome, location, "%s.%s" % (plugin, extension))

def get_fm_source_path(plugin):
	"""
	Returns path to location where plugin file is installed
	"""
	filename = "%s.py" % (plugin,)
	paths = (
		# Relative path used while developing or when running
		# ST-GTK without installation
		"./scripts/",
		# Default installation path
		"/usr/share/syncthing-gtk",
		# Not-so default installation path
		"/usr/local/share/syncthing-gtk",
	)
	for path in paths:
		fn = os.path.abspath(os.path.join(path, filename))	
		if os.path.exists(fn):
			return fn
	return None

def is_file_or_symlink(path):
	"""
	Returns True if specified file exists, even as broken symlink.
	(os.path.exists() returns False for broken symlinks)
	"""
	if os.path.exists(path): return True
	try:
		os.readlink(path)
		return True
	except:
		pass
	return False

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
