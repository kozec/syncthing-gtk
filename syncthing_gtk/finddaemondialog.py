#!/usr/bin/env python2
"""
Syncthing-GTK - 1st run wizard

Basicaly runs syncthing daemon with -generate option and setups some
values afterwards.
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, GLib
from syncthing_gtk import EditorDialog, StDownloader
from syncthing_gtk.tools import get_config_dir, IS_WINDOWS, IS_XP
from syncthing_gtk.tools import _ # gettext function
from syncthing_gtk.uisettingsdialog import UISettingsDialog, browse_for_binary
import os, platform

VALUES = [ "vsyncthing_binary" ]

class FindDaemonDialog(EditorDialog):
	RESPONSE_SAVED = 1
	RESPONSE_QUIT = 2
	def __init__(self, app):
		EditorDialog.__init__(self, app, "find-daemon.glade",
			_("Can't invoke the daemon"))
		self.app = app
		exe = "syncthing.exe" if IS_WINDOWS else _("Syncthing binary")
		self["lblMessage"].set_markup("%s\n%s" % (
			_("Syncthing daemon binary cannot be found."),
			_("If you have Syncthing installed, please, set path to "
			  "%s below or click on <b>Download</b> "
			  "button to download latest Syncthing package.") % (exe,)
		))
		if IS_XP or StDownloader is None:
			# Downloading is not offered on XP (github will not talk to it)
			# or if StDownloader module is not packaged
			self["lblMessage"].set_markup("%s\n%s" % (
				_("Syncthing daemon binary cannot be found."),
				_("If you have Syncthing installed, please, set path to "
				  "%s below") % (exe,)
			))
			self.hide_download_button()
	
	### Dialog emulation
	def set_transient_for(self, parent):
		self["editor"].set_transient_for(parent)
	
	def set_message(self, m):
		self["lblMessage"].set_markup(m)
	
	def hide_download_button(self):
		self["btDownload"].set_visible(False)
	
	def run(self):
		return self["editor"].run()
	
	def destroy(self):
		self.close()
	
	
	
	
	### UI callbacks
	def cb_btBrowse_clicked(self, *a):
		""" Display file browser dialog to browse for syncthing binary """
		browse_for_binary(self["editor"], self, "vsyncthing_binary")
	
	def cb_btDownload_clicked(self, *a):
		"""
		Disable half of dialog and start downloading syncthing package
		"""
		# Determine which syncthing to use
		suffix, tag = StDownloader.determine_platform()
		# Report error on unsupported platforms
		if suffix is None or tag is None:
			# Disable download button
			self["btDownload"].set_sensitive(False)
			# Set message
			pd = "%s %s" % (
				platform.uname()[0],	# OS
				platform.uname()[4])	# architecture
			self["lblDownloadProgress"].set_markup("%s %s" % (
					_("Cannot download Syncthing daemon."),
					_("This platform (%s) is not supported") % (pd,),
				))
			return
		# Determine target file & directory
		self.target = os.path.join(
			os.path.expanduser(StDownloader.get_target_folder()),
			"syncthing%s" % (suffix,)
			)
		# Create downloader and connect events
		sd = StDownloader(self.target, tag)
		sd.connect("error", self.cb_download_error)
		sd.connect("version", self.cb_version)
		sd.connect("download-progress", self.cb_progress)
		sd.connect("download-finished", self.cb_extract_start)
		sd.connect("extraction-progress", self.cb_progress)
		sd.connect("extraction-finished", self.cb_extract_finished)
		# Display message and start downloading
		self["lblDownloadProgress"].set_markup(_("Downloading..."))
		self["btDownload"].set_visible(False)
		self["pbDownload"].set_visible(True)
		self["vsyncthing_binary"].set_sensitive(False)
		self["btBrowse"].set_sensitive(False)
		self["btSave"].set_sensitive(False)
		sd.get_version()
	
	def cb_btQuit_clicked(self, *a):
		""" Handler for 'Quit' button """
		self["editor"].response(FindDaemonDialog.RESPONSE_QUIT)
	
	def cb_bt_ui_settings_clicked(self, *a):
		""" Handler for 'UI Settings' button """
		e = UISettingsDialog(self.app)
		e.connect('close', self.cb_ui_settings_closed)
		e.load()
		e.show(self["window"])
	
	def cb_ui_settings_closed(self, *a):
		self.load()
	
	### EditorDialog overrides
	
	#@Overrides
	def load_data(self):
		# Don't load data from syncthing daemon, it knows nothing...
		copy = { k : self.app.config[k] for k in self.app.config }
		self.cb_data_loaded(copy)
		self.cb_check_value()
	
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
		self["editor"].response(FindDaemonDialog.RESPONSE_SAVED)
	
	
	
	
	### Downloader callbacks
	def cb_download_error(self, downloader, error, message):
		"""
		Called when download fails. User can click 'Download' to
		try it again.
		"""
		self["lblDownloadProgress"].set_markup(_("Download failed."))
		self["btDownload"].set_visible(True)
		self["pbDownload"].set_visible(False)
		self["vsyncthing_binary"].set_sensitive(True)
		self["btBrowse"].set_sensitive(True)
		self["btSave"].set_sensitive(True)
	
	def cb_version(self, downloader, version):
		self["lblDownloadProgress"].set_markup("Downloading %s..." % (version, ))
		downloader.download()
	
	def cb_extract_start(self, *a):
		self["lblDownloadProgress"].set_markup("Extracting...")
	
	def cb_progress(self, downloader, progress):
		self["pbDownload"].set_fraction(progress)
	
	def cb_extract_finished(self, downloader, *a):
		""" Called after extraction is finished """
		self["vsyncthing_binary"].set_sensitive(True)
		self["btBrowse"].set_sensitive(True)
		self["vsyncthing_binary"].set_text(downloader.get_target())
		self["lblDownloadProgress"].set_markup("<b>" + _("Download finished.") + "</b>")
		self["pbDownload"].set_visible(False)
		self["btSave"].set_sensitive(True)
	
