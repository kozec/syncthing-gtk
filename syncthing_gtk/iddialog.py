#!/usr/bin/env python2
"""
Syncthing-GTK - IDDialog

Dialog with Device ID and generated QR code
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, Gio, GLib, Pango
from tools import IS_WINDOWS
from syncthing_gtk.tools import _ # gettext function
from syncthing_gtk import UIBuilder
import urllib2, httplib, ssl
import os, tempfile, logging
log = logging.getLogger("IDDialog")

class IDDialog(object):
	""" Dialog with Device ID and generated QR code """
	def __init__(self, app, device_id):
		self.app = app
		self.device_id = device_id
		self.setup_widgets()
		self.ssl_ctx = create_ssl_context()
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
		self.builder = UIBuilder()
		self.builder.add_from_file(os.path.join(self.app.gladepath, "device-id.glade"))
		self.builder.connect_signals(self)
		self["vID"].set_text(self.device_id)
	
	def load_data(self):
		""" Loads QR code from Syncthing daemon """
		if IS_WINDOWS:
			return self.load_data_urllib()
		uri = "%s/qr/?text=%s" % (self.app.daemon.get_webui_url(), self.device_id)
		io = Gio.file_new_for_uri(uri)
		io.load_contents_async(None, self.cb_syncthing_qr, ())
	
	def load_data_urllib(self):
		""" Loads QR code from Syncthing daemon """
		uri = "%s/qr/?text=%s" % (self.app.daemon.get_webui_url(), self.device_id)
		api_key = self.app.daemon.get_api_key()
		opener = urllib2.build_opener(DummyHTTPSHandler(self.ssl_ctx))
		if not api_key is None:
			opener.addheaders = [("X-API-Key", api_key)]
		a = opener.open(uri)
		data = a.read()
		tf = tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False)
		tf.write(data)
		tf.close()
		self["vQR"].set_from_file(tf.name)
		os.unlink(tf.name)
	
	def cb_btClose_clicked(self, *a):
		self.close()
	
	def cb_syncthing_qr(self, io, results, *a):
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
		except GLib.Error, e:
			if e.code == 14:
				# Unauthorized. Grab CSRF token from daemon and try again
				log.warning("Failed to load image using glib. Retrying with urllib2.")
				self.load_data_urllib()
		except Exception, e:
			log.exception(e)
			return
		finally:
			del io

def create_ssl_context():
	""" May return NULL if ssl is not available """
	if hasattr(ssl, "create_default_context"):
		ctx = ssl.create_default_context()
		ctx.check_hostname = False
		ctx.verify_mode = ssl.CERT_NONE
	else:
		log.warning("SSL is not available, cannot verify server certificate.")

class DummyHTTPSHandler(urllib2.HTTPSHandler):
	"""
	Dummy HTTPS handler that ignores certificate errors. This in unsafe,
	but used ONLY for QR code images.
	"""
	def __init__(self, ctx):
		urllib2.HTTPSHandler.__init__(self)
		self.ctx = ctx
	
	def https_open(self, req):
		return self.do_open(self.getConnection, req)
	
	def getConnection(self, host, timeout=300):
		if not self.ctx is None:
			return httplib.HTTPSConnection(host, context=ctx)
		return True

