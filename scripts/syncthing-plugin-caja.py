#!/usr/bin/env python2
"""
Caja plugin for Syncthing-GTK
See syncthing_gtk/nautilusplugin.py for more info
"""

from gi.repository import Caja

# Setting this environment variable will prevent __init__ in
# syncthing_gtk package from loading stuff that depends on GTK3-only
# features. It probably breaks other modules in most horrible ways,
# but they are not going to be used anyway
import os
os.environ["GTK2APP"] = "1"

from syncthing_gtk import nautilusplugin
CajaExtensionCls = nautilusplugin.build_class(Caja)
