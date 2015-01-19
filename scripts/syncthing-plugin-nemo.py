#!/usr/bin/env python2
"""
Nemo plugin for Syncthing-GTK
See syncthing_gtk/nautilusplugin.py for more info
"""

from gi.repository import Nemo
from syncthing_gtk import nautilusplugin

NemoExtensionCls = nautilusplugin.build_class(Nemo)
