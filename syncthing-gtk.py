#!/usr/bin/env python2
import sys

if __name__ == "__main__":
	from syncthing_gtk import App
	App("-w" not in sys.argv).run()
