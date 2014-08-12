#!/usr/bin/env python2
"""
Syncthing-GTK - Timer manager

Simple abstract class for named, cancelable timers
"""

from __future__ import unicode_literals
from gi.repository import GLib

class TimerManager(object):
	def __init__(self):
		self._timers = {}
	
	def timer(self, name, delay, callback, *data):
		"""
		Runs callback after specified number of seconds. Uses
		GLib.timeout_add_seconds with small wrapping to allow named
		timers to be canceled by reset() call
		"""
		if name is None:
			# No wrapping is needed, call GLib directly
			GLib.timeout_add_seconds(delay, callback, *data)
		else:
			if name in self._timers:
				# Cancel old timer
				GLib.source_remove(self._timers[name])
			# Create new one
			self._timers[name] = GLib.timeout_add_seconds(delay, self._callback, name, callback, *data)
	
	def timer_active(self, name):
		""" Returns True if named timer is active """
		return (name in self._timers)
	
	def cancel_timer(self, name):
		""" Cancels named timer """
		if name in self._timers:
			GLib.source_remove(self._timers[name])
			del self._timers[name]
	
	def cancel_all(self):
		""" Cancels all active timers """
		for x in self._timers:
			GLib.source_remove(self._timers[x])
		self._timers = {}
	
	def _callback(self, name, callback, *data):
		"""
		Removes name from list of active timers and calls real callback.
		"""
		del self._timers[name]
		callback(*data)
		return False
	
