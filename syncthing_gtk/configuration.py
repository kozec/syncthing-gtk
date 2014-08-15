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
		except Exception, e:
			print >>sys.stderr, "Warning: Failed to load configuration; Creating new one"
			print >>sys.stderr, "  exception was:", e
			self._create()
	
	def _create(self):
		""" Creates new, empty configuration with default values """
		self._values = {
			# Nothing so far...
			}
		self._save()
	
	def _save(self):
		""" Saves configuration file """
		file(self._conffile, "w").write(json.dumps(self._values))
	
	def __getitem__(self, key):
		return self._values[key]
	
	def __setitem__(self, key, value):
		self._values[key] = value
		self._save()
	
	def __contains__(self, key):
		""" Returns true if there is such widget """
		return key in self._values
