#!/usr/bin/env python2

"""
Syncthing-GTK - Notifications

Listens to syncing events on daemon and displays desktop notifications.
"""

from __future__ import unicode_literals
from syncthing_gtk.tools import IS_WINDOWS
DELAY = 5	# Display notification only after no file is downloaded for <DELAY> seconds
ICON_DEF = "syncthing-gtk"
ICON_ERR = "syncthing-gtk-error"

SERVER_CAPS = []

HAS_DESKTOP_NOTIFY = False
Notifications = None

try:
	if not IS_WINDOWS:
		import gi
		gi.require_version('Notify', '0.7')
		from gi.repository import Notify
		HAS_DESKTOP_NOTIFY = True
except ImportError:
	pass

if HAS_DESKTOP_NOTIFY:
	from syncthing_gtk.timermanager import TimerManager
	from syncthing_gtk.tools import _ # gettext function
	import os, logging
	log = logging.getLogger("Notifications")

	class STNotification():
		""" Basic class to track a notification and update its text """
		ACT_DEFAULT = "default"
		ACT_IGNORE = "IGNORE"
		ACT_ACCEPT = "ACCEPT"
		app = None
		n = None
		id = None
		label = None

		def __init__(self, app, id, label=None):
			self.app = app
			self.id = id
			self.set_label(label)

		def set_label(self, label):
			self.label = label

		def clean(self):
			pass

		def close_notification(self):
			try:
				self.n.close_notification()
			except Exception:
				# If I can't close the notification, I don't care
				pass

		def cb_notification_closed(self, notif):
			self.n = None
			self.clean()

		def supports(self, caps, supported=True, unsupported=False):
			if caps in SERVER_CAPS:
				return supported
			else:
				return unsupported

		def addactions(self, n, actions=[], clear=True):
			if not self.supports("actions"): return
			if clear: n.clear_actions()
			for act, label, cb, data in actions:
				n.add_action(act, label, cb, data)

		def show(self, n):
			try:
				n.show()
			except Exception:
				# Ignore all errors here, there is no way I can handle
				# everything what can be broken with notifications...
				pass

		def push(self, summary, body=None, **kwargs):
			icon = kwargs.get('icon', ICON_DEF)
			urg = kwargs.get('urg')
			actions = kwargs.get('actions', [])

			if not self.n:
				self.n = Notify.Notification.new(summary, body, icon)
				self.n.connect("closed", self.cb_notification_closed),
			else:
				self.n.update(summary, body, icon)

			if urg:
				self.n.set_urgency(urg)

			self.addactions(self.n, actions)
			self.show(self.n)

	class STNotificationDevice(STNotification):
		"""Notification class to track a notification, which is related to a syncthing device"""

		def cb_accept(self, n, action, user_data):
			self.app.open_editor_device(self.id, self.label)

		def cb_ignore(self, n, action, user_data):
			# Ignore unknown device
			# TODO: use better function
			# Copied from app.py, warrants an actual function
			def add_ignored(target, trash):
				if "ignoredDevices" not in target:
					target["ignoredDevices"] = []
				target["ignoredDevices"].append(self.id)
			self.app.change_setting_async("ignoredDevices", add_ignored, restart=False)

		def rejected(self):
			label_fb = self.label or self.id
			actions = [
				(self.ACT_DEFAULT, _('Accept device "%s"') % label_fb, self.cb_accept, None),
				(self.ACT_ACCEPT,  _('Accept device "%s"') % label_fb, self.cb_accept, None),
				(self.ACT_IGNORE,  _('Ignore device "%s"') % label_fb, self.cb_ignore, None),
			]
			summary = _("Unknown Device")
			body = _('Device "%s" is trying to connect to syncthing daemon.' % self.label)
			self.push(summary, body, actions=actions, urg=Notify.Urgency.CRITICAL)

	class STNotificationFolder(STNotification, TimerManager):
		"""Notification class to track a notification, which is related to a syncthing folder"""
		syncing = False

		updated = set([])
		deleted = set([])
		updating = set([])

		timer_id = "display"
		timer_delay = DELAY

		def __init__(self, app, id, label=None):
			TimerManager.__init__(self)
			STNotification.__init__(self, app, id, label)

		def set_label(self, label):
			if label:
				self.label = label
			elif self.id in self.app.folders:
				self.label = self.app.folders[self.id]["label"]

		def clean(self):
			self.syncing = False
			self.cancel_timer(self.timer_id)
			self.updated.clear()
			self.deleted.clear()
			self.updating.clear()

		def cb_accept(self, n, action, user_data):
			self.app.open_editor_folder(self.id, self.label, user_data)

		def cb_ignore(self, n, action, user_data):
			# TODO: unimplemented
			# I probably need help here!
			pass

		def rejected(self, nid):
			device = self.app.devices[nid].get_title()
			label_fb = self.label or self.id
			actions = [
				(self.ACT_DEFAULT, _('Accept folder "%s"') % label_fb, self.cb_accept, nid),
				(self.ACT_ACCEPT,  _('Accept folder "%s"') % label_fb, self.cb_accept, nid),
				(self.ACT_IGNORE,  _('Ignore folder "%s"') % label_fb, self.cb_ignore, nid),
			]

			markup_dev = self.supports("body-markup",
				"<b>%s</b>" % device,
				device)
			markup_fol = self.supports("body-markup",
				"<b>%s</b>" % label_fb,
				label_fb)

			summary = _("Folder rejected")
			body = _('Unexpected folder "%(folder)s" sent from device "%(device)s".') % {
				'device' : markup_dev,
				'folder' : markup_fol
			}
			self.push(summary, body, actions=actions, urg=Notify.Urgency.CRITICAL)

		def add_path(self, path, itm_finished=True):
			path_full = os.path.join(self.app.folders[self.id]["norm_path"], path)

			if itm_finished:

				if ".sync-conflict" in path and os.path.exists(path_full):
					# Updated or new conflict
					self.sync_conflict(path)

				elif path in self.updating:
					if os.path.exists(path_full):
						self.updated.add(path)
					else:
						self.deleted.add(path)

					self.updating.remove(path)

					if not self.timer_active(self.timer_id):
						self.timer(self.timer_id, self.timer_delay, self.display)
			else:
				self.updating.add(path)

		def display(self, finished=False):
			summary = ""
			body = ""
			filename = ""
			if finished:
				summary = _('Completed synchronisation in "%s"') % (self.label or self.id)
			else:
				summary = _('Updates in folder "%s"') % (self.label or self.id)

			if len(self.updated) == 1 and len(self.deleted) == 0:
				f_path = os.path.join(self.app.folders[self.id]["norm_path"], self.updated.pop())
				filename = os.path.split(f_path)[-1]

				self.supports("body-hyperlinks",
					"<a href='file://%s'>%s</a>" % (f_path.encode('unicode-escape'), filename),
					f_path)

				body = _("%(hostname)s: Downloaded '%(filename)s' to reflect remote changes.")
			elif len(self.updated) == 0 and len(self.deleted) == 1:
				f_path = os.path.join(self.app.folders[self.id]["norm_path"], self.deleted.pop())
				filename = os.path.split(f_path)[-1]
				body = _("%(hostname)s: Deleted '%(filename)s' to reflect remote changes.")
			elif len(self.deleted) == 0 and len(self.updated) > 0:
				body = _("%(hostname)s: Downloaded %(updated)s files to reflect remote changes.")
			elif len(self.updated) == 0 and len(self.deleted) > 0:
				body = _("%(hostname)s: Deleted %(deleted)s files to reflect remote changes.")
			elif len(self.deleted) > 0 and len(self.updated) > 0:
				body = _("%(hostname)s: downloaded %(updated)s files and deleted %(deleted)s files to reflect remote changes.")

			body = body % {
				'hostname' : self.app.get_local_name(),
				'updated'  : len(self.updated),
				'deleted'  : len(self.deleted),
				'filename' : (filename),
			}

			self.push(summary, body)

		def set_progress(self, progress):
			if progress < 1.0:
				self.syncing = True

		def finished(self):
			if len(self.deleted) + len(self.updating) + len(self.updated) > 0 \
			   or self.syncing:
				self.display(True)

		def sync_conflict(self, path):
			path_full = os.path.join(self.app.folders[self.id]["norm_path"], path)

			summary = _('Conflicting file in "%s"') % (self.label or self.id)
			text = _('Conflict in path "%s" detected.') % path_full

			n = Notify.Notification.new(summary, text, ICON_ERR)
			n.set_urgency(Notify.Urgency.CRITICAL)
			n.add_action(self.ACT_DEFAULT, _("Open Conflicting file in filemanager"), self.cb_open_conflict, path_full)

			self.show(n)

		def cb_open_conflict(self, n, action, user_data):
			if user_data and os.path.exists(user_data):
				# TODO: open filemanager here
				pass

	class NotificationsCls():
		""" Watches for filesystem changes and reports them to daemon """
		def __init__(self, app, daemon):
			Notify.init("Syncthing GTK")
			# Cache the server capabilities, as get_server_caps() always queries DBus
			global SERVER_CAPS
			SERVER_CAPS = Notify.get_server_caps()
			# Prepare stuff
			self.app = app
			self.daemon = daemon
			self.notify_folders = {}
			self.notify_devices = {}

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

		def get_folder(self, folder_id, label=None):
			if folder_id not in self.notify_folders:
				self.notify_folders[folder_id] = STNotificationFolder(self.app, folder_id, label)
			return self.notify_folders[folder_id]

		def get_device(self, device_id, label=None):
			if device_id not in self.notify_devices:
				self.notify_devices[device_id] = STNotificationDevice(self.app, device_id, label)
			return self.notify_devices[device_id]

		def clear_notifications(self):
			# Clear download list and close related notifications
			for dct in [self.notify_devices, self.notify_folders]:
				for obj in dct.values():
					obj.close_notification()
				dct = {}

		def kill(self, *a):
			""" Removes all event handlers and frees some stuff """
			for s in self.signals:
				self.daemon.handler_disconnect(s)
			self.clear_notifications()
			log.info("Notifications killed")

		def cb_syncthing_connected(self, *a):
			self.clear_notifications()

		def cb_syncthing_error(self, daemon, message):
			summary = _('An error occured in Syncthing!')
			n = Notify.Notification.new(summary, None, ICON_ERR)
			n.set_urgency(Notify.Urgency.CRITICAL)

			try:
				n.show()
			except Exception:
				pass

		def cb_syncthing_folder_rejected(self, daemon, device_id, folder_id, label):
			if device_id not in self.app.devices:
				return

			n = self.get_folder(folder_id, label)
			n.rejected(device_id)

		def cb_syncthing_device_rejected(self, daemon, nid, name, address):
			n = self.get_device(nid, name)
			n.rejected()

		def cb_syncthing_item_started(self, daemon, folder_id, path, time):
			n = self.get_folder(folder_id)
			n.add_path(path, itm_finished=False)

		def cb_syncthing_item_updated(self, daemon, folder_id, path, *a):
			n = self.get_folder(folder_id)
			n.add_path(path)

		def cb_syncthing_folder_progress(self, daemon, folder_id, progress):
			n = self.get_folder(folder_id)
			n.set_progress(progress)

		def cb_syncthing_folder_finished(self, daemon, folder_id):
			n = self.get_folder(folder_id)
			n.finished()

	# Notifications is set to class only if libnotify is available
	Notifications = NotificationsCls

"""
Events emitted when file is changed on remote node:
	ItemStarted repo_name, path, time
	LocalIndexUpdated (item-updated) repo_name, path, time
"""
