#!/usr/bin/env python2
"""
Syncthing-GTK - DaemonOutputDialog

Displays output from daemon subprocess
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, Gio
from syncthing_gtk import UIBuilder
import os, tempfile

class DaemonOutputDialog(object):
	""" Displays output from daemon subprocess """
	def __init__(self, app, proc):
		self.proc = proc
		self.app = app
		self.setup_widgets()
		self.handler = 0
	
	def __getitem__(self, name):
		""" Convince method that allows widgets to be accessed via self["widget"] """
		return self.builder.get_object(name)
	
	def show_with_lines(self, lines, parent=None):
		if not parent is None:
			self["dialog"].set_transient_for(parent)
		self["dialog"].show_all()
		self["tvOutput"].get_buffer().set_text("\n".join(lines))

	def show(self, parent=None, title=None):
		if parent is None:
			self["dialog"].set_modal(False)
		else:
			self["dialog"].set_transient_for(parent)
		if not title is None:
			self["dialog"].set_title(title)
		self["dialog"].show_all()
		self["tvOutput"].get_buffer().set_text("\n".join(self.proc.get_output()))
		self.handler = self.proc.connect('line', self.cb_line)
	
	def close(self, *a):
		if self.handler > 0:
			self.proc.disconnect(self.handler)
		self["dialog"].hide()
		self["dialog"].destroy()
	
	def setup_widgets(self):
		# Load glade file
		self.builder = UIBuilder()
		self.builder.add_from_file(os.path.join(self.app.gladepath, "daemon-output.glade"))
		self.builder.connect_signals(self)
		self["tvOutput"].connect('size-allocate', self.scroll)
	
	def cb_line(self, proc, line):
		b = self["tvOutput"].get_buffer()
		b.insert(b.get_iter_at_offset(-1), "\n%s" % (line,))
	
	def scroll(self, *a):
		adj = self["sw"].get_vadjustment()
		adj.set_value( adj.get_upper() - adj.get_page_size())
