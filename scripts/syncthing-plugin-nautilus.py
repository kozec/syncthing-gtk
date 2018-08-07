#/usr/bin/env python3
"""
Nautilus plugin for Syncthing-GTK
See syncthing_gtk/nautilusplugin.py for more info
"""

from gi.repository import Nautilus
from syncthing_gtk.nautilusplugin import NautiluslikeExtension

NautiluslikeExtension.set_plugin_module(Nautilus)

class SyncthingNautilus(NautiluslikeExtension, Nautilus.InfoProvider, Nautilus.MenuProvider):
	pass
