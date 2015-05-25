#!/usr/bin/env python2
"""
Syncthing-GTK - Watcher

Watches for filesystem changes and reports them to daemon
"""

from __future__ import unicode_literals

HAS_INOTIFY = False
Watcher = None

try:
	import pyinotify
	HAS_INOTIFY = True
except ImportError:
	pass
if HAS_INOTIFY:
	from gi.repository import GLib
	import os, sys, logging
	log = logging.getLogger("Watcher")
	
	class WatcherCls(object):
		""" Watches for filesystem changes and reports them to daemon """
		def __init__(self, app, daemon):
			self.app = app
			self.daemon = daemon
			self.wds = {}
			self.enabled = False
			self.wm = pyinotify.WatchManager()
			self.notifier = pyinotify.Notifier(self.wm, timeout=10, default_proc_fun=self._process)
			self.glibsrc = GLib.idle_add(self._process_events)
		
		def watch(self, path):
			""" Sets recursive watching on specified directory """
			added = self.wm.add_watch(path.encode("utf-8"),
				pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MOVED_TO | pyinotify.IN_MOVED_FROM |
				pyinotify.IN_DELETE | pyinotify.IN_CREATE, rec=True, quiet=False
			)
			if path in added:
				# Should be always
				self.wds[path] = added[path]
			log.verbose("Watching %s", path)
		
		def _clear(self):
			""" Cancels watching on everything """
			wds_v = self.wds.values()
			self.wds = {}
			for x in wds_v:
				self.wm.rm_watch(x, rec=True, quiet=True)
			log.verbose("Cleared all watches")
		
		def kill(self):
			""" Cancels & deallocates everything """
			if self.glibsrc > 0:
				GLib.source_remove(self.glibsrc)
				self.glibsrc = -1
			self._clear()
			self.enabled = False
			del self.notifier
			del self.wm
		
		def start(self):
			""" Starts watching """
			self.enabled = True
		
		def _process(self, event):
			""" Inotify event callback """
			if event.mask & pyinotify.IN_ISDIR != 0:
				if event.mask & pyinotify.IN_CREATE != 0:
					# New dir - Add watch to created dir as well
					self.watch(event.pathname.decode("utf-8"))
					self._report_created(event.pathname)
				elif event.mask & pyinotify.IN_DELETE != 0:
					# Deleted dir - Remove watch to deleted dir
					self.remove(event.pathname)
					self._report_deleted(event.pathname)
			elif event.mask & pyinotify.IN_CREATE != 0:
				# New file - ignore event, 'IN_CLOSE_WRITE' is enought for my purpose
				return
			elif event.mask & pyinotify.IN_CLOSE_WRITE != 0:
				# Changed file
				self._report_changed(event.pathname)
			elif event.mask & pyinotify.IN_DELETE != 0:
				# Deleted file
				self._report_deleted(event.pathname)
			elif event.mask & pyinotify.IN_MOVED_FROM != 0:
				# Moved out = deleted
				self._report_deleted(event.pathname)
			elif event.mask & pyinotify.IN_MOVED_TO != 0:
				# Moved in = created
				self._report_created(event.pathname)
		
		def _process_events(self):
			""" Called from GLib.idle_add """
			notifier = self.notifier
			notifier.process_events()
			while notifier.check_events():
				notifier.read_events()
				notifier.process_events()
			return True	# Repeat until killed
		
		def _report_created(self, path):
			if not enabled: return
			path = path.decode("utf-8")
			folder_id, relpath = self.app.get_folder_n_path(path)
			log.debug("File Created %s %s > %s", folder_id, path, relpath)
			if not folder_id is None:
				self.daemon.rescan(folder_id, relpath)
		
		def _report_changed(self, path):
			if not enabled: return
			path = path.decode("utf-8")
			folder_id, relpath = self.app.get_folder_n_path(path)
			log.debug("File Changed %s %s > %s", folder_id, path, relpath)
			if not folder_id is None:
				self.daemon.rescan(folder_id, relpath)
		
		def _report_deleted(self, path):
			if not enabled: return
			path = path.decode("utf-8")
			folder_id, relpath = self.app.get_folder_n_path(path)
			log.debug("File Deleted %s %s > %s", folder_id, path, relpath)
			if not folder_id is None:
				self.daemon.rescan(folder_id, relpath)
	
	# Watcher is set to class only if pyinotify is available
	Watcher = WatcherCls
