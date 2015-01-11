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

class OnituIconOverlayExtension(GObject.GObject, Nautilus.InfoProvider):
	def __init__(self):
		init_logging()
		set_logging_level(VERBOSE, DEBUG)
		log.info("Initializing...")
		self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
		self.folders = []
		# Try connect to ST-GTK instance. This will most likely fail,
		# as ST-GTK is not first thing starting before nautilus, but
		# it's necessary to prevent situation when plugin starts only
		# after connected event is emited.
		try:
			reply = self._request("ping", '(s)')
			connected, = self._request("is_connected", '(b)')
			if connected:
				log.info("ST-GTK running and connected to daemon")
				self._read_folders()
		except GLib.Error:
			# Syncthing-GTK is not up yet
			log.info("ST-GTK not running.")
	
	def _request(self, method, answer_fmt, *arguments):
		args = None
		if len(arguments) > 0:
			variants = []
			for a in arguments:
				if type(a) == str:
					variants.append(GLib.Variant.new_string(a))
				else:
					raise TypeError("Cannot convert type %s" % type(a))
			args = GLib.Variant.new_tuple(*variants)
		reply = self.connection.call_sync(SERVICE, PATH,
					SERVICE, method, args,
					GLib.VariantType.new (answer_fmt),
					Gio.DBusCallFlags.NONE,
					-1, None)
		return reply
	
	def _read_folders(self, *a):
		"""
		Reads list of synced foders. This is done synchronously, because
		plugin needs to know this list before nautilus starts requesting
		for file information.
		"""
		self.folders, = self._request("get_folders", "(as)")
		log.debug("Read %s folders", len(self.folders))
	
	def update_file_info(self, file):
		# Check if folder is one of repositories managed by syncthing
		path = file.get_location().get_path()
		if path in self.folders:
			# Determine what emblem should be used
			state, = self._request("get_folder_state", "(s)", path)
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
