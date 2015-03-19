#!/usr/bin/env python2
"""
Syncthing-GTK - DaemonProcess

Runs syncthing daemon process as subprocess of application
"""

from __future__ import unicode_literals
from gi.repository import Gio, GLib, GObject
from syncthing_gtk.tools import IS_WINDOWS
from collections import deque
import os, sys, logging
log = logging.getLogger("DaemonProcess")

HAS_SUBPROCESS = hasattr(Gio, "Subprocess")
if IS_WINDOWS:
	# POpen is used on Windows
	from subprocess import Popen, PIPE, STARTUPINFO, \
		STARTF_USESHOWWINDOW, CREATE_NEW_CONSOLE, \
		CREATE_NEW_PROCESS_GROUP
	from syncthing_gtk.windows import WinPopenReader, nice_to_priority_class
elif not HAS_SUBPROCESS:
	# Gio.Subprocess is not available in Gio < 3.12
	from subprocess import Popen, PIPE

class DaemonProcess(GObject.GObject):
	__gsignals__ = {
		# line(text)	- emited when process outputs full line
		b"line"			: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
		# exit(code)	- emited when process exits
		b"exit"			: (GObject.SIGNAL_RUN_FIRST, None, (int,)),
		# failed(exception) - emited if process fails to start
		b"failed"		: (GObject.SIGNAL_RUN_FIRST, None, (object,)),
	}
	SCROLLBACK_SIZE = 500	# Maximum number of output lines stored in memory
	PRIORITY_LOWEST		= 19
	PRIORITY_LOW		= 10
	PRIORITY_NORMAL		= 0
	PRIORITY_HIGH		= -10
	PRIORITY_HIGHEST	= -20
	
	def __init__(self, commandline, priority=PRIORITY_NORMAL):
		""" commandline should be list of arguments """
		GObject.GObject.__init__(self)
		self.commandline = commandline
		self.priority = priority
		self._proc = None
	
	def start(self):
		os.environ["STNORESTART"] = "1"	# see syncthing --help
		os.environ["STNOUPGRADE"] = "1"	# hopefully implemented later
		try:
			self._cancel = Gio.Cancellable()
			if IS_WINDOWS:
				# Windows
				sinfo = STARTUPINFO()
				sinfo.dwFlags = STARTF_USESHOWWINDOW
				sinfo.wShowWindow = 0
				cflags = nice_to_priority_class(self.priority)
				self._proc = Popen(self.commandline,
							stdin=PIPE, stdout=PIPE, stderr=PIPE,
							startupinfo=sinfo, creationflags=cflags)
				self._stdout = WinPopenReader(self._proc)
				self._check = GLib.timeout_add_seconds(1, self._cb_check_alive)
			elif HAS_SUBPROCESS:
				# New Gio
				flags = Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
				self._proc = Gio.Subprocess.new(self.commandline, flags)
				self._proc.wait_check_async(None, self._cb_finished)
				self._stdout = self._proc.get_stdout_pipe()
			else:
				# Gio < 3.12 - Gio.Subprocess is missing :(
				self._proc = Popen(self.commandline, stdout=PIPE)
				self._stdout = Gio.UnixInputStream.new(self._proc.stdout.fileno(), False)
				self._check = GLib.timeout_add_seconds(1, self._cb_check_alive)
		except Exception, e:
			# Startup failed
			self.emit("failed", e)
			return
		self._lines = deque([], DaemonProcess.SCROLLBACK_SIZE)
		self._buffer = ""
		self._stdout.read_bytes_async(256, 0, self._cancel, self._cb_read, ())
	
	def _cb_read(self, proc, results, *a):
		""" Handler for read_bytes_async """
		try:
			response = proc.read_bytes_finish(results)
		except Exception, e:
			if not self._cancel.is_cancelled():
				log.exception(e)
				GLib.idle_add(self._stdout.read_bytes_async, 256, 1, None, self._cb_read)
			return
		response = response.get_data().decode('utf-8')
		self._buffer = "%s%s" % (self._buffer, response)
		while "\n" in self._buffer:
			line, self._buffer = self._buffer.split("\n", 1)
			self._lines.append(line)
			self.emit('line', line)
		if not self._cancel.is_cancelled():
			GLib.idle_add(self._stdout.read_bytes_async, 256, 1, None, self._cb_read, ())
	
	def _cb_check_alive(self, *a):
		"""
		Repeatedly check if process is still alive.
		Called only on windows
		"""
		self._proc.poll()
		if self._proc.returncode is None:
			# Repeat until finished or canceled
			return (not self._cancel.is_cancelled())
		# Child just died :)
		self.emit('exit', self._proc.returncode)
		self._cancel.cancel()
		if IS_WINDOWS: self._stdout.close()
		return False
	
	def _cb_finished(self, proc, results):
		"""
		Callback for wait_check_async.
		With Gio < 3.12, timer and _cb_check_alive is used.
		"""
		try:
			r = proc.wait_check_finish(results)
			log.info("Subprocess finished with code %s", proc.get_exit_status())
		except GLib.GError:
			# Exited with exit code
			log.info("Subprocess exited with code %s", proc.get_exit_status())
		self.emit('exit', proc.get_exit_status())
		if IS_WINDOWS: self._stdout.close()
		self._cancel.cancel()
	
	def terminate(self):
		""" Terminates process (sends SIGTERM) """
		if not self._proc is None:
			if IS_WINDOWS:
				# Windows
				self._proc.terminate()
			elif HAS_SUBPROCESS:
				# Gio.Subprocess
				self._proc.send_signal(15)
			else:
				# subprocess.Popen
				self._proc.terminate()
			self._proc = None
			if IS_WINDOWS: self._stdout.close()
			self._cancel.cancel()
	
	def kill(self):
		""" Kills process (sends SIGTERM) """
		if not self._proc is None:
			if IS_WINDOWS:
				# Windows - can't actually kill
				self._proc.terminate()
			elif HAS_SUBPROCESS:
				# Gio.Subprocess
				self._proc.force_exit()
			else:
				# subprocess.Popen
				self._proc.kill()
			self._proc = None
			if IS_WINDOWS: self._stdout.close()
			self._cancel.cancel()
	
	def get_output(self):
		""" Returns process output as iterable list of lines """
		return self._lines
	
	def get_commandline(self):
		""" Returns commandline used to start process """
		return self.commandline
