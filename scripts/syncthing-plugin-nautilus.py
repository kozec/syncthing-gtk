#!/usr/bin/env python2
"""
Nautilus plugin for Syncthing-GTK
See syncthing_gtk/nautilusplugin.py for more info
"""

from gi.repository import Nautilus
from syncthing_gtk import nautilusplugin

NautilusExtensionCls = nautilusplugin.build_class(Nautilus)
