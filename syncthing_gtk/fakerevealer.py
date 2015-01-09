from __future__ import unicode_literals
from gi.repository import Gtk
import os, logging
log = logging.getLogger("FakeRevealer")

class FakeRevealer(Gtk.HBox):
	"""
	Gtk.Revealer compatibile widget that will not cause window border
	disapearing bug on Windows.
	"""
	def __init__(self):
		Gtk.HBox.__init__(self)
		self._reveal = True
	
	def add(self, child):
		Gtk.HBox.add(self, child)
		child.set_visible(self._reveal)
	
	def get_reveal_child(self):
		return self._reveal
	
	def set_reveal_child(self, b):
		self._reveal = b
		if len(self.get_children()) > 0:
			self.get_children()[0].set_visible(b)
	
	def get_child_revealed(self):
		return self._reveal
	
	def get_transition_duration(self):
		return 1
	
	def set_transition_duration(self, d):
		""" You wish... """
		pass
	
	def get_transition_type(self):
		return Gtk.Revealer.TransitionType.NONE
	
	def set_transition_type(self, t):
		""" Nobody gives orders to ME! """
		pass

