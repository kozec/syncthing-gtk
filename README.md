Syncthing-GTK
=============

GTK3 &amp; Python based GUI and notification area icon for [Syncthing][syncthing]

[![screenshot1](http://i.imgur.com/N36wmBM.png)](http://i.imgur.com/eX250tQ.png) [![screenshot2](http://i.imgur.com/43mmnC7.png)](http://i.imgur.com/RTRgRdC.png) [![screenshot3](http://i.imgur.com/KDBYekd.png)](http://i.imgur.com/OZ4xEeH.jpg)

Supported Syncthing features:
- Everything what WebUI can display
- Adding / editing / deleting nodes
- Adding / editing / deleting repositories
- Restart / shutdown server
- Editing daemon settings

Additional features:
- First run wizard for initial configuration
- Running Syncthing daemon in background
- Half-automatic setup for new nodes and repositories
- Filesystem watching and instant synchronization using inotify
- Nautilus (a.k.a. Files), Nemo and Caja integration
- Desktop notifications

Dependencies:
- python 2.7, GTK 3.8 or newer and [PyGObject](https://live.gnome.org/PyGObject)
- [python-gi-cairo](https://packages.debian.org/jessie/python-gi-cairo) on debian based distros (included in PyGObject elsewhere)
- [python-dateutil](http://labix.org/python-dateutil) (Python 2 version)
- [setuptools](https://pypi.python.org/pypi/setuptools)
- [psmisc](http://psmisc.sourceforge.net) (for the `killall` command)
- [Syncthing][syncthing] v0.11 or newer

Optional Dependencies:
- [pyinotify](https://github.com/seb-m/pyinotify/wiki) for instant synchronization.
- libnotify for desktop notifications.
- nautilus-python, nemo-python or caja-python for filemanager integration

Packages:
- Ubuntu (deb-based distros): in [Web Upd8 PPA](https://launchpad.net/~nilarimogard/+archive/ubuntu/webupd8/) (thanks!) or [DEBs](http://ppa.launchpad.net/nilarimogard/webupd8/ubuntu/pool/main/s/syncthing-gtk/)
- SUSE, Fedora (rpm-based distros): in [OpenSUSE Build Service](http://software.opensuse.org/download.html?project=home%3Akozec&package=syncthing-gtk). You can install [Syncthing Package](http://software.opensuse.org/package/syncthing) first.
- Arch Linux: In [[community] repository](https://www.archlinux.org/packages/community/any/syncthing-gtk/)
- Windows: Get [latest installer from here](https://github.com/kozec/syncthing-gui/releases/latest), or use [the Chocolatey package](https://chocolatey.org/packages/syncthing-gtk).
- Or, in worst case scenario, download [latest tarball](https://github.com/kozec/syncthing-gui/releases/latest), extract it and run syncthing-gtk.py.

Related links:
- http://syncthing.net
- https://forum.syncthing.net/t/syncthing-gtk-gui-for-syncthing-now-with-inotify-support/709
- https://forum.syncthing.net/t/lxle-a-respin-of-lubuntu-now-has-syncthing-included-by-default/1392

[syncthing]: https://syncthing.net
