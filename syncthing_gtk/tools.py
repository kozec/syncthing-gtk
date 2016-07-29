#!/usr/bin/env python2
"""
Syncthing-GTK - tools

Various stuff that I don't care to fit anywhere else.
"""

from __future__ import unicode_literals
from gi.repository import GLib
from base64 import b32decode
from datetime import datetime, tzinfo, timedelta
from subprocess import Popen
from dateutil import parser
import re, os, sys, random, string, platform, logging, shlex, gettext, __main__
log = logging.getLogger("tools.py")

IS_WINDOWS	= sys.platform in ('win32', 'win64')
IS_XP = IS_WINDOWS and platform.release() in ("XP", "2000", "2003")
IS_GNOME, IS_UNITY, IS_KDE, IS_CINNAMON, IS_XFCE, IS_MATE, IS_I3 = [False] * 7

if "XDG_CURRENT_DESKTOP" in os.environ:
	desktops = os.environ["XDG_CURRENT_DESKTOP"].split(":")
	IS_UNITY = ("Unity" in desktops)
	if not IS_UNITY:
		IS_GNOME = ("GNOME" in desktops) or ("GNOME-Flashback" in desktops) or ("GNOME-Fallback" in desktops)
	IS_KDE   = ("KDE" in desktops)
	IS_CINNAMON = ("X-Cinnamon" in desktops)
	IS_MATE = ("MATE" in desktops)
	IS_XFCE = ("XFCE" in desktops)
	IS_I3 = ("i3" in desktops)
if "DESKTOP_SESSION" in os.environ:
	if os.environ["DESKTOP_SESSION"] == "gnome":
		# Fedora...
		IS_GNOME = True

LUHN_ALPHABET			= "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" # Characters valid in device id
VERSION_NUMBER			= re.compile(r"^v?([0-9\.]*).*")
LOG_FORMAT				= "%(levelname)s %(name)-13s %(message)s"
GETTEXT_DOMAIN			= "syncthing-gtk" # used by "_" function
DESKTOP_FILE = """[Desktop Entry]
Name=%s
Exec=%s
Icon=%s
Comment=%s
X-GNOME-Autostart-enabled=true
Hidden=false
Type=Application
"""

portable_mode_enabled = False

if IS_WINDOWS:
	# On Windows, WMI and pywin32 libraries are reqired
	import wmi, _winreg

""" Localization lambdas """
_ = lambda(a): _uc(gettext.gettext(a))
_uc = lambda(b): b if type(b) == unicode else b.decode("utf-8")

def luhn_b32generate(s):
	"""
	Returns a check digit for the string s which should be composed of
	characters from LUHN_ALPHABET
	"""
	factor, sum, n = 1, 0, len(LUHN_ALPHABET)
	for c in s:
		try:
			codepoint = LUHN_ALPHABET.index(c)
		except ValueError:
			raise ValueError("Digit %s is not valid" % (c,))
		addend = factor * codepoint
		factor = 1 if factor == 2 else 2
		addend = (addend / n) + (addend % n)
		sum += addend
	remainder = sum % n
	checkcodepoint = (n - remainder) % n
	return LUHN_ALPHABET[checkcodepoint]

def check_device_id(nid):
	""" Returns True if device id is valid """
	# Based on nodeid.go
	nid = nid.strip("== \t").upper() \
		.replace("0", "O") \
		.replace("1", "I") \
		.replace("8", "B") \
		.replace("-", "") \
		.replace(" ", "")
	if len(nid) == 56:
		for i in xrange(0, 4):
			p = nid[i*14:((i+1)*14)-1]
			try:
				l = luhn_b32generate(p)
			except Exception, e:
				log.exception(e)
				return False
			g = "%s%s" % (p, l)
			if g != nid[i*14:(i+1)*14]:
				return False
		return True
	elif len(nid) == 52:
		try:
			b32decode("%s====" % (nid,))
			return True
		except Exception:
			return False
	else:
		# Wrong length
		return False

def sizeof_fmt(size):
	for x in ('B','kB','MB','GB','TB'):
		if size < 1024.0:
			if x in ('B', 'kB'):
				return "%3.0f %s" % (size, x)
			return "%3.2f %s" % (size, x)
		size /= 1024.0

def ints(s):
	""" Works as int(), but returns 0 for None, False and empty string """
	if s is None : return 0
	if s == False: return 0
	if hasattr(s, "__len__"):
		if len(s) == 0 : return 0
	return int(s)

def get_header(headers, key):
	"""
	Returns value of single header parsed from headers array or None
	if header is not found
	"""
	if not key.endswith(":"): key = "%s:" % (key,)
	for h in headers:
		if h.startswith(key):
			return h.split(" ", 1)[-1]
	return None

class Timezone(tzinfo):
	def __init__(self, hours, minutes):
		if hours >= 0:
			self.name = "+%s:%s" % (hours, minutes)
		else:
			self.name = "+%s:%s" % (hours, minutes)
		self.delta = timedelta(minutes=minutes, hours=hours)
	
	def __str__(self):
		return "<Timezone %s>" % (self.name,)
	
	def utcoffset(self, dt):
		return self.delta
	
	def tzname(self, dt):
		return self.name
	
	def dst(self, dt):
		return timedelta(0)

def parsetime(m):
	""" Parses time recieved from Syncthing daemon """
	try:
		return parser.parse(m)
	except ValueError:
		raise ValueError("Failed to parse '%s' as time" % m)

def parse_config_arguments(lst):
	"""
	Parses list of arguments and variables set in configuration
	Returns tuple of (variables_dict, prefix_arguments, arguments_list)
	"""
	vars, preargs, args = {}, [], []
	split = shlex.split(lst, False, False)
	args_target = preargs if "!" in split else args
	for i in split:
		if "=" in i and not i.startswith("-"):
			# Environment variable
			k, v = i.split("=", 1)
			vars[k] = v
			continue
		elif i == "!":
			args_target = args
		elif len(i.strip()) > 0:
			# Argument
			args_target.append(i.strip())
	return vars, preargs, args

def delta_to_string(d):
	"""
	Returns aproximate, human-readable and potentialy localized
	string from specified timedelta object
	"""
	# Negative time, 'some time ago'
	if d.days == -1:
		d = - d
		if d.seconds > 3600:
			return _("~%s hours ago") % (int(d.seconds / 3600),)
		if d.seconds > 60:
			return _("%s minutes ago") % (int(d.seconds / 60),)
		if d.seconds > 5:
			return _("%s seconds ago") % (d.seconds,)
		return _("just now")
	if d.days < -1:
		return _("%s days ago") % (-d.days,)

	# Positive time, 'in XY minutes'
	if d.days > 0:
		return _("in %s days") % (d.days,)
	if d.seconds > 3600:
		return _("~%s hours from now") % (int(d.seconds / 3600),)
	if d.seconds > 60:
		return _("%s minutes from now") % (int(d.seconds / 60),)
	if d.seconds > 5:
		return _("%s seconds from now") % (d.seconds,)
	return _("in a moment")

def init_logging():
	"""
	Initializes logging, sets custom logging format and adds one
	logging level with name and method to call.
	"""
	logging.basicConfig(format=LOG_FORMAT)
	logger = logging.getLogger()
	# Rename levels
	logging.addLevelName(10, "D")	# Debug
	logging.addLevelName(20, "I")	# Info
	logging.addLevelName(30, "W")	# Warning
	logging.addLevelName(40, "E")	# Error
	# Create additional, "verbose" level
	logging.addLevelName(15, "V")	# Verbose
	# Add 'logging.verbose' method
	def verbose(self, msg, *args, **kwargs):
		return self.log(15, msg, *args, **kwargs)
	logging.Logger.verbose = verbose
	# Wrap Logger._log in something that can handle utf-8 exceptions
	old_log = logging.Logger._log
	def _log(self, level, msg, args, exc_info=None, extra=None):
		args = tuple([
			(c if type(c) is unicode else str(c).decode("utf-8"))
			for c in args
		])
		msg = msg if type(msg) is unicode else str(msg).decode("utf-8")
		old_log(self, level, msg, args, exc_info, extra)
	logging.Logger._log = _log

def make_portable():
	"""
	Set's IS_PORTABLE flag to True. Has to be called before
	everything else.
	"""
	global portable_mode_enabled
	log.warning("Portable mode enabled")
	portable_mode_enabled = True

def is_portable():
	""" Returns True after make_portable() is called. """
	global portable_mode_enabled
	return portable_mode_enabled

_localedir = None

def init_locale(localedir=None):
	"""
	Initializes gettext-related stuff
	"""
	global _localedir
	_localedir = localedir
	gettext.bindtextdomain(GETTEXT_DOMAIN, localedir)
	gettext.bind_textdomain_codeset(GETTEXT_DOMAIN, "utf-8")
	gettext.textdomain(GETTEXT_DOMAIN)

def get_locale_dir():
	"""
	Returns localedir passed to init_locale or None
	"""
	global _localedir
	return _localedir

def set_logging_level(verbose, debug):
	""" Sets logging level """
	logger = logging.getLogger()
	if debug:		# everything
		logger.setLevel(0)
	elif verbose:	# everything but debug
		logger.setLevel(11)
	else:			# INFO and worse
		logger.setLevel(20)
	if (debug or verbose) and IS_WINDOWS:
		# Windows executable has no console to output to, so output is
		# written to logfile as well
		import tempfile
		logfile = tempfile.NamedTemporaryFile(delete=False,
			prefix="Syncthing-GTK-",
			suffix=".log")
		logfile.close()
		h = logging.FileHandler(logfile.name)
		h.setFormatter(logging.Formatter(LOG_FORMAT))
		logging.getLogger().addHandler(h)

def check_daemon_running():
	""" Returns True if syncthing daemon is running """
	if not IS_WINDOWS:
		# Unix
		if not "USER" in os.environ:
			# Unlikely
			return False
		# signal 0 doesn't kill anything, but killall exits with 1 if
		# named process is not found
		p = Popen(["killall", "-u", os.environ["USER"], "-q", "-s", "0", "syncthing"])
		p.communicate()
		return p.returncode == 0
	else:
		# Windows
		if not "USERNAME" in os.environ:
			# Much more likely
			os.environ["USERNAME"] = ""
		proclist = wmi.WMI().ExecQuery('select * from Win32_Process where Name LIKE "syncthing.exe"')
		try:
			proclist = list(proclist)
			for p in proclist:
				p_user = p.ExecMethod_('GetOwner').Properties_('User').Value
				if p_user == os.environ["USERNAME"]:
					return True
		except Exception, e:
			# Can't get or parse list, something is horribly broken here
			return False
		return False

def parse_version(ver):
	"""
	Parses ver as version string, returning integer.
	Only first 6 components are recognized; If version string uses less
	than 6 components, it's zero-paded from right (1.0 -> 1.0.0.0.0.0).
	Maximum recognized value for component is 255.
	If version string includes non-numeric character, part of string
	starting with this character is discarded.
	If version string starts with 'v', 'v' is ignored.
	"""
	comps = VERSION_NUMBER.match(ver).group(1).split(".")
	if comps[0] == "":
		if ver == "unknown-dev":
			# Exception for non-tagged releases.
			# See https://github.com/syncthing/syncthing-gtk/issues/133
			return parse_version("v9999.99")
		# Not even single number in version string
		return 0
	while len(comps) < 6:
		comps.append("0")
	res = 0
	for i in xrange(0, 6):
		res += min(255, int(comps[i])) << ((5-i) * 8)
	return res

def compare_version(a, b):
	"""
	Parses a and b as version strings.
	Returns True, if a >= b
	Returns False, if b > a
	"""
	return parse_version(a) >= parse_version(b)

def get_config_dir():
	"""
	Returns ~/.config, %APPDATA% or whatever has user set as
	configuration directory.
	"""
	if is_portable():
		return os.environ["XDG_CONFIG_HOME"]
	if IS_WINDOWS and not IS_XP:
		try:
			import windows
			return windows.get_unicode_home()
		except Exception:
			pass
	confdir = GLib.get_user_config_dir()
	if confdir is None or IS_XP:
		if IS_WINDOWS:
			if "LOCALAPPDATA" in os.environ:
				# W7 and later
				confdir = os.environ["LOCALAPPDATA"]
			elif "APPDATA" in os.environ:
				# XP
				from ctypes import cdll
				os_encoding = 'cp' + str(cdll.kernel32.GetACP())
				confdir = os.environ["APPDATA"].decode(os_encoding)
			else:
				# 95? :D
				confdir = os.path.expanduser("~/.config")
		else:
			# Linux
			confdir = os.path.expanduser("~/.config")
	return confdir

get_install_path = None
if IS_WINDOWS:
	def _get_install_path():
		"""
		Returns installation path from registry.
		Available only on Windows
		"""
		if is_portable():
			return os.environ["XDG_CONFIG_HOME"]
		try:
			key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, "Software\\SyncthingGTK")
			path, keytype = _winreg.QueryValueEx(key, "InstallPath")
			path = str(path)
			_winreg.CloseKey(key)
			return path
		except WindowsError:
			# This is really shouldn't happen. Use executable path.
			os.path.dirname(sys.executable)
		
	get_install_path = _get_install_path

def get_executable():
	"""
	Returns filename of executable that was used to launch program.
	"""
	if IS_WINDOWS:
		return os.path.join(get_install_path(), "syncthing-gtk.exe")
	else:
		executable = __main__.__file__.decode("utf-8")
		if not os.path.isabs(executable):
			cwd = os.getcwd().decode("utf-8")
			executable = os.path.normpath(os.path.join(cwd, executable))
		if executable.endswith(".py"):
			executable = "/usr/bin/env python2 %s" % (executable,)
		return executable

def is_ran_on_startup(program_name):
	"""
	Returns True if specified program is set to be ran on startup, either
	by XDG autostart or by windows registry.
	Only name (desktop filename or registry key) is checked.
	"""
	if IS_WINDOWS:
		# Check if there is value for application in ...\Run
		try:
			key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run")
			trash, keytype = _winreg.QueryValueEx(key, program_name)
			_winreg.CloseKey(key)
			return keytype in (_winreg.REG_SZ, _winreg.REG_EXPAND_SZ, _winreg.REG_MULTI_SZ)
		except WindowsError:
			# Key not found
			return False
	else:
		# Check if there application.desktop file exists
		desktopfile = os.path.join(get_config_dir(), "autostart", "%s.desktop" % (program_name,))
		if not os.path.exists(desktopfile):
			return False
		# Check if desktop file is not marked as hidden
		# (stupid way, but should work)
		in_entry = False
		for line in file(desktopfile, "r").readlines():
			line = line.strip(" \r\t").lower()
			if line == "[desktop entry]":
				in_entry = True
				continue
			if "=" in line:
				key, value = line.split("=", 1)
				if key.strip(" ") == "hidden":
					if value.strip(" ") == "true":
						# Desktop file is 'hidden', i.e. disabled
						return False
		# File is present and not hidden - autostart is enabled
		return True

def set_run_on_startup(enabled, program_name, executable, icon="", description=""):
	"""
	Sets or unsets program to be ran on startup, either by XDG autostart
	or by windows registry.
	'Description' parameter is ignored on Windows.
	Returns True on success.
	"""
	if is_ran_on_startup(program_name) == enabled:
		# Don't do anything if value is already set
		return
	if IS_WINDOWS:
		# Create/delete value for application in ...\Run
		key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
			"Software\\Microsoft\\Windows\\CurrentVersion\\Run",
			0, _winreg.KEY_ALL_ACCESS)
		if enabled:
			_winreg.SetValueEx(key, program_name, 0,
				_winreg.REG_SZ, '"%s"' % (executable,))
		else:
			_winreg.DeleteValue(key, program_name)
		_winreg.CloseKey(key)
	else:
		# Create/delete application.desktop with provided values,
		# removing any hidding parameters
		desktopfile = os.path.join(get_config_dir(), "autostart", "%s.desktop" % (program_name,))
		if enabled:
			try:
				os.makedirs(os.path.join(get_config_dir(), "autostart"), mode=755)
			except Exception:
				# Already exists
				pass
			try:
				file(desktopfile, "w").write((DESKTOP_FILE % (
					program_name, executable, icon, description)).encode('utf-8'))
			except Exception, e:
				# IO errors or out of disk space... Not really
				# expected, but may happen
				log.warning("Failed to create autostart entry: %s", e)
				return False
		else:
			try:
				if os.path.exists(desktopfile):
					os.unlink(desktopfile)
			except Exception, e:
				# IO or access error
				log.warning("Failed to remove autostart entry: %s", e)
				return False
	return True

def can_upgrade_binary(binary_path):
	"""
	Returns True if binary seems to be writable and placed in writable
	directory. Result may be wrong on Windows, but it's still more
	accurate that os.access, that respondes with complete fabulation --
	https://mail.python.org/pipermail/python-list/2011-May/604395.html
	"""
	if IS_WINDOWS:
		# Try to open file in same directory. It's not good idea trying
		# to open very same file as Windows throws IOError if file is
		# already open somewhere else (i.e. it's binary that is runing)
		try:
			path = binary_path + ".new"
			if os.path.exists(path):
				f = file(path, "r+b")
				f.close()
			else:
				f = file(path, "wb")
				f.close()
				os.unlink(path)
			# return Maybe
			return True
		except Exception, e:
			log.exception(e)
			return False
	else:
		# Life is just simpler on Unix
		if not os.access(binary_path, os.W_OK):
			return False
		path = os.path.split(binary_path)[0]
		if not os.access(path, os.W_OK):
			return False
		return True


def generate_folder_id():
	"""
	Returns new, randomly generated folder ID in a1bc2-x9y7z format
	"""
	return "-".join((
		("".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(5)))
		for _ in range(2)
	))
