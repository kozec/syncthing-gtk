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
	from syncthing_gtk.tools import parsetime
	from dateutil import tz
	from datetime import datetime
	from syncthing_gtk import DEBUG
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
			self.updating = set([])		# Filenames
			self.updated = set([])		# Filenames
			self.deleted = set([])		# Filenames
			# Load icons
			self.icon = None
			self.error_icon = None
			try:
				self.icon = GdkPixbuf.Pixbuf.new_from_file(os.path.join(self.app.iconpath, "st-logo-64.png"))
				self.error_icon = GdkPixbuf.Pixbuf.new_from_file(os.path.join(self.app.iconpath, "error-64.png"))
			except Exception, e:
				print >>sys.stderr, "Failed to load icon:", e
			# Make deep connection with daemon
			self.signals = [
				self.daemon.connect("connected", self.cb_syncthing_connected)
			]
			if self.app.config["notification_for_update"]:
				self.signals += [
					self.daemon.connect("error", self.cb_syncthing_error),
				]
				if DEBUG: print "Error notifications enabled"
			if self.app.config["notification_for_error"]:
				self.signals += [
					self.daemon.connect('item-started', self.cb_syncthing_item_started),
					self.daemon.connect('item-updated', self.cb_syncthing_item_updated),
				]
				if DEBUG: print "File update notifications enabled"
		
		def info(self, text, icon=None):
			n = Notify.Notification.new(
					_("Syncthing GTK"),
					text
				)
			if icon is None:
				icon = self.icon
			if not icon is None:
				n.set_icon_from_pixbuf(icon)
			try:
				if n.show ():
					return n
			except Exception, e:
				# Ignore all errors here, there is no way I can handle
				# everything what can be broken with notifications...
				pass
			del n
			return None
		
		def error(self, text):
			self.info(text, self.error_icon)
		
		def kill(self, *a):
			""" Removes all event handlers and frees some stuff """
			for s in self.signals:
				self.daemon.handler_disconnect(s)
			if DEBUG: print "Notifications killed"
		
		def cb_syncthing_connected(self, *a):
			# Clear download list
			self.updating = set([])
			self.updated = set([])
			self.deleted = set([])
		
		def cb_syncthing_error(self, daemon, error):
			self.error(error)
		
		def cb_syncthing_item_started(self, daemon, folder_id, path, time):
			if folder_id in self.app.folders:
				f_path = os.path.join(self.app.folders[folder_id]["norm_path"], path)
				self.updating.add(f_path)
		
		def cb_syncthing_item_updated(self, daemon, folder_id, path, *a):
			f_path = os.path.join(self.app.folders[folder_id]["norm_path"], path)
			if f_path in self.updating:
				# Check what kind of 'update' was done
				if os.path.exists(f_path):
					# Updated or new file
					self.updated.add(f_path)
				else:
					# Deleted file
					self.deleted.add(f_path)
				self.updating.remove(f_path)
				self.cancel_timer("display")
				self.timer("display", DELAY, self.display)
		
		def display(self):
			if len(self.updated) == 1 and len(self.deleted) == 0:
				# One updated file
				f_path = list(self.updated)[0]
				filename = os.path.split(f_path)[-1]
				self.info(_("The file '%s' was updated on remote device.") % (filename,))
			elif len(self.updated) == 0 and len(self.deleted) == 1:
				# One deleted file
				f_path = list(self.deleted)[0]
				filename = os.path.split(f_path)[-1]
				self.info(_("The file '%s' was deleted on remote device.") % (filename,))
			elif len(self.deleted) == 0:
				# Multiple updated, nothing deleted
				self.info(_("%s files were updated on remote device.") % (len(self.deleted),))
			elif len(self.updated) == 0:
				# Multiple deleted, no updated
				self.info(_("%s files were deleted on remote device.") % (len(self.deleted),))
			else:
				 # Multiple deleted, multiple updated
				self.info(
					_("%s files were updated and %s deleted on remote device.") % 
					(len(self.updated), len(self.deleted)))
			self.updated = set([])
			self.deleted = set([])
		
	# Notifications is set to class only if libnotify is available
	Notifications = NotificationsCls

"""
Events emitted when file is changed on remote node:
	ItemStarted repo_name, path, time
	LocalIndexUpdated (item-updated) repo_name, path, time
"""
