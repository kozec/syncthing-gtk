#!/usr/bin/env python2
"""
Syncthing-GTK - Windows related stuff.

This is only module not imported by __init__, so usage requires doing
from syncthing_gtk import windows
"""

from __future__ import unicode_literals
from syncthing_gtk.tools import IS_WINDOWS
import codecs

def fix_localized_system_error_messages():
	"""
	Python has trouble decoding messages like
	''
	as they are encoded in some crazy, Windows-specific, locale-specific,
	day-in-week-specific encoding.
	
	This simply eats exceptions caused by 'ascii' codec and replaces
	non-decodable characters by question mark.
	"""
	
	def handle_error(error):
		if error.encoding != "ascii":
			# Don't interfere with others
			raise error
		return (u'?', error.end)
	
	codecs.register_error("strict", handle_error)
