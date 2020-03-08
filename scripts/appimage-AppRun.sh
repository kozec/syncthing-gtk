#!/bin/bash
export BUILD_UUID=$(cat ${APPDIR}/build-uuid)

# General
rm -f "/tmp/${BUILD_UUID}-elf-interpreter"
ln -s "${APPDIR}/elf-interpreter" "/tmp/${BUILD_UUID}-elf-interpreter"
export PATH=${APPDIR}:${APPDIR}/usr/bin:$PATH
export LD_LIBRARY_PATH=${APPDIR}/usr/lib
export LD_LIBRARY_PATH=${APPDIR}/lib:$LD_LIBRARY_PATH

# gdk-pixbuf
cat "${APPDIR}/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache" \
	| sed "s|/usr/lib/gdk-pixbuf-2.0|${APPDIR}/usr/lib/gdk-pixbuf-2.0|g" \
	> "/tmp/${BUILD_UUID}-gdk-pixbuf-loaders.cache"
export GI_TYPELIB_PATH=${APPDIR}/usr/lib/girepository-1.0
export GDK_PIXBUF_MODULEDIR=${APPDIR}/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders
export GDK_PIXBUF_MODULE_FILE="/tmp/${BUILD_UUID}-gdk-pixbuf-loaders.cache"

# Python
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$GDK_PIXBUF_MODULEDIR"
export PYTHONPATH=${APPDIR}/usr/lib/python2.7/site-packages
export PYTHONHOME=${APPDIR}/usr/


# Start
if [ "x$1" == "xbash" ] ; then
	cd "${APPDIR}"
	bash
elif [ "x$1" == "xsh" ] ; then
	cd "${APPDIR}"
	bin/busybox sh
else
	python2 ${APPDIR}/usr/bin/syncthing-gtk $@
fi

rm -f "/tmp/${BUILD_UUID}-elf-interpreter" \
	"/tmp/${BUILD_UUID}-gdk-pixbuf-loaders.cache"

