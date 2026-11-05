#!/usr/bin/env bash
# Produce BOTH linux-nodalix and matching headers in an isolated build directory.
# This script is for the Nodalix CI/build server, not end-user installation.
set -euo pipefail

root="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
if [[ $# -lt 1 ]]; then
  echo 'usage: build.sh NODALIX_OS_RELEASE [OUTPUT_DIRECTORY]' >&2
  exit 2
fi
release="$1"
out="$root/dist/packages"
if [[ $# -ge 2 ]]; then out="$2"; fi

python3 "$root/scripts/check-policy.py" --release "$release"
command -v makepkg >/dev/null || { echo 'makepkg is required in the Arch build environment' >&2; exit 1; }
command -v pacman >/dev/null || { echo 'pacman is required to inspect built packages' >&2; exit 1; }

install -d -- "$out"
out="$(cd -- "$out" && pwd -P)"
work="$(mktemp -d /tmp/linux-nodalix-build.XXXXXXXX)"
trap 'rm -r -- "$work"' EXIT

install -m644 "$root/PKGBUILD" "$work/PKGBUILD"
install -m644 "$root/preserve-ble-identity.patch" "$work/preserve-ble-identity.patch"

cd -- "$work"
makepkg --cleanbuild --noconfirm

kernel="$(find "$work" -maxdepth 1 -type f -name 'linux-nodalix-[0-9]*.pkg.tar.zst' | head -n 1)"
headers="$(find "$work" -maxdepth 1 -type f -name 'linux-nodalix-headers-[0-9]*.pkg.tar.zst' | head -n 1)"
[[ -n "$kernel" && -n "$headers" && -s "$kernel" && -s "$headers" ]] || {
  echo "The kernel and matching headers were not both built" >&2
  exit 1
}

pkgver="$(sed -n 's/^pkgver=//p' "$root/PKGBUILD")"
pkgrel="$(sed -n 's/^pkgrel=//p' "$root/PKGBUILD")"
for package in "$kernel" "$headers"; do
  [[ -f "$package" && ! -L "$package" ]] || exit 1
  read -r name version < <(pacman -Qp -- "$package")
  [[ "$version" = "$pkgver-$pkgrel" ]] || {
    echo "Wrong package version: $name $version" >&2
    exit 1
  }
done

[[ "$(pacman -Qp -- "$kernel" | awk '{print $1}')" = linux-nodalix ]]
[[ "$(pacman -Qp -- "$headers" | awk '{print $1}')" = linux-nodalix-headers ]]

cp -- "$kernel" "$headers" "$out/"
(
  cd "$out"
  sha256sum -- "$(basename "$kernel")" "$(basename "$headers")" > SHA256SUMS
  sha256sum --check SHA256SUMS
)
printf 'Kernel and headers built for Nodalix OS %s in %s\n' "$release" "$out"
