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
import re, os, sys

_ = lambda (a) : a
IS_WINDOWS	= sys.platform in ('win32', 'win64')
LUHN_ALPHABET			= "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" # Characters valid in device id
VERSION_NUMBER			= re.compile(r"^v?([0-9\.]*).*")

if IS_WINDOWS:
	# On Windows, WMI and pywin32 libraries are reqired
	import wmi

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
				print e
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

PARSER = re.compile(r"([-0-9]+)[A-Z]([:0-9]+)\.([0-9]+)([\-\+][0-9]+):([0-9]+)")
PARSER_NODOT = re.compile(r"([-0-9]+)[A-Z]([:0-9]+)([\-\+][0-9]+):([0-9]+)")
FORMAT = "%Y-%m-%d %H:%M:%S %f"

def parsetime(m):
	""" Parses time recieved from Syncthing daemon """
	reformat, tz = None, None
	if "." in m:
		match = PARSER.match(m)
		times = list(match.groups()[0:3])
		times[2] = times[2][0:6]
		reformat = "%s %s %s" % tuple(times)
		tz = Timezone(int(match.group(4)), int(match.group(5)))
	else:
		match = PARSER_NODOT.match(m)
		times = list(match.groups()[0:2])
		reformat = "%s %s 00" % tuple(times)
		tz = Timezone(int(match.group(3)), int(match.group(4)))
	return datetime.strptime(reformat, FORMAT).replace(tzinfo=tz)

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
	Parses a and b as version strings. Rreturns True, if a >= b
	"""
	return parse_version(a) >= parse_version(b)

def get_config_dir():
	"""
	Returns ~/.config, %APPDATA% or whatever has user set as
	configuration directory.
	"""
	confdir = GLib.get_user_config_dir()
	if confdir is None:
		confdir = os.path.expanduser("~/.config")
	return confdir
