#!/bin/sh
# Runs INSIDE the Ubuntu 22.04 container started by ../build-appimage.sh.
# Don't run it directly on your machine.
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

echo ">>> Building the AppImage (this takes a few minutes)..."
appimage-builder --recipe packaging/AppImageBuilder.yml --skip-test

rm -rf AppDir appimage-build
