#!/usr/bin/env python2

"""
Syncthing-GTK - Notifications

Listens to syncing events on daemon and displays desktop notifications.
"""

from __future__ import unicode_literals
DELAY = 5	# Display notification only after no file is downloaded for <DELAY> seconds

HAS_DESKTOP_NOTIFY = False
Notifications = None

try:
	from gi.repository import Notify
	HAS_DESKTOP_NOTIFY = True
except ImportError:
	pass

if HAS_DESKTOP_NOTIFY:
	from gi.repository import GdkPixbuf
	from syncthing_gtk import TimerManager
	import os, sys
	_ = lambda (a) : a
	
	class NotificationsCls(TimerManager):
		""" Watches for filesystem changes and reports them to daemon """
		def __init__(self, app, daemon):
			TimerManager.__init__(self)
			Notify.init("Syncthing GTK")
			# Prepare stuff
			self.app = app
			self.daemon = daemon
			self.downloading = {}		# Key is repo-id
			self.finished = set([])		# Tuples of (path, repo-id)
			# Load icon
			self.icon = None
			try:
				self.icon = GdkPixbuf.Pixbuf.new_from_file(os.path.join(self.app.iconpath, "st-logo-64.png"))
			except Exception, e:
				print >>sys.stderr, "Failed to load icon:", e
			# Make deep connection with daemon
			self.daemon.connect("connected", self.cb_syncthing_connected)
			self.daemon.connect('item-started', self.cb_syncthing_item_started)
			self.daemon.connect('item-updated', self.cb_syncthing_item_updated)
		
		def info(self, text):
			n = Notify.Notification.new(
					_("Syncthing GTK"),
					text
				)
			if not self.icon is None:
				n.set_icon_from_pixbuf(self.icon)
			if n.show ():
				return n
			del n
			return None
		
		def cb_syncthing_connected(self, *a):
			# Clear download list
			self.downloading = {}
		
		def cb_syncthing_item_started(self, daemon, folder_id, path, *a):
			if not folder_id in self.downloading:
				self.downloading[folder_id] = []
			if not path in self.downloading[folder_id]:
				self.downloading[folder_id].append(path)
		
		def cb_syncthing_item_updated(self, daemon, folder_id, path, *a):
			if folder_id in self.downloading:
				if path in self.downloading[folder_id]:
					self.downloading[folder_id].remove(path)
					self.finished.add((path, folder_id))
					self.cancel_timer("display")
					self.timer("display", DELAY, self.display)
		
		def display(self):
			if len(self.finished) == 1:
				path, folder_id = list(self.finished)[0]
				filename = os.path.split(path)[-1]
				self.info(_("The file '%s' was updated from remote device") % (filename,))
			else:
				self.info(_("%s files were updated from remote device") % (len(self.finished),))
			self.finished = set([])
		
	# Notifications is set to class only if libnotify is available
	Notifications = NotificationsCls

"""
Events emitted when file is changed on remote node:
	ItemStarted repo_name, path, time
	LocalIndexUpdated (item-updated) repo_name, path, time
"""
