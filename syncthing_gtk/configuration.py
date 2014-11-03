#!/usr/bin/env python2
"""
Syncthing-GTK - Configuration

Configuration object implementation; Uses JSON.
Config file is by default in ~/.config/syncthing-gtk/config.json
or other ~/.config equivalent
"""

from __future__ import unicode_literals
from gi.repository import GLib
import os, sys, json

class Configuration(object):
	"""
	Configuration object implementation.
	Use like dict to save / access values
	"""
	
	REQUIRED_KEYS = {
		# key : (type, default)
		"autostart_daemon"			: (int, 2),	# 0 - wait for daemon, 1 - autostart, 2 - ask
		"autokill_daemon"			: (int, 2),	# 0 - never kill, 1 - always kill, 2 - ask
		"syncthing_binary"			: (str, "/usr/bin/syncthing"),
		"minimize_on_start"			: (bool, True),
		"use_old_header"			: (bool, False),
		"use_inotify"				: (list, []),
		"use_old_header"			: (bool, False),
		"notification_for_update"	: (bool, True),
		"notification_for_folder"	: (bool, False),
		"notification_for_error"	: (bool, True),
	}
	
	def __init__(self):
		self._load()
	
	def _load(self):
		confdir = GLib.get_user_config_dir()
		if confdir is None:
			confdir = os.path.expanduser("~/.config")
		confdir = os.path.join(confdir, "syncthing-gtk")
		if not os.path.exists(confdir):
			try:
				os.makedirs(confdir)
			except Exception, e:
				print >>sys.stderr, "Fatal: Cannot create configuration directory"
				print >>sys.stderr, e
				sys.exit(1)
		self._conffile = os.path.join(confdir, "config.json")
		try:
			self._values = json.loads(file(self._conffile, "r").read())
			if self._check_values():
				self._save()
		except Exception, e:
			print >>sys.stderr, "Warning: Failed to load configuration; Creating new one"
			print >>sys.stderr, "  exception was:", e
			self._create()
	
	def _create(self):
		""" Creates new, empty configuration """
		self._values = {}
		self._check_values()
		self._save()
	
	def _check_values(self):
		"""
		Check if all required values are in place and fill by default
		whatever is missing.
		
		Returns True if anything gets changed.
		"""
		needs_to_save = False
		for key in Configuration.REQUIRED_KEYS:
			tp, default = Configuration.REQUIRED_KEYS[key]
			if not self._check_type(key, tp):
				self._values[key] = default
				needs_to_save = True
		return needs_to_save
	
	def _check_type(self, key, tp):
		""" Returns True if value is set and type match """
		if not key in self._values:
			return False
		if type(self._values[key]) in (str, unicode) and tp in (str, unicode):
			# This case is little special
			return True
		return type(self._values[key]) == tp
	
	def _save(self):
		""" Saves configuration file """
		file(self._conffile, "w").write(json.dumps(
			self._values, sort_keys=True, indent=4, separators=(',', ': ')
			))
	
	def __iter__(self):
		for k in self._values:
			yield k
	
	def __getitem__(self, key):
		return self._values[key]
	
	def __setitem__(self, key, value):
		self._values[key] = value
		self._save()
	
	def __contains__(self, key):
		""" Returns true if there is such widget """
		return key in self._values
