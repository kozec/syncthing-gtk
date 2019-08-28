#!/bin/bash
export PATH=${APPDIR}:${APPDIR}/usr/bin:$PATH
export LD_LIBRARY_PATH=${APPDIR}/usr/lib:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=${APPDIR}/usr/lib64:$LD_LIBRARY_PATH
export GI_TYPELIB_PATH=${APPDIR}/usr/lib/girepository-1.0
export PYTHONPATH=${APPDIR}/usr/lib/python3.7/site-packages:$PYTHONPATH
export PYTHONPATH=${APPDIR}/usr/lib64/python3.7/site-packages:$PYTHONPATH

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

# Start
if [ "x$1" == "xbash" ] ; then
  cd "${APPDIR}"
  bash
else
  # Check dependencies 1st
  python3 -c "pass" \
    || dependency_check_failed "Please, install python package using"
  python3 -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk' \
    || dependency_check_failed "Syncthing-GTK requires GTK and gobject-introspection packages.\n Please, install GTK3 and gobject-introspection packages using your package manager"
  python3 -c 'import cairo;' \
    || dependency_check_failed "Cairo library is missing.\n Please, install cairo package using your package manager"

  python3 ${APPDIR}/usr/bin/syncthing-gtk $@
fi
