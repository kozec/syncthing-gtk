#!/usr/bin/env python2
"""
Syncthing-GTK - StDownloader

Instance of this class can download, extract and save syncthing daemon
to given location.
"""

from __future__ import unicode_literals
from gi.repository import GLib, Gio, GObject
import os, sys, stat, json, traceback, platform
import tempfile, tarfile, zipfile
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
	# Determine version
	sd.get_version()
	
	# (somewhere in 'version' signal callback) 
	sd.download()
	
	Signals:
		version(version)
			emitted after current syncthing version is determined.
			Version argument is string.
		download-starting()
			emitted when download of package is starting
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
			b"version"				: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"download-starting"	: (GObject.SIGNAL_RUN_FIRST, None, ()),
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
		self.dll_size = None
	
	def get_version(self):
		"""
		Determines latest version and prepares stuff needed for
		download.
		Emits 'version' signal on success.
		Handler for 'version' signal should call download method.
		"""
		uri = "https://api.github.com/repos/syncthing/syncthing/releases?per_page=2"
		f = Gio.File.new_for_uri(uri)
		f.load_contents_async(None, self._cb_read_latest, None)
	
	def get_target(self):
		""" Returns download target """
		return self.target
	
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
		except Exception, e:
			print >>sys.stderr, traceback.format_exc()
			self.emit("error", e,
				_("Failed to determine latest Syncthing version."))
			return
		# Everything is done, emit version signal
		self.emit("version", self.version)
	
	
	def download(self):
		try:
			suffix = ".%s" % (".".join(self.dll_url.split(".")[-2:]),)
			if suffix.endswith(".zip") :
				suffix = ".zip"	
			tmpfile = tempfile.NamedTemporaryFile(mode="wb",
				prefix="syncthing-package.", suffix=suffix, delete=False)
		except Exception, e:
			print >>sys.stderr, traceback.format_exc()
			self.emit("error", e, _("Failed to create temporaly file."))
			return
		f = Gio.File.new_for_uri(self.dll_url)
		f.read_async(GLib.PRIORITY_DEFAULT, None, self._cb_open_archive,
				(tmpfile,))
		self.emit("download-starting")
	
	
	def _cb_open_archive(self, f, result, (tmpfile,)):
		stream = None
		try:
			stream = f.read_finish(result)
			del f
		except Exception, e:
			print >>sys.stderr, traceback.format_exc()
			self.emit("error", e, _("Download failed."))
			return
		stream.read_bytes_async(CHUNK_SIZE, GLib.PRIORITY_DEFAULT, None,
				self._cb_download, (tmpfile, 0))
	
	def _cb_download(self, stream, result, (tmpfile, downloaded)):
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
						self._cb_download, (tmpfile, downloaded))
				self.emit("download-progress", float(downloaded) / float(self.dll_size))
			else:
				# EOF. Re-open tmpfile as tar and prepare to extract
				# binary
				self.emit("download-finished")
				stream.close()
				tmpfile.close()
				GLib.idle_add(self._open_achive, tmpfile.name)
		except Exception, e:
			print >>sys.stderr, traceback.format_exc()
			self.emit("error", e, _("Download failed."))
			return
	
	def _open_achive(self, archive_name):
		try:
			# Determine archive format
			archive = None
			if tarfile.is_tarfile(archive_name):
				# Open TAR
				archive = tarfile.open(archive_name, "r", bufsize=CHUNK_SIZE * 2)
			elif zipfile.is_zipfile(archive_name):
				# Open ZIP
				archive = ZipThatPretendsToBeTar(archive_name, "r")
			else:
				# Unrecognized format
				self.emit("error", None, _("Downloaded file is corrupted."))
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
			print >>sys.stderr, traceback.format_exc()
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
				if hasattr(os, "fchmod"):
					# ... (on Unix)
					os.fchmod(output.fileno(), stat.S_IRWXU | stat.S_IRGRP | 
							stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
				output.close()
				archive.close()
				compressed.close()
				self.emit("extraction-progress", 1.0)
				self.emit("extraction-finished")
		except Exception, e:
			print >>sys.stderr, traceback.format_exc()
			self.emit("error", e,
				_("Failed to determine latest Syncthing version."))
			return
		return False
	
	@staticmethod
	def determine_platform():
		"""
		Determines what syncthing package should be downloaded.
		Returns tuple (suffix, tag), where suffix is file extension
		and tag platform identification used on syncthing releases page.
		Returns (None, None) if package cannot be determined.
		"""
		suffix, tag = None, None
		if platform.system().lower().startswith("linux"):
			if platform.machine() in ("i386", "i586", "i686"):
				# Not sure, if anything but i686 is actually used
				suffix, tag = ".x86", "linux-386"
			elif platform.machine() == "x86_64":
				# Who in the world calls x86_64 'amd' anyway?
				suffix, tag = ".x64", "linux-amd64"
			elif platform.machine().lower() in ("armv5", "armv6", "armv7"):
				# TODO: This should work, but I don't have any way
				# to test this right now
				suffix = platform.machine().lower()
				tag = "linux-%s" % (suffix,)
		elif platform.system().lower().startswith("windows"):
			if platform.machine() == "AMD64":
				suffix, tag = ".exe", "windows-amd64"
			else:
				# I just hope that MS will not release ARM Windows for
				# next 50 years...
				suffix, tag = ".exe", "windows-386"
		for x in ("freebsd", "solaris", "openbsd"):
			# Syncthing-GTK should work on those as well...
			if platform.system().lower().startswith(x):
				if platform.machine() in ("i386", "i586", "i686"):
					suffix, tag = ".x86", "%s-386" % (x,)
				elif platform.machine() in ("amd64", "x86_64"):
					suffix, tag = ".x64", "%s-amd64" % (x,)
		return (suffix, tag)

class ZipThatPretendsToBeTar(zipfile.ZipFile):
	""" Because ZipFile and TarFile are _almost_ the same -_- """
	def __init__(self, filename, mode):
		zipfile.ZipFile.__init__(self, filename, mode)
	
	def getnames(self):
		""" Return the members as a list of their names. """
		return self.namelist()
		
	def getmember(self, name):
		"""
		Return a TarInfo object for member name. If name can not be
		found in the archive, KeyError is raised
		"""
		return ZipThatPretendsToBeTar.ZipInfo(self, name)
	
	def extractfile(self, name):
		return self.open(name, "r")
	
	class ZipInfo:
		def __init__(self, zipfile, name):
			info = zipfile.getinfo(name)
			for x in dir(info):
				if not (x.startswith("_") or x.endswith("_")):
					setattr(self, x, getattr(info, x))
			self.size = self.file_size
		
		def isfile(self, *a):
			# I don't exactly expect anything but files in ZIP...
			return True
