#!/bin/sh
# Build the mymc AppImage:  ./build-appimage.sh
#
# The AppImage is built inside an Ubuntu 22.04 container (podman or
# docker) so it runs on most Linux distributions: an AppImage only works
# on systems whose glibc is at least as new as the one it was built on.
set -e
cd "$(dirname "$0")"

if command -v podman >/dev/null 2>&1; then
	ENGINE=podman
elif command -v docker >/dev/null 2>&1; then
	ENGINE=docker
else
	echo "Error: podman or docker is needed to build the AppImage." >&2
	echo "  Fedora:        sudo dnf install podman" >&2
	echo "  Debian/Ubuntu: sudo apt install podman" >&2
	exit 1
fi

rm -f ./*.AppImage ./*.AppImage.zsync
echo ">>> Starting an Ubuntu 22.04 container with $ENGINE..."
"$ENGINE" run --rm -v "$PWD":/work:Z -w /work docker.io/library/ubuntu:22.04 \
	sh packaging/build-in-container.sh

# Files created by docker belong to root: give them back to the user.
if [ "$ENGINE" = docker ]; then
	docker run --rm -v "$PWD":/work -w /work docker.io/library/ubuntu:22.04 \
		chown -R "$(id -u):$(id -g)" /work
fi

APPIMAGE=$(ls -t ./*.AppImage 2>/dev/null | head -n 1)
if [ -z "$APPIMAGE" ]; then
	echo "Error: the build finished but no AppImage was produced." >&2
	exit 1
fi
chmod +x "$APPIMAGE"
SIZE=$(du -h "$APPIMAGE" | cut -f1)

cat <<EOF

========================================================================
  AppImage built successfully: ${APPIMAGE#./}  ($SIZE)

  Try it:
      ./${APPIMAGE#./}
      ./${APPIMAGE#./} /path/to/Mcd001.ps2

  Publish it as a GitHub Release asset:
      https://github.com/soiderxus/ps2-memcard-manager/releases/new

  Please consider submitting your AppImage to appimage.github.io, the
  crowd-sourced central directory of available AppImages, by opening a
  pull request at https://github.com/AppImage/appimage.github.io
========================================================================
EOF
