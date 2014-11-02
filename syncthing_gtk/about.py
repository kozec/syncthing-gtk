#!/usr/bin/env python2
"""
Syncthing-GTK - About dialog
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, Gio, GLib
from syncthing_gtk import DEBUG
import os, tempfile
_ = lambda (a) : a

class AboutDialog(object):
	""" Standard looking about dialog """
	def __init__(self, gladepath):
		self.gladepath = gladepath
		self.setup_widgets()
	
	def show(self, parent=None):
		if not parent is None:
			self.dialog.set_transient_for(parent)
		self.dialog.show_all()
	
	def run(self, *a):
		self.dialog.run()
	
	def close(self):
		if hasattr(self, "dialog"):
			self.dialog.set_visible(False)
			self.dialog.destroy()
	
	def setup_widgets(self):
		# Load glade file
		self.builder = Gtk.Builder()
		self.builder.add_from_file(os.path.join(self.gladepath, "about.glade"))
		self.builder.connect_signals(self)
		self.dialog = self.builder.get_object("dialog")
	
	def on_dialog_response(self, *a):
		self.close()
