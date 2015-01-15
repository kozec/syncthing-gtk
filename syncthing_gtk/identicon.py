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
_ = lambda (a) : a

class IdentIcon(Gtk.DrawingArea):
	def __init__(self, device_id):
		Gtk.DrawingArea.__init__(self)
		self.value = re.sub(r'[\W_]', "", device_id, 1)
		self.color = (1, 1, 0.95, 1)		# icon color, rgba
		self.size = 5
	
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
		def fillRectAt(row, col):
			cr.rectangle(
					offset_x + (col * rectSize),
					offset_y + (row * rectSize),
					rectSize, rectSize
			)
			cr.fill()
		
		def shouldFillRectAt(row, col):
			return not (ord(self.value[row + col * self.size]) % 2)
		
		def shouldMirrorRectAt(row, col):
			return not (self.size % 2 and col == middleCol)
		
		def mirrorColFor(col):
			return self.size - col - 1
		
		allocation = self.get_allocation()
		rectSize = min(allocation.width, allocation.height) / self.size
		offset_x = (allocation.width / 2) - (rectSize * self.size / 2)
		offset_y = (allocation.height / 2) - (rectSize * self.size / 2)
		middleCol = self.size / 2
		cr.set_source_rgba(*self.color)
		
		for row in xrange(0, self.size):
			for col in xrange(0, middleCol + 1):
				if shouldFillRectAt(row, col):
					fillRectAt(row, col)
					if shouldMirrorRectAt(row, col):
						fillRectAt(row, mirrorColFor(col))
