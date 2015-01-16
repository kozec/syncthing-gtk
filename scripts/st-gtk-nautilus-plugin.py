#!/usr/bin/env python2
from gi.repository import Nautilus, GObject, Gio, GLib
from syncthing_gtk.tools import init_logging, set_logging_level
import os, sys, logging
log = logging.getLogger("NautilusPlugin")

# Output options
VERBOSE	= True
DEBUG	= True

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
		self.folders = []
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
			pass
	
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
		self.folders = self.stgtk.get_folders()
		log.debug("Read %s folders", len(self.folders))
	
	### Plugin stuff
	def update_file_info(self, file):
		# Check if folder is one of repositories managed by syncthing
		path = file.get_location().get_path()
		if path in self.folders:
			# Determine what emblem should be used
			state = self.stgtk.get_folder_state("(s)", path)
			print path, state
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
	
	### DBus signal handlers
	def _cb_connected(self, src, *a):
		""" Handler for 'connected' dbus signal """
		self._read_folders()
	
	def _cb_folder_state_changed(self, *a):
		print "_cb_folder_state_changed", a
