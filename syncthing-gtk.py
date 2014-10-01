#!/usr/bin/env python2
import sys, signal

def sigint(*a):
	print("\n*break*")
	sys.exit(0)

if __name__ == "__main__":
	from syncthing_gtk import App
	signal.signal(signal.SIGINT, sigint)
	if "-h" in sys.argv or "--help" in sys.argv:
		print "Usage: %s [-h | [-w] [-s]]" % (sys.argv[0],)
		print "  -h   Display this help message and exit"
		print "  -w   Display window / don't start minimized"
		print "  -s   Use classic window header instead of Gtk.HeaderBar"
		sys.exit(0)
	App(
		"-w" not in sys.argv,
		"-s" not in sys.argv,
		".",
		"./icons"
	).run()
