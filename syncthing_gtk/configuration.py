#/usr/bin/env python3
"""
Syncthing-GTK - Configuration

Configuration object implementation; Uses JSON.
Config file is by default in ~/.config/syncthing-gtk/config.json
or other ~/.config equivalent
"""


from datetime import datetime
from syncthing_gtk.tools import IS_WINDOWS, get_config_dir, is_portable
import dateutil.parser
import os, sys, json, logging
log = logging.getLogger("Configuration")

LONG_AGO = datetime.fromtimestamp(1)

class _Configuration(object):
	"""
	Configuration object implementation.
	Use like dict to save / access values
	"""
	
	# Dict with keys that are required in configuration file
	# and default values for those keys.
	# Format: key : (type, default)
	REQUIRED_KEYS = {
		"autostart_daemon"			: (int, 2),	# 0 - wait for daemon, 1 - autostart, 2 - ask
		"autokill_daemon"			: (int, 2),	# 0 - never kill, 1 - always kill, 2 - ask
		"daemon_priority"			: (int, 0), # uses nice values
		"max_cpus"					: (int, 0), # 0 for all cpus
		"syncthing_binary"			: (str, "/usr/bin/syncthing"),
		"syncthing_arguments"		: (str, ""),
		"minimize_on_start"			: (bool, False),
		"folder_as_path"			: (bool, True),
		"use_old_header"			: (bool, False),
		"icons_in_menu"				: (bool, True),
		"animate_icon"				: (bool, True),
		"notification_for_update"	: (bool, True),
		"notification_for_folder"	: (bool, False),
		"notification_for_error"	: (bool, True),
		"st_autoupdate"				: (bool, False),
		"last_updatecheck"			: (datetime, LONG_AGO),
		"window_position"			: (tuple, None),
		"infobox_style"				: (str, 'font_weight="bold" font_size="large"'),
		"icon_theme"				: (str, 'syncthing'),
		"force_dark_theme"			: (bool, False),	# Windows-only
		"language"					: (str, ""),		# Windows-only
		"file_browser"				: (str, "explore"),	# Windows-only
	}
	
	# Overrides some default values on Windows
	WINDOWS_OVERRIDE = {
		"syncthing_binary"			: (str, "C:\\Program Files\\Syncthing\\syncthing.exe"),
		"autokill_daemon"			: (int, 1),
		"use_old_header"			: (bool, False),
		"st_autoupdate"				: (bool, True),
	}
	
	def __init__(self):
		try:
			self.load()
		except Exception as e:
			log.warning("Failed to load configuration; Creating new one.")
			log.warning("Reason: %s", (e,))
			self.create()
		
		# Convert objects serialized as string back to object
		self.convert_values()
		# Check if everything is in place, add default value
		# where value is missing
		if self.check_values():
			# check_values returns True if any default value is added
			log.info("Saving configuration...")
			self.save()
	
	def load(self):
		# Check & create directory
		if not os.path.exists(self.get_config_dir()):
			try:
				os.makedirs(self.get_config_dir())
			except Exception as e:
				log.error("Cannot create configuration directory")
				log.exception(e)
				sys.exit(1)
		# Load json
		with open(self.get_config_file(), "r") as conf:
			self.values = json.loads(conf.read())

	def get_default_value(self, key):
		if IS_WINDOWS:
			return self.WINDOWS_OVERRIDE.get(key, self.REQUIRED_KEYS[key])[-1]
		return self.REQUIRED_KEYS[key][-1]
	
	def get_config_dir(self):
		return os.path.join(get_config_dir(), "syncthing-gtk")
	
	def get_config_file(self):
		return os.path.join(self.get_config_dir(), "config.json")
	
	def create(self):
		""" Creates new, empty configuration """
		self.values = {}
		self.check_values()
		self.save()
	
	def check_values(self):
		"""
		Check if all required values are in place and fill by default
		whatever is missing.
		
		Returns True if anything gets changed.
		"""
		needs_to_save = False
		for key in Configuration.REQUIRED_KEYS:
			tp, default = Configuration.REQUIRED_KEYS[key]
			if not self.check_type(key, tp):
				log.verbose("Configuration key %s is missing. Using default", key)
				if IS_WINDOWS and key in Configuration.WINDOWS_OVERRIDE:
					tp, default = Configuration.WINDOWS_OVERRIDE[key]
				self.values[key] = default
				needs_to_save = True
		return needs_to_save
	
	def convert_values(self):
		"""
		Converts all objects serialized as string back to object
		"""
		for key in Configuration.REQUIRED_KEYS:
			if key in self.values:
				tp, trash = Configuration.REQUIRED_KEYS[key]
				try:
					if tp == datetime and type(self.values[key]) == str:
						# Parse datetime
						self.values[key] = dateutil.parser.parse(self.values[key])
					elif tp == tuple and type(self.values[key]) == list:
						# Convert list to tuple
						self.values[key] = tuple(self.values[key])
					elif tp == bool and type(self.values[key]) == int:
						# Convert bools
						self.values[key] = bool(self.values[key])
				except Exception as e:
					log.warning("Failed to parse configuration value '%s'. Using default.", key)
					log.warning(e)
					# Value will be re-created by check_values method
					del self.values[key]
	
	def check_type(self, key, tp):
		"""
		Returns True if value is set and type match.
		Auto-converts objects serialized as string back to objects
		"""
		if not key in self.values:
			return False
		# Handle special cases
		if type(self.values[key]) == str and tp == str:
			return True
		if tp in (tuple,) and self.values[key] == None:
			return True
		# Return value
		return type(self.values[key]) == tp
	
	def save(self):
		""" Saves configuration file """
		with open(self.get_config_file(), "w") as conf:
			conf.write(
				json.dumps(
					self.values,
					sort_keys=True,
					indent=4,
					separators=(',', ': '),
					default=serializer
				)
			)

	def __iter__(self):
		for k in self.values:
			yield k
	
	def get(self, key):
		return self.values[key]
	
	def set(self, key, value):
		self.values[key] = value
		self.save()
	
	__getitem__ = get
	__setitem__ = set
	
	def __delitem__(self, key):
		del self.values[key]
	
	def __contains__(self, key):
		""" Returns true if there is such value """
		return key in self.values

def serializer(obj):
	""" Handles serialization where json can't do it by itself """
	if hasattr(obj, "isoformat"):
		# datetime object
		return obj.isoformat()
	raise TypeError("Can't serialize object of type %s" % (type(obj),))

def Configuration(*a, **b):
	if IS_WINDOWS and not is_portable():
		from syncthing_gtk.windows import WinConfiguration
		return WinConfiguration(*a, **b)
	return _Configuration(*a, **b)
Configuration.REQUIRED_KEYS = _Configuration.REQUIRED_KEYS
Configuration.WINDOWS_OVERRIDE = _Configuration.WINDOWS_OVERRIDE


def migrate_fs_watch(stgtk_config, st_config):
	"""
	Migrates filesystem watch config from ST-GTK configuration
	to Syncthing configuration and posts it to daemon.
	
	Returns True if anything was changed.
	
	Called automatically if old fs watch setting is found in ST-GTK config.
	"""
	# TODO: This can be removed later
	if "use_inotify" not in stgtk_config:
		return False
	changed = False
	folder_by_id = { x["id"]: x for x in st_config['folders'] }
	for rid in stgtk_config["use_inotify"]:
		if rid in folder_by_id:
			folder_by_id[rid]["fsWatcherDelayS"] = 10
			folder_by_id[rid]["fsWatcherEnabled"] = True
			changed = True
	del stgtk_config["use_inotify"]
	return changed
