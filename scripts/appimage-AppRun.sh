#!/bin/bash
export PATH=${APPDIR}:${APPDIR}/usr/bin:$PATH
export LD_LIBRARY_PATH=${APPDIR}/usr/lib:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=${APPDIR}/usr/lib64:$LD_LIBRARY_PATH
export PYTHONPATH=${APPDIR}/usr/lib/python2.7/site-packages:$PYTHONPATH
export PYTHONPATH=${APPDIR}/usr/lib64/python2.7/site-packages:$PYTHONPATH
export SCC_SHARED=${APPDIR}/usr/share/scc

function dependency_check_failed() {
	# This checks 4 different ways to open error message in addition to
	# throwing it to screen directly
	echo "$1" >&2
	
	[ -e /usr/bin/zenity ] && run_and_die /usr/bin/zenity --no-wrap --error --text "$1"
	[ -e /usr/bin/yad ] && run_and_die /usr/bin/yad --error --text "$1"
	echo "$1" > /tmp/depcheck.$$.txt
	[ -e /usr/bin/Xdialog ] && run_and_die /usr/bin/Xdialog --textbox /tmp/depcheck.$$.txt 10 100
	[ -e /usr/bin/xdg ] && run_and_die /usr/bin/xdg-open /tmp/depcheck.$$.txt
	exit 1
}

function run_and_die() {
	"$@"
	exit 1
}

# Check dependencies 1st
python2 -c 'import gi' \
	|| dependency_check_failed "Please, install python-gobject package using your package manager"
python2 -c 'import gi; gi.require_version("Gtk", "3.0")' \
	|| dependency_check_failed "Syncthing-GTK requires GTK. Please, install GTK3 package using your package manager"
python2 -c 'import bcrypt' || dependency_check_failed "Please, install python-bcrypt package using your package manager"
python2 -c 'import dateutil' || dependency_check_failed "Please, install python-dateutil package using your package manager"

# Start
python2 ${APPDIR}/usr/bin/syncthing-gtk $@
