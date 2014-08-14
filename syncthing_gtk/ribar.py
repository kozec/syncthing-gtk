#!/usr/bin/env python2
"""
Syncthing-GTK - RIBar

Infobar wrapped in Revealer, for greater justice
"""
from __future__ import unicode_literals
from gi.repository import Gtk, GLib, GObject
from syncthing_gtk import DEBUG
import os
_ = lambda (a) : a

class RIBar(Gtk.Revealer):
	"""
	Infobar wrapped in Revealer
	
	Signals:
		Everything from Gtk.Revealer, plus:
		close()
			emitted when the user dismisses the info bar
		response(response_id)
			Emitted when an action widget (button) is clicked
	"""
	__gsignals__ = {
			# response(response_id), emited when action button is pressed
			b"response"	: (GObject.SIGNAL_RUN_FIRST, None, ()),
			# close(), emited 'X' button is pressed
			b"close"	: (GObject.SIGNAL_RUN_FIRST, None, ()),
		}
	
	### Initialization
	def __init__(self, label, message_type=Gtk.MessageType.INFO, *buttons):
		"""
		... where label can be Gtk.Widget or str and buttons are tuples
		of (Gtk.Button, response_id)
		"""
		# Init
		Gtk.Revealer.__init__(self)
		self._infobar = Gtk.InfoBar()
		# Icon
		icon_name = "dialog-information"
		if message_type == Gtk.MessageType.ERROR:
			icon_name = "dialog-error"
		elif message_type == Gtk.MessageType.WARNING:
			icon_name = "dialog-warning"
		icon = Gtk.Image()
		icon.set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
		self._infobar.get_content_area().pack_start(icon, False, False, 1)
		# Label
		if isinstance(label, Gtk.Widget):
			self._infobar.get_content_area().pack_start(label, True, True, 0)
		else:
			l = Gtk.Label()
			l.set_markup(label)
			self._infobar.get_content_area().add(l)
		# Buttons
		for button, response_id in buttons:
			self.add_button(button, response_id)
		# Settings
		self._infobar.set_message_type(message_type)
		self._infobar.set_show_close_button(True)
		self.set_reveal_child(False)
		# Packing
		self.add(self._infobar)
		self.show_all()
	
	def connect(self, signal, *data):
		if signal in ("close", "response"):
			return self._infobar.connect(signal, *data)
		# else:
		return Gtk.Revealer.connect(self, signal, *data)
	
	def add_button(self, button, response_id):
		self._infobar.add_action_widget(button, response_id)
		self._infobar.show_all()
	
	def close(self, *a):
		"""
		Closes revealer (with animation), removes it from parent and
		calls destroy()
		"""
		self.set_reveal_child(False)
		GLib.timeout_add(self.get_transition_duration() + 50, self._cb_destroy)
	
	def _cb_destroy(self, *a):
		""" Callback used by _cb_close method """
		if not self.get_parent() is None:
			self.get_parent().remove(self)
		self.destroy()
	
	@staticmethod
	def build_button(label, icon_name=None, icon_widget=None):
		""" Builds button situable for action area """
		b = Gtk.Button.new_with_label(label)
		b.set_use_underline(True)
		if not icon_name is None:
			icon_widget = Gtk.Image()
			icon_widget.set_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
		if not icon_widget is None:
			b.set_image(icon_widget)
			b.set_always_show_image(True)
		return b
