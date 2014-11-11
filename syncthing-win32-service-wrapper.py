DEBUG = True

from gi.repository import GObject
from syncthing_gtk import DaemonProcess, Configuration
import win32serviceutil, win32service, win32event, servicemanager
import socket, time, logging, sys

class DaemonData:
	def __init__(self):
		self.process = None
		self.stop_requested = False
		self.config = Configuration()
		self.mainloop = GObject.MainLoop()
	
	def cb_daemon_startup_failed(self, *a):
		logging.error("Failed to start syncthing daemon")
	
	def cb_daemon_exit(self, daemon, exit_code):
		if exit_code == 0:
			logging.info("Daemon shat down")
			self.stop_requested = True
		else:
			logging.info("Daemon exited with code %s. Restarting..." % (exit_code,))
			self.start_daemon()
	
	def cb_daemon_line(self, daemon, line):
		logging.info(line)
	
	def start_daemon(self):
		logging.info('Starting daemon...')
		self.process = DaemonProcess([self.config["syncthing_binary"], "-no-browser"])
		self.process.connect('failed', self.cb_daemon_startup_failed)
		self.process.connect('exit', self.cb_daemon_exit)
		if DEBUG:
			self.process.connect('line', self.cb_daemon_line)
		self.process.start()
	
	def stop_daemon(self):
		if not self.process is None:
			logging.info('Killing daemon ...')
			self.process.kill()
			self.process = None
	
	def main(self):
		logging.info('Starting %s ...' % (SyncthingService._svc_name_,))
		self.start_daemon()
		
		# Simulate a main loop
		while True:
			if self.stop_requested:
				logging.info('A stop signal was received: Breaking main loop ...')
				break
			self.mainloop.get_context().iteration(False)
			time.sleep(1)
		self.stop_daemon()
		return
	
	
class SyncthingService (win32serviceutil.ServiceFramework, DaemonData):
	_svc_name_ = "Syncthing-Service"
	_svc_display_name_ = "Syncthing Service"
	
	def __init__(self,args):
		win32serviceutil.ServiceFramework.__init__(self,args)
		DaemonData.__init__(self)
		self.stop_event = win32event.CreateEvent(None,0,0,None)
		socket.setdefaulttimeout(60)

	def SvcStop(self):
		self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
		win32event.SetEvent(self.stop_event)
		logging.info('Stopping service ...')
		self.stop_requested = True

	def SvcDoRun(self):
		servicemanager.LogMsg(
			servicemanager.EVENTLOG_INFORMATION_TYPE,
			servicemanager.PYS_SERVICE_STARTED,
			(self._svc_name_,'')
		)
		self.main()

if DEBUG and not "test" in sys.argv:
	logging.basicConfig(
		filename = 'c:\\Temp\\%s.log' % (SyncthingService._svc_name_,),
		level = logging.DEBUG, 
		format = '[%s] %%(levelname)-7.7s %%(message)s' % (SyncthingService._svc_name_,)
	)
else:
	logging.basicConfig(
		file = sys.stdout,
		level = logging.DEBUG, 
		format = '[%s] %%(levelname)-7.7s %%(message)s' % (SyncthingService._svc_name_,)
	)

if __name__ == '__main__':
	if "test" in sys.argv:
		d = DaemonData().main()
	else:
		win32serviceutil.HandleCommandLine(SyncthingService)
