#!/usr/bin/env python2

from distutils.core import setup
from subprocess import Popen, PIPE
import glob, os

def get_version():
	"""
	Returns current package version using git-describe or examining
	path. If both methods fails, returns 'unknown'.
	"""
	try:
		p = Popen(['git', 'describe', '--tags', '--match', 'v*'], stdout=PIPE)
		version = p.communicate()[0].strip("\n\r \t")
		if p.returncode != 0:
			raise Exception("git-describe failed")
		return version
	except: pass
	# Git-describe method failed, try to guess from working directory name
	path = os.getcwd().split(os.path.sep)
	version = 'unknown'
	while len(path):
		# Find path component that matches 'syncthing-gui-vX.Y.Z'
		if path[-1].startswith("syncthing-gui-") or path[-1].startswith("syncthing-gtk-"):
			version = path[-1].split("-")[-1]
			if not version.startswith("v"):
				version = "v%s" % (version,)
			break
		path = path[0:-1]
	return version

if __name__ == "__main__" : setup(
	name = 'syncthing-gtk',
	version = get_version(),
	description = 'GTK3 GUI for Syncthing',
	url = 'https://github.com/syncthing/syncthing-gtk',
	packages = ['syncthing_gtk'],
	data_files = [
		('share/syncthing-gtk', glob.glob("*.glade") ),
		('share/syncthing-gtk/icons', glob.glob("icons/*") ),
		('share/pixmaps', glob.glob("icons/emblem-*.png") ),
		('share/applications', ['syncthing-gtk.desktop'] ),
		],
	scripts = [ "scripts/syncthing-gtk" ],
)
