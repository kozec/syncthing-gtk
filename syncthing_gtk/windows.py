#!/usr/bin/env python2
"""
Syncthing-GTK - Windows related stuff.

This is only module not imported by __init__, so usage requires doing
from syncthing_gtk import windows
"""

from __future__ import unicode_literals
from syncthing_gtk.tools import IS_WINDOWS
from gi.repository import Gio, GLib, GObject
import os, codecs, msvcrt, win32pipe, _winreg

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
		if error.encoding != "ascii":
			# Don't interfere with others
			raise error
		return (u'?', error.end)
	
	codecs.register_error("strict", handle_error)

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
				print "Note: Converting old configuration to registry..."
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
					print >>sys.stderr, "Warning: Failed to remove old config file"
					print >>sys.stderr, e
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
				_winreg.SetValueEx(r, name, 0, _winreg.REG_SZ, str(value))
			elif tp in (int, bool):
				_winreg.SetValueEx(r, name, 0, _winreg.REG_DWORD, int(value))
			elif tp in (list, tuple):
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
				return value
		
	return _WinConfiguration
