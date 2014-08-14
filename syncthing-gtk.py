#!/usr/bin/env python2
import sys, signal

def sigint(*a):
	print("\n*break*")
	sys.exit(0)

if __name__ == "__main__":
	from syncthing_gtk import App
	signal.signal(signal.SIGINT, sigint)
	App("-w" not in sys.argv, ".", "./icons").run()
