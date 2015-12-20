#!/usr/bin/env python2
"""
Syncthing-GTK - InfoBox

Colorfull, expandlable widget displaying folder/device data
"""
from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, GLib, GObject, Pango, Rsvg
from syncthing_gtk.ribar import RevealerClass
from syncthing_gtk.tools import _ # gettext function
import os, logging, math
log = logging.getLogger("InfoBox")

COLOR_CHANGE_TIMER	= 10	# ms
COLOR_CHANGE_STEP	= 0.05
HILIGHT_INTENSITY	= 0.3	# 0.0 to 1.0
DARKEN_FACTOR		= 0.75	# 0.0 to 1.0

svg_cache = {}

class InfoBox(Gtk.Container):
	""" Expandlable widget displaying folder/device data """
	__gtype_name__ = "InfoBox"
	__gsignals__ = {
			# right-click(button, time)
			b"right-click"	: (GObject.SIGNAL_RUN_FIRST, None, (int, int)),
			# doubleclick, no arguments
			b"doubleclick"	: (GObject.SIGNAL_RUN_FIRST, None, () )
		}
	
	### Initialization
	def __init__(self, app, title, icon):
		# Variables
		self.app = app
		self.child = None
		self.header = None
		self.str_title = None
		self.str_status = None
		self.header_inverted = False
		self.values = {}
		self.icons = {}
		self.value_widgets = {}
		self.hilight = False
		self.hilight_factor = 0.0
		self.timer_enabled = False
		self.icon = icon
		self.color = (1, 0, 1, 1)		# rgba
		self.background = (1, 1, 1, 1)	# rgba
		self.dark_color  = None			# Overrides background if set
		self.text_color = (0, 0, 0, 1)	# rgba (text color)
		self.real_color = self.color	# set color + hilight
		self.border_width = 2
		self.children = [self.header, self.child]
		# Initialization
		Gtk.Container.__init__(self)
		self.init_header()
		self.init_grid()
		# Settings
		self.set_title(title)
		self.set_status(_("Disconnected"))
	
	def init_header(self):
		# Create widgets
		eb = Gtk.EventBox()
		self.title = Gtk.Label()
		self.status = Gtk.Label()
		hbox = Gtk.HBox()
		# Set values
		self.title.set_alignment(0.0, 0.5)
		self.status.set_alignment(1.0, 0.5)
		self.title.set_ellipsize(Pango.EllipsizeMode.START)
		hbox.set_spacing(4)
		# Connect signals
		eb.connect("realize", self.set_header_cursor)
		eb.connect("button-release-event", self.on_header_click)
		eb.connect('enter-notify-event', self.on_enter_notify)
		eb.connect('leave-notify-event', self.on_leave_notify)
		# Pack together
		hbox.pack_start(self.icon, False, False, 0)
		hbox.pack_start(self.title, True, True, 0)
		hbox.pack_start(self.status, False, False, 0)
		hbox.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(*self.color))
		eb.add(hbox)
		# Update stuff
		self.header_box = hbox
		self.header = eb
		self.header.set_parent(self)
		self.children = [self.header, self.child]
	
	def init_grid(self):
		# Create widgets
		self.grid = Gtk.Grid()
		self.rev = RevealerClass()
		align = Gtk.Alignment()
		self.eb = Gtk.EventBox()
		# Set values
		self.grid.set_row_spacing(1)
		self.grid.set_column_spacing(3)
		self.rev.set_reveal_child(False)
		align.set_padding(2, 2, 5, 5)
		self.eb.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(*self.background))
		self.grid.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(*self.background))
		# Connect signals
		self.eb.connect("button-release-event", self.on_grid_release)
		self.eb.connect("button-press-event", self.on_grid_click)
		self.eb.connect('enter-notify-event', self.on_enter_notify)
		self.eb.connect('leave-notify-event', self.on_leave_notify)
		# Pack together
		align.add(self.grid)
		self.eb.add(align)
		self.rev.add(self.eb)
		self.add(self.rev)
	
	### GtkWidget-related stuff
	def do_add(self, widget):
		if not widget is None:
			if self.child is None:
				self.child = widget
				self.children = [self.header, self.child]
				widget.set_parent(self)
 
	def do_remove(self, widget):
		if self.child == widget:
			self.child = None
			self.children = [self.header, self.child]
			widget.unparent()
 
	def do_child_type(self):
		return(Gtk.Widget.get_type())
 
	def do_forall(self, include_internals, callback, *callback_parameters):
		if not callback is None:
			if hasattr(self, 'children'): # No idea why this happens...
				for c in self.children:
					if not c is None:
						callback(c, *callback_parameters)
 
	def do_get_request_mode(self):
		return(Gtk.SizeRequestMode.CONSTANT_SIZE)
 
	def do_get_preferred_height(self):
		mw, nw, mh, nh = self.get_prefered_size()
		return(mh, nh)
 
	def do_get_preferred_width(self):
		mw, nw, mh, nh = self.get_prefered_size()
		return(mw, nw)
	
	def get_prefered_size(self):
		""" Returns (min_width, nat_width, min_height, nat_height) """
		min_width, nat_width = 0, 0
		min_height, nat_height = 0, 0
		# Use max of prefered widths from children;
		# Use sum of predered height from children.
		for c in self.children:
			if not c is None:
				if c != self.rev or self.rev.get_reveal_child() or self.rev.get_child_revealed():
					mw, nw = c.get_preferred_width()
					mh, nh = c.get_preferred_height()
					min_width = max(min_width, mw)
					nat_width = max(nat_width, nw)
					min_height = min_height + mh
					nat_height = nat_height + nh
		# Add border size
		min_width += self.border_width * 2	# Left + right border
		nat_width += self.border_width * 2
		min_height += self.border_width * 3	# Top + below header + bottom
		nat_height += self.border_width * 3
		return(min_width, nat_width, min_height, nat_height)
 
	def do_size_allocate(self, allocation):
		child_allocation = Gdk.Rectangle()
		child_allocation.x = self.border_width
		child_allocation.y = self.border_width
 
		self.set_allocation(allocation)
 
		if self.get_has_window():
			if self.get_realized():
				self.get_window().move_resize(allocation.x, allocation.y, allocation.width, allocation.height)
		
		# Allocate childrens as VBox does, always use all available width
		for c in self.children:
			if not c is None:
				if c.get_visible():
					min_size, nat_size = c.get_preferred_size()
					child_allocation.width = allocation.width - (self.border_width * 2)
					child_allocation.height = min_size.height
					# TODO: Handle child that has window (where whould i get it?)
					c.size_allocate(child_allocation)
					child_allocation.y += child_allocation.height + self.border_width

 
	def do_realize(self):
		allocation = self.get_allocation()
 
		attr = Gdk.WindowAttr()
		attr.window_type = Gdk.WindowType.CHILD
		attr.x = allocation.x
		attr.y = allocation.y
		attr.width = allocation.width
		attr.height = allocation.height
		attr.visual = self.get_visual()
		attr.event_mask = self.get_events() | Gdk.EventMask.EXPOSURE_MASK
 
		WAT = Gdk.WindowAttributesType
		mask = WAT.X | WAT.Y | WAT.VISUAL
 
		window = Gdk.Window(self.get_parent_window(), attr, mask);
		window.set_decorations(0)
		self.set_window(window)
		self.register_window(window)
		self.set_realized(True)
 
	def do_draw(self, cr):
		allocation = self.get_allocation()
		
		header_al = self.children[0].get_allocation()
		
		# Border
		cr.set_source_rgba(*self.real_color)
		cr.move_to(0, self.border_width / 2.0)
		cr.line_to(0, allocation.height)
		cr.line_to(allocation.width, allocation.height)
		cr.line_to(allocation.width, self.border_width / 2.0)
		cr.set_line_width(self.border_width * 2) # Half of border is rendered outside of widget
		cr.stroke()
		
		# Background
		if not self.background is None:
			# Use set background color
			cr.set_source_rgba(*self.background)
			cr.rectangle(self.border_width,
					self.border_width,
					allocation.width - (2 * self.border_width),
					allocation.height - (2 * self.border_width)
					)
			cr.fill()
		
		# Header
		cr.set_source_rgba(*self.real_color)
		cr.rectangle(self.border_width / 2.0, 0, allocation.width - self.border_width, header_al.height + (2 * self.border_width))
		cr.fill()
		
		for c in self.children:
			if not c is None:
				self.propagate_draw(c, cr)
            
	### InfoBox logic
	def set_header_cursor(self, eb, *a):
		""" Sets cursor over top part of infobox to hand """
		eb.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND1))
	
	def on_header_click(self, eventbox, event):
		"""
		Hides or reveals everything below header
		Displays popup menu on right click
		"""
		if event.button == 1:	# left
			self.rev.set_reveal_child(not self.rev.get_reveal_child())
			self.app.cb_open_closed(self)
		elif event.button == 3:	# right
			self.emit('right-click', event.button, 0)
	
	def on_grid_release(self, eventbox, event):
		""" Displays popup menu on right click """
		if event.button == 3:	# right
			self.emit('right-click', event.button, 0)
	
	def on_grid_click(self, eventbox, event):
		""" Emits 'doubleclick' signal """
		if event.button == 1:	# Left
			if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
				self.emit('doubleclick')
	
	def hilight_timer(self, *a):
		""" Called repeatedly while color is changing """
		if self.hilight and self.hilight_factor < 1.0:
			self.hilight_factor = min(1.0, self.hilight_factor + COLOR_CHANGE_STEP)
		elif not self.hilight and self.hilight_factor > 0.0:
			self.hilight_factor = max(0.0, self.hilight_factor - COLOR_CHANGE_STEP)		
		else:
			self.timer_enabled = False
		self.recolor()
		return self.timer_enabled
	
	def recolor(self, *a):
		"""
		Called to computes actual color every time when self.color or
		self.hilight_factor changes.
		"""
		if self.dark_color is None:
			self.real_color = tuple([ min(1.0, x + HILIGHT_INTENSITY * math.sin(self.hilight_factor)) for x in self.color])
		else:
			# Darken colors when dark bacground is enabled
			self.real_color = tuple([ min(1.0, DARKEN_FACTOR * (x + HILIGHT_INTENSITY * math.sin(self.hilight_factor))) for x in self.color])
		gdkcol = Gdk.RGBA(*self.real_color)
		self.header.override_background_color(Gtk.StateType.NORMAL, gdkcol)
		try:
			self.header.get_children()[0].override_background_color(Gtk.StateFlags.NORMAL, gdkcol)
		except IndexError:
			# Happens when recolor is called before header widget is created
			pass

		self.queue_draw()
	
	### Translated events
	def on_enter_notify(self, eb, event, *data):
		self.emit("enter-notify-event", None, *data)
	
	def on_leave_notify(self, eb, event, *data):
		self.emit("leave-notify-event", None, *data)
	
	### Methods
	def set_title(self, t):
		self.str_title = t
		inverted = self.header_inverted and self.dark_color is None
		col = "black" if inverted else "white"
		self.title.set_markup('<span color="%s" %s>%s</span>' % (
			col,
			self.app.config["infobox_style"],
			t
		))
	
	def get_title(self):
		return self.str_title
	
	def get_icon(self):
		""" Returns icon widget """
		return self.icon
	
	def set_icon(self, icon):
		""" Sets new icon. Expects widget as parameter """
		self.header_box.remove(self.icon)
		self.header_box.pack_start(icon, False, False, 0)
		self.header_box.reorder_child(icon, 0)
		self.header_box.show_all()
		self.icon = icon
	
	def set_hilight(self, h):
		if self.hilight != h:
			self.hilight = h
			if not self.timer_enabled:
				GLib.timeout_add(COLOR_CHANGE_TIMER, self.hilight_timer)
				self.timer_enabled = True
	
	def invert_header(self, e):
		self.header_inverted = e
		self.set_title(self.str_title)
	
	def set_status(self, t, percentage=0.0):
		if percentage > 0.0 and percentage < 1.0:
			percent = percentage * 100.0
			self.status.set_markup('<span color="white" %s>%s (%.f%%)</span>' % (
				self.app.config["infobox_style"],
				t, percent))
			log.debug("%s state changed to %s (%s%%)", self.str_title, t, percent)
		else:
			self.status.set_markup('<span color="white" %s>%s</span>' % (
				self.app.config["infobox_style"],
				t))
			if self.str_status != t:
				log.debug("%s state changed to %s", self.str_title, t)
		self.str_status = t
	
	def get_status(self):
		return self.str_status
	
	@classmethod
	def hex2color(self, hx):
		"""
		Converts color from AABBCC or #AABBCC format to tuple of floats
		"""
		hx = hx.lstrip('#')
		l = len(hx)
		color = [ float(int(hx[i:i+l/3], 16)) / 255.0 for i in range(0, l, l/3) ]
		while len(color) < 4:
			color.append(1.0)
		return color
	
	def set_color_hex(self, hx):
		""" Expects AABBCC or #AABBCC format """
		self.set_color(*InfoBox.hex2color(hx))
		
	def set_color(self, r, g, b, a):
		""" Expects floats """
		self.color = (r, g, b, a)
		self.recolor()
	
	def compare_color_hex(self, hx):
		"""
		Returns True if specified color is same as color currently used.
		Expects AABBCC or #AABBCC format
		"""
		return self.compare_color(*InfoBox.hex2color(hx))
	
	def compare_color(self, r, g, b, a):
		"""
		Returns True if specified color is same as color currently used.
		Expects floats.
		"""
		return (self.color == (r, g, b, a))
	
	def set_dark_color(self, r, g, b, a):
		""" 
		Overrides background color, inverts icon colors and darkens some borders
		"""
		# Override background
		self.background = self.dark_color = (r, g, b, a)
		self.set_bg_color(*self.background)
		# Recolor existing widgets
		self.text_color = (1, 1, 1, 1)
		col = Gdk.RGBA(*self.text_color)
		for key in self.value_widgets:
			for w in self.value_widgets[key]:
				if isinstance(w, Gtk.Image):
					if (Gtk.get_major_version(), Gtk.get_minor_version()) <= (3, 10):
						# Mint....
						v1 = GObject.Value(int, 0)
						v2 = GObject.Value(int, 0)
						self.grid.child_get_property(w, "left-attach", v1)
						self.grid.child_get_property(w, "top-attach", v2)
						la, ta = v1.get_int(), v2.get_int()
					else:
						la = self.grid.child_get_property(w, "left-attach")
						ta = self.grid.child_get_property(w, "top-attach")
					vis = not w.get_no_show_all()
					wIcon = self._prepare_icon(self.icons[key])
					w.get_parent().remove(w)
					self.grid.attach(wIcon, la, ta, 1, 1)
					if not vis:
						wIcon.set_no_show_all(True)
						wIcon.set_visible(False)
					wValue, trash, wTitle = self.value_widgets[key]
					self.value_widgets[key] = (wValue, wIcon, wTitle)
				else:
					w.override_color(Gtk.StateFlags.NORMAL, col)
		# Recolor borders
		self.recolor()
		# Recolor header
		self.set_title(self.str_title)
	
	def set_bg_color(self, r, g, b, a):
		""" Expects floats """
		if self.dark_color == None:
			self.background = (r, g, b, a)
		col = Gdk.RGBA(r, g, b, a)
		for key in self.value_widgets:
			for w in self.value_widgets[key ]:
				w.override_background_color(Gtk.StateFlags.NORMAL, col)
		self.eb.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(*self.background))
		self.grid.override_background_color(Gtk.StateType.NORMAL, col)
	
	def set_border(self, width):
		self.border_width = width
		self.queue_resize()
	
	def set_open(self, b):
		self.rev.set_reveal_child(b)
	
	def is_open(self):
		""" Returns True if box is open """
		return self.rev.get_reveal_child()
	
	def _prepare_icon(self, icon):
		if icon.endswith(".svg"):
			# Icon is svg file
			key = icon if self.dark_color is None else icon + "-dark"
			if not key in svg_cache:
				if not self.dark_color is None:
					# Recolor svg for dark theme
					svg_source = file(os.path.join(self.app.iconpath, icon), "r").read()
					svg_source = svg_source.replace('fill:rgb(0%,0%,0%)', 'fill:rgb(100%,100%,100%)')
					svg = Rsvg.Handle.new_from_data(svg_source.encode("utf-8"))
				else:
					# Load svg directly
					svg = Rsvg.Handle.new_from_file(os.path.join(self.app.iconpath, icon))
				pixbuf = svg.get_pixbuf()
				svg_cache[key] = pixbuf
			return Gtk.Image.new_from_pixbuf(svg_cache[key])
		elif "." in icon:
			# Icon is other image file (png)
			return Gtk.Image.new_from_file(os.path.join(self.app.iconpath, icon))
		else:
			# Icon is theme icon name
			return Gtk.Image.new_from_icon_name(icon, 1)
	
	def add_value(self, key, icon, title, value="", visible=True):
		""" Adds new line with provided properties """
		wIcon = self._prepare_icon(icon)
		wTitle, wValue = Gtk.Label(), Gtk.Label()
		self.value_widgets[key] = (wValue, wIcon, wTitle)
		self.set_value(key, value)
		self.icons[key] = icon
		wTitle.set_text(title)
		wTitle.set_alignment(0.0, 0.5)
		wValue.set_alignment(1.0, 0.5)
		wValue.set_ellipsize(Pango.EllipsizeMode.START)
		wTitle.set_property("expand", True)
		line = len(self.value_widgets)
		self.grid.attach(wIcon, 0, line, 1, 1)
		self.grid.attach_next_to(wTitle, wIcon, Gtk.PositionType.RIGHT, 1, 1)
		self.grid.attach_next_to(wValue, wTitle, Gtk.PositionType.RIGHT, 1, 1)
		for w in self.value_widgets[key]:
			w.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(*self.background))
			w.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(*self.text_color))
			if not visible:
				w.set_no_show_all(True)
	
	def clear_values(self):
		""" Removes all lines from UI, efectively making all values hidden """
		for ch in [ ] + self.grid.get_children():
			self.grid.remove(ch)
		self.value_widgets = {}
	
	def add_hidden_value(self, key, value):
		""" Adds value that is saved, but not shown on UI """
		self.set_value(key, value)
	
	def set_value(self, key, value):
		""" Updates already existing value """
		self.values[key] = value
		if key in self.value_widgets:
			if value is None:
				self.value_widgets[key][0].set_text("?")
			else:
				self.value_widgets[key][0].set_text(value)
	
	def hide_value(self, key):
		""" Hides value added by add_value """
		if key in self.value_widgets:
			for w in self.value_widgets[key]:
				w.set_no_show_all(True)
				w.set_visible(False)
	
	def show_value(self, key):
		""" Shows value added by add_value """
		if key in self.value_widgets:
			for w in self.value_widgets[key]:
				w.set_no_show_all(False)
				w.set_visible(True)
	
	def set_visible(self, key, show):
		""" Sets value visibility """
		if show:
			self.show_value(key)
		else:
			self.hide_value(key)

	def hide_values(self, *keys):
		""" Same as hide_value, but for multiple keys at once """
		for k in keys: self.hide_value(k)
	
	def show_values(self, *keys):
		""" Same as show_value, but for multiple keys at once """
		for k in keys: self.show_value(k)
	
	def get_value(self, key):
		return self.values[key]
	
	def __getitem__(self, key):
		""" Shortcut to get_value """
		return self.values[key]
	
	def __setitem__(self, key, value):
		""" Shortcut to set_value. Creates new hidden_value if key doesn't exist """
		self.set_value(key, value)
