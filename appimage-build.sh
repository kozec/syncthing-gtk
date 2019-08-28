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

function setup_dep() {
  NAME="$1"
  mkdir -p /tmp/${NAME}
  pushd /tmp/${NAME}
  tar --extract --strip-components=1 -f /tmp/${NAME}.tar.gz
  python2 setup.py build
  PYTHONPATH=${BUILD_APPDIR}/usr/lib/python2.7/site-packages python2 \
    setup.py install --optimize=1 \
    --prefix="/usr/" \
    --root="${BUILD_APPDIR}"
  popd
}

function build_dep() {
  NAME="$1"
  CONFIGURE="$2"
  if [ -e ${NAME}.prebuilt.tar.gz ] ; then
    cp ${NAME}.prebuilt.tar.gz /tmp/${NAME}.prebuilt.tar.gz
    unpack_dep "$NAME.prebuilt"
    return $?
  fi
  mkdir -p /tmp/${NAME}
  pushd /tmp/${NAME}
  tar --keep-newer-files --extract --strip-components=1 -f /tmp/${NAME}.tar.gz
  [ $# -gt 2 ] && $3
  ./configure $(echo $CONFIGURE)
  make
  make DESTDIR="${BUILD_APPDIR}" install
  popd
}

function unpack_dep() {
  NAME="$1"
  pushd ${BUILD_APPDIR}
  tar --extract --exclude="usr/include**" --exclude="usr/lib/pkgconfig**" \
      --exclude="usr/lib/python3.6**" -f /tmp/${NAME}.tar.gz
  popd
}

function unpack_gi() {
  NAME="$1"
  pushd ${BUILD_APPDIR}
  tar --extract --wildcards "usr/lib/girepository-1.0/*" -f /tmp/${NAME}.tar.gz
  popd
}

set -exu    # display commands, no empty vars, terminate on 1st failure

# Download deps
download_dep "python-dateutil-1.5" "http://labix.org/download/python-dateutil/python-dateutil-1.5.tar.gz"
download_dep "six-1.11.0" "https://pypi.python.org/packages/16/d8/bc6316cf98419719bd59c91742194c111b6f2e85abac88e496adefaf7afe/six-1.11.0.tar.gz"
download_dep "python-bcrypt-3.1.7" "https://archive.archlinux.org/packages/p/python2-bcrypt/python2-bcrypt-3.1.7-1-x86_64.pkg.tar.xz"
download_dep "python-cairo-1.18.1" "https://archive.archlinux.org/packages/p/python2-cairo/python2-cairo-1.18.1-1-x86_64.pkg.tar.xz"
download_dep "python-cffi-1.12.3" "https://archive.archlinux.org/packages/p/python2-cffi/python2-cffi-1.12.3-1-x86_64.pkg.tar.xz"
download_dep "python-gobject-3.32.2" "https://archive.archlinux.org/packages/p/python2-gobject/python2-gobject-3.32.2-1-x86_64.pkg.tar.xz"
download_dep "gir-1.60.2" "https://archive.archlinux.org/packages/g/gobject-introspection-runtime/gobject-introspection-runtime-1.60.2-1-x86_64.pkg.tar.xz"
download_dep "gtk-3.24.7" "https://archive.archlinux.org/packages/g/gtk3/gtk3-3.24.7-1-x86_64.pkg.tar.xz"
download_dep "atk-2.32" "https://archive.archlinux.org/packages/a/atk/atk-2.32-1-x86_64.pkg.tar.xz"
download_dep "glib-2.60.6" "https://archive.archlinux.org/packages/g/glib2/glib2-2.60.6-1-x86_64.pkg.tar.xz"
download_dep "pango-1.44.3" "https://archive.archlinux.org/packages/p/pango/pango-1%3A1.44.3-1-x86_64.pkg.tar.xz"
download_dep "gdk-pixbuf-2.36.9" "http://ftp.gnome.org/pub/gnome/sources/gdk-pixbuf/2.36/gdk-pixbuf-2.36.9.tar.xz"
download_dep "libxml2-2.9.9" "https://archive.archlinux.org/packages/l/libxml2/libxml2-2.9.9-2-x86_64.pkg.tar.xz"
download_dep "librsvg-2.42.2" "http://ftp.gnome.org/pub/gnome/sources/librsvg/2.42/librsvg-2.42.2.tar.xz"
download_dep "libpng-1.6.37" "https://archive.archlinux.org/packages/l/libpng/libpng-1.6.37-1-x86_64.pkg.tar.xz"
download_dep "libepoxy-1.5.3" "https://archive.archlinux.org/packages/l/libepoxy/libepoxy-1.5.3-1-x86_64.pkg.tar.xz"
download_dep "libnotify-0.7.8" "https://archive.archlinux.org/packages/l/libnotify/libnotify-0.7.8-1-x86_64.pkg.tar.xz"
download_dep "libxrandr-1.5.2" "https://archive.archlinux.org/packages/l/libxrandr/libxrandr-1.5.2-1-x86_64.pkg.tar.xz"
download_dep "icu-60.2" "https://ssl.icu-project.org/files/icu4c/60.2/icu4c-60_2-src.tgz"
download_dep "libpcre-8.42" "https://ftp.pcre.org/pub/pcre/pcre-8.42.tar.gz"

# Prepare & build
mkdir -p ${BUILD_APPDIR}/usr/lib/python2.7/site-packages/
setup_dep "python-dateutil-1.5"
setup_dep "six-1.11.0"
unpack_dep "python-bcrypt-3.1.7"
unpack_dep "python-cairo-1.18.1"
unpack_dep "python-cffi-1.12.3"
unpack_dep "python-gobject-3.32.2"

# PYTHON=python2 build_dep "glib-2.56.1" "--disable-selinux --disable-fam --disable-xattr --prefix=/usr"
unpack_dep "glib-2.60.6"
build_dep "icu-60.2" "--prefix=/usr --disable-dyload --enable-rpath --disable-draft --disable-extras --disable-tools --disable-tests --disable-samples" "cd source"
unpack_dep "gtk-3.24.7"
# PYTHON=python2 build_dep "gtk-3.24.5" "--prefix=/usr --disable-rpath --enable-x11-backend --disable-cups --disable-papi --disable-cloudprint --enable-introspection=yes"
build_dep "librsvg-2.42.2" "--prefix=/usr --disable-rpath --disable-static --enable-introspection=yes --disable-tools"
build_dep "libpcre-8.42" "--prefix=/usr --disable-rpath --disable-cpp --disable-static"
build_dep "gdk-pixbuf-2.36.9" "--prefix=/usr --disable-rpath --disable-static --enable-introspection=yes --without-libtiff --with-x11 --with-included-loaders=png,jpeg"
unpack_dep "gir-1.60.2"
unpack_dep "atk-2.32"
unpack_gi "pango-1.44.3"
unpack_dep "libxml2-2.9.9"
unpack_dep "libpng-1.6.37"
unpack_dep "libepoxy-1.5.3"
unpack_dep "libnotify-0.7.8"
unpack_dep "libxrandr-1.5.2"

# Cleanup
rm -R ${BUILD_APPDIR}/usr/bin
rm -R ${BUILD_APPDIR}/usr/include || true
for x in aclocal gtk-doc gdb gettext libalpm doc man vala locale bash-completion ; do
  rm -R ${BUILD_APPDIR}/usr/share/$x || true
done


python2 setup.py build
python2 setup.py install --prefix ${BUILD_APPDIR}/usr

# Move & patch desktop file
mv ${BUILD_APPDIR}/usr/share/applications/${APP}.desktop ${BUILD_APPDIR}/
sed -i "s/Icon=.*/Icon=${APP}/g" ${BUILD_APPDIR}/${APP}.desktop

# Copy icon
cp -H icons/${APP}.png ${BUILD_APPDIR}/${APP}.png
[ -e "${BUILD_APPDIR}/usr/share/${APP}/icons/${APP}.png" ] || ln -s "../../../../${APP}.png" "${BUILD_APPDIR}/usr/share/${APP}/icons/${APP}.png"

# Copy AppRun script
cp scripts/appimage-AppRun.sh ${BUILD_APPDIR}/AppRun
chmod +x ${BUILD_APPDIR}/AppRun

echo "Run appimagetool -n ${BUILD_APPDIR} to finish prepared appimage"
