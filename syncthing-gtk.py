#!/usr/bin/env python2
import os, sys, signal, gi

def sigint(*a):
	print("\n*break*")
	sys.exit(0)

if __name__ == "__main__":
	signal.signal(signal.SIGINT, sigint)
	
	gi.require_version('Gtk', '3.0')
	gi.require_version('Rsvg', '2.0')
	
	from syncthing_gtk.tools import init_logging, init_locale, IS_WINDOWS
	init_logging()
	
	if IS_WINDOWS:
		from syncthing_gtk import windows, Configuration
		config = Configuration()
		if config["force_dark_theme"]:
			os.environ["GTK_THEME"] = "Adwaita:dark"
		if config["language"] not in ("", "None", None):
			os.environ["LANGUAGE"] = config["language"]
	
	if IS_WINDOWS:
		from syncthing_gtk import windows
		windows.enable_localization()
	
	init_locale("locale/")
	
	if IS_WINDOWS:
		windows.fix_localized_system_error_messages()
		windows.override_menu_borders()
		from gi.repository import Gtk
		Gtk.IconTheme.get_default().prepend_search_path(os.path.abspath(os.path.join(os.getcwd(), "icons", "32x32", "apps")))
		Gtk.IconTheme.get_default().prepend_search_path(os.path.abspath(os.path.join(os.getcwd(), "icons")))
	
	from gi.repository import Gtk
	Gtk.IconTheme.get_default().append_search_path(os.path.join(os.getcwd(), "icons"))
	
	from syncthing_gtk import App
	App(".", "./icons").run(sys.argv)
