#!/usr/bin/env python2
"""
Syncthing-GTK - Ident Icon

Custom widget derived from Gtk.DrawingArea. 
Draws Ident Icon on transparent background.

Most of drawing code is ported from
https://github.com/syncthing/syncthing/blob/master/gui/scripts/syncthing/core/directives/identiconDirective.js"""

from __future__ import unicode_literals
from gi.repository import Gtk
import re, math

class IdentIcon(Gtk.DrawingArea):
	def __init__(self, device_id):
		Gtk.DrawingArea.__init__(self)
		self.value = re.sub(r'[\W_]', "", device_id, 1)
		self.color = (1, 1, 0.95, 1)		# icon color, rgba
		self.size = 5
	
	def set_color_hex(self, hx):
		""" Expects AABBCC or #AABBCC format """
		self.set_color(*InfoBox.hex2color(hx))
		
	def set_color(self, r, g, b, a):
		""" Expects floats """
		self.color = (r, g, b, a)
		self.queue_draw()

	def do_get_preferred_width(self):
		# Icon scales to whatever you give, but prefered
		# size is always 22x22
		return (22, 22)
	
	def do_get_preferred_height(self):
		# Rectangle...
		return self.do_get_preferred_width()
	
	def do_get_request_mode(self):
		return Gtk.SizeRequestMode.CONSTANT_SIZE
	
	def do_draw(self, cr):
		def fill_rect_at(row, col):
			cr.rectangle(
					offset_x + (col * rect_size),
					offset_y + (row * rect_size),
					rect_size, rect_size
			)
			cr.fill()
		
		def should_fill_rect_at(row, col):
			return not (ord(self.value[row + col * self.size]) % 2)
		
		def should_mirror_rect_at(row, col):
			return not (self.size % 2 and col == middle_col)
		
		def mirror_col_for(col):
			return self.size - col - 1
		
		# Prepare stuff
		allocation	= self.get_allocation()
		rect_size	= min(allocation.width, allocation.height) / self.size
		offset_x	= (allocation.width / 2) - (rect_size * self.size / 2)
		offset_y	= (allocation.height / 2) - (rect_size * self.size / 2)
		middle_col	= self.size / 2
		
		# Set color
		cr.set_source_rgba(*self.color)
		# Do drawing
		for row in xrange(0, self.size):
			for col in xrange(0, middle_col + 1):
				if should_fill_rect_at(row, col):
					fill_rect_at(row, col)
					if should_mirror_rect_at(row, col):
						fill_rect_at(row, mirror_col_for(col))
