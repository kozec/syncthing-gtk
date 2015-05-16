#!/usr/bin/env python2
from distutils.core import setup, Command
from subprocess import Popen, PIPE
from time import gmtime, strftime
import glob, os, shutil, pwd
ICON_SIZES = (16, 24, 32, 64, 128, 256)

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

def deb_version(v):
	"""
	Converts internal version string to something better suitable
	for debian.
	v0.7.1.1-5-g893c4f9 -> 0.7.1.1.5.g893c4f9
	"""
	return v.replace("-", ".").lstrip("v")

class make_deb(Command):
	"""
	make_deb commands creates debian/ folder with all files needed to build
	working, binary package for debian.
	Actual package can be build using `debuild` command
	
	Notes to myself:
	  debuild -d
	    -- builds package without checking builddeps
	  debuild -d -ai386 
	    -- builds package for another architecture
	"""
	description = "prepares debian package"
	user_options = [ ]
	boolean_options = []
	negative_opt = {}
	sub_commands = [('sdist', lambda x:True)]
	
	### Pure madness follows ###
	CONTROL = '''Source: syncthing-gtk
Section: gnome
Priority: extra
Maintainer: kozec <kozec@kozec.com>
Build-Depends: debhelper (>= 9),
	python-all-dev (>=2.7)
X-Python-Version: >= 2.7
Standards-Version: 3.9.5
Homepage: https://github.com/kozec/syncthing-gui

Package: syncthing-gtk
Architecture: any
Depends: ${misc:Depends},
	${python:Depends},
	syncthing (>=0.11.0),
	syncthing (<<0.12.0),
	python-gobject | python-gi,
	python-dateutil,
	libappindicator3-1,
	libgtk-3-0,
	gir1.2-gtk-3.0,
	gir1.2-glib-2.0,
	gir1.2-appindicator3-0.1,
	python-notify,
	python-gi-cairo
Recommends: python-pyinotify
Suggests: python-nautilus | python-nemo | python-caja
Description: GUI for Syncthing
 Syncthing GUI is a GTK3 & python based GUI and notification
 area icon for Syncthing.
 .
 Supported syncthing features:
 - Everything what WebUI can display
 - Adding / editing / deleting nodes
 - Adding / editing / deleting repositories
 - Restart / shutdown server
 - Editing daemon settings
 .
 Additional features:
 - First run wizard for initial configuration
 - Running Syncthing daemon in background
 - Half-automatic setup for new nodes and repositories
 - Filesystem watching and instant synchronization using inotify
 - Nautilus (a.k.a. Files), Nemo and Caja integration
 - Desktop notifications
'''
	COMPAT = '''9\n'''
	RULES = '''#!/usr/bin/make -f
%:
		dh $@ --with python2
'''
	CHANGELOG = '''syncthing-gtk (%(version)s) vivid; urgency=medium

  * Packaging of v%(version)s.

 -- %(user)s <dummy@mail.com>  %(time)s
'''
	COPYRIGHT = '''
Format: http://dep.debian.net/deps/dep5
Upstream-Name: syspeek
Source: https://launchpad.net/syspeek

Files: *
Copyright: 2014 kozec https://github.com/kozec
License: GPL-2.0
  See /usr/share/common-licenses/GPL-2
'''
	### Pure madness ends ###

	def initialize_options (self):
		pass
	
	def finalize_options (self):
		pass
	
	def run(self):
		# Output directory
		deb = os.path.join(os.getcwd(), "debian")
		# Remove output directory, if exists and create it empty
		if os.path.exists(deb):
			shutil.rmtree(deb)
		os.mkdir(deb)
		
		# Create required package structure and files
		file(os.path.join(deb, "control"), "w").write(make_deb.CONTROL)
		file(os.path.join(deb, "compat"), "w").write(make_deb.COMPAT)
		file(os.path.join(deb, "rules"), "w").write(make_deb.RULES)
		file(os.path.join(deb, "copyright"), "w").write(make_deb.COPYRIGHT)
		file(os.path.join(deb, "changelog"), "w").write(make_deb.CHANGELOG % {
				'version' : deb_version(self.distribution.get_version()),
				'user' : pwd.getpwuid(os.getuid())[0],
				'time' : strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime())
		})
		
		# Set options for sdist command and generate source package in current directory
		self.distribution.get_option_dict('sdist')['dist_dir'] = ("build_deb", ".")
		self.distribution.get_option_dict('sdist')['formats'] = ("build_deb", "gztar")
		for cmd_name in self.get_sub_commands():
			self.run_command(cmd_name)
		
		# TODO: This. No idea how...
		## Remove StDownloader class to disable autoupdates
		#os.unlink(os.path.join(deb, "usr/lib/python2.7/site-packages/syncthing_gtk/stdownloader.py"))
		#os.unlink(os.path.join(deb, "usr/lib/python2.7/site-packages/syncthing_gtk/stdownloader.pyc"))

if __name__ == "__main__" : 
	data_files = [
		('share/syncthing-gtk', glob.glob("*.glade") ),
		('share/syncthing-gtk', glob.glob("scripts/syncthing-plugin-*.py") ),
		('share/syncthing-gtk/icons', [
				"icons/%s.png" % x for x in (
					'add_node', 'add_repo', 'address',
					'announce', 'clock', 'compress', 'cpu', 'dl_rate',
					'eye', 'folder', 'global', 'home', 'ignore', 'lock',
					'ram', 'restart', 'settings', 'shared', 'show_id',
					'shutdown', 'show_id', 'sync', 'thumb_up',
					'up_rate', 'version'
			)]),
		('share/pixmaps', glob.glob("icons/emblem-*.png") ),
		('share/pixmaps', ["icons/syncthing-gtk.png"]),
		('share/applications', ['syncthing-gtk.desktop'] ),
	] + [
		(
			'share/icons/hicolor/%sx%s/apps' % (size,size),
			glob.glob("icons/%sx%s/apps/*" % (size,size))
		) for size in ICON_SIZES 
	]
	setup(
		name = 'syncthing-gtk',
		version = get_version(),
		description = 'GTK3 GUI for Syncthing',
		url = 'https://github.com/syncthing/syncthing-gtk',
		packages = ['syncthing_gtk'],
		cmdclass= {
			'make_deb' : make_deb
		},
		data_files = data_files,
		scripts = [ "scripts/syncthing-gtk" ],
)
