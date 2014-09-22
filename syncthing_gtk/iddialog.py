#!/usr/bin/env python2
"""
Syncthing-GTK - IDDialog

Dialog with Node ID and generated QR code
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, Gio, GLib, Pango
from syncthing_gtk import DEBUG
import os, tempfile
_ = lambda (a) : a

class IDDialog(object):
	""" Dialog with Node ID and generated QR code """
	def __init__(self, app, node_id):
		self.app = app
		self.node_id = node_id
		self.setup_widgets()
		self.load_data()
	
	def __getitem__(self, name):
		""" Convince method that allows widgets to be accessed via self["widget"] """
		return self.builder.get_object(name)
	
	def show(self, parent=None):
		if not parent is None:
			self["dialog"].set_transient_for(parent)
		self["dialog"].show_all()
	
	def close(self):
		self["dialog"].hide()
		self["dialog"].destroy()
	
	def setup_widgets(self):
		# Load glade file
		self.builder = Gtk.Builder()
		self.builder.add_from_file(os.path.join(self.app.gladepath, "node-id.glade"))
		self.builder.connect_signals(self)
		self["vID"].set_text(self.node_id)

	def load_data(self):
		""" Loads QR code from Syncthing daemon """
		uri = "%s/qr/?text=%s" % (self.app.daemon.get_webui_url(), self.node_id)
		io = Gio.file_new_for_uri(uri)
		io.load_contents_async(None, self.cb_syncthing_qr)
	
	def cb_btClose_clicked(self, *a):
		self.close()
	
	def cb_syncthing_qr(self, io, results):
		"""
		Called when QR code is loaded or operation fails. Image is then
		displayed in dialog, failure is silently ignored.
		"""
		try:
			ok, contents, etag = io.load_contents_finish(results)
			if ok:
				# QR is loaded, save it to temp file and let GTK to handle
				# rest
				tf = tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False)
				tf.write(contents)
				tf.close()
				self["vQR"].set_from_file(tf.name)
				os.unlink(tf.name)
		except Exception, e:
			return
		finally:
			del io
