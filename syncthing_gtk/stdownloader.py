#!/usr/bin/env python2
"""
Syncthing-GTK - StDownloader

Instance of this class can download, extract and save syncthing daemon
to given location.
"""

from __future__ import unicode_literals
from gi.repository import GLib, Gio, GObject
import os, sys, json, tempfile
_ = lambda (a) : a

CHUNK_SIZE = 102400

class StDownloader(GObject.GObject):
	"""
	Downloads, extracts and saves syncthing daemon to given location.
	
	# Create instance
	sd = StDownloader("/tmp/syncthing.x86", "linux-386")
	# Connect to singals
	sd.connect(...
	...
	...
	# Start download
	sd.start()
	
	Signals:
		download-starting(version)
			emitted after current syncthing version is determined, when
			download of latest package is starting. Version argument is
			string with version number beign downloaded.
		download-progress(progress)
			emitted durring download. Progress goes from 0.0 to 1.0
		download-finished()
			emitted when download is finished
		extraction-progress(progress)
			emitted durring extraction. Progress goes from 0.0 to 1.0
		extraction-finished()
			emitted when extraction is finished and daemon binary saved
			(i.e. when all work is done)
		error(exception, message):
			Emited on error. Either exception or message can be None
	"""
	__gsignals__ = {
			b"download-starting"	: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"download-progress"	: (GObject.SIGNAL_RUN_FIRST, None, (float,)),
			b"download-finished"	: (GObject.SIGNAL_RUN_FIRST, None, ()),
			b"extraction-progress"	: (GObject.SIGNAL_RUN_FIRST, None, (float,)),
			b"extraction-finished"	: (GObject.SIGNAL_RUN_FIRST, None, ()),
			b"error"				: (GObject.SIGNAL_RUN_FIRST, None, (object,object)),
		}
	
	def __init__(self, target, platform):
		"""
		Target		- ~/.local/bin/syncthing or similar target location 
					for daemon binary
		Platform	- linux-386, windows-adm64 or other suffix used on
					syncthing releases page.
		"""
		
		GObject.GObject.__init__(self)
		self.target = target
		self.platform = platform
		self.version = None
		self.dll_url = None
		self.dll_size = -1
		self.downloaded = 0
		self.tmpfile = None
	
	def start(self):
		# Determine latest release first
		uri = "https://api.github.com/repos/syncthing/syncthing/releases?per_page=2"
		f = Gio.File.new_for_uri(uri)
		f.load_contents_async(None, self._cb_read_latest, None)
	
	def _cb_read_latest(self, f, result, buffer, *a):
		# Extract release version from response
		try:
			success, data, etag = f.load_contents_finish(result)
			if not success: raise Exception("Gio download failed")
			data = json.loads(data)[0]
			self.version = data["name"]
			for asset in data["assets"]:
				if self.platform in asset["name"]:
					self.dll_url = asset["browser_download_url"]
					self.dll_size = int(asset["size"])
					break
			del f
			if self.dll_url is None:
				raise Exception("No release to download")
			suffix = ".".join(self.dll_url.split(".")[-2:])
			if suffix.endswith(".zip") : suffix = ".zip"
			self.tmpfile = tempfile.NamedTemporaryFile(mode="wb",
				prefix="syncthing-package.", suffix=suffix, delete=False)
		except Exception, e:
			self.emit("error", e,
				_("Failed to determine latest Syncthing version."))
			return
		
		f = Gio.File.new_for_uri(self.dll_url)
		self.emit("download-starting", self.version)
		f.read_async(GLib.PRIORITY_DEFAULT, None, self._cb_open_archive, None)
	
	def _cb_open_archive(self, f, result, *a):
		try:
			stream = f.read_finish(result)
		except Exception, e:
			self.emit("error", e, _("Download failed."))
			return
		del f
		stream.read_bytes_async(CHUNK_SIZE, GLib.PRIORITY_DEFAULT, None, self._cb_download, None)
	
	def _cb_download(self, stream, result, f, *a):
		try:
			response = stream.read_bytes_finish(result)
			if response == None:
				raise Exception("No data recieved")
		except Exception, e:
			self.emit("error", e, _("Download failed."))
			return
		if response.get_size() > 0:
			self.downloaded += response.get_size()
			self.tmpfile.write(response.get_data())
			stream.read_bytes_async(CHUNK_SIZE, GLib.PRIORITY_DEFAULT, None, self._cb_download, None)
			self.emit("download-progress", float(self.downloaded) / float(self.dll_size))
		else:
			print "DLL completed", self.tmpfile.name
			stream.close()
			self.tmpfile.close()
