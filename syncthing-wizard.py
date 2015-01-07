#!/usr/bin/env python2
import sys, signal

def sigint(*a):
	print("\n*break*")
	sys.exit(0)

if __name__ == "__main__":
	signal.signal(signal.SIGINT, sigint)
	
	from syncthing_gtk.tools import init_logging, set_logging_level, IS_WINDOWS
	init_logging()
	set_logging_level(True, True)
	if IS_WINDOWS:
		from syncthing_gtk import windows
		windows.fix_localized_system_error_messages()
		windows.dont_use_localization_in_gtk()
	
	from syncthing_gtk import Wizard
	Wizard("./icons", None).run()
