from gi.repository import GObject
import win32serviceutil
import win32service
import win32event
import win32evtlogutil
import servicemanager
import socket
import time
import logging

class SyncthingService (win32serviceutil.ServiceFramework):
	_svc_name_ = "Syncthing-Service"
	_svc_display_name_ = "Syncthing Service"
	
	def __init__(self,args):
		win32serviceutil.ServiceFramework.__init__(self,args)
		self.stop_event = win32event.CreateEvent(None,0,0,None)
		socket.setdefaulttimeout(60)
		self.stop_requested = False

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

	def main(self):
		logging.info('Starting %s ...' % (SyncthingService._svc_name_,))
		mainloop = GObject.MainLoop()
		# Simulate a main loop
		while True:
			if self.stop_requested:
				logging.info('A stop signal was received: Breaking main loop ...')
				break
			mainloop.get_context().iteration(False)
			logging.info("Hello at %s" % time.ctime())
			time.sleep(1)
		return

logging.basicConfig(
	filename = 'c:\\Temp\\%s.log' % (SyncthingService._svc_name_,),
	level = logging.DEBUG, 
	format = '[%s] %%(levelname)-7.7s %%(message)s' % (SyncthingService._svc_name_,)
)

if __name__ == '__main__':
	# win32serviceutil.HandleCommandLine(SyncthingService)
	
	
