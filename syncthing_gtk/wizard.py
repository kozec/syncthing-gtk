#!/usr/bin/env python2
"""
Syncthing-GTK - 1st run wizard

Runs syncthing daemon with -generate option and setups some
values afterwards.
"""

from __future__ import unicode_literals
from gi.repository import Gtk, Gdk, GLib
from syncthing_gtk import Configuration, Daemon
from syncthing_gtk import DaemonProcess, DaemonOutputDialog
import os, sys, socket, random, string

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
	
	def fatal_error(self, text):
		# TODO: Better way to handle this
		# TODO: Move to tools, along with same method in app.py
		print >>sys.stderr, text
		d = Gtk.MessageDialog(
				None,
				Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
				Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
				text
				)
		d.run()
		d.hide()
		d.destroy()
	
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

class GenerateKeysPage(Page):
	TYPE = Gtk.AssistantPageType.PROGRESS
	TITLE = _("Generate Keys")
	def init_page(self):
		""" Displayed while syncthing binary is being searched for """
		self.lines = []
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
		self.cb_daemon_line(None, "syncthing-gtk: Configuration directory: '%s'" % (self.parent.st_configdir,))
		# Create it, if needed
		try:
			os.makedirs(self.parent.st_configdir)
		except Exception, e:
			self.cb_daemon_line(None, "syncthing-gtk: Failed to create configuration directory")
			self.cb_daemon_line(None, "syncthing-gtk: %s" % (str(e),))
		# Run syncthing -generate
		self.process = DaemonProcess([ self.parent.config["syncthing_binary"], '-generate=%s' % self.parent.st_configdir ])
		self.process.connect('line', self.cb_daemon_line)
		self.process.connect('exit', self.cb_daemon_exit)
	
	def error(self):
		"""
		GenerateKeysPage turns into error page if syncthing binary
		fails to generate keys.
		"""
		# Text
		st_link = '<a href="https://github.com/syncthing/syncthing/issues">syncthing</a>'
		stgtk_link = '<a href="https://github.com/kozec/syncthing-gui/issues">Syncthing-GTK</a>'
		self.label.set_markup(
			_("<b>Failed to generate keys.</b>") +
			"\n\n" +
			_("Syncthing daemon failed to generate RSA key or certificate.") +
			"\n\n" +
			_("This usually shouldn't happen. Please, check error log "
			  "and fill bug report against %s or %s.") % (st_link, stgtk_link)
		)
		# 'Display error log' button
		vbox = Gtk.Box()
		button = Gtk.Button(_("Display error log"))
		vbox.pack_end(button, False, False, 25)
		self.attach(vbox, 0, 1, 1, 1)
		self.set_row_spacing(25)
		self.show_all()
		button.connect("clicked", lambda *a : self.show_output())
	
	def show_output(self, *a):
		"""
		Displays DaemonOutput window with error messages captured
		durring key generation.
		"""
		d = DaemonOutputDialog(self.parent, None)
		d.show_with_lines(self.lines, self.parent)
	
	def cb_daemon_line(self, dproc, line):
		""" Called for every line that syncthing process outputs """
		self.lines.append(line)
		print line
	
	def cb_daemon_exit(self, dproc, exit_code):
		""" Called when syncthing finishes """
		if exit_code == 0:
			# Finished without problem, advance to next page
			self.lines = []
			self.parent.set_page_complete(self, True)
			self.parent.next_page()
		else:
			self.error()

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
			self.parent.syncthing_options["password"] = str(self.tx_username.get_text())
	
	def prepare(self):
		# Refresh UI
		self.cb_stuff_changed()

class SaveSettingsPage(GenerateKeysPage):
	TYPE = Gtk.AssistantPageType.PROGRESS
	TITLE = _("Save Settings")
	def init_page(self):
		""" Displayed while syncthing binary is being searched for """
		self.lines = []
		self.label = WrappedLabel(_("<b>Saving settings...</b>") + "\n\n")
		self.status = Gtk.Label(_("Checking for available port..."))
		self.attach(self.label,		0, 0, 1, 1)
		self.attach(self.status,	0, 1, 1, 1)
	
	def prepare(self):
		GLib.idle_add(self.check_port, DEFAULT_PORT)
	
	def error(self):
		"""
		SaveSettingsPage turns into error page if syncthing binary
		fails to start or save settings.
		"""
		GenerateKeysPage.error(self)
		self.status.set_visible(False)
		# Text
		stgtk_link = '<a href="https://github.com/kozec/syncthing-gui/issues">Syncthing-GTK</a>'
		# No bug against syncthing here, should anything bad happen here,
		# it's most likely my mistake.
		self.label.set_markup(
			_("<b>Failed to store configuration.</b>") +
			"\n\n" +
			_("This usually shouldn't happen. Please, check error log "
			  "and fill bug report against %s.") % (stgtk_link,)
		)
	
	def check_port(self, port):
		"""
		Tries to open TCP port to check it availability.
		It this fails, checks next ports, until MAX_PORT is reached.
		When maxport is reached, assumes something completly wrong
		happens and displays error.
		"""
		if port >= MAX_PORT:
			self.error()
			return
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			s.bind((self.parent.syncthing_options["listen_ip"], port))
			s.listen(0.1)
			s.close()
			# Good, port is available
			del s
			self.cb_daemon_line(None, "syncthing-gtk: choosen port %s" % (port,))
			self.port = port
			self.parent.syncthing_options["port"] = str(port)
			GLib.idle_add(self.start_binary)
		except socket.error:
			# Address already in use (most likely)
			del s
			self.cb_daemon_line(None, "syncthing-gtk: port %s is not available" % (port,))
			GLib.idle_add(self.check_port, port + 1)
	
	def start_binary(self):
		"""
		Starts syncthing binary listening only on localhost, with
		authentification disabled. Waits until it finishes loading
		and sets WebUI configuration.
		"""
		self.status.set_markup(_("Starting syncthing daemon..."))
		# Generate API key
		self.apikey = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(30))
		# Start sycnthing daemon
		self.process = DaemonProcess([self.parent.config["syncthing_binary"],
			"-no-browser", "-gui-address=127.0.0.1:%s" % (self.port,),
			"-gui-authentication=",
			"-gui-apikey=",
		])
		self.process.connect('line', self.cb_daemon_line)
		self.process.connect('exit', self.cb_daemon_exit)
		self.parent.connect('cancel', self.terminate_process)
		# Create daemon instance and wait until startup completes
		self.retries = 10
		self.daemon = Daemon()
		self.daemon.connect("startup-complete", self.cb_syncthing_startup_complete)
		self.daemon.connect("connection-error", self.cb_syncthing_con_error)
		self.daemon.override_config("127.0.0.1:%s" % (self.port,), None)
		self.daemon.reconnect()
	
	def terminate_process(self, *a):
		"""
		Called when user exits wizard while daemon process is still active,
		or for any other reason that requires daemon to be murdered.
		"""
		if self.process != None:
			self.process.terminate()
			self.process = None
			print "Terminated process"
	
	def cb_syncthing_con_error(self, daemon, reason, message):
		"""
		Called when connection to daemon fails. It's expected to have few
		con.refused errors, as daemon is just starting, but anything else
		is big problem.
		"""
		if reason == Daemon.REFUSED and self.retries > 0:
			self.retries -= 1
			self.cb_daemon_line(None, "syncthing-gtk: %s" % (message,))
			return
		self.cb_daemon_line(None, "syncthing-gtk: Failed to connect to daemon")
		self.cb_daemon_line(None, "syncthing-gtk: %s" % (message,))
		self.daemon.close()
		self.terminate_process()
		self.error()
	
	def cb_syncthing_startup_complete(self, *a):
		""" Called when daemon is ready to be reconfigured """
		self.status.set_markup(_("Storing configuration..."))
		self.daemon.read_config(self.cb_syncthing_config_loaded, self.cb_syncthing_config_load_failed)
	
	def cb_syncthing_config_loaded(self, config):
		try:
			config["GUI"]["Address"] = "%s:%s" % (self.parent.syncthing_options["listen_ip"], self.parent.syncthing_options["port"])
			config["GUI"]["User"] = self.parent.syncthing_options["user"]
			config["GUI"]["Password"] = self.parent.syncthing_options["password"]
			config["GUI"]["UseTLS"] = False
			config["GUI"]["Enabled"] = True
			config["GUI"]["apikey"] = self.apikey
		except Exception, e:
			self.cb_daemon_line(None, "syncthing-gtk: Failed to modify settings")
			self.cb_daemon_line(None, "syncthing-gtk: %s" % (str(e),))
			self.daemon.close()
			self.terminate_process()
			self.error()
			return
		self.daemon.write_config(config, self.cb_syncthing_config_saved, self.cb_syncthing_config_save_failed)
	
	def cb_syncthing_config_load_failed(self, exception, *a):
		self.cb_daemon_line(None, "syncthing-gtk: Failed to load configuration from daemon")
		self.cb_daemon_line(None, "syncthing-gtk: %s" % (str(exception)))
		self.daemon.close()
		self.terminate_process()
		self.error()
	
	def cb_syncthing_config_save_failed(self, exception, *a):
		self.cb_daemon_line(None, "syncthing-gtk: Failed to save daemon configuration")
		self.cb_daemon_line(None, "syncthing-gtk: %s" % (str(exception)))
		self.daemon.close()
		self.terminate_process()
		self.error()
	
	def cb_syncthing_config_saved(self, *a):
		"""
		Called after configuration is sucesfully saved. Only thing left
		is to let daemon exit and say done.
		"""
		self.status.set_markup(_("Finishing things..."))
		self.process.connect('exit', self.cb_everything_finished)
		self.daemon.shutdown()
	
	def cb_everything_finished(self, *a):
		""" Called after everything """
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
		self.parent.quit_button.get_parent().remove(self.parent.quit_button)
		self.parent.finished = True
