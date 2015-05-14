#!/usr/bin/env python2
from distutils.core import setup, Command
from distutils.command.install import install as Install
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

class build_deb(Command):
	"""
	build_deb commands creates deb/ folder with all files needed to build
	working, debian binary package.
	Actual package can be build using `dpkg-buildpackage` command from
	created deb/ directory
	
	Notes to myself:
	  dpkg-buildpackage -d
	    -- builds package without checking builddeps
	  dpkg-buildpackage -d -ai386 
	    -- builds package for another architecture
	"""
	description = "builds deb package"
	user_options = [ ]
	boolean_options = []
	negative_opt = {}
	sub_commands = [('install', lambda x:True)]
	
	def initialize_options (self):
		pass
	
	def finalize_options (self):
		pass
	
	def run(self):
		# Output directory
		deb = os.path.join(os.getcwd(), "deb")
		# Remove output directory, if exists and create it empty
		if os.path.exists(deb):
			shutil.rmtree(deb)
		os.mkdir(deb)
		
		# Create required package structure and files
		os.mkdir(os.path.join(deb, "debian"))
		file(os.path.join(deb, "debian", "control"), "w").write(
"""Source: syncthing-gtk
Section: gnome
Priority: extra
Maintainer: kozec <kozec@kozec.com>
Build-Depends: debhelper (>= 9),
	python-all-dev (>=2.7),
	python-gobject-2-dev,
	libgtk-3-dev,
	libappindicator3-dev,
	libnotify-dev,
	python-notify
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
""")
		file(os.path.join(deb, "debian/compat"), "w").write("9\n")
		file(os.path.join(deb, "debian/rules"), "w").write(
"""#!/usr/bin/make -f
%:
		dh $@
""")
		file(os.path.join(deb, "debian/changelog"), "w").write(
"""syncthing-gtk (%(version)s) release; urgency=medium

  * Packaging of v%(version)s.

 -- %(user)s <dummy@mail.com>  %(time)s
""" % {
			'version' : self.distribution.get_version().strip("v"),
			'user' : pwd.getpwuid(os.getuid())[0],
			'time' : strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime())
		})
		# Set prefix for install command and install ST-GTK to output directory
		self.distribution.get_option_dict('install')['root'] = ("build_deb", deb)
		for cmd_name in self.get_sub_commands():
			self.run_command(cmd_name)
		
		# Remove StDownloader class to disable autoupdates
		os.unlink(os.path.join(deb, "usr/lib/python2.7/site-packages/syncthing_gtk/stdownloader.py"))
		os.unlink(os.path.join(deb, "usr/lib/python2.7/site-packages/syncthing_gtk/stdownloader.pyc"))

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
			'build_deb' : build_deb
		},
		data_files = data_files,
		scripts = [ "scripts/syncthing-gtk" ],
)
