#!/usr/bin/env python2

from distutils.core import setup
from distutils.command.build_py import build_py
from subprocess import Popen, PIPE
import glob, os
APP_ICON_SIZES = (16, 24, 32, 64, 128, 256)
SI_ICON_SIZES = (16, 24, 32)

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

class BuildPyEx(build_py):
	""" Little extension to install command; Allows --nostupdater argument """
	user_options = build_py.user_options + [
		# Note to self: use
		# # ./setup.py build_py --nostdownloader install
		# to enable this option
		#
		('nostdownloader', None, 'prevents installing StDownloader module; disables autoupdate capability'),
	]
	
	def run(self):
		build_py.run(self)
	
	def initialize_options(self):
		build_py.initialize_options(self)
		self.nostdownloader = False
	
	def find_package_modules(self, package, package_dir):
		rv = build_py.find_package_modules(self, package, package_dir)
		if self.nostdownloader:
			for i in rv:
				if i[1] == "stdownloader":
					rv.remove(i)
					break
		return rv

def find_mos(parent, lst=[]):
	for f in os.listdir(parent):
		fp = os.path.join(parent, f)
		if os.path.isdir(fp):
			find_mos(fp, lst)
		elif fp.endswith(".mo"):
			lst += [ fp ]
	return lst

if __name__ == "__main__" : 
	data_files = [
		('share/syncthing-gtk', glob.glob("*.glade") ),
		('share/syncthing-gtk', glob.glob("scripts/syncthing-plugin-*.py") ),
		('share/syncthing-gtk/icons', [
				"icons/%s.svg" % x for x in (
					'add_node', 'add_repo', 'address',
					'announce', 'clock', 'compress', 'cpu', 'dl_rate',
					'eye', 'folder', 'global', 'home', 'ignore', 'lock',
					'ram', 'shared', 'show_id', 'show_id', 'sync', 'thumb_up',
					'up_rate', 'version', 'rescan'
			)] + [
				"icons/%s.png" % x for x in (
					'restart', 'settings', 'shutdown', "st-gtk-logo"
			)]),
		('share/man/man1', glob.glob("doc/*") ),
		('share/icons/hicolor/64x64/emblems', glob.glob("icons/emblem-*.png") ),
		('share/pixmaps', ["icons/syncthing-gtk.png"]),
		('share/applications', ['syncthing-gtk.desktop'] ),
	] + [
		(
			'share/icons/hicolor/%sx%s/apps' % (size,size),
			glob.glob("icons/%sx%s/apps/*" % (size,size))
		) for size in APP_ICON_SIZES 
	] + [
		(
			'share/icons/hicolor/%sx%s/status' % (size,size),
			glob.glob("icons/%sx%s/status/*" % (size,size))
		) for size in SI_ICON_SIZES
	] + [
		("share/" + os.path.split(x)[0], (x,)) for x in find_mos("locale/")
	]
	setup(
		name = 'syncthing-gtk',
		version = get_version(),
		description = 'GTK3 GUI for Syncthing',
		url = 'https://github.com/syncthing/syncthing-gtk',
		packages = ['syncthing_gtk'],
		data_files = data_files,
		scripts = [ "scripts/syncthing-gtk" ],
		cmdclass = { 'build_py': BuildPyEx },
	)
