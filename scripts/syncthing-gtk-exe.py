#!/c/Python27/python.exe
# Note: this one is used by Windows
import sys, os, gi, cairo, _winreg

if __name__ == "__main__":
	path = "."
	if not os.path.exists("./app.glade"):
		# Usually
		from syncthing_gtk.tools import get_install_path
		path = get_install_path()
		os.chdir(path)
	
	# Tell cx_Freeze that I really need this library
	gi.require_foreign('cairo')
	
	from syncthing_gtk.tools import init_logging
	init_logging()
	
	from syncthing_gtk import windows
	windows.fix_localized_system_error_messages()
	windows.dont_use_localization_in_gtk()
	windows.override_menu_borders()
	
	from gi.repository import Gtk
	Gtk.IconTheme.get_default().prepend_search_path(os.path.abspath(os.path.join(os.getcwd(), "icons", "32x32", "apps")))
	Gtk.IconTheme.get_default().prepend_search_path(os.path.abspath(os.path.join(os.getcwd(), "icons")))
	
	from syncthing_gtk import App
	App(path, os.path.join(path, "icons")).run(sys.argv)
