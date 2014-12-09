#!/c/Python27/python.exe
# Note: this one is used by Windows
import sys, os, gi, cairo, _winreg

if __name__ == "__main__":
	path = "."
	if not os.path.exists("./app.glade"):
		# Usually
		from syncthing_gtk.tools import get_install_path
		path = get_install_path()
	if "-h" in sys.argv or "--help" in sys.argv:
		print "Usage: %s [options]" % (sys.argv[0],)
		print "  -h   Display this help message and exit"
		print "  -w   Display window (don't start minimized)"
		print "  -s   Use classic window header"
		print "  -v   Be verbose"
		print "  -vv  Be more verbose (debug mode)"
		print "  -1   Run 'first start wizard' and exit"
		print "  -a   Display about dialog and exits"
		sys.exit(0)
	
	# Tell cx_Freeze that I really need this library
	gi.require_foreign('cairo')
	
	from syncthing_gtk.tools import init_logging
	init_logging("-v" in sys.argv, "-vv" in sys.argv)
	
	from syncthing_gtk import windows
	windows.fix_localized_system_error_messages()
	windows.dont_use_localization_in_gtk()
	
	if "-a" in sys.argv:
		from syncthing_gtk import AboutDialog
		AboutDialog(None, path).run([])
	elif "-1" in sys.argv:
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
