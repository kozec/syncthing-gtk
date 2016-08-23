#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Syncthing-GTK - StatusIcon

"""
from __future__ import unicode_literals

import locale
import os
import sys
import logging

from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gtk

from syncthing_gtk.tools import IS_UNITY, IS_KDE, IS_CINNAMON
from syncthing_gtk.tools import _ # gettext function

log = logging.getLogger("StatusIcon")


#                | KDE5            | MATE      | Unity      | Cinnamon   | Cairo-Dock (classic) | Cairo-Dock (modern) | KDE4      |
#----------------+-----------------+-----------+------------+------------+----------------------+---------------------+-----------+
# StatusIconKDE4 | excellent       | usable³   | very good⁵ | usable³    | usable³              | excellent           | excellent |
# StatusIconQt5  | very good (KF5) | -         | -          | -          | -                    | -                   | -         |
# StatusIconAppI | good²           | none      | excellent  | none       | none                 | excellent           | good²     |
# StatusIconGTK3 | none            | excellent | none       | very good¹ | very good¹           | none                | good⁴     |
#
# Notes:
#  - StatusIconQt5:
#     - It's pretty unstable and leads to crashes
#     - Only tested on Qt 5.4 which only supports Qt5 through a KDE frameworks plugin
#  - StatusIconAppIndicator does not implement any fallback (but the original libappindicator did)
#  - Markers:
#     ¹ Icon cropped
#     ² Does not support left-click
#     ³ It works, but looks ugly and does not support left-click
#     ⁴ Does not support icon states
#     ⁵ For some menu items the standard GTK icons are used instead of the monotone ones


class StatusIcon(GObject.GObject):
	"""
	Base class for all status icon backends
	"""
	TRAY_TITLE     = _("Syncthing")
	
	__gsignals__ = {
		b"clicked": (GObject.SIGNAL_RUN_FIRST, None, ()),
	}
	
	__gproperties__ = {
		b"active": (
			GObject.TYPE_BOOLEAN,
			"is the icon user-visible?",
			"does the icon back-end think that anything is might be shown to the user?",
			True,
			GObject.PARAM_READWRITE
		)		
	}
	
	def __init__(self, icon_path, popupmenu, force=False):
		GObject.GObject.__init__(self)
		self.__icon_path = os.path.normpath(os.path.abspath(icon_path))
		self.__popupmenu = popupmenu
		self.__active    = True
		self.__visible   = False
		self.__hidden    = False
		self.__icon      = "si-syncthing-unknown"
		self.__text      = ""
		self.__force     = force
	
	def get_active(self):
		"""
		Return whether there is at least a chance that the icon might be shown to the user
		
		If this returns `False` then the icon will definetely not be shown, but if it returns `True` it doesn't have to
		be visible...
		
		<em>Note:</em> This value is not directly influenced by calling `hide()` and `show()`.
		
		@return {bool}
		"""
		return self.get_property("active")
	
	def set(self, icon=None, text=None):
		"""
		Set the status icon image and descriptive text
		
		If either of these are `None` their previous value will be used.
		
		@param {String} icon
		       The name of the icon to show (i.e. `si-syncthing-idle`)
		@param {String} text
		       Some text that indicates what the application is currently doing (generally this be used for the tooltip)
		"""
		if IS_KDE and isinstance(self, StatusIconDBus) and not icon.startswith("si-syncthing"):
			# KDE seems to be the only platform that has proper support for icon states
			# (all other implementations just hide the icon completely when its passive)
			self.__visible = False
		elif not icon.endswith("-0"): # si-syncthing-0
			# Ignore first syncing icon state to prevent the icon from flickering
			# into the main notification bar during initialization
			self.__visible = True
		
		if self.__hidden:
			self._set_visible(False)
		else:
			self._set_visible(self.__visible)
	
	def hide(self):
		"""
		Hide the icon
		
		This method tries its best to ensure the icon is hidden, but there are no guarantees as to how use well its
		going to work.
		"""
		self.__hidden = True
		self._set_visible(False)
	
	def show(self):
		"""
		Show a previously hidden icon
		
		This method tries its best to ensure the icon is hidden, but there are no guarantees as to how use well its
		going to work.
		"""
		self.__hidden = False
		self._set_visible(self.__visible)
	
	
	def _is_forced(self):
		return self.__force
	
	def _on_click(self, *a):
		self.emit("clicked")
	
	def _get_icon(self, icon=None):
		"""
		@internal
		
		Use `set()` instead.
		"""
		if icon:
			self.__icon = icon
		return self.__icon
	
	def _get_text(self, text=None):
		"""
		@internal
		
		Use `set()` instead.
		"""
		if text:
			self.__text = text
		return self.__text
	
	def _get_popupmenu(self):
		"""
		@internal
		"""
		return self.__popupmenu
	
	def _set_visible(self, visible):
		"""
		@internal
		"""
		pass

	def do_get_property(self, property):
		if property.name == "active":
			return self.__active
		else:
			raise AttributeError("Unknown property %s" % property.name)
	
	def do_set_property(self, property, value):
		if property.name == "active":
			self.__active = value
		else:
			raise AttributeError("unknown property %s" % property.name)


class StatusIconDummy(StatusIcon):
	"""
	Dummy status icon implementation that does nothing
	"""
	def __init__(self, *args, **kwargs):
		StatusIcon.__init__(self, *args, **kwargs)
		
		# Pretty unlikely that this will be visible...
		self.set_property("active", False)
	
	def set(self, icon=None, text=None):
		StatusIcon.set(self, icon, text)
		
		self._get_icon(icon)
		self._get_text(text)


class StatusIconGTK3(StatusIcon):
	"""
	Gtk.StatusIcon based status icon backend
	"""
	def __init__(self, *args, **kwargs):
		StatusIcon.__init__(self, *args, **kwargs)
		
		if not self._is_forced():
			if IS_UNITY:
				# Unity fakes SysTray support but actually hides all icons...
				raise NotImplementedError
		
			if IS_KDE:
				# While the GTK backend works fine on KDE 4, the StatusIconKDE4 backend will achieve better
				# results and should be available on any standard KDE 4 installation
				# (since several KDE applications depend on it)
				raise NotImplementedError
		
		self._tray = Gtk.StatusIcon()
		
		self._tray.connect("activate", self._on_click)
		self._tray.connect("popup-menu", self._on_rclick)
		self._tray.connect("notify::embedded", self._on_embedded_change)
		
		self._tray.set_visible(True)
		self._tray.set_name("syncthing-gtk")
		self._tray.set_title(self.TRAY_TITLE)
		
		# self._tray.is_embedded() must be called asynchronously
		# See: http://stackoverflow.com/a/6365904/277882
		GLib.idle_add(self._on_embedded_change)
	
	def set(self, icon=None, text=None):
		StatusIcon.set(self, icon, text)
		
		self._tray.set_from_icon_name(self._get_icon(icon))
		self._tray.set_tooltip_text(self._get_text(text))
	
	def _on_embedded_change(self, *args):
		# Without an icon update at this point GTK might consider the icon embedded and visible even through
		# it can't actually be seen...
		self._tray.set_from_file(self._get_icon())
		
		# An invisible tray icon will never be embedded but it also should not be replaced
		# by a fallback icon
		is_embedded = self._tray.is_embedded() or not self._tray.get_visible() or IS_CINNAMON
		if is_embedded != self.get_property("active"):
			self.set_property("active", is_embedded)
	
	def _on_rclick(self, si, button, time):
		self._get_popupmenu().popup(None, None, None, None, button, time)
	
	def _set_visible(self, active):
		StatusIcon._set_visible(self, active)
		
		self._tray.set_visible(active)


class StatusIconDBus(StatusIcon):
	pass


class StatusIconQt(StatusIconDBus):
	"""
	Base implementation for all Qt-based backends that provides GMenu to QMenu conversion services
	"""
	def _make_qt_action(self, menu_child_gtk, menu_qt):
		# This is a separate function to make sure that the Qt callback function are executed
		# in the correct `locale()` context and do net trigger events on the wrong Gtk menu item
		
		# Create menu item
		action = self._qt_types["QAction"](menu_qt)
		
		# Convert item to separator if appropriate
		action.setSeparator(isinstance(menu_child_gtk, Gtk.SeparatorMenuItem))
		
		# Copy sensitivity
		def set_sensitive(*args):
			action.setEnabled(menu_child_gtk.is_sensitive())
		menu_child_gtk.connect("notify::sensitive", set_sensitive)
		set_sensitive()
		
		# Copy checkbox state
		if isinstance(menu_child_gtk, Gtk.CheckMenuItem):
			action.setCheckable(True)
			def _set_visible(*args):
				action.setChecked(menu_child_gtk.get_active())
			menu_child_gtk.connect("notify::active", _set_visible)
			_set_visible()
		
		# Copy icon
		if isinstance(menu_child_gtk, Gtk.ImageMenuItem):
			def set_image(*args):
				image = menu_child_gtk.get_image()
				if image and image.get_storage_type() == Gtk.ImageType.PIXBUF:
					# Converting GdkPixbufs to QIcons might be a bit inefficient this way,
					# but it requires only very little code and looks very stable
					png_buffer = image.get_pixbuf().save_to_bufferv("png", [], [])[1]
					image      = self._qt_types["QImage"].fromData(png_buffer)
					pixmap     = self._qt_types["QPixmap"].fromImage(image)
					
					action.setIcon(self._qt_types["QIcon"](pixmap))
				elif image:
					icon_name = None
					if image.get_storage_type() == Gtk.ImageType.ICON_NAME:
						icon_name = image.get_icon_name()[0]
					if image.get_storage_type() == Gtk.ImageType.STOCK:
						icon_name = image.get_stock()[0]
					
					action.setIcon(self._get_icon_by_name(icon_name))
				else:
					action.setIcon(self._get_icon_by_name(None))
			menu_child_gtk.connect("notify::image", set_image)
			set_image()
		
		# Set label
		def set_label(*args):
			label = menu_child_gtk.get_label()
			if isinstance(menu_child_gtk, Gtk.ImageMenuItem) and menu_child_gtk.get_use_stock():
				label = Gtk.stock_lookup(label).label
			if isinstance(label, str):
				label = label.decode(locale.getpreferredencoding())
			if menu_child_gtk.get_use_underline():
				label = label.replace("_", "&")
			action.setText(label)
		menu_child_gtk.connect("notify::label", set_label)
		set_label()
		
		# Add submenus
		def set_popupmenu(*args):
			action.setMenu(self._get_popupmenu(menu_child_gtk.get_submenu()))
		menu_child_gtk.connect("notify::popupmenu", set_popupmenu)
		set_popupmenu()
		
		# Hook up Qt signals to their GTK counterparts
		action.triggered.connect(lambda *a: menu_child_gtk.emit("activate"))
		
		return action
	
	def _get_icon_by_name(self, icon_name):
		if icon_name:
			icon_file = self._gtk_icon_theme.lookup_icon(icon_name, 48, 0)
			if not icon_file:
				log.info("Skipping unknown icon file: %s" % (icon_name))
				return self._qt_types["QIcon"]()
			
			icon_path = icon_file.get_filename()
			if not icon_path:
				return self._qt_types["QIcon"]()
			
			icon_dir, icon_basename = os.path.split(os.path.realpath(icon_path))
		
			# If we don't resolve all icon names (i.e.: realpath) before passing them to Qt
			# SOME OF THEM will be dropped (especially if their name started with "gtk-" originally)
			icon_name = os.path.splitext(icon_basename)[0]
		
			# Make sure that Qt can find this icon by its name, by adding
			# the directory to the icon theme search path
			# This extra step is required because we have to set the application
			# style to "motif" during Qt initialization
			if icon_dir not in self._qt_types["QIcon"].themeSearchPaths():
				theme_search_paths = self._qt_types["QIcon"].themeSearchPaths()
				theme_search_paths.prepend(icon_dir)
				self._qt_types["QIcon"].setThemeSearchPaths(theme_search_paths)
		
			return self._qt_types["QIcon"].fromTheme(icon_name, self._qt_types["QIcon"](icon_path))
		
		return self._qt_types["QIcon"]()
	
	def _set_qt_types(self, **kwargs):
		self._gtk_icon_theme = Gtk.IconTheme.get_default()
		
		self._qt_types = kwargs
	
	def _get_popupmenu(self, menu_gtk=False):
		menu_gtk = menu_gtk if menu_gtk is not False else StatusIcon._get_popupmenu(self)
		if not menu_gtk:
			return None
		
		menu_qt = self._qt_types["QMenu"]()
		for menu_child_gtk in menu_gtk.get_children():
			menu_qt.addAction(self._make_qt_action(menu_child_gtk, menu_qt))
		
		return menu_qt

class StatusIconKDE4(StatusIconQt):
	"""
	PyKDE5.kdeui.KStatusNotifierItem based status icon backend
	"""
	def __init__(self, *args, **kwargs):
		StatusIcon.__init__(self, *args, **kwargs)
		
		try:
			import PyQt4.Qt     as qt
			import PyQt4.QtGui  as qtgui
			import PyKDE4.kdeui as kdeui
			
			self._set_qt_types(
				QAction = qtgui.QAction,
				QMenu   = kdeui.KMenu,
				QIcon   = qtgui.QIcon,
				QImage  = qtgui.QImage,
				QPixmap = qtgui.QPixmap
			)
			
			self._status_active  = kdeui.KStatusNotifierItem.Active
			self._status_passive = kdeui.KStatusNotifierItem.Passive
		except ImportError:
			raise NotImplementedError
		
		if b"GNOME_DESKTOP_SESSION_ID" in os.environ:
			del os.environ[b"GNOME_DESKTOP_SESSION_ID"]
		# Create Qt GUI application (required by the KdeUI libraries)
		# We force "--style=motif" here to prevent Qt to load platform theme
		# integration libraries for "Gtk+" style that cause GTK 3 to abort like this:
		#   Gtk-ERROR **: GTK+ 2.x symbols detected. Using GTK+ 2.x and GTK+ 3 in the same process is not supported
		self._qt_app = qt.QApplication([sys.argv[0], "--style=motif"])
		
		# Keep reference to KMenu object to prevent SegFault...
		self._kde_menu = self._get_popupmenu()
		
		self._tray = kdeui.KStatusNotifierItem("syncthing-gtk", None)
		self._tray.setStandardActionsEnabled(False) # Prevent KDE quit item from showing
		self._tray.setContextMenu(self._kde_menu)
		self._tray.setCategory(kdeui.KStatusNotifierItem.ApplicationStatus)
		self._tray.setTitle(self.TRAY_TITLE)
		
		self._tray.activateRequested.connect(self._on_click)
	
	def _set_visible(self, active):
		StatusIcon._set_visible(self, active)
		
		self._tray.setStatus(self._status_active if active else self._status_passive)
	
	def set(self, icon=None, text=""):
		StatusIcon.set(self, icon, text)
		
		self._tray.setIconByName(self._get_icon(icon))
		self._tray.setToolTip(self._get_icon(icon), self._get_text(text), "")


class StatusIconAppIndicator(StatusIconDBus):
	"""
	Unity's AppIndicator3.Indicator based status icon backend
	"""
	def __init__(self, *args, **kwargs):
		StatusIcon.__init__(self, *args, **kwargs)
		
		try:
			from gi.repository import AppIndicator3 as appindicator
			
			self._status_active  = appindicator.IndicatorStatus.ACTIVE
			self._status_passive = appindicator.IndicatorStatus.PASSIVE
		except ImportError:
			raise NotImplementedError
		
		category = appindicator.IndicatorCategory.APPLICATION_STATUS
		# Whatever icon is set here will be used as a tooltip icon during the entire time to icon is shown
		self._tray = appindicator.Indicator.new("syncthing-gtk", self._get_icon(), category)
		self._tray.set_menu(self._get_popupmenu())
		self._tray.set_title(self.TRAY_TITLE)
	
	def _set_visible(self, active):
		StatusIcon._set_visible(self, active)
		
		self._tray.set_status(self._status_active if active else self._status_passive)
	
	def set(self, icon=None, text=None):
		StatusIcon.set(self, icon, text)
		
		self._tray.set_icon_full(self._get_icon(icon), self._get_text(text))



class StatusIconProxy(StatusIcon):
	def __init__(self, *args, **kwargs):
		StatusIcon.__init__(self, *args, **kwargs)
		
		self._arguments  = (args, kwargs)
		self._status_fb  = None
		self._status_gtk = None
		self.set("si-syncthing-unknown", "")
		
		# Do not ever force-show indicators when they do not think they'll work
		if "force" in self._arguments[1]:
			del self._arguments[1]["force"]
		
		try:
			# Try loading GTK native status icon
			self._status_gtk = StatusIconGTK3(*args, **kwargs)
			self._status_gtk.connect(b"clicked",        self._on_click)
			self._status_gtk.connect(b"notify::active", self._on_notify_active_gtk)
			self._on_notify_active_gtk()
			
			log.info("Using backend StatusIconGTK3 (primary)")
		except NotImplementedError:
			# Directly load fallback implementation
			self._load_fallback()
	
	def _on_click(self, *args):
		self.emit(b"clicked")
	
	def _on_notify_active_gtk(self, *args):
		if self._status_fb:
			# Hide fallback icon if GTK icon is active and vice-versa
			if self._status_gtk.get_active():
				self._status_fb.hide()
			else:
				self._status_fb.show()
		elif not self._status_gtk.get_active():
			# Load fallback implementation
			self._load_fallback()
	
	def _on_notify_active_fb(self, *args):
		active = False
		if self._status_gtk and self._status_gtk.get_active():
			active = True
		if self._status_fb and self._status_fb.get_active():
			active = True
		self.set_property("active", active)
	
	def _load_fallback(self):
		if IS_UNITY:
			status_icon_backends = [StatusIconAppIndicator, StatusIconKDE4, StatusIconDummy]
		else:
			status_icon_backends = [StatusIconKDE4, StatusIconAppIndicator, StatusIconDummy]
		
		if not self._status_fb:
			for StatusIconBackend in status_icon_backends:
				try:
					self._status_fb = StatusIconBackend(*self._arguments[0], **self._arguments[1])
					self._status_fb.connect(b"clicked",        self._on_click)
					self._status_fb.connect(b"notify::active", self._on_notify_active_fb)
					self._on_notify_active_fb()
					
					log.warning("StatusIcon: Using backend %s (fallback)" % StatusIconBackend.__name__)
					break
				except NotImplementedError:
					continue
		
			# At least the dummy backend should have been loaded at this point...
			assert self._status_fb
		
		# Update fallback icon
		self.set(self._icon, self._text)
	
	def set(self, icon=None, text=None):
		self._icon = icon
		self._text = text
		
		if self._status_gtk:
			self._status_gtk.set(icon, text)
		if self._status_fb:
			self._status_fb.set(icon, text)
	
	def hide(self):
		if self._status_gtk:
			self._status_gtk.hide()
		if self._status_fb:
			self._status_fb.hide()
	
	def show(self):
		if self._status_gtk:
			self._status_gtk.show()
		if self._status_fb:
			self._status_fb.show()

def get_status_icon(*args, **kwargs):
	# Try selecting backend based on environment variable
	if "SYNCTHING_STATUS_BACKEND" in os.environ:
		kwargs["force"] = True
		
		status_icon_backend_name = "StatusIcon%s" % (os.environ.get("SYNCTHING_STATUS_BACKEND"))
		if status_icon_backend_name in globals():
			try:
				status_icon = globals()[status_icon_backend_name](*args, **kwargs)
				log.info("StatusIcon: Using requested backend %s" % (status_icon_backend_name))
				return status_icon
			except NotImplementedError:
				log.error("StatusIcon: Requested backend %s is not supported" % (status_icon_backend_name))
		else:
			log.error("StatusIcon: Requested backend %s does not exist" % (status_icon_backend_name))
		
		return StatusIconDummy(*args, **kwargs)
	
	# Use proxy backend to determine the correct backend while the application is running
	return StatusIconProxy(*args, **kwargs)
