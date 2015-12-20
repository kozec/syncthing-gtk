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
DEBUG	= False

# Magic numbers
STATE_IDLE		= 1
STATE_SYNCING	= 2
STATE_OFFLINE	= 3
STATE_STOPPED	= 4

def build_class(plugin_module):
	"""
	Builds extension class based on provided plugin module.
	This allows sharing code between extensions and creating
	extensions for Nautilus forks just by doing:
	
	from syncthing_gtk import nautilusplugin
	from gi.repository import Nemo
	NemoExtensionCls = nautilusplugin.build_class(Nemo)
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
			# Dict of known repos -> set of associated devices
			self.rid_to_dev = {}
			# Set of online devices
			self.online_nids = set()
			# Set of online repos (at least one associated device connected)
			self.onlide_rids = set()
			# List (cache) for folders that are known to be placed below
			# some syncthing repo
			self.subfolders = set()
			# List (cache) for files that plugin were asked about
			self.files = {}
			self.downloads = set()
			# Connect to Daemon object signals
			self.daemon.connect("connected", self.cb_connected)
			self.daemon.connect("connection-error", self.cb_syncthing_con_error)
			self.daemon.connect("disconnected", self.cb_syncthing_disconnected)
			self.daemon.connect("device-connected", self.cb_device_connected)
			self.daemon.connect("device-disconnected", self.cb_device_disconnected)
			self.daemon.connect("folder-added", self.cb_syncthing_folder_added)
			self.daemon.connect("folder-sync-started", self.cb_syncthing_folder_state_changed, STATE_SYNCING)
			self.daemon.connect("folder-sync-finished", self.cb_syncthing_folder_state_changed, STATE_IDLE)
			self.daemon.connect("folder-stopped", self.cb_syncthing_folder_stopped)
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
		
		def _clear_emblems_in_dir(self, path):
			"""
			Same as _clear_emblems, but only for one directory and its
			subdirectories.
			"""
			for f in self.files:
				if f.startswith(path + os.path.sep) or f == path	:
					self._invalidate(f)
		
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
				if not file.get_location().get_path() is None:
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
			self.rid_to_dev = {}
			self.online_nids = set()
			self.onlide_rids = set()
			self.subfolders = set()
			self.downloads = set()
			self._clear_emblems()
			self.ready = True
			log.info("Connected to Syncthing daemon")
		
		def cb_device_connected(self, daemon, nid):
			self.online_nids.add(nid)
			# Mark any repo attached to this device online
			for rid in self.rid_to_dev:
				if not rid in self.onlide_rids:
					if nid in self.rid_to_dev[rid]:
						log.debug("Repo '%s' now online", rid)
						self.onlide_rids.add(rid)
						if self.repos[self.rid_to_path[rid]] == STATE_OFFLINE:
							self.repos[self.rid_to_path[rid]] = STATE_IDLE
						self._clear_emblems_in_dir(self.rid_to_path[rid])
		
		def cb_device_disconnected(self, daemon, nid):
			self.online_nids.remove(nid)
			# Check for all online repos atached to this device
			for rid in self.rid_to_dev:
				if rid in self.onlide_rids:
					# Check if repo is atached to any other, online device
					if len([ x for x in self.rid_to_dev[rid] if x in self.online_nids ]) == 0:
						# Nope
						log.debug("Repo '%s' now offline", rid)
						self.onlide_rids.remove(rid)
						self.repos[self.rid_to_path[rid]] = STATE_OFFLINE
						self._clear_emblems_in_dir(self.rid_to_path[rid])
		
		def cb_syncthing_folder_added(self, daemon, rid, r):
			"""
			Called when folder is readed from configuration (by syncthing
			daemon, not locally).
			Adds path to list of known repositories and asks Nautilus to
			re-read emblem.
			"""
			path = os.path.expanduser(r["path"])
			if path.endswith(os.path.sep):
				path = path.rstrip("/")
			self.rid_to_path[rid] = path
			self.path_to_rid[path] = rid
			self.repos[path] = STATE_OFFLINE
			self._invalidate(path)
			# Store repo id in dict of associated devices
			self.rid_to_dev[rid] = set()
			for d in r['devices']:
				self.rid_to_dev[rid].add(d['deviceID'])
		
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
				if self.repos[path] != STATE_OFFLINE:
					self.repos[path] = state
					log.debug("State of %s changed to %s", path, state)
					self._invalidate(path)
					# Invalidate all files in repository as well
					self._clear_emblems_in_dir(path)
		
		def cb_syncthing_folder_stopped(self, daemon, rid, *a):
			""" Called when synchronization error is detected """
			self.cb_syncthing_folder_state_changed(daemon, rid, STATE_STOPPED)
		
		def cb_syncthing_item_started(self, daemon, rid, filename, *a):
			""" Called when file download starts """
			if rid in self.rid_to_path:
				path = self.rid_to_path[rid]
				filepath = os.path.join(path, filename)
				log.debug("Download started %s", filepath)
				self.downloads.add(filepath)
				self._invalidate(filepath)
				placeholderpath = os.path.join(path, ".syncthing.%s.tmp" % filename)
				if placeholderpath in self.files:
					self._invalidate(placeholderpath)
				
		
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
			# TODO: This remembers every file user ever saw in Nautilus.
			# There *has* to be memory effecient alternative...
			path = self._get_path(file)
			pathonly, filename = os.path.split(path)
			self.files[path] = file
			if not self.ready: return plugin_module.OperationResult.COMPLETE
			# Check if folder is one of repositories managed by syncthing
			if path in self.downloads:
				file.add_emblem("syncthing-active")
			if filename.startswith(".syncthing.") and filename.endswith(".tmp"):
				# Check for placeholder files
				realpath = os.path.join(pathonly, filename[11:-4])
				if realpath in self.downloads:
					file.add_emblem("syncthing-active")
					return plugin_module.OperationResult.COMPLETE
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
			return plugin_module.OperationResult.COMPLETE
		
		### MenuProvider stuff
		def get_file_items(self, window, sel_items):
			if len(sel_items) == 1:
				# Display context menu only if one item is selected and
				# that item is directory
				return self.get_background_items(window, sel_items[0])
			return []
		
		def cb_remove_repo_menu(self, menuitem, path):
			if path in self.path_to_rid:
				path = os.path.abspath(os.path.expanduser(path))
				path = path.replace("'", "\'")
				os.system("syncthing-gtk --remove-repo '%s' &" % path)
		
		def cb_add_repo_menu(self, menuitem, path):
			path = os.path.abspath(os.path.expanduser(path))
			path = path.replace("'", "\'")
			os.system("syncthing-gtk --add-repo '%s' &" % path)
		
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
