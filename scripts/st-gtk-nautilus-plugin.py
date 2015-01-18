#!/usr/bin/env python2
from gi.repository import Nautilus, GObject, Gio, GLib
from syncthing_gtk.tools import init_logging, set_logging_level
import os, sys, logging
log = logging.getLogger("NautilusPlugin")

# Output options
VERBOSE	= True
DEBUG	= True

# How often should plugin search for ST-GTK, if it's not available
QUERY_INTERVAL = 5	# seconds

# ST-GTK service data
SERVICE	= 'net.syncthing.syncthinggtk'
PATH	= '/net/syncthing/SyncthingGTK'
IFACE	= SERVICE

class STGTKExtension_Nautilus(GObject.GObject, Nautilus.InfoProvider):
	def __init__(self):
		# Prepare stuff
		init_logging()
		set_logging_level(VERBOSE, DEBUG)
		log.info("Initializing...")
		self.stgtk = None
		self.have_stgtk = False
		# List of known syncthing repos
		self.folders = set([])
		# List (cache) for folders that are known to be placed bellow
		# some syncthing repo
		self.subfolders = set([])
		# List (cache) for files with emblems
		self.files = set([])
		# Connect to DBus & ST-GTK instance
		Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION,
			Gio.DBusProxyFlags.NONE, None, SERVICE, PATH, IFACE,
			None, self._cb_got_interface)
	
	### Internal stuff
	def _cb_got_interface(self, bus, res):
		self.stgtk = Gio.DBusProxy.new_for_bus_finish(res)
		self.stgtk.connect("g-signal", self._cb_g_signal)
		# Try call ST-GTK instance. This will most likely fail,
		# as ST-GTK is usualy not starting before nautilus, but it's
		# necessary to prevent situation when plugin starts only
		# after connected event is emited.
		try:
			if self.stgtk.is_connected():
				self._cb_connected(self.stgtk)
		except GLib.Error:
			self._wait_for_stgtk()
	
	def _cb_g_signal(self, src, no_idea, dbus_signal, pars):
		"""
		Handler for "recieved-dbus-signal" signal. Searchs for associated
		dbus signal handler and calls it, if found.
		"""
		if hasattr(self, "_cb_%s" % (dbus_signal,)):
			getattr(self, "_cb_%s" % (dbus_signal,))(src, *pars)
		else:
			print "Not handled:", dbus_signal, pars
	
	def _read_folders(self, *a):
		"""
		Reads list of synced foders. This is done synchronously, because
		plugin needs to know this list before nautilus starts requesting
		for file information.
		"""
		self.folders = set(self.stgtk.get_folders())
		log.debug("Read %s folders", len(self.folders))
	
	def _syncthing_lost(self):
		"""
		Called when ST-GTK disappears and stops responding to DBus calls
		"""
		self.have_stgtk = False
		self.folders = set([])
		self.subfolders = set([])
		log.info("ST-GTK lost")
		self._clear_emblems()
		self._wait_for_stgtk()
	
	def _clear_emblems(self):
		""" Clear emblems on all files that had emblem added """
		for path in self.files:
			file = Nautilus.FileInfo.create(Gio.File.new_for_path(path))
			print "cleared emblem on ", path
			# invalidate_extension_info will force nautilus to re-read emblems
			file.invalidate_extension_info()
		self.files = set([])
	
	def _wait_for_stgtk(self, *a):
		"""
		Uses Glib.timeout_add to query for ST-GTK every 5 seconds,
		until it becames available.
		"""
		if self.have_stgtk: return False
		# Check if ST-GTK is there
		try:
			if self.stgtk.is_connected():
				# Yep
				log.debug("ST-GTK available")
				self._cb_connected(self.stgtk)
				return False
		except GLib.Error:
			# Nope :(
			log.debug("ST-GTK still not available")
		# Try again later
		GLib.timeout_add_seconds(QUERY_INTERVAL, self._wait_for_stgtk)
		return False
	
	### Plugin stuff
	def update_file_info(self, file):
		if not self.have_stgtk: return
		# Check if folder is one of repositories managed by syncthing
		path = file.get_location().get_path()
		if path in self.folders:
			# Determine what emblem should be used
			try:
				state = self.stgtk.get_folder_state("(s)", path)
			except GLib.Error:
				# ST-GTK doesn't respond anymore, it was most likely
				# shut down
				self._syncthing_lost()
				return
			if state in ("idle", "scanning"):
				# File manager probably shoudn't care about folder being scanned
				file.add_emblem("syncthing")
			elif state == "stopped":
				file.add_emblem("syncthing-error")
			elif state == "syncing":
				file.add_emblem("syncthing-active")
			else:
				# Default (i-have-no-idea-what-happened) state
				file.add_emblem("syncthing-offline")
			self.files.add(path)
	
	### DBus signal handlers
	def _cb_connected(self, src, *a):
		"""
		Handler for 'connected' dbus signal.
		Signal is emmited when ST-GTK connects to Syncthing daemon
		"""
		if not self.have_stgtk:
			log.info("ST-GTK found")
			self.have_stgtk = True
		self._read_folders()
	
	def _cb_disconnected(self, src, *a):
		"""
		Handler for 'disconnected' dbus signal
		Signal is emmited when connection to Syncthing daemon is lost.
		"""
		print "---DISCONNECTED"
		if self.have_stgtk:
			self.folders = set([])
			self.subfolders = set([])
			self._clear_emblems()
		
	def _cb_folder_state_changed(self, src, path, state):
		file = Nautilus.FileInfo.create(Gio.File.new_for_path(path))
		log.debug("Folder state changed: %s", path)
		# invalidate_extension_info will force nautilus to re-read emblems
		file.invalidate_extension_info()
