#!/usr/bin/env python2
"""
Nautilus plugin for Syncthing-GTK
See syncthing_gtk/nautilusplugin.py for more info
"""

from gi.repository import Nautilus
from syncthing_gtk.nautilusplugin import build_class

NautilusExtensionCls = build_class(Nautilus)
