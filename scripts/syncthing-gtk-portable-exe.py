#!/c/Python27/python.exe
# Windows, "portable" executable
import sys, os, gi, cairo, _winreg

# Tell cx_Freeze that I really need this library
gi.require_foreign('cairo')

if __name__ == "__main__":
	# Set path based on cwd() and store it in environment
	data_path = os.path.join(os.getcwd(), "data")
	config_dir = os.path.join(data_path, "syncthing-gtk")
	if not os.path.exists(config_dir):
		print "creating", config_dir
		os.makedirs(config_dir)
		print "created", config_dir, os.path.exists(config_dir)
	os.environ["LOCALAPPDATA"] = data_path
	os.environ["APPDATA"] = data_path
	os.environ["XDG_CONFIG_HOME"] = data_path
	
	# Enable portable mode
	from syncthing_gtk.tools import make_portable, get_config_dir
	make_portable()
	
	# Initialize stuff
	from syncthing_gtk.tools import init_logging, IS_WINDOWS
	init_logging()
	
	# Override syncthing_binary value in _Configuration class
	from syncthing_gtk.configuration import _Configuration
	_Configuration.WINDOWS_OVERRIDE["syncthing_binary"] = (str, ".\\data\\syncthing.exe")
	
	# Force dark theme if reqested
	from syncthing_gtk import Configuration
	config = Configuration()
	if config["force_dark_theme"]:
		os.environ["GTK_THEME"] = "Adwaita:dark"
	
	# Force dark theme if reqested
	config = Configuration()
	if config["force_dark_theme"]:
		os.environ["GTK_THEME"] = "Adwaita:dark"
	
	# Fix various windows-only problems
	from syncthing_gtk import windows
	windows.fix_localized_system_error_messages()
	windows.dont_use_localization_in_gtk()
	windows.override_menu_borders()
	
	from gi.repository import Gtk
	Gtk.IconTheme.get_default().prepend_search_path(os.path.abspath(os.path.join(os.getcwd(), "icons", "32x32", "apps")))
	Gtk.IconTheme.get_default().prepend_search_path(os.path.abspath(os.path.join(os.getcwd(), "icons")))
	
	from syncthing_gtk import App
	App("./", "./icons").run(sys.argv)
