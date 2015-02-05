#!/usr/bin/env python2
"""
Syncthing-GTK - StatusIcon

"""

from __future__ import unicode_literals
from gi.repository import Gtk, GObject
from syncthing_gtk.tools import IS_UNITY, IS_KDE5
import os, sys

# Why the hell does ubuntu use own notifications system?
THE_HELL, HAS_INDICATOR = False, False
if IS_UNITY or IS_KDE5:
	THE_HELL = True
	try:
		from gi.repository import AppIndicator3 as appindicator
		HAS_INDICATOR = True
	except ImportError: pass

_ = lambda (a) : a

class StatusIcon(GObject.GObject):
	"""
	StatusIcon wrapper
	
	List of signals:
		clicked ()
			Emited when user left-clicks on icon. Except, in Ubuntu with
			Unity desktop, left clicking opens menu and this event is
			never fired.
	"""
	
	__gsignals__ = {
			b"clicked"			: (GObject.SIGNAL_RUN_FIRST, None, ()),
		}
	
	def __init__(self, icon_path, popupmenu):
		GObject.GObject.__init__(self)
		self._icon_path = os.path.normpath(os.path.abspath(icon_path))
		self._popupmenu = popupmenu
		self._si = None
		self._text = ""
	
	def _create_icon(self, icon, text):
		if THE_HELL and HAS_INDICATOR:
			self._si = appindicator.Indicator.new_with_path(
								"syncthing-gtk",
								icon,
								appindicator.IndicatorCategory.APPLICATION_STATUS,
								self._icon_path
								)
			self._si.set_status(appindicator.IndicatorStatus.ACTIVE)
			self._si.set_menu(self._popupmenu)
		else:
			self._si = Gtk.StatusIcon.new_from_file(os.path.join(self._icon_path, icon))
			self._si.set_title(text)
			self._si.connect("activate", self._cb_click)
			self._si.connect("popup-menu", self._cb_rclick)
	
	def _cb_click(self, *a):
		self.emit("clicked")
	
	def _cb_rclick(self, si, button, time):
		self._popupmenu.popup(None, None, None, None, button, time)
	
	def hide(self):
		"""
		Hides status icon. This is workaround for Windows not doing this
		automatically when process exits and is not generaly needed on
		X/Unity
		"""
		if THE_HELL and HAS_INDICATOR:
			pass
		else:
			self._si.set_visible(False)
	
	def set(self, icon, text=None):
		# TODO: That text part on ubuntu...
		if text == None:
			text = self._text
		else:
			self._text = text
		if self._si == None:
			self._create_icon(icon, text)
		else:
			if THE_HELL and HAS_INDICATOR:
				self._si.set_icon(icon)
			else:
				self._si.set_from_file(os.path.join(self._icon_path, "%s.png" % (icon,)))
				self._si.set_title(text)
