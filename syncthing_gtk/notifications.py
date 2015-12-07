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
	from gi.repository import Gtk
	from syncthing_gtk import TimerManager
	from syncthing_gtk.tools import parsetime
	from syncthing_gtk.tools import _ # gettext function
	from dateutil import tz
	from datetime import datetime
	import os, sys, logging
	log = logging.getLogger("Notifications")
	
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
			self.syncing = set([])		# Folder id's
			# Load icons
			self.icon = None
			self.error_icon = None
			try:
				self.icon = Gtk.IconTheme.get_default().load_icon("syncthing-gtk", 64, Gtk.IconLookupFlags.FORCE_SIZE)
				self.error_icon = Gtk.IconTheme.get_default().load_icon("syncthing-gtk-error", 64, Gtk.IconLookupFlags.FORCE_SIZE)
			except Exception, e:
				log.error("Failed to load icon: %s", e)
			# Make deep connection with daemon
			self.signals = [
				self.daemon.connect("connected", self.cb_syncthing_connected)
			]
			if self.app.config["notification_for_error"]:
				self.signals += [
					self.daemon.connect("error", self.cb_syncthing_error),
					self.daemon.connect("folder-rejected", self.cb_syncthing_folder_rejected),
					self.daemon.connect("device-rejected", self.cb_syncthing_device_rejected)
				]
				log.verbose("Error notifications enabled")
			if self.app.config["notification_for_update"]:
				self.signals += [
					self.daemon.connect('item-started', self.cb_syncthing_item_started),
					self.daemon.connect('item-updated', self.cb_syncthing_item_updated),
				]
				log.verbose("File update notifications enabled")
			if self.app.config["notification_for_folder"]:
				self.signals += [
					self.daemon.connect('folder-sync-progress', self.cb_syncthing_folder_progress),
					self.daemon.connect('folder-sync-finished', self.cb_syncthing_folder_finished)
					]
				log.verbose("Folder notifications enabled")
		
		def info(self, text, icon=None):
			n = Notify.Notification.new(
					_("Syncthing-GTK"),
					text,
					None
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
			log.info("Notifications killed")
		
		def cb_syncthing_connected(self, *a):
			# Clear download list
			self.updating = set([])
			self.updated = set([])
			self.deleted = set([])
			self.syncing = set([])
		
		def cb_syncthing_error(self, daemon, message):
			if "Unexpected folder ID" in message:
				# Handled by event, don't display twice
				return
			self.error(message)
		
		def cb_syncthing_folder_rejected(self, daemon, nid, rid):
			if nid in self.app.devices:
				device = self.app.devices[nid].get_title()
				markup = _('Unexpected folder ID sent from device "%s".') % ("<b>%s</b>" % device,)
				self.info(markup)
		
		def cb_syncthing_device_rejected(self, daemon, nid, address):
			markup = _('Unknown device is trying to connect to syncthing daemon.')
			self.info(markup)
			
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
		
		def cb_syncthing_folder_progress(self, daemon, folder_id, progress):
			if progress < 1.0:
				self.syncing.add(folder_id)
		
		def cb_syncthing_folder_finished(self, daemon, folder_id):
			if folder_id in self.syncing:
				self.syncing.remove(folder_id)
				self.info(_("Synchronization of folder '%s' is completed.") % (folder_id,))
		
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
			elif len(self.deleted) == 0 and len(self.updated) > 0:
				# Multiple updated, nothing deleted
				self.info(_("%s files were updated on remote device.") % (len(self.updated),))
			elif len(self.updated) == 0 and len(self.deleted) > 0:
				# Multiple deleted, no updated
				self.info(_("%s files were deleted on remote device.") % (len(self.deleted),))
			elif len(self.deleted) > 0 and len(self.updated) > 0:
				 # Multiple deleted, multiple updated
				self.info(
					_("%(updated)s files were updated and %(deleted)s deleted on remote device.") % {
						'updated' : len(self.updated),
						'deleted' : len(self.deleted)
						}
					)
			self.updated = set([])
			self.deleted = set([])
		
	# Notifications is set to class only if libnotify is available
	Notifications = NotificationsCls

"""
Events emitted when file is changed on remote node:
	ItemStarted repo_name, path, time
	LocalIndexUpdated (item-updated) repo_name, path, time
"""
