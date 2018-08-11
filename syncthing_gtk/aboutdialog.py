#/usr/bin/env python3
"""
Syncthing-GTK - About dialog
"""


from syncthing_gtk.tools import IS_WINDOWS
from syncthing_gtk.uibuilder import UIBuilder
import os

class AboutDialog(object):
	""" Standard looking about dialog """
	def __init__(self, app, gladepath, iconpath):
		self.gladepath = gladepath
		self.iconpath = iconpath
		self.setup_widgets(app)
	
	def show(self, parent=None):
		if not parent is None:
			self.dialog.set_transient_for(parent)
		self.dialog.show()
	
	def run(self, *a):
		self.dialog.run()
	
	def close(self):
		if hasattr(self, "dialog"):
			self.dialog.set_visible(False)
			self.dialog.destroy()
	
	def setup_widgets(self, app):
		self.builder = UIBuilder()
		# Fix icon path
		self.builder.replace_icon_path("icons/", self.iconpath)
		# Load glade file
		self.builder.add_from_file(os.path.join(self.gladepath, "about.glade"))
		self.builder.connect_signals(self)
		self.dialog = self.builder.get_object("dialog")
		# Get app version
		app_ver = "unknown"
		try:
			if IS_WINDOWS:
				# pkg_resources will not work on cx_Frozen package
				from syncthing_gtk.tools import get_install_path
				with open(os.path.join(get_install_path(), "__version__"), "r") as vfile:
					app_ver = vfile.read().strip(" \t\r\n")
			else:
				import pkg_resources, syncthing_gtk
				if syncthing_gtk.__file__.startswith(pkg_resources.require("syncthing-gtk")[0].location):
					app_ver = pkg_resources.require("syncthing-gtk")[0].version
		except:
			# pkg_resources is not available or __version__ file missing
			# There is no reason to crash on this.
			pass
		# Get daemon version
		try:
			daemon_ver = app.daemon.get_version()
			app_ver = "%s (Daemon %s)" % (app_ver, daemon_ver)
		except:
			# App is None or daemon version is not yet known
			pass
		# Display versions in UI
		self.builder.get_object("lblVersion").set_label(app_ver)
	
	def on_dialog_response(self, *a):
		self.close()
