#!/usr/bin/env python2
"""
Syncthing-GTK - 1st run wizard

Runs syncthing daemon with -generate option and setups some
values afterwards.
"""

from __future__ import unicode_literals
from gi.repository import Gtk, GLib
from syncthing_gtk import Configuration, DaemonProcess
import os, sys

_ = lambda (a) : a

class Wizard(Gtk.Assistant):
	def __init__(self, iconpath="/usr/share/syncthing-gtk/icons", config=None):
		# Init
		Gtk.Assistant.__init__(self)
		if not config is None:
			self.config = config
		else:
			self.config = Configuration()
		self.iconpath = iconpath
		self.connect("prepare", self.prepare_page)
		# Window setup
		self.set_position(Gtk.WindowPosition.CENTER)
		self.set_size_request(550, -1)
		self.set_default_size(550, 300)
		self.set_deletable(True)
		self.set_icon_from_file(os.path.join(self.iconpath, "st-logo-24.png"))
		self.set_title("%s %s" % (_("Syncthing-GTK"), _("First run wizard")))
		# Add "Quit" button
		quit_button = Gtk.Button.new_from_stock("gtk-quit")
		self.add_action_widget(quit_button)
		quit_button.set_visible(True)
		quit_button.connect("clicked", lambda *a : self.emit("cancel"))
		# Pages
		self.add_page(IntroPage())
		self.add_page(FindDaemonPage())
		self.add_page(GenerateKeysPage())
		self.add_page(HttpSettingsPage())
	
	def add_page(self, page):
		""" Adds page derived from custom Page class """
		self.append_page(page)
		page.parent = self
		self.set_page_type(page, page.TYPE)
		self.set_page_title(page, page.TITLE)
	
	def prepare_page(self, another_self, page):
		""" Called before page is displayed """
		self.commit() # Prevents back button from being displayed
		page.prepare()
	
	def find_widget(self, compare_fn, parent=None):
		"""
		Recursively searchs for widget, returning first one
		for which compare_fn(widget) returns True
		"""
		if parent is None : parent = self
		for w in parent.get_children():
			if isinstance(w, Gtk.Button):
				print w.get_label()
			if compare_fn(w): return w
			if isinstance(w, Gtk.Container):
				r = self.find_widget(compare_fn, w)
				if not r is None: return r
		return None
	
	def run(self, *a):
		self.show()
		self.connect('cancel', Gtk.main_quit)
		self.connect('close', Gtk.main_quit)
		Gtk.main()

class WrappedLabel(Gtk.Label):
	def __init__(self, markup):
		Gtk.Label.__init__(self)
		self.set_justify(Gtk.Justification.LEFT)
		self.set_line_wrap(True)
		self.set_markup(markup)

# @AbstractClass
class Page(Gtk.Grid):
	# TYPE = <needs to be defined in derived class>
	# TITLE = <needs to be defined in derived class>
	def __init__(self):
		Gtk.Grid.__init__(self)
		self.init_page()
		self.show_all()
		self.parent = None
	
	def prepare(self):
		""" Sets page as complete by default """
		self.parent.set_page_complete(self, True)

class IntroPage(Page):
	TYPE = Gtk.AssistantPageType.INTRO
	TITLE = _("Intro")
	def init_page(self):
		""" First, intro page. Just static text that explains what's going on """ 
		config_folder = "~/.config/syncthing"
		config_folder_link = '<a href="file://%s">%s</a>' % (
				os.path.expanduser(config_folder), config_folder)
		self.attach(WrappedLabel(
			_("<b>Welcome to Syncthing-GTK first run wizard!</b>") +
			"\n\n" +
			_("It looks like you never have used Syncthing.") + " " +
			_("Initial configuration should be created.") +  " " +
			_("Please, click <b>next</b> to create Syncthing configuration or <b>quit</b> to exit") +
			"\n\n" +
			(_("If you already had Syncthing daemon configured, please, "
			  "exit this wizard and check your %s folder") % config_folder_link )
		), 0, 0, 1, 1)

class FindDaemonPage(Page):
	TYPE = Gtk.AssistantPageType.PROGRESS
	TITLE = _("Find Daemon")
	def init_page(self):
		""" Displayed while syncthing binary is being searched for """
		self.label = WrappedLabel(
			_("<b>Searching for syncthing daemon.</b>") +
			"\n\n" +
			_("Please wait...")
		)
		self.attach(self.label, 0, 0, 1, 1)
	
	def error(self):
		"""
		FindDaemonPage turns into error page if syncthing binary
		is not found.
		"""
		local_bin_folder = "~/.local/bin"
		local_bin_folder_link = '<a href="file://%s">%s</a>' % (
				os.path.expanduser(local_bin_folder), local_bin_folder)
		dll_link = '<a href="https://github.com/syncthing/syncthing/releases">' + \
				_('download latest binary') + '</a>'
		self.label.set_markup(
			_("<b>Syncthing daemon not found.</b>") +
			"\n\n" +
			_("Please, use package manager to install syncthing package") +
			(_("or %s from syncthing page and save it") % dll_link) +
			(_("to your %s or any other directory in PATH") % local_bin_folder_link)
		)
	
	def prepare(self):
		paths = [ "./" ]
		paths += [ os.path.expanduser("~/.local/bin") ]
		if "PATH" in os.environ:
			paths += os.environ["PATH"].split(":")
		print "Searching for syncthing binary..."
		GLib.idle_add(self.search, paths)
	
	def search(self, paths):
		"""
		Called repeatedly throught GLib.idle_add, until binary is found
		or all possible paths are tried.
		"""
		try:
			path, paths = paths[0], paths[1:]
		except IndexError:
			# Out of possible paths. Not found
			return self.error()
		for bin in ("syncthing", "syncthing.x86", "syncthing.x86_64", "pulse"):
			bin_path = os.path.join(path, bin)
			print " ...", bin_path,
			if os.path.isfile(bin_path):
				if os.access(bin_path, os.X_OK):
					# File exists and is executable
					print "FOUND"
					self.parent.config["syncthing_binary"] = bin_path
					self.parent.set_page_complete(self, True)
					self.parent.next_page()
					return
				else:
					print "not executable"
			else:
				print "not found"
		GLib.idle_add(self.search, paths)

class GenerateKeysPage(Page):
	TYPE = Gtk.AssistantPageType.PROGRESS
	TITLE = _("Generate keys")
	def init_page(self):
		""" Displayed while syncthing binary is being searched for """
		self.label = WrappedLabel(
			_("<b>Syncthing is generating RSA key and certificate.</b>") +
			"\n\n" +
			_("This may take a while...")
		)
		self.attach(self.label, 0, 0, 1, 1)
	
	def prepare(self):
		GLib.idle_add(self.start_binary)
	
	def start_binary(self):
		"""
		Starts syncthing binary with -generate parameter and waits until
		key generation is finished
		"""
		# self.process = DaemonProcess([ self.parent.config["syncthing_binary"], "-no-browser" ])
		self.process = DaemonProcess([ "false" ])
		self.process.connect('line', self.cb_daemon_line)
		self.process.connect('exit', self.cb_daemon_exit)
	
	def error(self):
		"""
		GenerateKeysPage turns into error page if syncthing binary
		fails to generate keys.
		"""
		self.label.set_markup(
			_("<b>Failed to generate keys.</b>") +
			"\n\n" +
			_("blah.") +
			_("TODO: This message")
		)
		
	def cb_daemon_line(self, dproc, line):
		print line
	
	def cb_daemon_exit(self, dproc, exit_code):
		if exit_code == 0:
			self.parent.set_page_complete(self, True)
		else:
			self.error()

class HttpSettingsPage(Page):
	TYPE = Gtk.AssistantPageType.CONTENT
	TITLE = _("Setup WebUI")
	def init_page(self):
		""" Displayed while syncthing binary is being searched for """
		self.attach(WrappedLabel(
			_("<b>WebUI setup</b>")
		), 0, 0, 1, 1)
	
	#def prepare(self):
	#	pass
