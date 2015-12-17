#!/usr/bin/env python2
"""
Syncthing-GTK - 1st run wizard

Basically runs Syncthing daemon with -generate option and setups some
values afterwards.
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
from syncthing_gtk import Configuration, DaemonProcess
from syncthing_gtk import DaemonOutputDialog, StDownloader
from syncthing_gtk.tools import get_config_dir, IS_WINDOWS, is_portable
from syncthing_gtk.tools import can_upgrade_binary, compare_version
from syncthing_gtk.tools import _ # gettext function
import os, sys, socket, random, string
import logging, traceback, platform
from xml.dom import minidom

log = logging.getLogger("Wizard")

DEFAULT_PORT = 8080
MAX_PORT = 8100

class Wizard(Gtk.Assistant):
	def __init__(self, gladepath="/usr/share/syncthing-gtk",
				iconpath="/usr/share/syncthing-gtk/icons", config=None):
		# Init
		Gtk.Assistant.__init__(self)
		if not config is None:
			self.config = config
		else:
			self.config = Configuration()
		self.gladepath = gladepath
		self.iconpath = iconpath
		self.syncthing_options = {}
		self.lines = []					# Daemon and wizard output,
										# maybe for error reports
		self.finished = False
		self.connect("prepare", self.prepare_page)
		# Find syncthing configuration directory
		self.st_configdir = os.path.join(get_config_dir(), "syncthing")
		self.st_configfile = os.path.join(get_config_dir(), "syncthing", "config.xml")
		# Window setup
		self.set_position(Gtk.WindowPosition.CENTER)
		self.set_size_request(720, -1)
		self.set_default_size(720, 300)
		self.set_deletable(True)
		if IS_WINDOWS:
			self.set_icon_list([GdkPixbuf.Pixbuf.new_from_file("icons/32x32/apps/syncthing-gtk.png")])
		else:
			self.set_icon_name("syncthing-gtk")
		self.set_title("%s %s" % (_("Syncthing-GTK"), _("First run wizard")))
		# Add "Quit" button
		self.quit_button = Gtk.Button.new_from_stock("gtk-quit")
		self.add_action_widget(self.quit_button)
		self.quit_button.set_visible(True)
		self.quit_button.connect("clicked", lambda *a : self.emit("cancel"))
		# Pages
		self.add_page(IntroPage())
		self.add_page(FindDaemonPage())
		self.add_page(GenerateKeysPage())
		self.add_page(HttpSettingsPage())
		self.add_page(SaveSettingsPage())
		self.add_page(LastPage())
	
	def add_page(self, page):
		""" Adds page derived from custom Page class """
		index = self.append_page(page)
		page.parent = self
		self.set_page_type(page, page.TYPE)
		self.set_page_title(page, _(page.TITLE) + "  ")
		return index
	
	def insert(self, page):
		"""
		Inserts new page after currently displayed.
		"""
		index = self.get_current_page()
		index = self.insert_page(page, index + 1)
		page.parent = self
		self.set_page_type(page, page.TYPE)
		self.set_page_title(page, _(page.TITLE) + "  ")
		return index
	
	def insert_and_go(self, page):
		"""
		Inserts new page after currently displayed
		and switches to it.
		"""
		index = self.insert(page)
		self.set_current_page(index)		
		return index
	
	def prepare_page(self, another_self, page):
		""" Called before page is displayed """
		self.commit() # Prevents back button from being displayed
		page.prepare()
	
	def find_widget(self, compare_fn, parent=None):
		"""
		Recursively searches for widget, returning first one
		for which compare_fn(widget) returns True
		"""
		if parent is None : parent = self
		for w in parent.get_children():
			if compare_fn(w): return w
			if isinstance(w, Gtk.Container):
				r = self.find_widget(compare_fn, w)
				if not r is None: return r
		return None
	
	def output_line(self, line):
		""" Called for every line that wizard or daemon process outputs """
		self.lines.append(line)
		log.info(line)
	
	def error(self, page, title, message, display_bugreport_link):
		"""
		Called from pages on error. Removes everything from page and
		creates error message.
		"""
		for c in [] + page.get_children() :
			page.remove(c)
		# Title
		l_title = WrappedLabel("<b>%s</b>" % (title,))
		l_title.props.margin_bottom = 15
		page.attach(l_title,	0, 0, 2, 1)
		# Message
		l_message = WrappedLabel(message)
		l_message.props.margin_bottom = 15
		page.attach(l_message,	0, 1, 2, 1)
		# Bugreport link
		if display_bugreport_link:
			github_link = '<a href="https://github.com/syncthing/syncthing-gtk/issues">GitHub</a>'
			l_bugreport = WrappedLabel(
				_("Please, check error log and fill bug report on %s.") % (github_link,)
			)
			page.attach(l_bugreport, 0, 2, 2, 1)
			# 'Display error log' button
			button = Gtk.Button(_("Display error log"))
			button.props.margin_top = 25
			page.attach(button, 1, 3, 2, 1)
			button.connect("clicked", lambda *a : self.show_output())
		
		page.show_all()
		return page
	
	def show_output(self, *a):
		"""
		Displays DaemonOutput window with error messages captured
		during key generation.
		"""
		d = DaemonOutputDialog(self, None)
		d.show_with_lines(self.lines, self)
	
	def is_finished(self):
		""" Returns True if user finished entire wizard """
		return self.finished
	
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
		self.set_alignment(0, 0.5)

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
	TITLE = "Intro"
	def init_page(self):
		""" First, intro page. Just static text that explains what's going on """ 
		config_folder = "~/.config/syncthing"
		config_folder_link = '<a href="file://%s">%s</a>' % (
				os.path.expanduser(config_folder), config_folder)
		self.attach(WrappedLabel(
			"<b>" + _("Welcome to Syncthing-GTK first run wizard!") + "</b>" +
			"\n\n" +
			_("It looks like you never have used Syncthing.") + " " +
			_("Initial configuration should be created.") +  " " +
			_("Please click <b>Next</b> to create a Syncthing configuration file or <b>Quit</b> to exit") +
			"\n\n" +
			(_("If you already had Syncthing daemon configured, please, "
			  "exit this wizard and check your %s folder") % config_folder_link )
		), 0, 0, 1, 1)

class FindDaemonPage(Page):
	# Next page, "Download Daemon" is displayed only if needed.
	# When that happens, it becomes page with longest title and wizard
	# window changes size to accommodate this change. And i don't like
	# that.
	# To prevent this 'window jumping', padding is added here, so
	# this page is always one with longest name.
	TITLE = "Find Daemon"
	TYPE = Gtk.AssistantPageType.PROGRESS
	def init_page(self):
		""" Displayed while Syncthing binary is being searched for """
		self.label = WrappedLabel(
			"<b>" + _("Searching for Syncthing daemon.") + "</b>" +
			"\n\n" +
			_("Please wait...")
		)
		self.paths = []
		self.version_string = "v0.0"
		self.ignored_version = None
		self.attach(self.label, 0, 0, 1, 1)
	
	def prepare(self):
		self.paths = [ "./" ]
		self.paths += [ os.path.expanduser("~/.local/bin"), self.parent.st_configdir ]
		if is_portable():
			self.paths += [ ".\\data" ]
		if StDownloader is None:
			self.binaries = ["syncthing"]
		else:
			suffix, trash = StDownloader.determine_platform()
			self.binaries = ["syncthing", "syncthing%s" % (suffix,)]
			if suffix == "x64":
				# Allow 32bit binary on 64bit
				self.binaries += ["syncthing.x86"]
		if IS_WINDOWS:
			self.paths += [ "c:/Program Files/syncthing",
				"c:/Program Files (x86)/syncthing",
				self.parent.st_configdir
				]
			self.binaries = ("syncthing.exe",)
		if "PATH" in os.environ:
			self.paths += os.environ["PATH"].split(":")
		log.info("Searching for syncthing binary...")
		GLib.idle_add(self.search)
	
	def search(self):
		"""
		Called repeatedly through GLib.idle_add, until binary is found
		or all possible paths are tried.
		"""
		try:
			path, self.paths = self.paths[0], self.paths[1:]
		except IndexError:
			# Out of possible paths. Not found
			if IS_WINDOWS:
				# On Windows, don't say anything and download Syncthing
				# directly
				self.parent.insert_and_go(DownloadSTPage())
				return False
			elif StDownloader is None:
				# On Linux with updater disabled, generate and
				# display error page
				title = _("Syncthing daemon not found.")
				message = _("Please, use package manager to install the Syncthing package.")
				page = self.parent.error(self, title, message, False)
				page.show_all()
				return False
			else:
				# On Linux with updater generate similar display error
				# and offer download
				from syncthing_gtk.app import MIN_ST_VERSION
				target_folder_link = '<a href="file://%s">%s</a>' % (
						os.path.expanduser(StDownloader.get_target_folder()),
						StDownloader.get_target_folder())
				dll_link = '<a href="https://github.com/syncthing/syncthing/releases">' + \
						_('download latest binary') + '</a>'
				message, title = "", None
				if self.ignored_version == None:
					# No binary was found
					title = _("Syncthing daemon not found.")
					message += _("Please, use package manager to install the Syncthing package "
								 "or %(download_link)s from Syncthing page and save it to your "
								 "%(target)s directory.") % {
						'download_link' : dll_link,
						'target' : target_folder_link
					}
				else:
					# Binary was found, but it was too old to be ussable
					title = _("Syncthing daemon is too old.")
					message += _("Syncthing-GTK needs Syncthing daemon %(min)s or newer, but only %(actual)s were found.") % {
						'min' : MIN_ST_VERSION,
						'actual' : self.ignored_version
					}
					message += "\n"
					message += _("Please, use package manager to install the Syncthing package "
								 "or %(download_link)s from Syncthing page and save it to your "
								 "%(target)s directory.") % {
						'download_link' : dll_link,
						'target' : target_folder_link
					}
				message += "\n\n"
				message += _("Alternatively, Syncthing-GTK can download Syncthing binary") + " "
				message += _("to %s and keep it up-to-date, but this option is meant as") % \
							(target_folder_link,) + " "
				message += _("last resort and generally not suggested.")
				page = self.parent.error(self, title, message, False)
				# Attach [ ] Download Syncthing checkbox
				cb = Gtk.CheckButton(_("_Download Syncthing binary"), use_underline=True)
				cb.connect("toggled", lambda cb, *a : self.parent.set_page_complete(page, cb.get_active()))
				page.attach(cb,	0, 2, 2, 1)
				# Attach [ ] Autoupdate checkbox
				cb = Gtk.CheckButton(_("Auto_update downloaded binary"), use_underline=True)
				cb.connect("toggled", lambda cb, *a : self.parent.config.set("st_autoupdate", cb.get_active()))
				page.attach(cb,	0, 3, 2, 1)
				page.show_all()
				# Add Download page
				self.parent.insert(DownloadSTPage())
				return False
		
		for bin in self.binaries:
			bin_path = os.path.join(path, bin)
			log.info(" ... %s", bin_path)
			if os.path.isfile(bin_path):
				if os.access(bin_path, os.X_OK):
					# File exists and is executable, run it and parse
					# version string from output
					log.info("Binary found in %s", bin_path)
					if IS_WINDOWS: bin_path = bin_path.replace("/", "\\")
					p = DaemonProcess([ bin_path, '-version' ])
					p.connect('line', self.cb_process_output)
					p.connect('exit', self.cb_process_exit)
					p.connect('failed', self.cb_process_exit)
					p.start()
					return False
				else:
					log.info("Binary in %s is not not executable", bin_path)
		return True
	
	def cb_process_output(self, process, line):
		"""
		Called when daemon binary outputs line while it's being asked
		for version string.
		"""
		try:
			# Parse version string
			v = line.split(" ")[1]
			if v.startswith("v"):
				self.version_string = v
		except Exception:
			# Not line with version string, probably some other output
			pass
	
	def cb_process_exit(self, process, *a):
		""" Called after daemon binary outputs version and exits """
		from syncthing_gtk.app import MIN_ST_VERSION
		bin_path = process.get_commandline()[0]
		if compare_version(self.version_string, MIN_ST_VERSION):
			# Daemon binary exists, is executable and meets
			# version requirements. That's good, btw.
			self.parent.config["syncthing_binary"] = bin_path
			if not can_upgrade_binary(bin_path):
				# Don't try enable auto-update if binary is in
				# non-writable location (auto-update is enabled
				# by default on Windows only)
				self.parent.config["st_autoupdate"] = False
			self.parent.set_page_complete(self, True)
			self.label.set_markup(
					"<b>" + _("Syncthing daemon binary found.") + "</b>" +
					"\n\n" +
					_("Binary path:") + " " + bin_path + "\n" +
					_("Version:") + " " + self.version_string
				)
		else:
			# Found daemon binary too old to be ussable.
			# Just ignore it and try to find better one.
			log.info("Binary in %s is too old", bin_path)
			self.ignored_version = self.version_string
			GLib.idle_add(self.search)

class DownloadSTPage(Page):
	TYPE = Gtk.AssistantPageType.PROGRESS
	TITLE = "Download Daemon"
	
	def init_page(self):
		""" Displayed while wizard downloads and extracts daemon """
		self.label = WrappedLabel("<b>" + _("Downloading Syncthing daemon.") + "</b>")
		self.version = WrappedLabel(_("Please wait..."))
		self.pb = Gtk.ProgressBar()
		self.label.props.margin_bottom = 15
		self.target = None
		self.attach(self.label,		0, 0, 1, 1)
		self.attach(self.version,	0, 1, 1, 1)
		self.attach(self.pb,		0, 2, 1, 1)
	
	def prepare(self):
		# Determine which Syncthing to use
		suffix, tag = StDownloader.determine_platform()
		# Report error on unsupported platforms
		if suffix is None or tag is None:
			pd = "%s %s %s" % (
				platform.uname()[0], platform.uname()[2],	# OS, version
				platform.uname()[4])						# architecture
			self.parent.error(self,
				_("Cannot download Syncthing daemon."),
				_("This platform (%s) is not supported") % (pd,),
				False)
			return
		# Determine target file & directory
		self.target = os.path.join(
			os.path.expanduser(StDownloader.get_target_folder()),
			"syncthing%s" % (suffix,)
			)
		# Create downloader and connect events
		self.sd = StDownloader(self.target, tag)
		self.sd.connect("error", self.on_download_error)
		self.sd.connect("version", self.on_version)
		self.sd.connect("download-progress", self.on_progress)
		self.sd.connect("download-finished", self.on_extract_start)
		self.sd.connect("extraction-progress", self.on_progress)
		self.sd.connect("extraction-finished", self.on_extract_finished)
		# Start downloading
		self.sd.get_version()
	
	def on_download_error(self, downloader, error, message):
		"""
		Called when download fails. This is fatal for now, user can
		only observe message, cry and quit program.
		"""
		message = "%s\n%s" % (
			str(error) if not error is None else "",
			message if not message is None else ""
			)
		self.parent.error(self,
			_("Failed to download Syncthing daemon package."),
			message, False)
		return
	
	def on_version(self, dowloader, version):
		self.version.set_markup("Downloading %s..." % (version, ))
		dowloader.download()
	
	def on_extract_start(self, *a):
		self.version.set_markup("Extracting...")
	
	def on_progress(self, dowloader, progress):
		self.pb.set_fraction(progress)
	
	def on_extract_finished(self, *a):
		""" Called after extraction is finished """
		# Everything done. Praise supernatural entities...
		self.label.set_markup("<b>" + _("Download finished.") + "</b>")
		self.parent.config["syncthing_binary"] = self.target
		self.version.set_markup(_("Binary path:") +
				" " + self.target)
		self.pb.set_visible(False)
		self.parent.set_page_complete(self, True)
	
class GenerateKeysPage(Page):
	TYPE = Gtk.AssistantPageType.PROGRESS
	TITLE = "Generate Keys"
	def init_page(self):
		""" Displayed while Syncthing binary is being searched for """
		self.label = WrappedLabel(
			"<b>%s</b>\n\n%s" % (
				_("Syncthing is generating RSA key and certificate."),
				_("This may take a while...")
			)
		)
		self.attach(self.label, 0, 0, 1, 1)
	
	def prepare(self):
		GLib.idle_add(self.start_binary)
	
	def start_binary(self):
		"""
		Starts Syncthing binary with -generate parameter and waits until
		key generation is finished
		"""
		self.parent.output_line("syncthing-gtk: Configuration directory: '%s'" % (self.parent.st_configdir,))
		# Create it, if needed
		try:
			os.makedirs(self.parent.st_configdir)
		except Exception, e:
			self.parent.output_line("syncthing-gtk: Failed to create configuration directory")
			self.parent.output_line("syncthing-gtk: %s" % (str(e),))
		# Run syncthing -generate
		self.parent.output_line("syncthing-gtk: Syncthing configuration directory: %s" % (self.parent.st_configdir,))
		self.process = DaemonProcess([ self.parent.config["syncthing_binary"], '-generate=%s' % self.parent.st_configdir ])
		self.process.connect('line', lambda proc, line : self.parent.output_line(line))
		self.process.connect('exit', self.cb_daemon_exit)
		self.process.connect('failed', self.cb_daemon_start_failed)
		self.process.start()
		return False
	
	def cb_daemon_start_failed(self, dproc, exception):
		self.parent.output_line("syncthing-gtk: Daemon startup failed")
		self.parent.output_line("syncthing-gtk: %s" % (str(exception),))
		self.cb_daemon_exit(dproc, -1)
	
	def cb_daemon_exit(self, dproc, exit_code):
		""" Called when Syncthing finishes """
		if exit_code == 0:
			# Finished without problem, advance to next page
			self.parent.set_page_complete(self, True)
			self.parent.next_page()
		else:
			self.parent.error(self,
				_("Failed to generate keys"),
				_("Syncthing daemon failed to generate RSA key or certificate."),
				True)

class HttpSettingsPage(Page):
	TYPE = Gtk.AssistantPageType.CONTENT
	TITLE = "Setup WebUI"
	def init_page(self):
		""" Permits user to set WebUI settings """
		# Wall of text
		label = WrappedLabel(
			"<b>" + _("WebUI setup") + "</b>" +
			"\n\n" +
			_("Syncthing can be managed remotely using WebUI and "
			  "even if you are going to use Syncthing-GTK, WebUI needs "
			  "to be enabled, as Syncthing-GTK uses it to communicate "
			  "with the Syncthing daemon.") +
			"\n\n" +
			_("If you prefer to be able to manage Syncthing remotely, "
			  "over the internet or on your local network, select <b>listen "
			  "on all interfaces</b> and set username and password to "
			  "protect Syncthing from unauthorized access.") +
			"\n" +
			_("Otherwise, select <b>listen on localhost</b>, so only "
			  "users and programs on this computer will be able to "
			  "interact with Syncthing.") +
			"\n"
		)
		# Radiobuttons
		lbl_radios = WrappedLabel("<b>" + _("WebUI Listen Addresses") + "</b>")
		self.rb_localhost = Gtk.RadioButton(label=_("Listen on _localhost"))
		self.rb_all_intfs = Gtk.RadioButton.new_from_widget(self.rb_localhost)
		self.rb_all_intfs.set_label(_("Listen on _all interfaces"))
		for x in (self.rb_localhost, self.rb_all_intfs):
			x.set_use_underline(True)
			x.set_property('margin-left', 15)
		# Username & password input boxes
		self.tx_username = Gtk.Entry()
		self.tx_password = Gtk.Entry()
		self.lbl_username = WrappedLabel(_("_Username"))
		self.lbl_password = WrappedLabel(_("_Password"))
		self.lbl_username.set_mnemonic_widget(self.tx_username)
		self.lbl_password.set_mnemonic_widget(self.tx_password)
		self.tx_password.set_visibility(False)
		self.tx_password.props.caps_lock_warning = True
		for x in (self.lbl_username, self.lbl_password):
			x.set_use_underline(True)
			x.set_property('margin-left', 45)
			x.set_property('margin-bottom', 5)
		for x in (self.tx_username, self.tx_password):
			x.set_property('margin-bottom', 5)
		# Connect signals
		for x in (self.rb_localhost, self.rb_all_intfs):
			x.connect("toggled", self.cb_stuff_changed)
		for x in (self.tx_username, self.tx_password):
			x.connect("changed", self.cb_stuff_changed)
			x.connect("delete-text", self.cb_stuff_changed)
			x.connect("insert-text", self.cb_stuff_changed)
		# Attach everything
		self.attach(label, 0, 0, 3, 1)
		self.attach(lbl_radios, 0, 1, 3, 1)
		self.attach(self.rb_localhost, 0, 2, 2, 1)
		self.attach(self.rb_all_intfs, 0, 3, 2, 1)
		self.attach(self.lbl_username, 0, 4, 1, 1)
		self.attach(self.lbl_password, 0, 5, 1, 1)
		self.attach(self.tx_username, 1, 4, 2, 1)
		self.attach(self.tx_password, 1, 5, 2, 1)
	
	def cb_stuff_changed(self, *a):
		""" Called every time user changes anything on this page """
		# Enable / disable username & password input boxes
		for x in (self.tx_username, self.tx_password, self.lbl_username, self.lbl_password):
			x.set_sensitive(self.rb_all_intfs.get_active())
		# Set page as 'complete' and store settings
		# if either localhost is selected, or username & password is filled
		values_ok = self.rb_localhost.get_active() or (len(self.tx_username.get_text().strip()) and len(self.tx_password.get_text().strip()))
		self.parent.set_page_complete(self, values_ok)
		if values_ok:
			if self.rb_localhost.get_active():
				self.parent.syncthing_options["listen_ip"] = "127.0.0.1"
			else:
				self.parent.syncthing_options["listen_ip"] = "0.0.0.0"
			self.parent.syncthing_options["user"] = str(self.tx_username.get_text())
			self.parent.syncthing_options["password"] = str(self.tx_password.get_text())
	
	def prepare(self):
		# Refresh UI
		self.cb_stuff_changed()

class SaveSettingsPage(Page):
	TYPE = Gtk.AssistantPageType.PROGRESS
	TITLE = "Save Settings"
	def init_page(self):
		""" Displayed while settings are being saved """
		self.label = WrappedLabel("<b>" + _("Saving settings...") + "</b>" + "\n\n")
		self.status = Gtk.Label(_("Checking for available port..."))
		self.attach(self.label,		0, 0, 1, 1)
		self.attach(self.status,	0, 1, 1, 1)
	
	def prepare(self):
		GLib.idle_add(self.check_port, DEFAULT_PORT)
	
	def check_port(self, port):
		"""
		Tries to open TCP port to check it availability.
		It this fails, checks next ports, until MAX_PORT is reached.
		When MAX_PORT is reached, it's safe to assume that something
		completely wrong is happening and an error should be displayed.
		"""
		if port >= MAX_PORT:
			# Remove config.xml that I just created
			try:
				os.unlink(self.parent.st_configfile)
			except Exception, e:
				self.parent.output_line("syncthing-gtk: %s" % (str(e),))
			self.parent.error(self,
				_("Failed to find unused port for listening."),
				_("Please, check your firewall settings and try again."),
				False)
			return
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			s.bind((self.parent.syncthing_options["listen_ip"], port))
			s.listen(0.1)
			s.close()
			# Good, port is available
			del s
			self.parent.output_line("syncthing-gtk: chosen port %s" % (port,))
			self.port = port
			self.parent.syncthing_options["port"] = str(port)
			self.status.set_markup(_("Saving..."))
			GLib.idle_add(self.save_settings)
		except socket.error:
			# Address already in use (or some crazy error)
			del s
			self.parent.output_line("syncthing-gtk: port %s is not available" % (port,))
			GLib.idle_add(self.check_port, port + 1)
	
	def ct_textnode(self, xml, parent, name, value):
		""" Helper method """
		el = xml.createElement(name)
		text = xml.createTextNode(value)
		el.appendChild(text)
		parent.appendChild(el)
	
	def save_settings(self):
		"""
		Loads&parses XML, changes some values and writes it back.
		No backup is created as this wizard is expected to be ran
		only if there is no config in first place.
		"""
		# Generate API key
		self.apikey = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(30))
		log.debug("Generated apikey %s", self.apikey)
		xml = None
		try:
			# Load XML file
			config = file(self.parent.st_configfile, "r").read()
			xml = minidom.parseString(config)
		except Exception, e:
			self.parent.output_line("syncthing-gtk: %s" % (traceback.format_exc(),))
			self.parent.error(self,
				_("Failed to load Syncthing configuration"),
				str(e),
				True)
			return False
		try:
			# Prepare elements
			gui = xml.getElementsByTagName("configuration")[0] \
					.getElementsByTagName("gui")[0]
			au = xml.getElementsByTagName("configuration")[0] \
					.getElementsByTagName("options")[0] \
					.getElementsByTagName("autoUpgradeIntervalH")[0]
			while gui.firstChild != None:
				gui.removeChild(gui.firstChild)
			# Update data
			self.ct_textnode(xml, gui, "address", "%s:%s" % (
							self.parent.syncthing_options["listen_ip"],
							self.parent.syncthing_options["port"],
					))
			self.ct_textnode(xml, gui, "user", self.parent.syncthing_options["user"])
			self.ct_textnode(xml, gui, "password", self.parent.syncthing_options["password"])
			self.ct_textnode(xml, gui, "apikey", self.apikey)
			gui.setAttribute("enabled", "true")
			gui.setAttribute("tls", "false")
			au.firstChild.replaceWholeText("0")
		except Exception, e:
			self.parent.output_line("syncthing-gtk: %s" % (traceback.format_exc(),))
			self.parent.error(self,
				_("Failed to modify Syncthing configuration"),
				str(e),
				True)
			return False
		try:
			# Write XML back to file
			file(self.parent.st_configfile, "w").write(xml.toxml())
		except Exception, e:
			self.parent.output_line("syncthing-gtk: %s" % (traceback.format_exc(),))
			self.parent.error(self,
				_("Failed to save Syncthing configuration"),
				str(e),
				True)
			return False
		self.parent.set_page_complete(self, True)
		self.parent.next_page()
		return False

class LastPage(GenerateKeysPage):
	TYPE = Gtk.AssistantPageType.SUMMARY
	TITLE = "Finish"
	def init_page(self):
		""" Well, it's last page. """
		label = WrappedLabel(
			"<b>" + _("Done.") + "</b>" +
			"\n\n" +
			_("Syncthing has been successfully configured.") +
			"\n" +
			_("You can configure more details later, in "
			  "<b>UI Settings</b> and <b>Daemon Settings</b> menus "
			  "in main window of application.")
		)
		self.attach(label, 0, 0, 1, 1)
	
	def prepare(self):
		# Configure main app to manage Syncthing daemon by default
		self.parent.config["autostart_daemon"] = 1
		self.parent.config["autokill_daemon"] = 1
		self.parent.config["minimize_on_start"] = False
		if IS_WINDOWS:
			self.parent.config["use_old_header"] = True
		self.parent.quit_button.get_parent().remove(self.parent.quit_button)
		self.parent.finished = True
