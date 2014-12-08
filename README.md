Syncthing-GTK
=============

GTK3 &amp; python based GUI and notification area icon for Syncthing

<a href="http://i.imgur.com/eX250tQ.png"><img src="http://i.imgur.com/N36wmBM.png"></a> &nbsp; <a href="http://i.imgur.com/RTRgRdC.png"><img src="http://i.imgur.com/43mmnC7.png"></a> &nbsp; <a href="http://i.imgur.com/OZ4xEeH.jpg"><img src="http://i.imgur.com/KDBYekd.png"></a>

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
- Desktop notifications

Dependencies:  
- python 2.7, GTK 3.10 or newer and <a href=https://live.gnome.org/PyGObject>PyGObject</a>
- <a href="http://labix.org/python-dateutil">python-dateutil</a> (Python2 version)
- <a href="https://pypi.python.org/pypi/setuptools">setuptools</a>
- <a href="http://syncthing.net">Syncthing</a> 0.10 or newer

Optional Dependencies:  
- <a href="https://github.com/seb-m/pyinotify/wiki">pyinotify</a> for instant synchronization.
- libnotify for desktop notifications.

Packages:
- Ubuntu (deb-based distros): in <a href="https://launchpad.net/~nilarimogard/+archive/ubuntu/webupd8/">Web Upd8 PPA</a> (thanks!) or <a href="http://ppa.launchpad.net/nilarimogard/webupd8/ubuntu/pool/main/s/syncthing-gtk/">DEBs</a>
- SUSE, Fedora (rpm-based distros): in <a href="http://software.opensuse.org/download.html?project=home%3Akozec&package=syncthing-gtk">OpenSUSE Build Service</a>. You can install <a href="http://software.opensuse.org/package/syncthing">Syncthing Package</a> first.
- Arch Linux: In <a href="https://www.archlinux.org/packages/community/any/syncthing-gtk/">[community] repository</a>
- Windows: Get <a href="https://github.com/kozec/syncthing-gui/releases/latest">latest installer from here</a>, or  use  <a href="https://chocolatey.org/packages/syncthing-gtk">the Chocolatey package</a>.
- Or, in worst case scenario, download <a href="https://github.com/kozec/syncthing-gui/releases/latest">latest tarball</a>, extract it and run syncthing-gtk.py.

Related links:
- http://syncthing.net
- https://discourse.syncthing.net/t/syncthing-gtk-gui-for-syncthing/709
- https://discourse.syncthing.net/t/lxle-a-respin-of-lubuntu-now-has-syncthing-included-by-default/1392
