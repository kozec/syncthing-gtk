#!/usr/bin/env python2
"""
Syncthing-GTK - Windows related stuff.

This is only module not imported by __init__, so usage requires doing
from syncthing_gtk import windows
"""

from __future__ import unicode_literals
from syncthing_gtk.tools import IS_WINDOWS, get_config_dir
from gi.repository import Gio, GLib, GObject, Gtk, Gdk
import os, sys, logging, codecs, msvcrt, win32pipe, win32api, _winreg
import win32process
from win32com.shell import shell, shellcon
log = logging.getLogger("windows.py")

SM_SHUTTINGDOWN = 0x2000
ST_INOTIFY_EXE = "syncthing-inotify-v0.8.3.exe"

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

def enable_localization():
	"""
	Updates environment variables with windows locale.
	"""
	loc = "en"
	domain = "syncthing-gtk"
	try:
		import locale
		loc = locale.getdefaultlocale()[0]
	except Exception, e:
		pass
	if not 'LANGUAGE' in os.environ:
		os.environ['LANGUAGE'] = loc

def is_shutting_down():
	""" Returns True if Windows initiated shutdown process """
	return (win32api.GetSystemMetrics(SM_SHUTTINGDOWN) != 0)

def nice_to_priority_class(nice):
	""" Converts nice value to windows priority class """
	if nice <= -20:	# PRIORITY_HIGHEST
		return win32process.HIGH_PRIORITY_CLASS,
	if nice <= -10:	# PRIORITY_HIGH
		return win32process.ABOVE_NORMAL_PRIORITY_CLASS
	if nice >= 10:	# PRIORITY_LOW
		return win32process.BELOW_NORMAL_PRIORITY_CLASS
	if nice >= 19:	# PRIORITY_LOWEST
		return win32process.IDLE_PRIORITY_CLASS
	# PRIORITY_NORMAL
	return win32process.NORMAL_PRIORITY_CLASS

def override_menu_borders():
	""" Loads custom CSS to create borders around popup menus """
	style_provider = Gtk.CssProvider()
	style_provider.load_from_data(b"""
		.menu {
			border-image: linear-gradient(to top,
										  alpha(@borders, 0.80),
										  alpha(@borders, 0.60) 33%,
										  alpha(@borders, 0.50) 66%,
										  alpha(@borders, 0.15)) 2 2 2 2/ 2px 2px 2px 2px;
		}

		.menubar .menu {
			border-image: linear-gradient(to top,
										  alpha(@borders, 0.80),
										  alpha(@borders, 0.60) 33%,
										  alpha(@borders, 0.50) 66%,
										  transparent 99%) 2 2 2 2/ 2px 2px 2px 2px;
		}
		""")
	Gtk.StyleContext.add_provider_for_screen(
		Gdk.Screen.get_default(), 
		style_provider,     
		Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
	)

def get_unicode_home():
	return shell.SHGetFolderPath(0, shellcon.CSIDL_LOCAL_APPDATA, None, 0)

class WinPopenReader:
	"""
	Reads from PIPE using GLib timers or idle_add. Emulates part of
	UnixInputStream, but its in no way even close to complete
	emulation.
	
	This is only way that I found so far to have pipe and hidden
	console window on Windows.
	"""
	
	def __init__(self, pipe):
		# Prepare stuff
		self._pipe = pipe
		self._waits_for_read = None
		self._buffer = ""
		self._buffer_size = 32
		self._closed = False
		self._osfhandle = msvcrt.get_osfhandle(self._pipe.fileno())
		# Start reading
		GLib.idle_add(self._peek)
	
	def _peek(self):
		if self._closed:
			return False
		# Check if there is anything to read and read if available
		(read, nAvail, nMessage) = win32pipe.PeekNamedPipe(self._osfhandle, 0)
		if nAvail >= self._buffer_size:
			data = self._pipe.read(self._buffer_size)
			self._buffer += data
		# If there is read_async callback and buffer has some data,
		# send them right away
		if not self._waits_for_read is None and len(self._buffer) > 0:
			r = WinPopenReader.Results(self._buffer)
			self._buffer = ""
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
	from syncthing_gtk.configuration import _Configuration
	from syncthing_gtk.configuration import serializer
	class _WinConfiguration(_Configuration):
		"""
		Configuration implementation for Windows - stores values
		in registry
		"""
		
		#@ Overrides
		def load(self):
			self.values = {}
			r = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, "Software\\SyncthingGTK")
			for key in _Configuration.REQUIRED_KEYS:
				tp, trash = _Configuration.REQUIRED_KEYS[key]
				try:
					self.values[key] = self._read(r, key, tp)
				except WindowsError:
					# Not found
					pass
			_winreg.CloseKey(r)
		
		#@ Overrides
		def save(self):
			r = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, "Software\\SyncthingGTK")
			for key in _Configuration.REQUIRED_KEYS:
				tp, trash = _Configuration.REQUIRED_KEYS[key]
				value = self.values[key]
				self._store(r, key, tp, value)
			_winreg.CloseKey(r)
		
		def _store(self, r, name, tp, value):
			""" Stores value in registry, handling special types """
			if tp in (unicode, str):
				_winreg.SetValueEx(r, name, 0, _winreg.REG_SZ, str(value))
			elif tp in (int, bool):
				value = int(value)
				if value > 0xFFFF:
					raise ValueError("Overflow")
				if value < 0:
					# This basicaly prevents storing anything >0xFFFF to registry.
					# Luckily, that shouldn't be needed, largest thing stored as int is 20
					value = 0xFFFF + (-value)
				_winreg.SetValueEx(r, name, 0, _winreg.REG_DWORD, int(value))
			elif tp in (list, tuple):
				if not value is None:	# None is default value for window_position
					_winreg.SetValueEx(r, "%s_size" % (name,), 0, _winreg.REG_DWORD, len(value))
					for i in xrange(0, len(value)):
						self._store(r, "%s_%s" % (name, i), type(value[i]), value[i])
			else:
				_winreg.SetValueEx(r, name, 0, _winreg.REG_SZ, serializer(value))
		
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
				if type(value) == int and value > 0xFFFF:
					value = - (value - 0xFFFF)
				return value
		
	return _WinConfiguration()

def WinWatcher():
	if hasattr(sys, "frozen"):
		path = os.path.dirname(unicode(sys.executable))
	else:
		import __main__
		path = os.path.dirname(__main__.__file__)
	exe = os.path.join(path, ST_INOTIFY_EXE)
	
	from daemonprocess import DaemonProcess
	class _WinWatcher:
		"""
		Filesystem watcher implementation for Windows. Passes watched
		directories to syncthing-notify executable ran on background.
		
		Available only if executable is found in same folder as
		syncthing-gtk.exe is.
		"""
		
		def __init__(self, app, daemon):
			self.watched_ids = []
			self.app = app
			self.proc = None
		
		def watch(self, id, path):
			self.watched_ids += [id]
		
		def kill(self):
			""" Cancels & deallocates everything """
			self.watched_ids = []
			if not self.proc is None:
				self.proc.kill()
			self.proc = None
		
		def start(self):
			if not self.proc is None:
				self.proc.kill()
			if len(self.watched_ids) > 0:
				self.proc = DaemonProcess([
					exe,
					"-home", os.path.join(get_config_dir(), "syncthing"),
					"-folders", ",".join(self.watched_ids)
					])
				self.proc.connect("exit", self._on_exit)
				self.proc.connect("failed", self._on_failed)
				log.info("Starting syncthing-inotify for %s" % (",".join(self.watched_ids)))
				self.proc.start()
		
		def _on_exit(self, proc, code):
			log.warning("syncthing-inotify exited with code %s" % (code,))
		
		def _on_failed(self, proc, error):
			log.error("Failed to start syncthing-inotify: %s" % (error,))
			self.proc = None
	
	if os.path.exists(exe):
		return _WinWatcher
	else:
		return None

