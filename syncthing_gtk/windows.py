#!/usr/bin/env python2
"""
Syncthing-GTK - Windows related stuff.

This is only module not imported by __init__, so usage requires doing
from syncthing_gtk import windows
"""

from __future__ import unicode_literals
from syncthing_gtk.tools import IS_WINDOWS, hex2color
from gi.repository import Gtk, Gdk, Gio, GLib, GObject
from ctypes import c_int, CDLL, Structure, windll, pythonapi
from ctypes import c_void_p, py_object, byref
import os, logging, cairo, codecs, msvcrt, win32pipe, _winreg

log = logging.getLogger("windows.py")

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
				_winreg.SetValueEx(r, name, 0, _winreg.REG_SZ, str(value))
			elif tp in (int, bool):
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
				return value
		
	return _WinConfiguration

def enable_aero_glass(window, root_element, iconpath):
	"""
	Enables Aero Glass effect on main application Window and changes
	some colors to make text readable on transparent background.
	"""
	# Prepare stuff
	class MARGINS(Structure):
		_fields_ = [("cxLeftWidth", c_int),
				  ("cxRightWidth", c_int),
				  ("cyTopHeight", c_int),
				  ("cyBottomHeight", c_int)
				 ]
	margins = MARGINS(1, 1, 1, -1)
	dwm = windll.dwmapi
	
	# Get me some glass
	window.realize()
	pythonapi.PyCapsule_GetPointer.restype = c_void_p
	pythonapi.PyCapsule_GetPointer.argtypes = [py_object]
	gpointer = pythonapi.PyCapsule_GetPointer(window.get_window().__gpointer__, None)  
	gdkdll = CDLL ("libgdk-3-0.dll")
	hwnd = gdkdll.gdk_win32_window_get_handle(gpointer)
	dwm.DwmExtendFrameIntoClientArea(hwnd, byref(margins))
	window.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0,0,0,0))
	
	# Put main widget to frame with border & background
	class WeirLookingFrame(Gtk.Frame):
		BORDER_COLOR_1 = hex2color("596979FE")
		BORDER_COLOR_2 = hex2color("000050FE")
		# BORDER_COLOR_2 = hex2color("FF0000FE")
		def __init__(self, child):
			Gtk.Frame.__init__(self)
			self.background = cairo.ImageSurface.create_from_png(os.path.join(
					iconpath, "..", "images", "aero-glass-background.png"))
			self.set_shadow_type(Gtk.ShadowType.NONE)
			self.add(child)
		
		def draw_line(self, cr, x1, y1, x2, y2):
			cr.move_to(x1, y1)
			cr.line_to(x2, y2)
			cr.stroke()
		
		def do_draw(self, cr):
			allocation = self.get_allocation()
			# Draw outer border
			cr.save()
			cr.set_line_width(1)
			cr.set_source_rgba(*WeirLookingFrame.BORDER_COLOR_1)
			self.draw_line(cr, 1, 0, allocation.width - 1, 0)
			self.draw_line(cr, 0, 1, 0, allocation.height - 1)
			self.draw_line(cr, allocation.width, 1, allocation.width, allocation.height - 1)
			self.draw_line(cr, 1, allocation.height, allocation.width - 1, allocation.height)
			# Draw inner border
			cr.set_source_rgba(*WeirLookingFrame.BORDER_COLOR_2)
			cr.rectangle(1, 1, allocation.width - 2, allocation.height - 2)
			cr.clip()
			cr.paint()
			# Draw background
			scale = max(
					1.0,
					float(allocation.width - 2) / float(self.background.get_width()),
					float(allocation.height - 2) / float(self.background.get_height()))
			cr.rectangle(2, 2, allocation.width - 4, allocation.height - 4)
			cr.clip()
			cr.scale(scale, scale)
			cr.translate(1, 1)
			cr.set_source_surface(self.background, 0, 0)
			cr.paint()
			cr.restore()
			# Draw child widget
			self.propagate_draw(self.get_children()[0], cr)
	
	p = root_element.get_parent()
	p.remove(root_element)
	p.set_border_width(0)
	f = WeirLookingFrame(root_element)
	p.add(f)
	f.set_border_width(3)
	f.set_vexpand(True)
	f.set_visible(True)
	
	# Make buttons transparent
	CSS = """
		GtkButton, GtkButton:hover {
			background-color: rgba(0,0,0,0);
			background-image: none;
			border-color: rgba(0, 0, 0, 0);
			border-radius: 32;
		}
	"""
	cssprovider = Gtk.CssProvider()
	cssprovider.load_from_data(str(CSS))
	screen = Gdk.Screen.get_default()
	sc = Gtk.StyleContext()
	sc.add_provider_for_screen(screen, cssprovider,
			Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

def make_dragable(window, widget):
	""" Makes window dragable by draging specified widget """
	# Make window dragable by header
	def on_header_drag(w, event):
		if event.button == 1:
			window.begin_move_drag(event.button, 
				event.x_root, event.y_root, event.time)
	widget.connect("button-press-event", on_header_drag)
