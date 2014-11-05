#!/c/Python27/python.exe
# Note: this one is used by Windows
import sys, os, gi, cairo, _winreg

if __name__ == "__main__":
	path = "."
	if not os.path.exists("./app.glade"):
		# Usually
		try:
			key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, "Software\\SyncthingGTK")
			path, keytype = _winreg.QueryValueEx(key, "InstallPath")
			path = str(path)
		except WindowsError:
			# This is pretty bad and shouldn't really happen. Just use default path
			# in that case
			path = "C:\\Program Files\\SyncthingGTK"
		pass
	if "-h" in sys.argv or "--help" in sys.argv:
		print "Usage: %s [-h | [-w] [-s]]" % (sys.argv[0],)
		print "  -h   Display this help message and exit"
		print "  -w   Display window / don't start minimized"
		print "  -s   Use classic window header instead of Gtk.HeaderBar"
		print "  -1   Run 'first start wizard' and exit"
		sys.exit(0)
	
	# Tell cx_Freeze that I really need this library
	gi.require_foreign('cairo')
	
	from syncthing_gtk import windows
	windows.fix_localized_system_error_messages()
	
	if "-1" in sys.argv:
		from syncthing_gtk import Wizard
		Wizard(
			path,
			os.path.join(path, "icons"),
			None
			).run([])
	else:
		from syncthing_gtk import App
		App(
			"-w" not in sys.argv,
			"-s" not in sys.argv,
			path,
			os.path.join(path, "icons")
		).run([])
