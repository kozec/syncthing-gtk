#!/bin/bash
APP="syncthing-gtk"
EXEC="syncthing-gtk"
[ x"$BUILD_APPDIR" == "x" ] && BUILD_APPDIR=$(pwd)/appimage

set -ex		# display commands, terminate after 1st failure

# Prepare & build
mkdir -p ${BUILD_APPDIR}/usr
python2 setup.py build
python2 setup.py install --prefix ${BUILD_APPDIR}/usr

# Move & patch desktop file
mv ${BUILD_APPDIR}/usr/share/applications/${APP}.desktop ${BUILD_APPDIR}/
sed -i "s/Icon=.*/Icon=${APP}/g" ${BUILD_APPDIR}/${APP}.desktop

# Copy
cp -H icons/${APP}.png ${BUILD_APPDIR}/${APP}.png

# Copy appdata.xml
mkdir -p ${BUILD_APPDIR}/usr/share/metainfo/
cp scripts/${APP}.appdata.xml ${BUILD_APPDIR}/usr/share/metainfo/${APP}.appdata.xml

# Copy AppRun script
cp scripts/appimage-AppRun.sh ${BUILD_APPDIR}/AppRun
chmod +x ${BUILD_APPDIR}/AppRun

echo "Run appimagetool ${BUILD_APPDIR} to finish prepared appimage"
