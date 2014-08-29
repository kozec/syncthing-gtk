#!/usr/bin/env python2
"""
Syncthing-GTK - Watcher

Watches for filesystem changes and reports them to daemon
"""

from __future__ import unicode_literals
from gi.repository import Gio
import os, sys

class Watcher(object):
	""" Watches for filesystem changes and reports them to daemon """
	def __init__(self, app):
		self.app = app
		self._monitors = []
	
	def add_root(self, path):
		""" Starts watch on specified folder """
		f = Gio.File.new_for_path(os.path.expanduser(path))
		m = f.monitor_directory(Gio.FileMonitorFlags.NONE, None)
		if m is None:
			print >>sys.stderr, "Error: Failed to monitor directory", path
			return
		m.connect("changed", self._on_monitor)
		self._monitors.append(m)
		print "Added monitor for", path
		# Scan for subdirectories, add them recursively
		f.enumerate_children_async(
			"standard::name",
			Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
			0, None, # priority, cancelable
			self._on_enum_children)
	
	def remove_root(self):
		""" Cancels watching for specified folder """
		pass
	
	def _on_monitor(self, *a):
		print a
	
	def _on_enum_children(self, f, res):
		e = f.enumerate_children_finish(res)
		if e == None:
			print >>sys.stderr, "Error: Failed to enumerate directory", f.get_path()
			return
		e.next_files_async(
			10, 0, None, # number of files, priority, cancelable
			self._on_enum_child
		)
	
	def _on_enum_child(self, e, res):
		files = e.next_files_finish(res)
		if e == None:
			print >>sys.stderr, "Error: Failed to read directory", f.get_path()
			return
		path = e.get_container().get_path()
		for x in e:
			if x.get_file_type() == Gio.FileType.DIRECTORY:
				self.add_root(os.path.join(path, x.get_name()))
