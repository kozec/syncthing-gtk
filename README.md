syncthing-gui
=============

GTK3 &amp; python based GUI and notification area icon for Syncthing

Supported syncthing features:
- Everything what WebUI can display
- Adding / editing / deleting nodes
- Adding / editing / deleting repositories
- Restart / shutdown server
- Editing daemon settings

Additional features:
- Running Syncthing daemon in background
- Half-automatic setup for new nodes and repositories

Dependencies:  
&nbsp;&nbsp;&nbsp;python 2.7, gtk3, <a href=https://live.gnome.org/PyGObject>PyGObject</a>,
<a href="http://labix.org/python-dateutil">python-dateutil</a> (Python&lt;3.0 version), <a href="http://syncthing.net">syncthing 0.10 or newer</a>

Packages:
- Ubuntu: in <a href="https://launchpad.net/~nilarimogard/+archive/ubuntu/webupd8/">Web Upd8 PPA</a> (thanks!) or <a href="http://ppa.launchpad.net/nilarimogard/webupd8/ubuntu/pool/main/s/syncthing-gtk/">DEBs</a>
- Arch Linux: <a href="https://aur.archlinux.org/packages/syncthing-gtk/">AUR</a>
- Or, in worst case scenario, download <a href="https://github.com/kozec/syncthing-gui/releases/latest">latest tarball</a>, extract it and run syncthing-gtk.py.

Related links:
- http://syncthing.net
- https://discourse.syncthing.net/t/syncthing-gtk-gui-for-syncthing/709
