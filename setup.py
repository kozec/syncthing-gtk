#!/usr/bin/env python2

from distutils.core import setup
import glob

setup(
	name = 'syncthing-gtk',
	version = '0.1',
	description = 'GTK3 GUI for Syncthing',
	url = 'https://github.com/kozec/syncthing-gui',
	packages = ['syncthing_gtk'],
	data_files = [
		('share/syncthing-gtk', glob.glob("*.glade") ),
		('share/syncthing-gtk/icons', glob.glob("icons/*") ),
		('share/applications', ['syncthing-gtk.desktop'] ),
		],
	scripts = [ "scripts/syncthing-gtk" ],
)
