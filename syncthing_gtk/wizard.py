#!/usr/bin/env python2
"""
Syncthing-GTK - 1st run wizard

Basicaly runs syncthing daemon with -generate option and setups some
values afterwards.
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, GLib
from syncthing_gtk import Configuration, DaemonProcess
from syncthing_gtk import DaemonOutputDialog, StDownloader
from syncthing_gtk.tools import IS_WINDOWS
import os, sys, socket, random, string, traceback, platform
from xml.dom import minidom

_ = lambda (a) : a
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
		confdir = GLib.get_user_config_dir()
		if confdir is None:
			confdir = os.path.expanduser("~/.config")
		self.st_configdir = os.path.join(confdir, "syncthing")
		self.st_configfile = os.path.join(confdir, "syncthing", "config.xml")
		# Window setup
		self.set_position(Gtk.WindowPosition.CENTER)
		self.set_size_request(650, -1)
		self.set_default_size(650, 300)
		self.set_deletable(True)
		self.set_icon_from_file(os.path.join(self.iconpath, "st-logo-24.png"))
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
		self.set_page_title(page, page.TITLE)
		return index
	
	def insert_and_go(self, page):
		"""
		Inserts new page after currently displayed
		and switches to it.
		"""
		index = self.get_current_page()
		index = self.insert_page(page, index + 1)
		page.parent = self
		self.set_page_type(page, page.TYPE)
		self.set_page_title(page, page.TITLE)
		self.set_current_page(index)
		return index
	
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
	
	def output_line(self, line):
		""" Called for every line that wizard or daemon process outputs """
		self.lines.append(line)
		print line
	
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
			github_link = '<a href="https://github.com/kozec/syncthing-gui/issues">GitHub</a>'
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
	
	def show_output(self, *a):
		"""
		Displays DaemonOutput window with error messages captured
		durring key generation.
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
	# Next page, "Download Daemon" is displayed only if needed.
	# When that happens, it becames page with longest title and  wizard
	# window changes size to accomodate to this change. And i don't like
	# that.
	# To prevent this 'window jumping', padding is added here, so
	# this page is always one with longest name.
	TITLE = _("Find Daemon") + "                 "
	TYPE = Gtk.AssistantPageType.PROGRESS
	def init_page(self):
		""" Displayed while syncthing binary is being searched for """
		self.label = WrappedLabel(
			_("<b>Searching for syncthing daemon.</b>") +
			"\n\n" +
			_("Please wait...")
		)
		self.attach(self.label, 0, 0, 1, 1)
	
	def prepare(self):
		paths = [ "./" ]
		paths += [ os.path.expanduser("~/.local/bin") ]
		self.binaries = ("syncthing", "syncthing.x86", "syncthing.x86_64", "pulse")
		if IS_WINDOWS:
			paths += [ "c:/Program Files/syncthing", "c:/Program Files (x86)/syncthing" ]
			self.binaries = ("syncthing.exe", "pulse.exe")
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
			if True or IS_WINDOWS:	# TODO: Just for testing
				# On Windows, don't say anything and download syncthing
				# directly
				p = DownloadSTPage()
				self.parent.insert_and_go(p)
				return False
			else:
				# On Linux, generate and display error page and give up
				# TODO: Download on Linux as well?
				local_bin_folder = "~/.local/bin"
				local_bin_folder_link = '<a href="file://%s">%s</a>' % (
						os.path.expanduser(local_bin_folder), local_bin_folder)
				dll_link = '<a href="https://github.com/syncthing/syncthing/releases">' + \
						_('download latest binary') + '</a>'
				return self.parent.error(self,
						_("Syncthing daemon not found."),
						(_("Please, use package manager to install syncthing package") + " " +
						 _("or %s from syncthing page and save it") + " " +
						 _("to your %s or any other directory in PATH")) %
							(dll_link, local_bin_folder_link,),
						False)
		
		for bin in self.binaries:
			bin_path = os.path.join(path, bin)
			print " ...", bin_path,
			if os.path.isfile(bin_path):
				if os.access(bin_path, os.X_OK):
					# File exists and is executable
					print "FOUND"
					if IS_WINDOWS: bin_path = bin_path.replace("/", "\\")
					self.parent.config["syncthing_binary"] = bin_path
					self.parent.set_page_complete(self, True)
					self.label.set_markup(
							_("<b>Syncthing daemon binary found.</b>") +
							"\n\n" +
							_("Binary path:") +
							" " +
							bin_path
						)
					return
				else:
					print "not executable"
			else:
				print "not found"
		GLib.idle_add(self.search, paths)

class DownloadSTPage(Page):
	TYPE = Gtk.AssistantPageType.PROGRESS
	TITLE = _("Download Daemon")
	
	def init_page(self):
		""" Displayed while wizard downloads and extraacts daemon """
		self.label = WrappedLabel(_("<b>Downloading Syncthing daemon.</b>"))
		self.version = WrappedLabel(_("Please wait..."))
		self.pb = Gtk.ProgressBar()
		self.label.props.margin_bottom = 15
		self.target = None
		self.attach(self.label,		0, 0, 1, 1)
		self.attach(self.version,	0, 1, 1, 1)
		self.attach(self.pb,		0, 2, 1, 1)
	
	def prepare(self):
		# Determine which syncthing to use
		suffix, tag = None, None
		if platform.system().lower().startswith("linux"):
			if platform.machine() in ("i386", "i586", "i686"):
				# Not sure, if anything but i686 is actually used
				suffix, tag = ".x86", "linux-386"
			elif platform.machine() == "x86_64":
				# Who in the world calls x86_64 'amd' anyway?
				suffix, tag = ".x64", "linux-amd64"
			elif platform.machine().lower() in ("armv5", "armv6", "armv7"):
				# TODO: This should work, but I don't have any way
				# to test this right now
				suffix = platform.machine().lower()
				tag = "linux-%s" % (suffix,)
		elif platform.system().lower().startswith("windows"):
			if platform.machine() == "AMD64":
				suffix, tag = ".exe", "windows-amd64"
			else:
				# I just hope that MS will not release ARM Windows for
				# next 50 years...
				suffix, tag = ".exe", "windows-386"
		for x in ("freebsd", "solaris", "openbsd"):
			# Syncthing-GTK should work on those as well...
			if platform.system().lower().startswith(x):
				if platform.machine() in ("i386", "i586", "i686"):
					suffix, tag = ".x86", "%s-386" % (x,)
				elif platform.machine() in ("amd64", "x86_64"):
					suffix, tag = ".x64", "%s-amd64" % (x,)
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
		confdir = GLib.get_user_config_dir()
		if confdir is None:
			confdir = os.path.expanduser("~/.config")
		self.target = os.path.join(confdir, "syncthing", "syncthing%s" % (suffix,))
		# Create downloader and connect events
		self.sd = StDownloader(self.target, tag)
		self.sd.connect("error", self.on_download_error)
		self.sd.connect("download-starting", self.on_download_start)
		self.sd.connect("download-progress", self.on_progress)
		self.sd.connect("download-finished", self.on_extract_start)
		self.sd.connect("extraction-progress", self.on_progress)
		self.sd.connect("extraction-finished", self.on_extract_finished)
		# Start downloading
		self.sd.start()
	
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
			_("Failed todownload Syncthing daemon package."),
			message, False)
		return
	
	def on_download_start(self, dowloader, version):
		self.version.set_markup("Downloading %s..." % (version, ))
	
	def on_extract_start(self, *a):
		self.version.set_markup("Extracting...")
	
	def on_progress(self, dowloader, progress):
		self.pb.set_fraction(progress)
	
	def on_extract_finished(self, *a):
		""" Called after extraction is finished """
		# Everything done. Praise supernatural entities...
		self.label.set_markup(_("<b>Download finished.</b>"))
		self.parent.config["syncthing_binary"] = self.target
		self.version.set_markup(_("Binary path:") +
				" " + self.target)
		self.pb.set_visible(False)
		self.parent.set_page_complete(self, True)
	
class GenerateKeysPage(Page):
	TYPE = Gtk.AssistantPageType.PROGRESS
	TITLE = _("Generate Keys")
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
	
	def cb_daemon_exit(self, dproc, exit_code):
		""" Called when syncthing finishes """
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
	TITLE = _("Setup WebUI")
	def init_page(self):
		""" Let's user to set webui settings """
		# Wall of text
		label = WrappedLabel(
			_("<b>WebUI setup</b>") +
			"\n\n" +
			_("Syncthing can be controlled remotely using WebUI and "
			  "even if you are going to use Syncthing-GTK, WebUI needs "
			  "to be enabled, as Syncthing-GTK uses it to communicate "
			  "with syncthing daemon.") +
			"\n\n" +
			_("If you prefer to be able to control syncthing remotely, "
			  "over internet or on your local network, select <b>listen "
			  "on all interfaces</b> and set username and password to "
			  "protect syncthing from unauthorized access.") +
			"\n" +
			_("Otherwise, select <b>listen on localhost</b>, so only "
			  "users and programs on this computer will be able to "
			  "interact with syncthing.") +
			"\n"
		)
		# Radiobuttons
		lbl_radios = WrappedLabel("<b>WebUI Listen Addresses</b>")
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
	TITLE = _("Save Settings")
	def init_page(self):
		""" Displayed while settings are being saved """
		self.label = WrappedLabel(_("<b>Saving settings...</b>") + "\n\n")
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
		completly wrong is happening and to display error.
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
			self.parent.output_line("syncthing-gtk: choosen port %s" % (port,))
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
		xml = None
		try:
			# Load XML file
			config = file(self.parent.st_configfile, "r").read()
			xml = minidom.parseString(config)
		except Exception, e:
			self.parent.output_line("syncthing-gtk: %s" % (traceback.format_exc(),))
			return self.parent.error(self,
				_("Failed to load syncthing configuration"),
				str(e),
				True)
		try:
			# Prepare elements
			gui = xml.getElementsByTagName("configuration")[0] \
					.getElementsByTagName("gui")[0]
			while gui.firstChild != None:
				gui.removeChild(gui.firstChild)
			# Update data
			self.ct_textnode(xml, gui, "address", "%s:%s" % (
							self.parent.syncthing_options["listen_ip"],
							self.parent.syncthing_options["port"],
					))
			self.ct_textnode(xml, gui, "user", self.parent.syncthing_options["user"])
			self.ct_textnode(xml, gui, "password", self.parent.syncthing_options["password"])
			gui.setAttribute("enabled", "true")
			gui.setAttribute("tls", "false")
				
		except Exception, e:
			self.parent.output_line("syncthing-gtk: %s" % (traceback.format_exc(),))
			return self.parent.error(self,
				_("Failed to modify syncthing configuration"),
				str(e),
				True)
		try:
			# Write xml back to file
			file(self.parent.st_configfile, "w").write(xml.toxml())
		except Exception, e:
			self.parent.output_line("syncthing-gtk: %s" % (traceback.format_exc(),))
			return self.parent.error(self,
				_("Failed to save syncthing configuration"),
				str(e),
				True)
		self.parent.set_page_complete(self, True)
		self.parent.next_page()

class LastPage(GenerateKeysPage):
	TYPE = Gtk.AssistantPageType.SUMMARY
	TITLE = _("Finish")
	def init_page(self):
		""" Well, it's last page. """
		label = WrappedLabel(
			_("<b>Done.</b>") +
			"\n\n" +
			_("Syncthing has been successfully configured.") +
			"\n" +
			_("You can configure more details later, in "
			  "<b>UI Settings</b> and <b>Daemon Settings</b> menus "
			  "in main window of application.")
		)
		self.attach(label, 0, 0, 1, 1)
	
	def prepare(self):
		# Configure main app to manage syncthing daemon by default
		self.parent.config["autostart_daemon"] = 1
		self.parent.config["autokill_daemon"] = 1
		self.parent.config["minimize_on_start"] = False
		if IS_WINDOWS:
			self.parent.config["use_old_header"] = True
		self.parent.quit_button.get_parent().remove(self.parent.quit_button)
		self.parent.finished = True
