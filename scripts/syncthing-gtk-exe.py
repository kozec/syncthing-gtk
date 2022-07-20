#!/c/Python27/python.exe
# Note: this one is used by Windows
import sys, os, winreg

if __name__ == "__main__":
	portable = False
	
	if "--portable" in sys.argv:
		sys.argv.remove("--portable")
		portable = True
	
	if portable:
		# Running from current directory
		path = "."
		data_path = os.path.join(os.getcwd(), "data")
		config_dir = os.path.join(data_path, "syncthing-gtk")
		if not os.path.exists(config_dir):
			print "creating", config_dir
			os.makedirs(config_dir)
		os.environ["LOCALAPPDATA"] = data_path
		os.environ["APPDATA"] = data_path
		os.environ["XDG_CONFIG_HOME"] = data_path
	else:
		# Running from /program files
		path = "."
		if not os.path.exists("./app.glade"):
			# Usually
			from syncthing_gtk.tools import get_install_path
			path = get_install_path()
			os.chdir(path)
		os.environ["PATH"] = path
	
        import gi, cairo
	gi.require_version('Gtk', '3.0')
	gi.require_version('Rsvg', '2.0')
	
	from syncthing_gtk.tools import init_logging, init_locale
	from syncthing_gtk.windows import (
		enable_localization, fix_localized_system_error_messages,
		override_menu_borders
	)
	from syncthing_gtk.configuration import Configuration
	
	init_logging()
	config = Configuration()
	
	# Force dark theme if reqested
	if config["force_dark_theme"]:
		os.environ["GTK_THEME"] = "Adwaita:dark"
	if config["language"] not in ("", "None", None):
		os.environ["LANGUAGE"] = config["language"]
	
	
	enable_localization()
	init_locale(os.path.join(path, "locale"))
	
	# Tell cx_Freeze that I really need this library
	gi.require_foreign('cairo')
	
	if portable:
		# Enable portable mode
		from syncthing_gtk.tools import make_portable
		make_portable()
	
	# Initialize stuff
	if portable:
		# Override syncthing_binary value in _Configuration class
		from syncthing_gtk.configuration import _Configuration
		_Configuration.WINDOWS_OVERRIDE["syncthing_binary"] = (str, ".\\data\\syncthing.exe")
	
	# Fix various windows-only problems
	fix_localized_system_error_messages()
	override_menu_borders()
	
	from gi.repository import Gtk
	Gtk.IconTheme.get_default().prepend_search_path(os.path.abspath(os.path.join(os.getcwd(), "icons", "32x32", "apps")))
	Gtk.IconTheme.get_default().prepend_search_path(os.path.abspath(os.path.join(os.getcwd(), "icons", "32x32", "status")))
	Gtk.IconTheme.get_default().prepend_search_path(os.path.abspath(os.path.join(os.getcwd(), "icons")))
	
	from syncthing_gtk.app import App
	if portable:
		App("./", "./icons").run(sys.argv)
	else:
		App(path, os.path.join(path, "icons")).run(sys.argv)
	
