Syncthing-GTK
=============

GTK3 &amp; Python based GUI and notification area icon for [Syncthing](https://github.com/syncthing/syncthing)

[![screenshot1](http://i.imgur.com/N36wmBM.png)](http://i.imgur.com/eX250tQ.png) [![screenshot2](http://i.imgur.com/43mmnC7.png)](http://i.imgur.com/RTRgRdC.png) [![screenshot3](http://i.imgur.com/KDBYekd.png)](http://i.imgur.com/OZ4xEeH.jpg)

##### Supported Syncthing features
- Everything what WebUI can display
- Adding / editing / deleting nodes
- Adding / editing / deleting repositories
- Restart / shutdown server
- Editing daemon settings

##### Additional features
- First run wizard for initial configuration
- Running Syncthing daemon in background
- Half-automatic setup for new nodes and repositories
- Nautilus (a.k.a. Files), Nemo and Caja integration
- Desktop notifications

##### Like what I'm doing?
[![Help me become filthy rich on Liberapay](https://img.shields.io/badge/Help%20me%20become%20filthy%20rich%20on-Liberapay-yellow.svg)](https://liberapay.com/kozec) <sup>or</sup> [![donate anything with PayPal](https://img.shields.io/badge/donate_anything_with-Paypal-blue.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=77DQD3L9K8RPU&lc=SK&item_name=kozec&item_number=scc&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donate_LG%2egif%3aNonHosted)

##### Packages
- Ubuntu, Debian, deb-based distros: in [OpenSUSE Build Service](http://software.opensuse.org/download.html?project=home%3Akozec&package=syncthing-gtk).
- Arch Linux: In [[community] repository](https://www.archlinux.org/packages/community/any/syncthing-gtk/)
- Fedora: search for `syncthing-gtk` in Software Center
- SUSE (and other rpm-based distros): in [OpenSUSE Build Service](http://software.opensuse.org/download.html?project=home%3Akozec&package=syncthing-gtk).
- Flatpak (distro-agnostic): in [Flathub](https://flathub.org/apps/details/me.kozec.syncthingtk)
- Windows: Get [latest installer from here](https://github.com/kozec/syncthing-gui/releases/latest), or use [the Chocolatey package](https://chocolatey.org/packages/syncthing-gtk).
- Or, in worst case scenario, download [latest tarball](https://github.com/kozec/syncthing-gui/releases/latest), extract it and run syncthing-gtk.py.

##### Dependencies
- python 2.7, GTK 3.8 or newer and [PyGObject](https://live.gnome.org/PyGObject)
- [python-gi-cairo](https://packages.debian.org/sid/python-gi-cairo),
[gir1.2-notify](https://packages.debian.org/sid/gir1.2-notify-0.7) and [gir1.2-rsvg](https://packages.debian.org/sid/gir1.2-rsvg-2.0) on debian based distros (included in PyGObject elsewhere)
- [python-dateutil](http://labix.org/python-dateutil) (Python 2 version)
- [python-bcrypt](https://pypi.python.org/pypi/bcrypt/2.0.0)
- [setuptools](https://pypi.python.org/pypi/setuptools)
- [psmisc](http://psmisc.sourceforge.net) (for the `killall` command)
- [Syncthing](https://github.com/syncthing/syncthing) v0.13 or newer

##### Optional Dependencies
- libnotify for desktop notifications.
- nautilus-python, nemo-python or caja-python for filemanager integration
- [this Gnome Shell extension](https://extensions.gnome.org/extension/615/appindicator-support/), if running Gnome Shell
- [gir1.2-appindicator3](https://packages.debian.org/sid/gir1.2-appindicator3-0.1) (part of [libappindicator](https://launchpad.net/libappindicator)), if running Gnome Shell or Unity

##### Windows Building Dependencies _(you don't need to install these just to **run** Syncthing-GTK)_
- Python for Windows 2.7
- [PyGObject for Windows](http://sourceforge.net/projects/pygobjectwin32/) with GTK3 enabled (tested with version 3.14.0)
- [python-dateutil](http://labix.org/python-dateutil) (Python 2 version)
- [Python for Windows Extensions](http://sourceforge.net/projects/pywin32/)
- [WMI](http://timgolden.me.uk/python/wmi/index.html)
- [NSIS2](http://nsis.sourceforge.net/NSIS_2) with NSISdl, [ZipDLL](http://nsis.sourceforge.net/ZipDLL_plug-in) and [FindProcDLL](http://forums.winamp.com/showpost.php?p=2777729&postcount=8) plugins (optional, for building installer)

##### Related links
- https://syncthing.net
- https://forum.syncthing.net/t/syncthing-gtk-gui-for-syncthing-now-with-inotify-support/709
- https://forum.syncthing.net/t/lxle-a-respin-of-lubuntu-now-has-syncthing-included-by-default/1392
