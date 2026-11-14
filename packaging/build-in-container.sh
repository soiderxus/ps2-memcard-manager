#!/bin/sh
# Runs INSIDE the Ubuntu 22.04 container started by ../build-appimage.sh.
# Don't run it directly on your machine.
#
# Two steps:
#  1. appimage-builder collects the app and its dependencies into AppDir/.
#  2. appimagetool packs AppDir/ into the AppImage, using the current
#     static AppImage runtime.  Unlike the older runtime appimage-builder
#     ships, it doesn't need libfuse2 on the user's system, which recent
#     Ubuntu, Linux Mint, Pop!_OS, etc. no longer install by default.
set -e
export DEBIAN_FRONTEND=noninteractive

echo ">>> Installing build tools..."
apt-get update -qq
apt-get install -y -qq python3-pip squashfs-tools desktop-file-utils fakeroot \
	file gpg wget zsync patchelf libgdk-pixbuf2.0-dev \
	gtk-update-icon-cache libglib2.0-bin >/dev/null
# appimage-builder 1.1 breaks with packaging >= 22 (it can't parse Debian
# version strings anymore), so pin the last compatible release.
pip3 install -q appimage-builder "packaging<22"

echo ">>> Collecting the app and its dependencies (this takes a few minutes)..."
appimage-builder --recipe packaging/AppImageBuilder.yml --skip-test --skip-appimage

echo ">>> Packing the AppImage with appimagetool..."
TOOLS=$(mktemp -d)
wget -q -O "$TOOLS/appimagetool" \
	https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x "$TOOLS/appimagetool"
VERSION=$(sed -n 's/^ *version: *\([^ ]*\).*/\1/p' packaging/AppImageBuilder.yml | sed -n 2p)
# The container has no FUSE: run appimagetool without mounting it.
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 \
	"$TOOLS/appimagetool" --no-appstream AppDir "mymc-${VERSION}-x86_64.AppImage"

rm -rf AppDir appimage-build "$TOOLS"
