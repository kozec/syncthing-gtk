#!/usr/bin/env python2
"""
Syncthing-GTK - Windows related stuff.

This is only module not imported by __init__, so usage requires doing
from syncthing_gtk import windows
"""

from __future__ import unicode_literals
from syncthing_gtk.tools import IS_WINDOWS
from gi.repository import Gio, GLib, GObject
import os, sys, logging, codecs, msvcrt, win32pipe, win32api, _winreg
log = logging.getLogger("windows.py")

SM_SHUTTINGDOWN = 0x2000

def fix_localized_system_error_messages():
	"""
	Python has trouble decoding messages like
	'S?bor, ktor? u? existuje, sa ned? vytvori:'
	as they are encoded in some crazy, Windows-specific, locale-specific,
	day-in-week-specific encoding.
	
	This simply eats exceptions caused by 'ascii' codec and replaces
	non-decodable characters by question mark.
	"""
	
	def handle_error(error):
		return (u'?', error.end)
	
	codecs.register_error("strict", handle_error)

def dont_use_localization_in_gtk():
	"""
	Set's LANGUAGE environment variable to en_US, preventing
	use of localized labels on GTK stock menus and widgets.
	
	This will prevent interface from being 'half-translated' until
	real translation support is done.
	"""
	os.environ['LANGUAGE'] = 'en_US'

def os_paths_for_non_ascii_usernames():
	"""
	Replaces os.environ with custom implementation that decodes some
	fields from whatever locale Windows is using to unicode when they
	are being read and encodes them back when being set.
	Specialy handled are path-related fields (USERPROFILE, APPDATA, etc)
	and USER.
	
	Fix is applied only if os.path.expanduser("~") can't be decoded normaly.
	
	This fixes (along with other) bug in os.path.expanduser that occurs
	when user has non-ascii characters in username (or rather USERPROFILE).
	
	See http://bugs.python.org/issue13207 , may some random deity damn
	their unworthy souls -_-
	"""
	
	
	"""
	Replaces os.path.expanduser function with my own version that
	correctly handles non-ascii characters in ~ directory.
	See http://bugs.python.org/issue13207 , may some random deity damn
	their unworthy souls -_-
	
	Also replaces os.environ with dict that have fields like APPDATA,
	USERNAME (etc) decoded from whatever locale Windows is using to
	unicode.
	"""
	if "?" in os.path.expanduser("~"):
		# Yeah, Windows actually does this
		log.warn("Applying os_paths_for_non_ascii_usernames")
		if not "USERPROFILE" in os.environ:
			log.error("Sorry, You are using Windows, non-ascii character in username")
			log.error("and You don't have USERPROFILE environment variable set. Stop")
			log.error("doing at least one of named.")
			# ^^ wrapped to cmd.exe window width
			sys.exit(1)
		
		os.environ = SomeInUnicodeEnviron()
		
		"""
		os_environ = os.environ
		os.environ = []
		for x in ("USERPROFILE", "APPDATA", "USERNAME", "LOCALAPPDATA"):
			print x
			os.environ[x] = os_environ[x].decode(sys.stdout.encoding)
		for x in os_environ:
			if not x in os.environ:
				os.environ[x] = os_environ[x]
		userprofile = os.environ["USERPROFILE"]
		
		def os_path_expanduser(path):
			" ""
			Expand ~ constructs. ~user is not supported
			If %USERPROFILE%, code already crashed
			" ""
			if path.startswith("~/"):
				return os.path.join(userprofile, path[2:])
			if path.startswith("~"):
				raise ValueError("~user construct is not supported")
			return path
		
		os.path.expanduser = os_path_expanduser
		"""

def is_shutting_down():
	""" Returns True if Windows initiated shutdown process """
	return (win32api.GetSystemMetrics(SM_SHUTTINGDOWN) != 0)

class WinPopenReader:
	"""
	Reads from PIPE using GLib timers or idle_add. Emulates part of
	UnixInputStream, but its in no way even close to complete
	emulation.
	
	This is only way that I found so far to have pipe and hidden
	console window on Windows.
	"""
	
	def __init__(self, process):
		# Prepare stuff
		self._process = process
		self._waits_for_read = None
		self._buffer = ""
		self._buffer_size = 32
		self._closed = False
		self._stdouthandle = msvcrt.get_osfhandle(self._process.stdout.fileno())
		# Start reading
		GLib.idle_add(self._peek)
	
	def _peek(self):
		if self._closed:
			return False
		# Check if there is anything to read and read if available
		(read, nAvail, nMessage) = win32pipe.PeekNamedPipe(self._stdouthandle, 0)
		if nAvail >= self._buffer_size:
			data = self._process.stdout.read(self._buffer_size)
			self._buffer += data
		# If there is read_async callback and buffer has enought of data,
		# send them right away
		if not self._waits_for_read is None and len(self._buffer) > self._buffer_size:
			r = WinPopenReader.Results(self._buffer[0:self._buffer_size])
			self._buffer = self._buffer[self._buffer_size:]
			callback, data = self._waits_for_read
			self._waits_for_read = None
			callback(self, r, *data)
			GLib.idle_add(self._peek)
			return False
		GLib.timeout_add_seconds(1, self._peek)
		return False
	
	def read_bytes_async(self, size, trash, cancel, callback, data=()):
		if self._waits_for_read != None:
			raise Exception("Already reading")
		self._buffer_size = size
		self._waits_for_read = (callback, data)
	
	def read_bytes_finish(self, results):
		return results
	
	def close(self):
		self._closed = True
	
	class Results:
		""" Also serves as response object """
		def __init__(self, data):
			self._data = data
		
		def get_data(self):
			return self._data

def WinConfiguration():
	from syncthing_gtk.configuration import _Configuration as Configuration
	from syncthing_gtk.configuration import serializer
	class _WinConfiguration(Configuration):
		"""
		Configuration implementation for Windows - stores values
		in registry
		"""
		
		#@ Overrides
		def load(self):
			if os.path.exists(self.get_config_file()):
				# Copy file-based cofiguration to registry and remove
				# configuration folder
				#
				# TODO: Remove this later
				log.info("Converting old configuration to registry...")
				Configuration.load(self)
				self.convert_values()
				self.check_values()
				self.save()
				try:
					os.unlink(self.get_config_file())
					try:
						os.rmdir(self.get_config_dir())
					except Exception, e:
						# May happen, no problem here
						pass
				except Exception, e:
					# Shouldn't happen, report problem here
					log.warning("Failed to remove old config file")
					log.warning(e)
				return
			self.values = {}
			r = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, "Software\\SyncthingGTK")
			for key in Configuration.REQUIRED_KEYS:
				tp, trash = Configuration.REQUIRED_KEYS[key]
				try:
					self.values[key] = self._read(r, key, tp)
				except WindowsError:
					# Not found
					pass
			_winreg.CloseKey(r)
		
		#@ Overrides
		def save(self):
			r = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, "Software\\SyncthingGTK")
			for key in Configuration.REQUIRED_KEYS:
				tp, trash = Configuration.REQUIRED_KEYS[key]
				value = self.values[key]
				self._store(r, key, tp, value)
			_winreg.CloseKey(r)
		
		def _store(self, r, name, tp, value):
			""" Stores value in registry, handling special types """
			if tp in (unicode, str):
				_winreg.SetValueEx(r, name, 0, _winreg.REG_SZ, value.encode(sys.stdout.encoding))
			elif tp in (int, bool):
				_winreg.SetValueEx(r, name, 0, _winreg.REG_DWORD, int(value))
			elif tp in (list, tuple):
				if not value is None:	# None is default value for window_position
					_winreg.SetValueEx(r, "%s_size" % (name,), 0, _winreg.REG_DWORD, len(value))
					for i in xrange(0, len(value)):
						self._store(r, "%s_%s" % (name, i), type(value[i]), value[i])
			else:
				_winreg.SetValueEx(r, name, 0, _winreg.REG_SZ, serializer(value).encode(sys.stdout.encoding))
		
		def _read(self, r, name, tp):
			""" Reads value from registry, handling special types """
			if tp in (list, tuple):
				size, trash = _winreg.QueryValueEx(r, "%s_size" % (name,))
				value = []
				for i in xrange(0, size):
					value.append(self._read(r, "%s_%s" % (name, i), None))
				return value
			else:
				value, keytype = _winreg.QueryValueEx(r, name)
				return value.decode(sys.stdout.encoding)
		
	return _WinConfiguration

_os_environ = os.environ
class SomeInUnicodeEnviron:
	""" See os_paths_for_non_ascii_usernames """
	HANDLED = ("USERPROFILE", "APPDATA", "USERNAME", "LOCALAPPDATA", "USER", "USERNAME")
	def __setitem__(self, key, item): 
		if key in SomeInUnicodeEnviron.HANDLED:
			item = unicode(item).encode(sys.stdout.encoding)
		_os_environ[key] = item
	
	def __getitem__(self, key): 
		if key in SomeInUnicodeEnviron.HANDLED:
			print "TRANSLATING", key, _os_environ[key], _os_environ[key].decode(sys.stdout.encoding)
			return _os_environ[key].decode(sys.stdout.encoding)
		print "not translating", key
		return _os_environ[key]
	
	def get(self, key, default):
		if key in self:
			return self[key]
		return default
	
	def set(self, key, value):
		self[key] = value
	
	def __len__(self): 
		return len(_os_environ)
	
	def __delitem__(self, key): 
		del self._os_environ[key]
	
	def keys(self): 
		return _os_environ.keys()
	
	def values(self):
		return [ self[x] for x in _os_environ ]
		
	def __cmp__(self, dict):
		return cmp(_os_environ, dict)
	
	def __contains__(self, item):
		return item in _os_environ
	
	def __iter__(self):
		return iter(_os_environ)
	
	def __call__(self):
		return _os_environ
