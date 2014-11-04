#!/usr/bin/env python2
"""
Syncthing-GTK - StDownloader

Instance of this class can download, extract and save syncthing daemon
to given location.
"""

from __future__ import unicode_literals
from gi.repository import GLib, Gio, GObject
import os, sys, stat, json, tempfile, tarfile, zipfile
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
		self.extract_size = -1
		self.extracted = 0
	
	def start(self):
		# Determine latest release
		uri = "https://api.github.com/repos/syncthing/syncthing/releases?per_page=2"
		f = Gio.File.new_for_uri(uri)
		f.load_contents_async(None, self._cb_read_latest, None)
	
	def _cb_read_latest(self, f, result, buffer, *a):
		# Extract release version from response
		version, dll_url, dll_size = None, None, None
		tmpfile = None
		try:
			success, data, etag = f.load_contents_finish(result)
			if not success: raise Exception("Gio download failed")
			data = json.loads(data)[0]
			version = data["name"]
			for asset in data["assets"]:
				if self.platform in asset["name"]:
					dll_url = asset["browser_download_url"]
					dll_size = int(asset["size"])
					break
			del f
			if dll_url is None:
				raise Exception("No release to download")
			suffix = ".%s" % (".".join(dll_url.split(".")[-2:]),)
			if suffix.endswith(".zip") : suffix = ".zip"
			tmpfile = tempfile.NamedTemporaryFile(mode="wb",
				prefix="syncthing-package.", suffix=suffix, delete=False)
		except Exception, e:
			self.emit("error", e,
				_("Failed to determine latest Syncthing version."))
			return
		
		f = Gio.File.new_for_uri(dll_url)
		self.emit("download-starting", version)
		f.read_async(GLib.PRIORITY_DEFAULT, None, self._cb_open_archive,
				(tmpfile, dll_size))
	
	def _cb_open_archive(self, f, result, (tmpfile, dll_size)):
		stream = None
		try:
			stream = f.read_finish(result)
			del f
		except Exception, e:
			self.emit("error", e, _("Download failed."))
			return
		stream.read_bytes_async(CHUNK_SIZE, GLib.PRIORITY_DEFAULT, None,
				self._cb_download, (tmpfile, 0, dll_size,))
	
	def _cb_download(self, stream, result, (tmpfile, downloaded, dll_size)):
		try:
			# Get response from async call
			response = stream.read_bytes_finish(result)
			if response == None:
				raise Exception("No data recieved")
			# 0b of data read indicates end of file
			if response.get_size() > 0:
				# Not EOF. Write buffer to disk and download some more
				downloaded += response.get_size()
				tmpfile.write(response.get_data())
				stream.read_bytes_async(CHUNK_SIZE, GLib.PRIORITY_DEFAULT, None,
						self._cb_download, (tmpfile, downloaded, dll_size))
				self.emit("download-progress", float(downloaded) / float(dll_size))
			else:
				# EOF. Re-open tmpfile as tar and prepare to extract
				# binary
				self.emit("download-finished")
				stream.close()
				tmpfile.close()
				GLib.idle_add(self._open_achive, tmpfile.name)
		except Exception, e:
			self.emit("error", e, _("Download failed."))
			return
	
	def _open_achive(self, archive_name):
		try:
			# Sanity check
			if not tarfile.is_tarfile(archive_name):
				self.emit("error", None, _("Downloaded file is corrupted."))
				return
			# Open Archive
			archive = tarfile.open(archive_name, "r", bufsize=CHUNK_SIZE * 2)
			# Find binary inside
			for pathname in archive.getnames():
				filename = pathname.replace("\\", "/").split("/")[-1]
				if filename.startswith("syncthing"):
					# Last sanity check, then just open files
					# and start extracting
					tinfo = archive.getmember(pathname)
					if tinfo.isfile():
						compressed = archive.extractfile(pathname)
						try:
							os.makedirs(os.path.split(self.target)[0])
						except Exception: pass
						output = file(self.target, "wb")
						GLib.idle_add(self._extract, (archive, compressed, output, 0, tinfo.size))
						return
		except Exception, e:
			self.emit("error", e,
				_("Failed to determine latest Syncthing version."))
			return
	
	def _extract(self, (archive, compressed, output, extracted, ex_size)):
		try:
			buffer = compressed.read(CHUNK_SIZE)
			read_size = len(buffer)
			if read_size == CHUNK_SIZE:
				# Need some more
				output.write(buffer)
				extracted += read_size
				GLib.idle_add(self._extract, (archive, compressed, output, extracted, ex_size))
				self.emit("extraction-progress", float(extracted) / float(ex_size))
			else:
				# End of file
				# Write rest, if any
				if read_size > 0:
					output.write(buffer)
				# Change file mode to 0755
				os.fchmod(output.fileno(), stat.S_IRWXU | stat.S_IRGRP | 
						stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
				output.close()
				archive.close()
				compressed.close()
				self.emit("extraction-progress", 1.0)
				self.emit("extraction-finished")
		except Exception, e:
			self.emit("error", e,
				_("Failed to determine latest Syncthing version."))
			return
		return False
