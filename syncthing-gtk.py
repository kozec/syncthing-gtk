#!/usr/bin/env python2
import sys, signal

def sigint(*a):
	print("\n*break*")
	sys.exit(0)

if __name__ == "__main__":
	signal.signal(signal.SIGINT, sigint)
	
	from syncthing_gtk.tools import init_logging, init_locale, IS_WINDOWS
	init_logging()
	init_locale("locale")
	if IS_WINDOWS:
		from syncthing_gtk import windows
		windows.fix_localized_system_error_messages()
		windows.dont_use_localization_in_gtk()
		windows.override_menu_borders()
	
	from syncthing_gtk import App
	App(".", "./icons").run(sys.argv)
