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
	PYTHONPATH=${BUILD_APPDIR}/usr/lib/python2.7/site-packages python2 setup.py install --prefix ${BUILD_APPDIR}/usr --optimize=1
	popd
}

function unpack_dep() {
	NAME="$1"
	pushd ${BUILD_APPDIR}
	tar --extract --exclude="usr/include**" --exclude="usr/lib/pkgconfig**" \
			--exclude="usr/lib/python3.6**" -f /tmp/${NAME}.tar.gz
	popd
}

set -exu		# display commands, no empty vars, terminate on 1st failure

# Download deps
download_dep "python-pyinotify-0.9.6" "https://github.com/seb-m/pyinotify/archive/0.9.6.tar.gz"
download_dep "python-bcrypt-2.0.0" "https://pypi.python.org/packages/11/7d/4c7980d04314466de42ea804db71995c9b3a2a47dc79a63c51f1be0cfd50/bcrypt-2.0.0.tar.gz"
download_dep "python-dateutil-1.5" "http://labix.org/download/python-dateutil/python-dateutil-1.5.tar.gz"
download_dep "six-1.11.0" "https://pypi.python.org/packages/16/d8/bc6316cf98419719bd59c91742194c111b6f2e85abac88e496adefaf7afe/six-1.11.0.tar.gz"
download_dep "cffi-1.11.4" "https://pypi.python.org/packages/10/f7/3b302ff34045f25065091d40e074479d6893882faef135c96f181a57ed06/cffi-1.11.4.tar.gz"
download_dep "PyGObject-3.26.1" "https://github.com/GNOME/pygobject/archive/3.26.1.tar.gz"
download_dep "pycairo-1.16.3" "https://github.com/pygobject/pycairo/releases/download/v1.16.3/pycairo-1.16.3.tar.gz"
download_dep "libxml2-2.9.7" "https://archive.archlinux.org/packages/l/libxml2/libxml2-2.9.7%2B4%2Bg72182550-2-x86_64.pkg.tar.xz"
download_dep "librsvg-2.42.2" "https://archive.archlinux.org/packages/l/librsvg/librsvg-2%3A2.42.2-1-x86_64.pkg.tar.xz"
download_dep "icu-60.2" "https://archive.archlinux.org/packages/i/icu/icu-60.2-1-x86_64.pkg.tar.xz"


# Prepare & build
mkdir -p ${BUILD_APPDIR}/usr/lib/python2.7/site-packages/
build_dep "python-pyinotify-0.9.6"
build_dep "python-bcrypt-2.0.0"
build_dep "python-dateutil-1.5"
build_dep "six-1.11.0"
build_dep "cffi-1.11.4"
build_dep "PyGObject-3.26.1"
build_dep "pycairo-1.16.3"
unpack_dep "libxml2-2.9.7"
unpack_dep "librsvg-2.42.2"
unpack_dep "icu-60.2"

# Cleanup
rm -R ${BUILD_APPDIR}/usr/bin
rm -R ${BUILD_APPDIR}/usr/include
rm -R ${BUILD_APPDIR}/usr/share/gtk-doc
rm -R ${BUILD_APPDIR}/usr/share/doc
rm -R ${BUILD_APPDIR}/usr/share/man
rm -R ${BUILD_APPDIR}/usr/share/vala

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

echo "Run appimagetool -n ${BUILD_APPDIR} to finish prepared appimage"
