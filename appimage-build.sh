#!/bin/bash
APP="syncthing-gtk"
EXEC="syncthing-gtk"
[ x"$BUILD_APPDIR" == "x" ] && BUILD_APPDIR=$(pwd)/appimage

function download_dep() {
	NAME=$1
	URL=$2
	if [ -e ../../${NAME}.obstargz ] ; then
		# Special case for OBS
		cp ../../${NAME}.obstargz /tmp/${NAME}.tar.gz
	elif [ -e ${NAME}.tar.gz ] ; then
		cp ${NAME}.tar.gz /tmp/${NAME}.tar.gz
	else
		wget -c "${URL}" -O /tmp/${NAME}.tar.gz
	fi
}

function build_dep() {
	NAME="$1"
	mkdir -p /tmp/${NAME}
	pushd /tmp/${NAME}
	tar --extract --strip-components=1 -f /tmp/${NAME}.tar.gz
	python2 setup.py build
	PYTHONPATH=${BUILD_APPDIR}/usr/lib/python2.7/site-packages python2 setup.py install --prefix ${BUILD_APPDIR}/usr
	popd
}

set -ex		# display commands, terminate after 1st failure

# Download deps
download_dep "python-pyinotify-0.9.6" "https://github.com/seb-m/pyinotify/archive/0.9.6.tar.gz"
download_dep "python-bcrypt-2.0.0" "https://pypi.python.org/packages/11/7d/4c7980d04314466de42ea804db71995c9b3a2a47dc79a63c51f1be0cfd50/bcrypt-2.0.0.tar.gz"
download_dep "python-dateutil-1.5" "http://labix.org/download/python-dateutil/python-dateutil-1.5.tar.gz"

# Prepare & build
mkdir -p ${BUILD_APPDIR}/usr/lib/python2.7/site-packages/
build_dep "python-pyinotify-0.9.6"
build_dep "python-bcrypt-2.0.0"
build_dep "python-dateutil-1.5"

python2 setup.py build
python2 setup.py install --prefix ${BUILD_APPDIR}/usr

# Move & patch desktop file
mv ${BUILD_APPDIR}/usr/share/applications/${APP}.desktop ${BUILD_APPDIR}/
sed -i "s/Icon=.*/Icon=${APP}/g" ${BUILD_APPDIR}/${APP}.desktop

# Copy icon
cp -H icons/${APP}.png ${BUILD_APPDIR}/${APP}.png

# Copy appdata.xml
mkdir -p ${BUILD_APPDIR}/usr/share/metainfo/
cp scripts/${APP}.appdata.xml ${BUILD_APPDIR}/usr/share/metainfo/${APP}.appdata.xml

# Copy AppRun script
cp scripts/appimage-AppRun.sh ${BUILD_APPDIR}/AppRun
chmod +x ${BUILD_APPDIR}/AppRun

echo "Run appimagetool ${BUILD_APPDIR} to finish prepared appimage"
