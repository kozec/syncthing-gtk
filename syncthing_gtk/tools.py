#!/usr/bin/env python2
"""
Syncthing-GTK - tools

Various stuff that I don't care to fit anywhere else.
"""

from __future__ import unicode_literals
from base64 import b32decode
LUHN_ALPHABET			= "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" # Characters valid in node id

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

def check_node_id(nid):
	""" Returns True if node id is valid """
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
