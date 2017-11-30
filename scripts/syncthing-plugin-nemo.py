#!/usr/bin/env python2
"""
Nemo plugin for Syncthing-GTK
See syncthing_gtk/nautilusplugin.py for more info
"""

from gi.repository import Nemo
from syncthing_gtk.nautilusplugin import NautiluslikeExtension

NautiluslikeExtension.set_plugin_module(Nemo)

class SyncthingNemu(NautiluslikeExtension, Nemo.InfoProvider, Nemo.MenuProvider):
	pass
