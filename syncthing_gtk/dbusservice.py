#!/usr/bin/env python2
"""
Syncthing-GTK - DBus integration

Provides simple DBus API for Syncthing and Syncthing-GTK.
Used by Syncthing-GTK filemanager plugins.
"""
from gi.repository import GObject
import os, sys, logging

log = logging.getLogger("DBus")

HAS_DBUS = False
DBusService = None

try:
	import dbus
	import dbus.service
	from dbus.mainloop.glib import DBusGMainLoop
	HAS_DBUS = True
except Exception, e:
	pass

SERVICE	= 'net.syncthing.syncthinggtk'
PATH	= '/net/syncthing/SyncthingGTK'

if HAS_DBUS:
	class DBusServiceCls(dbus.service.Object):

		def __init__(self, daemon):
			# DBus initialization
			dbus.service.Object.__init__(self,
				dbus.service.BusName(
					SERVICE,
					bus=dbus.SessionBus(mainloop=dbus_main_loop)
				),
				PATH
			)
			# Service initialization
			self.folders = []
			self.id_by_path = {}
			self.path_by_id = {}
			self.state_by_id = {}
			self.is_connected = False
			# Daemon & callbacks setup
			self.daemon = daemon
			self.daemon.connect("config-loaded", self.cb_config_loaded)
			self.daemon.connect("connection-error", self.cb_disconnected)
			self.daemon.connect("disconnected", self.cb_disconnected)
			self.daemon.connect("folder-added", self.cb_folder_added)
			self.daemon.connect("folder-sync-started", self.cb_folder_state_changed, "syncing")
			# self.daemon.connect("folder-sync-progress", ...
			self.daemon.connect("folder-sync-finished", self.cb_folder_state_changed, "idle")
			self.daemon.connect("folder-scan-started", self.cb_folder_state_changed, "scanning")
			self.daemon.connect("folder-scan-finished", self.cb_folder_state_changed, "idle")
			self.daemon.connect("folder-stopped", self.cb_folder_stopped)
			# TODO: Offline state
			log.info("Service initialized")
		
		# Callbacks
		def cb_disconnected(self, *a):
			self.folders = []
			if self.is_connected:
				self.is_connected = False
				self.disconnected()
		
		def cb_config_loaded(self, *a):
			# This is emited by daemon after all folders are parsed
			self.connected()
			self.is_connected = True
		
		def cb_folder_added(self, daemon, rid, r):
			path = os.path.expanduser(r["Path"])
			self.id_by_path[path] = rid
			self.path_by_id[rid] = path
			self.state_by_id[rid] = "Offline"
			self.folders.append(path)
			self.folder_state_changed(path, "offline")
		
		def cb_folder_state_changed(self, daemon, rid, state):
			self.state_by_id[rid] = state
			if rid in self.path_by_id:
				self.folder_state_changed(self.path_by_id[rid], state)
		
		def cb_folder_stopped(self, daemon, rid, message, *a):
			self.state_by_id[rid] = "stopped"
			if rid in self.path_by_id:
				self.folder_state_changed(self.path_by_id[rid], "stopped")
		
		# Service signals
		@dbus.service.signal(SERVICE, signature='')
		def connected(self): pass
		@dbus.service.signal(SERVICE, signature='')
		def disconnected(self): pass
		@dbus.service.signal(SERVICE, signature='ss')
		def folder_state_changed(self, path, state): pass
		
		# Service methods
		@dbus.service.method(SERVICE, out_signature='s')
		def ping(self):
			""" Returns ball back to player one """
			return "pong"
		
		@dbus.service.method(SERVICE, out_signature='b')
		def is_connected(self):
			""" Returns True if ST-GTK is connected to daemon instance """
			return self.daemon.is_connected()
		
		@dbus.service.method(SERVICE, out_signature='as')
		def get_folders(self):
			""" Returns list of folders synchronized by syncthig """
			return self.folders
	
		@dbus.service.method(SERVICE, in_signature='s', out_signature='s')
		def get_folder_state(self, path):
			"""
			Returns current state of folder. Returns empty string if
			there is no such folder
			Possible values:
			idle, syncing, scanning, offline, stopped
			"""
			if path in self.id_by_path:
				if self.id_by_path[path] in self.state_by_id:
					return self.state_by_id[self.id_by_path[path]]
			return ""
	
	dbus_main_loop = DBusGMainLoop()
	DBusService = DBusServiceCls
