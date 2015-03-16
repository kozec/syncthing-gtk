#!/usr/bin/env python2
"""
Syncthing-GTK - Daemon

Class interfacing with syncthing daemon

Create instance, connect singal handlers and call daemon.reconnect()

"""

from __future__ import unicode_literals
from gi.repository import Gio, GLib, GObject
from syncthing_gtk import TimerManager
from syncthing_gtk.tools import parsetime, get_header, compare_version
from syncthing_gtk.tools import get_config_dir
from dateutil import tz
from xml.dom import minidom
from datetime import datetime
import json, os, sys, time, logging
log = logging.getLogger("Daemon")

# Minimal version supported by Daemon class
MIN_VERSION = "0.10"

# Random constant used as key when adding headers to returned data in
# REST requests; Anything goes, as long as it isn't string
HTTP_HEADERS = int(65513)

# Last-seen values before this date are translated to never
NEVER = datetime(1971, 1, 1, 1, 1, 1, tzinfo=tz.tzlocal())

class Daemon(GObject.GObject, TimerManager):
	"""
	Object for interacting with syncthing daemon.
	
	List of signals:
		config-out-of-sync ()
			Emited when daemon synchronization gets out of sync and
			daemon needs to be restarted.
		
		config-saved ()
			Emited when daemon saves configuration without need for
			restarting.
		
		connected ()
			Emited when connection to daemon is initiated, before
			configuration is loaded and parsed.
		
		disconnected (reason, message)
			Emited after connection to daemon is lost. Connection can
			be reinitiated by calling reconnect()
				reason :	Daemon.SHUTDOWN if connection is closed
							after calling shutdown()
							Daemon.RESTART if connection is closed
							after calling restart()
							Daemon.UNEXPECTED for all other cases
				message:	generated error message
		
		config-loaded(config)
			Emited while connection do daemon is being created, when
			configuration is loaded from daemon.
				config:		decoded /rest/config YAML file
		
		connection-error (reason, message, exception)
			Emited if connection to daemon fails.
				reason:		Daemon.REFUSED if connection is refused and
							daemon probably offline. Connection will be
							retried automaticaly.
							Daemon.UNKNOWN for all other problems.
							Connection can be reinitiated by calling
							reconnect() in this case.
				message:	generated error message
				exception:	Exeception that caused problem or None
		
		my-id-changed (my_id, replaced)
			Emited when ID is retrieved from device or when ID changes
			after client connects to another device
				my_id:		ID of device that is instance connected to.
		
		error (message)
			Emited every time when daemon generates error readable by
			WebUI (/rest/errors call)
				message:	Error message sent by daemon
		
		folder-rejected(device_id, folder_id)
			Emited when daemon detects unexpected folder from known
			device.
				device_id:	id of device that send unexpected folder id
				folder_id:	id of unexpected folder
		
		device-rejected(device_id, address)
			Emited when daemon detects connection from unknown device
				device_id:	device id
				address:	address which connection come from
		
		device-added (id, name, used, data)
			Emited when new device is loaded from configuration
				id:		id of loaded device
				name:	name of loaded device (may be None)
				used:	true if there is any folder shared with this device
				data:	dict with rest of device data
		
		device-connected (id)
			Emited when daemon connects to remote device
				id:			id of device
		
		device-disconnected (id)
			Emited when daemon losts connection to remote device
				id:			id of device
		
		device-discovered (id, addresses)
			# TODO: What this event does?
				id:			id of device
				addresses:	list of device addresses
		
		device-data-changed (id, address, version, inbps, outbps, inbytes, outbytes)
			Emited when device data changes
				id:			id of device
				address:	address of remote device
				version:	daemon version of remote device
				inbps:		download rate
				outbps:	upload rate
				inbytes:	total number of bytes downloaded
				outbytes:	total number of bytes uploaded
		
		last-seen-changed (id, last_seen)
			Emited when daemon reported 'last seen' value for device changes
			or when is this value recieved for first time
				id:			id of device
				last_seen:	datetime object or None, if device was never seen
		
		device-sync-started (id, progress):
			Emited after device synchronization is started
				id:			id of folder
				progress:	synchronization progress (0.0 to 1.0)
		
		device-sync-progress (id, progress):
			Emited repeatedly while device is being synchronized
				id:			id of folder
				progress:	synchronization progress (0.0 to 1.0)
	
		device-sync-finished (id):
			Emited after device synchronization is finished
				id:		id of folder
		
		folder-added (id, data)
			Emited when new folder is loaded from configuration
				id:		id of loaded folder
				data:	dict with rest of folder data
		
		folder-data-changed (id, data):
			Emited when change in folder data (/rest/model call)
			is detected and sucesfully loaded.
				id:		id of folder
				data:	dict with loaded data
		
		folder-data-failed (id):
			Emited when daemon fails to load folder data (/rest/model call),
			most likely beacause folder was just added and syncthing
			daemon needs to be restarted
				id:		id of folder
		
		folder-sync-progress (id, progress):
			Emited repeatedly while folder is being synchronized
				id:			id of folder
				progress:	synchronization progress (0.0 to 1.0)
	
		folder-sync-finished (id):
			Emited after folder synchronization is finished
				id:		id of folder
		
		folder-scan-started (id):
			Emited after folder scan is started
				id:		id of folder
		
		folder-scan-finished (id):
			Emited after folder scan is finished
				id:		id of folder
		
		folder-stopped (id, message):
			Emited when folder enters 'stopped' state.
			No 'folder-sync', 'folder-sync-progress' and 'folder-scan-started'
			events are emitted after folder enters this state, until
			reconnect() is called.
				id:			id of folder
				message:	error message
		
		item-started (folder_id, filename, time):
			Emited when synchronization of file starts
				folder_id:	id of folder that contains file
				filename:	synchronized file
				time:		event timestamp
		
		item-updated (folder_id, filename, mtime):
			Emited when change in local file is detected (LocalIndexUpdated event)
				folder_id:	id of folder that contains file
				filename:	updated file
				mtime:		last modification time of updated file
		
		startup-complete():
			Emited when daemon initialization is complete.
		
		system-data-updated (ram_ussage, cpu_ussage, announce)
			Emited every time when system informations are recieved
			from daemon.
				ram_ussage:	memory ussage in bytes
				cpu_ussage:	CPU ussage in percent (0.0 to 100.0)
				announce:	Dict with list of { announce_server : value }
							or None if announce is disabled
							Value is True if daemon is connected to server
	"""
	
	
	__gsignals__ = {
			b"config-out-of-sync"	: (GObject.SIGNAL_RUN_FIRST, None, ()),
			b"config-saved"			: (GObject.SIGNAL_RUN_FIRST, None, ()),
			b"connected"			: (GObject.SIGNAL_RUN_FIRST, None, ()),
			b"disconnected"			: (GObject.SIGNAL_RUN_FIRST, None, (int, object)),
			b"config-loaded"		: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"connection-error"		: (GObject.SIGNAL_RUN_FIRST, None, (int, object, object)),
			b"error"				: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"folder-rejected"		: (GObject.SIGNAL_RUN_FIRST, None, (object,object)),
			b"device-rejected"		: (GObject.SIGNAL_RUN_FIRST, None, (object,object)),
			b"my-id-changed"		: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"device-added"			: (GObject.SIGNAL_RUN_FIRST, None, (object, object, bool, object)),
			b"device-connected"		: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"device-disconnected"	: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"device-discovered"	: (GObject.SIGNAL_RUN_FIRST, None, (object,object,)),
			b"device-data-changed"	: (GObject.SIGNAL_RUN_FIRST, None, (object, object, object, float, float, object, object)),
			b"last-seen-changed"	: (GObject.SIGNAL_RUN_FIRST, None, (object, object)),
			b"device-sync-started"	: (GObject.SIGNAL_RUN_FIRST, None, (object, float)),
			b"device-sync-progress"	: (GObject.SIGNAL_RUN_FIRST, None, (object, float)),
			b"device-sync-finished"	: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"folder-added"			: (GObject.SIGNAL_RUN_FIRST, None, (object, object)),
			b"folder-data-changed"	: (GObject.SIGNAL_RUN_FIRST, None, (object, object)),
			b"folder-data-failed"	: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"folder-sync-started"	: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"folder-sync-finished"	: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"folder-sync-progress"	: (GObject.SIGNAL_RUN_FIRST, None, (object, float)),
			b"folder-scan-started"	: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"folder-scan-finished"	: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"folder-scan-progress"	: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
			b"folder-stopped"		: (GObject.SIGNAL_RUN_FIRST, None, (object,object)),
			b"item-started"			: (GObject.SIGNAL_RUN_FIRST, None, (object,object,object)),
			b"item-updated"			: (GObject.SIGNAL_RUN_FIRST, None, (object,object,object)),
			b"startup-complete"		: (GObject.SIGNAL_RUN_FIRST, None, ()),
			b"system-data-updated"	: (GObject.SIGNAL_RUN_FIRST, None, (int, float, object)),
		}
	
	# Constants for 'reason' parameter of disconnected event
	UNEXPECTED	= 0 # connection closed by daemon
	SHUTDOWN	= 1
	RESTART		= 2
	
	# Constants for 'reason' parameter of connection-error event
	REFUSED			= 1
	NOT_AUTHORIZED	= 2
	OLD_VERSION		= 3
	TLS_UNSUPPORTED	= 4
	UNKNOWN			= 255
	
	def __init__(self):
		GObject.GObject.__init__(self)
		TimerManager.__init__(self)
		self._CSRFtoken = None
		self._address = None
		self._api_key = None
		self._connected = False
		self._refresh_interval = 1 # seconds
		# syncing_folders holds set of folders that are being synchronized
		self._syncing_folders = set()
		# stopped_folders holds set of folders in 'stopped' state
		# No 'folder-sync', 'folder-sync-progress' and 'folder-scan-started'
		# events are emitted after folder enters this state
		self._stopped_folders = set()
		# syncing_devices does same thing, only for devices
		self._syncing_devices = set()
		# and once again, for folders in 'Scanning' state
		self._scanning_folders = set()
		# needs_update holds set of folders & devices whose state was
		# recently changed and needs to be fetched from server
		# (None, folder_id) for local index
		# (device_id, folder_id) for remote completion
		self._needs_update = set()
		# device_data stores data needed to compute transfer speeds
		# and synchronization state
		self._device_data = {}
		# folder_devices stores list of devices assigned to folder
		self._folder_devices = {}
		# last_seen holds last_seen value for each folder, preventing firing
		# last-seen-changed event with same values twice
		self._last_seen = {}
		# last_error_time is used to discard repeating errors
		self._last_error_time = None # Time is taken for first event
		# last_id is id of last event recieved from daemon
		self._last_id = 0
		# Epoch is incereased when reconnect() method is called; It is
		# used to discard responses for old REST requests
		self._epoch = 1
		self._my_id = None
		self._read_config()
	
	### Internal stuff ###
	
	def _read_config(self):
		# Read syncthing config to get connection url
		configxml = os.path.join(get_config_dir(), "syncthing", "config.xml")
		try:
			config = file(configxml, "r").read()
		except Exception, e:
			raise InvalidConfigurationException("Failed to read daemon configuration: %s" % e)
		try:
			xml = minidom.parseString(config)
		except Exception, e:
			raise InvalidConfigurationException("Failed to parse daemon configuration: %s" % e)
		tls = "false"
		try:
			tls = xml.getElementsByTagName("configuration")[0] \
				.getElementsByTagName("gui")[0].getAttribute("tls")
		except Exception, e:
			pass
		self._tls = False
		if tls.lower() == "true":
			self._tls = True
		try:
			self._address = xml.getElementsByTagName("configuration")[0] \
							.getElementsByTagName("gui")[0] \
							.getElementsByTagName("address")[0] \
							.firstChild.nodeValue
			if self._address.startswith("0.0.0.0"):
				addr, port = self._address.split(":", 1)
				self._address = "127.0.0.1:%s" % (port,)
				log.debug("WebUI listens on 0.0.0.0, connecting to 127.0.0.1 instead")
		except Exception, e:
			log.exception(e)
			raise InvalidConfigurationException("Required configuration node not found in daemon config file")
		try:
			self._api_key = xml.getElementsByTagName("configuration")[0] \
							.getElementsByTagName("gui")[0] \
							.getElementsByTagName("apikey")[0] \
							.firstChild.nodeValue
		except Exception, e:
			# API key can be none
			pass
	
	def override_config(self, address, api_key):
		"""
		Can be used to override settings loaded from config file.
		api_key can be None.
		"""
		self._address = address
		self.api_key = api_key
	
	def _get_device_data(self, nid):
		""" Returns dict with device data, creating it if needed """
		if not nid in self._device_data:
			self._device_data[nid] = {
					"InBytesTotal" : 0, "OutBytesTotal" : 0,
					"inbps" : 0, "outbps" : 0 , "ClientVersion" : "?",
					"Address": "", "completion" : {}, "connected" : False,
				}
		return self._device_data[nid]
	
	def _rest_request(self, command, callback, error_callback=None, *callback_data):
		"""
		Requests response from server. After response is recieved,
		callback with parsed json data is called.
		If requests fails and error_callback is set, error_callback is
		called. If error_callback is None, request is repeated.
		
		Callback signatures:
			callback(json_data, callback_data... )
			error_callback(exception, command, callback_data... )
		"""
		sc = Gio.SocketClient(tls=self._tls, tls_validation_flags=0)
		sc.connect_to_host_async(self._address, 0, None, self._rest_connected,
			(command, self._epoch, callback, error_callback, callback_data))
	
	def _rest_connected(self, sc, results, (command, epoch, callback, error_callback, callback_data)):
		""" Second part of _rest_request, called after HTTP connection is initiated """
		try:
			con = sc.connect_to_service_finish(results)
			if con == None:
				raise Exception("Unknown error")
		except Exception, e:
			log.exception(e)
			if hasattr(e, "domain") and e.domain == "g-tls-error-quark":
				e = TLSUnsupportedException(e.message)
			self._rest_error(e, epoch, command, callback, error_callback, callback_data)
			return
		if epoch < self._epoch :
			# Too late, throw it away
			con.close(None)
			log.verbose("Discarded old connection for %s", command)
		# Build GET request
		get_str = "\r\n".join([
			"GET /rest/%s HTTP/1.0" % command,
			(("X-API-Key: %s" % self._api_key) if not self._api_key is None else "X-nothing: x"),
			"Connection: close",
			"", ""
			]).encode("utf-8")
		# Send it out and wait for response
		try:
			con.get_output_stream().write_all(get_str, None)
		except Exception, e:
			self._rest_error(e, epoch, command, callback, error_callback, callback_data)
			return
		con.get_input_stream().read_bytes_async(102400, 1, None, self._rest_response,
			(con, command, epoch, callback, error_callback, callback_data, []))
	
	def _rest_response(self, sc, results, (con, command, epoch, callback, error_callback, callback_data, buffer)):
		try:
			response = sc.read_bytes_finish(results)
			if response == None:
				raise Exception("No data recieved")
		except Exception, e:
			con.close(None)
			self._rest_error(e, epoch, command, callback, error_callback, callback_data)
			return
		if epoch < self._epoch :
			# Too late, throw it away
			con.close(None)
			log.verbose("Discarded old response for %s", command)
		# Repeat read_bytes_async until entire response is readed in buffer
		buffer.append(response.get_data().decode("utf-8"))
		if response.get_size() > 0:
			con.get_input_stream().read_bytes_async(102400, 1, None, self._rest_response,
				(con, command, epoch, callback, error_callback, callback_data, buffer))
			return
		con.close(None)
		response = "".join(buffer)
		# Split headers from response
		try:
			headers, response = response.split("\r\n\r\n", 1)
			headers = headers.split("\r\n")
			code = int(headers[0].split(" ")[1])
			if code == 401:
				self._rest_error(HTTPAuthException("".join(buffer)), epoch, command, callback, error_callback, callback_data)
				return
			elif code != 200:
				self._rest_error(HTTPCode(code, response, "".join(buffer)), epoch, command, callback, error_callback, callback_data)
				return
		except Exception, e:
			# That probably wasn't HTTP
			self._rest_error(InvalidHTTPResponse("".join(buffer)), epoch, command, callback, error_callback, callback_data)
			return
		# Parse response and call callback
		try:
			rdata = json.loads(response)
		except IndexError: # No data
			rdata = { }
		except ValueError: # Not a JSON
			rdata = {'data' : response }
		if type(rdata) == dict:
			rdata[HTTP_HEADERS] = headers
		if callback_data:
			callback(rdata, *callback_data)
		else:
			callback(rdata)
	
	def _rest_error(self, exception, epoch, command, callback, error_callback, callback_data):
		""" Error handler for _rest_response method """
		if error_callback:
			if epoch != self._epoch:
				exception = ConnectionRestarted()
			if callback_data:
				error_callback(exception, command, *callback_data)
			else:
				error_callback(exception, command)
		elif epoch == self._epoch:
			try:
				log.error("Request '%s' failed (%s); Repeating...", command, exception)
			except UnicodeDecodeError:
				# Windows...
				log.error("Request '%s' failed; Repeating...", command)
			self.timer(None, 1, self._rest_request, command, callback, error_callback, *callback_data)
	
	def _rest_post(self, command, data, callback, error_callback=None, *callback_data):
		""" POSTs data (formated with json) to daemon. Works like _rest_request """
		sc = Gio.SocketClient(tls=self._tls)
		sc.connect_to_host_async(self._address, 0, None, self._rest_post_connected,
			(command, data, self._epoch, callback, error_callback, callback_data))
	
	def _rest_post_connected(self, sc, results, (command, data, epoch, callback, error_callback, callback_data)):
		""" Second part of _rest_post, called after HTTP connection is initiated """
		try:
			con = sc.connect_to_service_finish(results)
			if con == None:
				raise Exception("Unknown error")
		except Exception, e:
			if hasattr(e, "domain") and e.domain == "g-tls-error-quark":
				e = TLSUnsupportedException(e.message)
			self._rest_post_error(e, epoch, command, data, callback, error_callback, callback_data)
			return
		if epoch < self._epoch :
			# Too late, throw it away
			con.close(None)
			log.verbose("Discarded old connection for POST %s", command)
		post_str = None
		if self._CSRFtoken is None and self._api_key is None:
			# Request CSRF token first
			log.verbose("Requesting cookie")
			post_str = "\r\n".join([
				"GET / HTTP/1.0",
				"Host: %s" % self._address,
				(("X-API-Key: %s" % self._api_key) if not self._api_key is None else "X-nothing: x"),
				"Connection: close",
				"",
				"",
				]).encode("utf-8")
		else:
			# Build POST request
			json_str = json.dumps(data)
			post_str = "\r\n".join([
				"POST /rest/%s HTTP/1.0" % command,
				"Connection: close",
				"Cookie: CSRF-Token=%s" % self._CSRFtoken,
				"X-CSRF-Token: %s" % self._CSRFtoken,
				(("X-API-Key: %s" % self._api_key) if not self._api_key is None else "X-nothing: x"),
				"Content-Length: %s" % len(json_str),
				"Content-Type: application/json",
				"",
				json_str
				]).encode("utf-8")
		# Send it out and wait for response
		try:
			con.get_output_stream().write_all(post_str, None)
		except Exception, e:
			self._rest_error(e, epoch, command, callback, error_callback, callback_data)
			return
		con.get_input_stream().read_bytes_async(102400, 1, None, self._rest_post_response,
			(con, command, data, epoch, callback, error_callback, callback_data, []))
	
	def _rest_post_response(self, sc, results, (con, command, data, epoch, callback, error_callback, callback_data, buffer)):
		try:
			response = sc.read_bytes_finish(results)
			if response == None:
				raise Exception("No data recieved")
		except Exception, e:
			con.close(None)
			self._rest_post_error(e, epoch, command, data, callback, error_callback, callback_data)
			return
		if epoch < self._epoch :
			# Too late, throw it away
			con.close(None)
			log.verbose("Discarded old response for POST %s", command)
		# Repeat _rest_post_response until entire response is readed in buffer
		buffer.append(response.get_data().decode("utf-8"))
		if response.get_size() > 0:
			con.get_input_stream().read_bytes_async(102400, 1, None, self._rest_post_response,
				(con, command, data, epoch, callback, error_callback, callback_data, buffer))
			return
		con.close(None)
		response = "".join(buffer)
		# Parse response
		if self._CSRFtoken is None and self._api_key is None:
			# I wanna cookie!
			response = response.split("\n")
			for d in response:
				if d.startswith("Set-Cookie:"):
					for c in d.split(":", 1)[1].split(";"):
						if c.strip().startswith("CSRF-Token="):
							self._CSRFtoken = c.split("=", 1)[1].strip(" \r\n")
							log.verbose("Got new cookie: %s", self._CSRFtoken)
							break
					if self._CSRFtoken != None:
						break
			if self._CSRFtoken == None:
				# This is pretty fatal and likely to fail again,
				# so request is not repeated automaticaly
				if error_callback == None:
					log.error("Request '%s' failed: Error: failed to get CSRF cookie from daemon", command)
				else:
					self._rest_post_error(Exception("Failed to get CSRF cookie"), epoch, command, data, callback, error_callback, callback_data)
				return
			# Repeat request with acqiured cookie
			self._rest_post(command, data, callback, error_callback, *callback_data)
			return
		# Extract response code
		try:
			headers, response = response.split("\r\n\r\n", 1)
			headers = headers.split("\r\n")
			code = int(headers[0].split(" ")[1])
			if code == 500:
				self._rest_error(HTTPCode(500, response, "".join(buffer)), epoch, command, callback, error_callback, callback_data)
				return
			elif code != 200:
				self._rest_post_error(HTTPCode(code, response, "".join(buffer)), epoch, command, data, callback, error_callback, callback_data)
				return
		except Exception:
			# That probably wasn't HTTP
			self._rest_post_error(InvalidHTTPResponse("".join(buffer)), epoch, command, data, callback, error_callback, callback_data)
			return
		if "CSRF Error" in response:
			# My cookie is too old; Throw it away and try again
			log.verbose("Throwing away my cookie :(")
			self._CSRFtoken = None
			self._rest_post(command, data, callback, error_callback, *callback_data)
			return
		
		# Parse response and call callback
		try:
			rdata = json.loads(response)
		except IndexError: # No data
			rdata = { }
		except ValueError: # Not a JSON
			rdata = {'data' : response }
		if type(rdata) == dict:
			rdata[HTTP_HEADERS] = headers
		if callback_data:
			callback(rdata, *callback_data)
		else:
			callback(rdata)
	
	def _rest_post_error(self, exception, epoch, command, data, callback, error_callback, callback_data):
		""" Error handler for _rest_post_response method """
		if error_callback:
			if epoch != self._epoch:
				exception = ConnectionRestarted()
			if callback_data:
				error_callback(exception, command, data, *callback_data)
			else:
				error_callback(exception, command, data)
		elif epoch != self._epoch:
			try:
				log.error("Post '%s' failed (%s) Repeating...", command, exception)
			except UnicodeDecodeError:
				# Windows...
				log.error("Post '%s' failed; Repeating...", command)
			self.timer(None, 1, self._rest_post, command, data, callback, error_callback, callback_data)
	
	def _request_config(self, *a):
		""" Request settings from syncthing daemon """
		self._rest_request("config", self._syncthing_cb_config, self._syncthing_cb_config_error)
	
	def _request_folder_data(self, rid):
		self._rest_request("model?folder=%s" % (rid,), self._syncthing_cb_folder_data, self._syncthing_cb_folder_data_failed, rid)
	
	def _request_completion(self, nid, rid=None):
		"""
		Requests completion data for specified device and folder.
		If rid is None, requests completion data for specified device and
		ALL folders.
		"""
		if rid is None:
			for rid in self._folder_devices:
				if nid in self._folder_devices[rid]:
					self._request_completion(nid, rid)
			return
		self._rest_request("completion?device=%s&folder=%s" % (nid, rid), self._syncthing_cb_completion, None, nid, rid)
	
	def _request_events(self, *a):
		""" Request new events from syncthing daemon """
		self._rest_request("events?since=%s" % self._last_id, self._syncthing_cb_events, self._syncthing_cb_events_error)
	
	def _request_last_seen(self, *a):
		""" Request 'last seen' values for all devices """
		self._rest_request("stats/device", self._syncthing_cb_last_seen, lambda *a: True)
	
	def _parse_dev_n_folders(self, config):
		"""
		Parses devices and folders from configuration and emits
		associated events.
		"""
		# Pre-parse folders to detect unused devices
		device_folders = {}
		for r in config["Folders"]:
			rid = r["ID"]
			for n in r["Devices"]:
				nid = n["DeviceID"]
				if not nid in device_folders : device_folders[nid] = []
				device_folders[nid].append(rid)

		# Parse devices
		for n in sorted(config["Devices"], key=lambda x : x["Name"].lower()):
			nid = n["DeviceID"]
			self._get_device_data(nid)	# Creates dict with device data
			used = (nid in device_folders) and (len(device_folders[nid]) > 0)
			self.emit("device-added", nid, n["Name"], used, n)
			
		# Parse folders
		for r in config["Folders"]:
			rid = r["ID"]
			self._syncing_folders.add(rid)
			self._folder_devices[rid] = [ n["DeviceID"] for n in r["Devices"] ]
			self.emit("folder-added", rid, r)
			self._request_folder_data(rid)
	
	### Callbacks ###
	
	def _syncthing_cb_shutdown(self, data, reason):
		""" Callback for 'shutdown' AND 'restart' request """
		if 'ok' in data:
			if self._connected:
				self._connected = False
				self._epoch += 1
				self.emit("disconnected", reason, "")
			self.cancel_all()
	
	def _init_event_pooling(self, events):
		if type(events) == list and len(events) > 0:
			self._last_id = events[-1]["id"]
			try:
				self._last_error_time = parsetime(events[-1]["time"])
			except ValueError:
				self._last_error_time = datetime.datetime.now()
			self._rest_request("errors", self._syncthing_cb_errors)
			self._request_events()
		else:
			# Retry for invalid data
			self._rest_request("events?limit=1", self._init_event_pooling)

	
	def _syncthing_cb_events(self, events):
		""" Called when event list is pulled from syncthing daemon """
		if type(events) == list:	# Ignore invalid data
			if len(events) > 0:
				this_epoch = self._epoch
				for e in events:
					if e["id"] > self._last_id:
						self._on_event(e)
						if this_epoch != self._epoch:
							# Restarted durring last event handler
							self._last_id = events[-1]["id"]
							return
				self._last_id = events[-1]["id"]
				
				for nid, rid in self._needs_update:
					if nid is None:
						self._request_folder_data(rid)
					else:
						self._request_completion(nid, rid)
				self._needs_update.clear()
		
		self.timer("event", self._refresh_interval, self._request_events)
	
	def _syncthing_cb_errors(self, errors):
		for e in errors["errors"]:
			t = parsetime(e["Time"])
			if t > self._last_error_time:
				self.emit("error", e["Error"])
				self._last_error_time = t
		self.timer("errors", self._refresh_interval * 5, self._rest_request, "errors", self._syncthing_cb_errors)
	
	def _syncthing_cb_events_error(self, exception, command):
		"""
		As most frequent request, "event" request is used to detect when
		daemon stops to respond. "Please wait" message is displayed in
		that case, UI is restarted and waits until daemon respawns.
		"""
		if isinstance(exception, GLib.GError):
			if exception.code in (0, 39, 34):	# Connection terminated unexpectedly, Connection Refused
				if self._connected:
					self._connected = False
					self.emit("disconnected", Daemon.UNEXPECTED, exception.message)
				self.cancel_all()
				return
		# Other errors are ignored and events are pulled again after prolonged delay
		self.timer("event", self._refresh_interval * 5, self._request_events)
	
	def _syncthing_cb_connections(self, data, prev_time):
		now = time.time()
		td = now - prev_time
		
		for id in data:
			# Load device data
			if id == HTTP_HEADERS:
				# Special key added by rest_request method
				continue
			nid = id
			if id == "total":
				# Use my own device for totals, if it is already known
				# It it is not known, just skip totals for now
				if self._my_id is None:
					continue
				nid = self._my_id
			device_data = self._get_device_data(nid)
			
			# Compute rates
			try:
				data[id]["inbps"] = max(0.0, (data[id]["InBytesTotal"] - device_data["InBytesTotal"]) / td);
				data[id]["outbps"] = max(0.0, (data[id]["OutBytesTotal"] - device_data["OutBytesTotal"]) / td);
			except Exception:
				data[id]["inbps"] = 0.0
				data[id]["outbps"] = 0.0
			# Store updated device_data
			for key in data[id]:
				if key != "ClientVersion" or data[id][key] != "":	# Happens for 'total'
					device_data[key] = data[id][key]
			
			# Send "device-connected" signal, if device was disconnected until now
			if not device_data["connected"] and nid != self._my_id:
				device_data["connected"] = True
				self.emit("device-connected", nid)
			# Send "device-data-changed" signal
			self.emit("device-data-changed", nid, 
				device_data["Address"],
				device_data["ClientVersion"],
				device_data["inbps"],
				device_data["outbps"],
				device_data["InBytesTotal"],
				device_data["OutBytesTotal"])
		
		# ... repeat until pronounced dead
		self.timer("conns", self._refresh_interval * 5, self._rest_request, "connections", self._syncthing_cb_connections, None, now)
	
	def _syncthing_cb_last_seen(self, data):
		for nid in data:
			if nid != HTTP_HEADERS:
				t = parsetime(data[nid]["LastSeen"])
				if t < NEVER: t = None
				if not nid in self._last_seen or self._last_seen[nid] != t:
					self._last_seen[nid] = t
					self.emit('last-seen-changed', nid, t)
	
	def _syncthing_cb_completion(self, data, nid, rid):
		if "completion" in data:
			# Store acquired value
			device = self._get_device_data(nid)
			device["completion"][rid] = float(data["completion"])
			
			# Recompute stuff
			total = 100.0 * len(device["completion"])
			sync = 0.0
			if total > 0.0:
				sync = sum(device["completion"].values()) / total
			if sync <= 0 or sync >= 100:
				# Not syncing
				if nid in self._syncing_devices:
					self._syncing_devices.discard(nid)
					self.emit("device-sync-finished", nid)
			else:
				# Syncing
				if not nid in self._syncing_devices:
					self._syncing_devices.add(nid)
					self.emit("device-sync-started", nid, sync)
				else:
					self.emit("device-sync-progress", nid, sync)

	
	def _syncthing_cb_system(self, data):
		if self._my_id != data["myID"]:
			if self._my_id != None:
				# Can myID be ever changed?
				log.warning("My ID has been changed on the fly")
			self._my_id = data["myID"]
			self.emit('my-id-changed', self._my_id)
			version = get_header(data[HTTP_HEADERS], "X-Syncthing-Version")
			if version:
				self._syncthing_cb_version_known(version)
			else:
				self._rest_request("version", self._syncthing_cb_version)
		
		announce = None
		if "extAnnounceOK" in data:
			if hasattr(data["extAnnounceOK"], "keys"):
				# Dict, Syncthing >= 0.10.9
				announce = data["extAnnounceOK"]
			else:
				# Boolean, older Syncthing
				announce = { 'default' : bool(data["extAnnounceOK"]) }
		
		self.emit('system-data-updated',
			data["sys"], float(data["cpuPercent"]),
			announce)
		
		self.timer("system", self._refresh_interval * 5, self._rest_request, "system", self._syncthing_cb_system)
	
	def _syncthing_cb_version(self, data):
		if "version" in data:
			# New since https://github.com/syncthing/syncthing/commit/d7956dd4957fa6eee5971c072fd7181015fa876c
			version = data["version"]
		else:
			version = data["data"]
		self._syncthing_cb_version_known(version)
	
	def _syncthing_cb_version_known(self, version):
		"""
		Called when version is recieved from daemon, either by
		calling /rest/version or from X-Syncthing-Version header.
		"""
		if not compare_version(version, MIN_VERSION):
			# Syncting version too low. Cancel everything and report error
			self.cancel_all()
			self._epoch += 1
			msg = "daemon is too old"
			self.emit("connection-error", Daemon.OLD_VERSION, msg, Exception(msg))
			return
		if self._my_id != None:
			device = self._get_device_data(self._my_id)
			if version != device["ClientVersion"]:
				device["ClientVersion"] = version
				self.emit("device-data-changed", self._my_id, 
					None,
					device["ClientVersion"],
					device["inbps"], device["outbps"],
					device["InBytesTotal"], device["OutBytesTotal"])
	
	def _syncthing_cb_folder_data(self, data, rid):
		state = data['state']
		if len(data['invalid'].strip()) > 0:
			if not rid in self._stopped_folders:
				self._stopped_folders.add(rid)
				self.emit("folder-stopped", rid, data["invalid"])
		self.emit('folder-data-changed', rid, data)
		if state == "syncing":
			p = 0.0
			if float(data["globalBytes"]) > 0.0:
				p = float(data["inSyncBytes"]) / float(data["globalBytes"])
			if self._folder_state_changed(rid, state, p):
				self.timer("folder_%s" % rid, self._refresh_interval, self._request_folder_data, rid)
		else:
			if self._folder_state_changed(rid, state, 0):
				self.timer("folder_%s" % rid, self._refresh_interval, self._request_folder_data, rid)
	
	def _syncthing_cb_folder_data_failed(self, exception, request, rid):
		self.emit('folder-data-failed', rid)
	
	def _syncthing_cb_config(self, config):
		"""
		Called when configuration is loaded from syncthing daemon.
		After configuraion is sucessfully parsed, app starts quering for events
		"""
		if not self._connected:
			self._connected = True
			self.emit('connected')
			
			self._parse_dev_n_folders(config)
			
			self._rest_request("events?limit=1", self._init_event_pooling)	# Requests most recent event only
			self._rest_request("config/sync", self._syncthing_cb_config_in_sync)
			self._rest_request("connections", self._syncthing_cb_connections, None, time.time())
			self._rest_request("system", self._syncthing_cb_system)
			self._request_last_seen()
			self.check_config()
			self.emit('config-loaded', config)
	
	def _syncthing_cb_config_error(self, exception, command):
		self.cancel_all()
		if isinstance(exception, GLib.GError):
			if exception.code in (0, 39, 34):	# Connection Refused / Cannot connect to destination
				# It usualy means that daemon is not yet fully started or not running at all.
				epoch = self._epoch
				self.emit("connection-error", Daemon.REFUSED, exception.message, exception)
				if epoch == self._epoch:
					self.timer("config", self._refresh_interval, self._rest_request, "config", self._syncthing_cb_config, self._syncthing_cb_config_error)
				return
		elif isinstance(exception, HTTPAuthException):
			self.emit("connection-error", Daemon.NOT_AUTHORIZED, exception.message, exception)
			return
		elif isinstance(exception, TLSUnsupportedException):
			self.emit("connection-error", Daemon.TLS_UNSUPPORTED, exception.message, exception)
			return
		elif isinstance(exception, ConnectionRestarted):
			# Happens on Windows. Just try again.
			GLib.idle_add(self._request_config)
			return
		elif isinstance(exception, TLSUnsupportedException):
			self.emit("connection-error", Daemon.TLS_UNSUPPORTED, exception.message, exception)
			return
		self.emit("connection-error", Daemon.UNKNOWN, exception.message, exception)
	
	def _syncthing_cb_config_in_sync(self, data):
		"""
		Handler for config/sync response. Emits 'config-out-of-sync' if
		configuration is not in sync.
		"""
		if "configInSync" in data:
			if not data["configInSync"]:
				# Not in sync...
				self.emit("config-out-of-sync")
	
	def _folder_state_changed(self, rid, state, progress):
		"""
		Emits event according to last known and new state.
		Returns False or True to indicate that folder status should be
		re-checked after short time.
		"""
		recheck = False
		if state != "syncing" and rid in self._syncing_folders:
			self._syncing_folders.discard(rid)
			if not rid in self._stopped_folders:
				self.emit("folder-sync-finished", rid)
		if state != "scanning" and rid in self._scanning_folders:
			self._scanning_folders.discard(rid)
			if not rid in self._stopped_folders:
				self.emit("folder-scan-finished", rid)
		if state == "syncing":
			if not rid in self._stopped_folders:
				if rid in self._syncing_folders:
					self.emit("folder-sync-progress", rid, progress)
				else:
					self._syncing_folders.add(rid)
					self.emit("folder-sync-started", rid)
				recheck = True
		elif state == "scanning":
			if not rid in self._stopped_folders:
				if rid in self._scanning_folders:
					self.emit("folder-scan-progress", rid)
				else:
					self._scanning_folders.add(rid)
					self.emit("folder-scan-started", rid)
				recheck = True
		return recheck
	
	def _on_event(self, e):
		eType = e["type"]
		if eType in ("Ping", "Starting"):
			# Just ignore ignore those
			pass
		elif eType == "StartupComplete":
			self.emit("startup-complete")
		elif eType == "StateChanged":
			state = e["data"]["to"]
			rid = e["data"]["folder"]
			if self._folder_state_changed(rid, state, 0):
				self._needs_update.add((None, rid))
		elif eType in ("RemoteIndexUpdated"):
			rid = e["data"]["folder"]
			nid = e["data"]["device"]
			if (not rid in self._syncing_devices) and (not rid in self._scanning_folders):
				self._needs_update.add((None, rid))
			self._needs_update.add((nid, rid))
		elif eType == "DeviceConnected":
			nid = e["data"]["id"]
			self.emit("device-connected", nid)
			self._request_completion(nid)
		elif eType == "DeviceDisconnected":
			nid = e["data"]["id"]
			self.emit("device-disconnected", nid)
			self._request_last_seen()
		elif eType == "DeviceDiscovered":
			nid = e["data"]["device"]
			addresses = e["data"]["addrs"]
			self.emit("device-discovered", nid, addresses)
		elif eType == "FolderRejected":
			nid = e["data"]["device"]
			rid = e["data"]["folder"]
			self.emit("folder-rejected", nid, rid)
		elif eType == "DeviceRejected":
			nid = e["data"]["device"]
			address = e["data"]["address"]
			self.emit("device-rejected", nid, address)
		elif eType == "ItemStarted":
			rid = e["data"]["folder"]
			filename = e["data"]["item"]
			t = parsetime(e["time"])
			self.emit("item-started", rid, filename, t)
		elif eType == "LocalIndexUpdated":
			rid = e["data"]["folder"]
			filename = e["data"]["name"]
			mtime = parsetime(e["data"]["modified"])
			if (not rid in self._syncing_devices) and (not rid in self._scanning_folders):
				self._needs_update.add((None, rid))
			self.emit("item-updated", rid, filename, mtime)
			# Request completion data for each device that shares this folder
			for nid in self._folder_devices[rid]:
				self._needs_update.add((nid, rid))
		elif eType == "ConfigSaved":
			self.emit("config-saved")
		elif eType == "ItemFinished":
			# Not handled (yet?)
			pass
		elif eType == "DownloadProgress":
			# Not handled (yet?)
			pass
		else:
			log.warning("Unhandled event type: %s", e)
	
	### External stuff ###
	
	def reconnect(self):
		"""
		Cancel all pending requests, throw away all data and (re)connect.
		Should be called from glib loop
		"""
		self.close()
		GLib.idle_add(self._request_config)
	
	def reload_config(self, error_callback=None):
		"""
		Reloads config from syncthing daemon.
		Calling this will cause or may cause emiting following events
		with reloaded data:
		- folder-added
		- device-added
		- config-out-of-sync
		"""
		def reload_config_cb(config):
			self._parse_dev_n_folders(config)
			self._rest_request("config/sync", self._syncthing_cb_config_in_sync)
		self._rest_request("config", reload_config_cb, error_callback)
	
	def close(self):
		"""
		Terminates everything, cancel all pending requests, throws away
		data.
		Works like reconnect(), but without reconnecting.
		"""
		self._my_id = None
		self._connected = False
		self._syncing_folders = set()
		self._stopped_folders = set()
		self._syncing_devices = set()
		self._scanning_folders = set()
		self._needs_update = set()
		self._device_data = {}
		self._folder_devices = {}
		self._last_id = 0
		self._last_seen = {}
		self.cancel_all()
		self._epoch += 1
	
	def check_config(self):
		"""
		Check if configuration is in sync.
		Should cause 'config-out-of-sync' event to be raised ASAP.
		"""
		self._rest_request("config/sync", self._syncthing_cb_config_in_sync)
	
	def read_config(self, callback, error_callback=None, *calbackdata):
		"""
		Asynchronously reads last configuration version from daemon
		(even if this version is not currently used). Calls
		callback(config) with data decoded from json on success,
		error_callback(exception) on failure
		"""
		self._rest_request("config", callback, error_callback, *calbackdata)
	
	def write_config(self, config, callback, error_callback=None, *calbackdata):
		"""
		Asynchronously POSTs new configuration to daemon. Calls
		callback() on success, error_callback(exception) on failure.
		Should cause 'config-out-of-sync' event to be raised ASAP.
		"""
		def run_before(data, *a):
			self.check_config()
			callback(*calbackdata)
		self._rest_post("config", config, run_before, error_callback, *calbackdata)
	
	def read_stignore(self, folder_id, callback, error_callback=None, *calbackdata):
		"""
		Asynchronously reads .stignore data from from daemon.
		Calls callback(text) with .stignore content on success,
		error_callback(exception) on failure
		"""
		def r_filter(data, *a):
			if "ignore" in data and not data["ignore"] is None:
				callback("\n".join(data["ignore"]).strip(" \t\n"), *a)
			else:
				callback("", *a)
		self._rest_request("ignores?folder=%s" % (folder_id,), r_filter, error_callback, *calbackdata)
	
	def write_stignore(self, folder_id, text, callback, error_callback=None, *calbackdata):
		"""
		Asynchronously POSTs .stignore to daemon. Calls callback()
		with on success, error_callback(exception) on failure.
		"""
		data = { 'ignore': text.split("\n") }
		self._rest_post("ignores?folder=%s" % (folder_id,), data, callback, error_callback, *calbackdata)
	
	def restart(self):
		"""
		Asks daemon to restart. If sucesfull, call will cause
		'disconnected' event with Daemon.RESTART reason to be fired
		"""
		self._rest_post("restart",  {}, self._syncthing_cb_shutdown, None, Daemon.RESTART)
	
	def shutdown(self):
		"""
		Asks daemon to shutdown. If sucesfull, call will cause
		'disconnected' event with Daemon.SHUTDOWN reason to be fired
		"""
		self._rest_post("shutdown",  {}, self._syncthing_cb_shutdown, None, Daemon.SHUTDOWN)
	
	def syncing(self):
		""" Returns true if any folder is being synchronized right now  """
		return len(self._syncing_folders) > 0
	
	def get_min_version(self):
		"""
		Returns minimal syncthing daemon version that daemon instance
		can handle.
		"""
		return MIN_VERSION
	
	def get_syncing_list(self):
		"""
		Returns list of ids of foldersitories that are being
		synchronized right now.
		"""
		return list(self._syncing_folders)
	
	def get_my_id(self):
		"""
		Returns ID of device that is instance connected to.
		May return None to indicate that ID is not yet known
		"""
		return self._my_id
	
	def get_webui_url(self):
		""" Returns webiu url in http(s)://127.0.0.1:8080 format """
		return "%s://%s" % (
			"https" if self._tls else "http",
			self._address
		)
	
	def get_address(self):
		""" Returns tuple address on which daemon listens on. """
		return self._address
	
	def is_connected(self):
		""" Returns True if daemon is known to be alive """
		return self._connected
	
	def rescan(self, folder_id, path=None):
		""" Asks daemon to rescan entire folder or specified path """
		# Errors here are ignored; Syncthing rescans stuff periodicaly,
		# so it's not big problem if call fails.
		if path is None:
			self._rest_post("scan?folder=%s" % (folder_id,), {}, lambda *a: a, lambda *a: a, folder_id)
		else:
			self._rest_post("scan?folder=%s&sub=%s" % (folder_id, path), {}, lambda *a: a, lambda *a: a, folder_id)
	
	def override(self, folder_id):
		""" Asks daemon to override changes made in specified folder """
		# Errors here are non-fatal, not expected and thus ignored.
		def on_error(*a):
			print a
		self._rest_post("model/override?folder=%s" % (folder_id,), {}, lambda *a: a, on_error, folder_id)
	
	def request_events(self):
		"""
		Requests event directly, without waiting for timer to fire.
		May fail silently if instance is not connected to daemon or is
		already waiting for events.
		"""
		if self.cancel_timer("event"):
			self._request_events()
			log.verbose("Forced to request events")
	
	def set_refresh_interval(self, i):
		""" Sets interval used mainly by event quering timer """
		self._refresh_interval = i
		log.verbose("Set refresh interval to %s", i)

class InvalidConfigurationException(RuntimeError): pass
class TLSUnsupportedException(RuntimeError): pass

class HTTPError(RuntimeError):
	def __init__(self, message, full_response):
		RuntimeError.__init__(self, message)
		self.full_response = full_response

class InvalidHTTPResponse(HTTPError):
	def __init__(self, full_response):
		HTTPError.__init__(self, "Invalid HTTP response", full_response)

class HTTPCode(HTTPError):
	def __init__(self, code, message, full_response):
		HTTPError.__init__(self, "HTTP error %s" % (code,), message, full_response)
		self.code = code
		self.message = message
	def __str__(self):
		if self.message is None:
			return "HTTP/%s" % (self.code,)
		else:
			return "HTTP/%s: %s" % (self.code, self.message)

class HTTPAuthException(HTTPCode):
	def __init__(self, full_response):
		HTTPCode.__init__(self, 401, None, full_response)
	def __str__(self):
		return "HTTP/401 Unauthorized"

class ConnectionRestarted(Exception):
	def __init__(self):
		Exception.__init__(self, "Connection was restarted after request")
