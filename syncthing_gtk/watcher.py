#!/usr/bin/env python2
"""
Syncthing-GTK - Watcher

Watches for filesystem changes and reports them to daemon
"""

from __future__ import unicode_literals
from gi.repository import Gio, GLib
import os, sys
DEBUG = True

class Watcher(object):
	""" Watches for filesystem changes and reports them to daemon """
	def __init__(self, app):
		self.app = app
		self._monitors = {}
	
	def add_root(self, path):
		""" Starts watch on specified folder """
		path = os.path.abspath(os.path.expanduser(path))
		if path in self._monitors:
			# Remove old monitor, just in case
			self._monitors[path].cancel()
			del self._monitors[path]
		
		f = Gio.File.new_for_path(path)
		m = f.monitor_directory(Gio.FileMonitorFlags.NONE, None)
		if m is None:
			print >>sys.stderr, "Error: Failed to monitor directory", path
			return
		
		m.connect("changed", self._on_monitor)
		self._monitors[path] = m
		if DEBUG: print "Added monitor for", path
		# Scan for subdirectories, add them recursively
		f.enumerate_children_async(
			"standard::name,standard::file_type",
			Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
			0, None, # priority, cancelable
			self._on_enum_children)
	
	def remove_root(self, path):
		""" Cancels watching for specified folder and all subfolders """
		path = os.path.abspath(os.path.expanduser(path))
		for p in self._monitors.keys():
			if p == path or p.startswith("%s/" % (path,)):
				self._monitors[p].cancel()
				del self._monitors[p]
				if DEBUG: print "Removed monitor for", p
	
	def _on_enum_children(self, f, res):
		try:
			e = f.enumerate_children_finish(res)
		except Exception, e:
			print >>sys.stderr, "Error: Failed to enumerate directory", f.get_path()
			return
		GLib.timeout_add(100, e.next_files_async,
			100, 0, None, # number of files, priority, cancelable
			self._on_enum_child
		)
	
	def _on_enum_child(self, e, res):
		try:
			files = e.next_files_finish(res)
		except Exception, e:
			print >>sys.stderr, "Error: Failed to read directory", f.get_path()
			return
		path = e.get_container().get_path()
		for x in files:
			if x.get_file_type() == Gio.FileType.DIRECTORY:
				self.add_root(os.path.join(path, x.get_name()))
		GLib.timeout_add(100, e.next_files_async,
			100, 0, None, # number of files, priority, cancelable
			self._on_enum_child
		)
	
	def _on_monitor(self, monitor, src, dest, e_type):
		if e_type == Gio.FileMonitorEvent.ATTRIBUTE_CHANGED:
			if DEBUG: print "ATTRIBUTE_CHANGED", src.get_path()
		elif e_type == Gio.FileMonitorEvent.CREATED:
			f_type = src.query_file_type(Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS)
			if DEBUG: print "CREATED", f_type, src.get_path()
			if f_type == Gio.FileType.DIRECTORY:
				self.add_root(src.get_path())
		elif e_type == Gio.FileMonitorEvent.DELETED:
			path = os.path.abspath(src.get_path())
			if DEBUG: print "DELETED", src.get_path()
			if path in self._monitors:
				self.remove_root(path)
