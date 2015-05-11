#!/usr/bin/env python2
import os, sys, signal

def sigint(*a):
	print("\n*break*")
	sys.exit(0)

if __name__ == "__main__":
	signal.signal(signal.SIGINT, sigint)
	
	from syncthing_gtk.tools import init_logging, IS_WINDOWS
	init_logging()
	if IS_WINDOWS:
		from syncthing_gtk import windows
		windows.fix_localized_system_error_messages()
		windows.dont_use_localization_in_gtk()
	
	from gi.repository import Gtk
	Gtk.IconTheme.get_default().append_search_path(os.path.join(os.getcwd(), "icons"))
	
	from syncthing_gtk import App
	App(".", "./icons").run(sys.argv)
