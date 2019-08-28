#!/usr/bin/env python3
"""
Syncthing-GTK - Windows related stuff.
"""


from syncthing_gtk.tools import get_config_dir
from gi.repository import GLib, Gtk, Gdk
import os, sys, logging, codecs, msvcrt, win32pipe, win32api, winreg
import win32process
from win32com.shell import shell, shellcon
log = logging.getLogger("windows.py")

SM_SHUTTINGDOWN = 0x2000

def fix_localized_system_error_messages():
    """
    Python has trouble decoding messages like
    'S?bor, ktor? u? existuje, sa ned? vytvori:'
    as they are encoded in some crazy, Windows-specific, locale-specific,
    day-in-week-specific encoding.

    This simply eats exceptions caused by 'ascii' codec and replaces
    non-decodable characters by question mark.
    """

    def handle_error(error):
        return ('?', error.end)

    codecs.register_error("strict", handle_error)

def enable_localization():
    """
    Updates environment variables with windows locale.
    """
    loc = "en"
    try:
        import locale
        loc = locale.getdefaultlocale()[0]
    except Exception:
        pass
    if not 'LANGUAGE' in os.environ:
        os.environ['LANGUAGE'] = loc

def is_shutting_down():
    """ Returns True if Windows initiated shutdown process """
    return (win32api.GetSystemMetrics(SM_SHUTTINGDOWN) != 0)

def nice_to_priority_class(nice):
    """ Converts nice value to windows priority class """
    if nice <= -20: # PRIORITY_HIGHEST
        return win32process.HIGH_PRIORITY_CLASS,
    if nice <= -10: # PRIORITY_HIGH
        return win32process.ABOVE_NORMAL_PRIORITY_CLASS
    if nice >= 10:  # PRIORITY_LOW
        return win32process.BELOW_NORMAL_PRIORITY_CLASS
    if nice >= 19:  # PRIORITY_LOWEST
        return win32process.IDLE_PRIORITY_CLASS
    # PRIORITY_NORMAL
    return win32process.NORMAL_PRIORITY_CLASS

def override_menu_borders():
    """ Loads custom CSS to create borders around popup menus """
    style_provider = Gtk.CssProvider()
    style_provider.load_from_data(b"""
        .menu {
            border-image: linear-gradient(to top,
                                          alpha(@borders, 0.80),
                                          alpha(@borders, 0.60) 33%,
                                          alpha(@borders, 0.50) 66%,
                                          alpha(@borders, 0.15)) 2 2 2 2/ 2px 2px 2px 2px;
        }

        .menubar .menu {
            border-image: linear-gradient(to top,
                                          alpha(@borders, 0.80),
                                          alpha(@borders, 0.60) 33%,
                                          alpha(@borders, 0.50) 66%,
                                          transparent 99%) 2 2 2 2/ 2px 2px 2px 2px;
        }
        """)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        style_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

def get_unicode_home():
    return shell.SHGetFolderPath(0, shellcon.CSIDL_LOCAL_APPDATA, None, 0)

class WinPopenReader:
    """
    Reads from PIPE using GLib timers or idle_add. Emulates part of
    UnixInputStream, but its in no way even close to complete
    emulation.

    This is only way that I found so far to have pipe and hidden
    console window on Windows.
    """

    def __init__(self, pipe):
        # Prepare stuff
        self._pipe = pipe
        self._waits_for_read = None
        self._buffer = ""
        self._buffer_size = 32
        self._closed = False
        self._osfhandle = msvcrt.get_osfhandle(self._pipe.fileno())
        # Start reading
        GLib.idle_add(self._peek)

    def _peek(self):
        if self._closed:
            return False
        # Check if there is anything to read and read if available
        (read, nAvail, nMessage) = win32pipe.PeekNamedPipe(self._osfhandle, 0)
        if nAvail >= self._buffer_size:
            data = self._pipe.read(self._buffer_size)
            self._buffer += data
        # If there is read_async callback and buffer has some data,
        # send them right away
        if not self._waits_for_read is None and len(self._buffer) > 0:
            r = WinPopenReader.Results(self._buffer)
            self._buffer = ""
            callback, data = self._waits_for_read
            self._waits_for_read = None
            callback(self, r, *data)
            GLib.idle_add(self._peek)
            return False
        GLib.timeout_add_seconds(1, self._peek)
        return False

    def read_bytes_async(self, size, trash, cancel, callback, data=()):
        if self._waits_for_read != None:
            raise Exception("Already reading")
        self._buffer_size = size
        self._waits_for_read = (callback, data)

    def read_bytes_finish(self, results):
        return results

    def close(self):
        self._closed = True

    class Results:
        """ Also serves as response object """
        def __init__(self, data):
            self._data = data

        def get_data(self):
            return self._data

def WinConfiguration():
    from syncthing_gtk.configuration import _Configuration
    from syncthing_gtk.configuration import serializer
    class _WinConfiguration(_Configuration):
        """
        Configuration implementation for Windows - stores values
        in registry
        """

        #@ Overrides
        def load(self):
            self.values = {}
            r = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\SyncthingGTK")
            for key in _Configuration.REQUIRED_KEYS:
                tp, trash = _Configuration.REQUIRED_KEYS[key]
                try:
                    self.values[key] = self._read(r, key, tp)
                except WindowsError:
                    # Not found
                    pass
            winreg.CloseKey(r)

        #@ Overrides
        def save(self):
            r = winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\SyncthingGTK")
            for key in _Configuration.REQUIRED_KEYS:
                tp, trash = _Configuration.REQUIRED_KEYS[key]
                value = self.values[key]
                self._store(r, key, tp, value)
            winreg.CloseKey(r)

        def _store(self, r, name, tp, value):
            """ Stores value in registry, handling special types """
            if tp in (str, str):
                winreg.SetValueEx(r, name, 0, winreg.REG_SZ, str(value))
            elif tp in (int, bool):
                value = int(value)
                if value > 0xFFFF:
                    raise ValueError("Overflow")
                if value < 0:
                    # This basicaly prevents storing anything >0xFFFF to registry.
                    # Luckily, that shouldn't be needed, largest thing stored as int is 20
                    value = 0xFFFF + (-value)
                winreg.SetValueEx(r, name, 0, winreg.REG_DWORD, int(value))
            elif tp in (list, tuple):
                if not value is None:   # None is default value for window_position
                    winreg.SetValueEx(r, "%s_size" % (name,), 0, winreg.REG_DWORD, len(value))
                    for i in range(0, len(value)):
                        self._store(r, "%s_%s" % (name, i), type(value[i]), value[i])
            else:
                winreg.SetValueEx(r, name, 0, winreg.REG_SZ, serializer(value))

        def _read(self, r, name, tp):
            """ Reads value from registry, handling special types """
            if tp in (list, tuple):
                size, trash = winreg.QueryValueEx(r, "%s_size" % (name,))
                value = []
                for i in range(0, size):
                    value.append(self._read(r, "%s_%s" % (name, i), None))
                return value
            else:
                value, keytype = winreg.QueryValueEx(r, name)
                if type(value) == int and value > 0xFFFF:
                    value = - (value - 0xFFFF)
                return value

    return _WinConfiguration()
