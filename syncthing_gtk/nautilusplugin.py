#!/usr/bin/env python2
"""
Nautilus plugin for Syncthing.
This program is part of Syncthing-GTK, but can be used independently
with small modification

This module is not imported by __init__, so usage requires doing
from syncthing_gtk import nautilusplugin
"""

from __future__ import unicode_literals
from gi.repository import GObject, Gio, GLib
from syncthing_gtk.tools import init_logging, set_logging_level
from syncthing_gtk import Daemon
import os, sys, logging, urlparse, urllib
log = logging.getLogger("SyncthingPlugin")

# Output options
VERBOSE	= True
DEBUG	= True

# Magic numbers
STATE_IDLE		= 1
STATE_SYNCING	= 2
STATE_OFFLINE	= 3
STATE_STOPPED	= 4

def build_class(plugin_module):
	"""
	Builds extension class base on provided plugin module.
	This allows sharing code between extensions and creating
	extensions for Nautilus forks jus by doing:
	
	from syncthing_gtk import nautilusplugin
	from gi.repository import Nemo
	NemoExtensionCls = nautilusplugin..build_class(Nemo)
	"""

	class __NautiluslikeExtension(GObject.GObject, plugin_module.InfoProvider, plugin_module.MenuProvider):
		def __init__(self):
			# Prepare stuff
			init_logging()
			set_logging_level(VERBOSE, DEBUG)
			log.info("Initializing...")
			# ready field is set to True while connection to Syncthing
			# daemon is maintained.
			self.ready = False
			try:
				self.daemon = Daemon()
			except Exception, e:
				# Syncthing is not configured, most likely never launched.
				log.error("%s", e)
				log.error("Failed to read Syncthing configuration.")
				return
			# List of known repos + their states
			self.repos = {}
			self.rid_to_path = {}
			self.path_to_rid = {}
			# List (cache) for folders that are known to be placed bellow
			# some syncthing repo
			self.subfolders = set([])
			# List (cache) for files that plugin were asked about
			self.files = {}
			self.downloads = set([])
			# Connect to Daemon object signals
			self.daemon.connect("connected", self.cb_connected)
			self.daemon.connect("connection-error", self.cb_syncthing_con_error)
			self.daemon.connect("disconnected", self.cb_syncthing_disconnected)
			self.daemon.connect("folder-added", self.cb_syncthing_folder_added)
			self.daemon.connect("folder-sync-started", self.cb_syncthing_folder_state_changed, STATE_SYNCING)
			self.daemon.connect("folder-sync-finished", self.cb_syncthing_folder_state_changed, STATE_IDLE)
			self.daemon.connect("folder-stopped", self.cb_syncthing_folder_state_changed, STATE_STOPPED)
			self.daemon.connect("item-started", self.cb_syncthing_item_started)
			self.daemon.connect("item-updated", self.cb_syncthing_item_updated)
			
			log.info("Initialized.")
			# Let Daemon object connect to Syncthing
			self.daemon.reconnect()
		
		### Internal stuff
		def _clear_emblems(self):
			""" Clear emblems on all files that had emblem added """
			for path in self.files:
				self._invalidate(path)
		
		def _invalidate(self, path):
			""" Forces Nautils to re-read emblems on specified file """
			if path in self.files:
				file = self.files[path]
				file.invalidate_extension_info()
		
		def _get_parent_repo_state(self, path):
			"""
			If file belongs to any known repository, returns state of if.
			Returns None otherwise.
			"""
			# TODO: Probably convert to absolute paths and check for '/' at
			# end. It shouldn't be needed, in theory.
			for x in self.repos:
				if path.startswith(x + os.path.sep):
					return self.repos[x]
			return None
		
		def _get_path(self, file):
			""" Returns path for provided FileInfo object """
			if hasattr(file, "get_location"):
				return file.get_location().get_path().decode('utf-8')
			return urllib.unquote(file.get_uri().replace("file://", ""))
		
		### Daemon callbacks
		def cb_connected(self, *a):
			"""
			Called when connection to Syncthing daemon is created.
			Clears list of known folders and all caches.
			Also asks Nautilus to clear all emblems.
			"""
			self.repos = {}
			self.subfolders = set([])
			self.downloads = set([])
			self._clear_emblems()
			self.ready = True
			log.info("Connected to Syncthing daemon")
		
		def cb_syncthing_folder_added(self, daemon, rid, r):
			"""
			Called when folder is readed from configuration (by syncthing
			daemon, not locally).
			Adds path to list of known repositories and asks Nautilus to
			re-read emblem.
			"""
			path = os.path.expanduser(r["Path"])
			self.rid_to_path[rid] = path
			self.path_to_rid[path.rstrip("/")] = rid
			self.repos[path] = STATE_OFFLINE
			self._invalidate(path)
		
		def cb_syncthing_con_error(self, *a):
			pass
		
		def cb_syncthing_disconnected(self, *a):
			"""
			Called when connection to Syncthing daemon is lost or Daemon
			object fails to (re)connect.
			Check if connection was already finished before and clears up
			stuff in that case.
			"""
			if self.ready:
				log.info("Connection to Syncthing daemon lost")
				self.ready = False
				self._clear_emblems()
			self.daemon.reconnect()
		
		def cb_syncthing_folder_state_changed(self, daemon, rid, state):
			""" Called when folder synchronization starts or stops """
			if rid in self.rid_to_path:
				path = self.rid_to_path[rid]
				self.repos[path] = state
				log.debug("State of %s changed to %s", path, state)
				self._invalidate(path)
				# Invalidate all files in repository as well
				for f in self.files:
					if f.startswith(path + os.path.sep):
						self._invalidate(f)
		
		def cb_syncthing_item_started(self, daemon, rid, filename, *a):
			""" Called when file download starts """
			if rid in self.rid_to_path:
				path = self.rid_to_path[rid]
				filepath = os.path.join(path, filename)
				log.debug("Download started %s", filepath)
				self.downloads.add(filepath)
				self._invalidate(filepath)
		
		def cb_syncthing_item_updated(self, daemon, rid, filename, *a):
			""" Called after file is downloaded """
			if rid in self.rid_to_path:
				path = self.rid_to_path[rid]
				filepath = os.path.join(path, filename)
				log.debug("Download finished %s", filepath)
				if filepath in self.downloads:
					self.downloads.remove(filepath)
					self._invalidate(filepath)
		
		### InfoProvider stuff
		def update_file_info(self, file):
			if not self.ready: return plugin_module.OperationResult.COMPLETE
			# Check if folder is one of repositories managed by syncthing
			path = self._get_path(file)
			if path in self.downloads:
				file.add_emblem("syncthing-active")
			elif path in self.repos:
				# Determine what emblem should be used
				state = self.repos[path]
				if state == STATE_IDLE:
					# File manager probably shoudn't care about folder being scanned
					file.add_emblem("syncthing")
				elif state == STATE_STOPPED:
					file.add_emblem("syncthing-error")
				elif state == STATE_SYNCING:
					file.add_emblem("syncthing-active")
				else:
					# Default (i-have-no-idea-what-happened) state
					file.add_emblem("syncthing-offline")
			else:
				state = self._get_parent_repo_state(path)
				if state is None:
					# _get_parent_repo_state returns None if file doesn't
					# belongs to repo
					pass
				elif state in (STATE_IDLE, STATE_SYNCING):
					# File manager probably shoudn't care about folder being scanned
					file.add_emblem("syncthing")
				else:
					# Default (i-have-no-idea-what-happened) state
					file.add_emblem("syncthing-offline")
			# TODO: This remembers every file user ever saw in Nautilus.
			# There *has* to be memory effecient alternative...
			self.files[path] = file
			return plugin_module.OperationResult.COMPLETE
		
		### MenuProvider stuff
		def get_file_items(self, window, sel_items):
			if len(sel_items) == 1:
				# Display context menu only if one item is selected and
				# that item is directory
				return self.get_background_items(window, sel_items[0])
			return []
		
		def cb_remove_repo_menu(self, menuitem, path):
			print path
			print self.path_to_rid
			if path in self.path_to_rid:
				rid = self.path_to_rid[path]
				print "cb_remove_repo_menu", rid
		
		def cb_add_repo_menu(self, menuitem, path):
			print "cb_add_repo_menu", path
		
		def get_background_items(self, window, item):
			if not item.is_directory():
				# Context menu is enabled only for directories
				# (file can't be used as repo)
				return []
			path = self._get_path(item).rstrip("/")
			if path in self.repos:
				# Folder is already repository.
				# Add 'remove from ST' item
				menu = plugin_module.MenuItem(name='STPlugin::remove_repo',
										 label='Remove Directory from Syncthing',
										 tip='Remove selected directory from Syncthing',
										 icon='syncthing-offline')
				menu.connect('activate', self.cb_remove_repo_menu, path)
				return [menu]
			elif self._get_parent_repo_state(path) is None:
				# Folder doesn't belongs to any repository.
				# Add 'add to ST' item
				menu = plugin_module.MenuItem(name='STPlugin::add_repo',
										 label='Synchronize with Syncthing',
										 tip='Add selected directory to Syncthing',
										 icon='syncthing')
				menu.connect('activate', self.cb_add_repo_menu, path)
				return [menu]
			# Folder belongs to some repository.
			# Don't add anything
			return []
		
	return __NautiluslikeExtension
