#!/usr/bin/env bash
# Stage a signed pacman repository. Does not upload/publish anything.
# Run only in trusted release infrastructure with an existing GPG signing key.
set -euo pipefail
if [[ $# -ne 3 ]]; then
  echo 'usage: stage-signed-repo.sh NODALIX_OS_VERSION PACKAGES_DIR OUTPUT_PARENT' >&2
  exit 2
fi
root="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
release="$1"
packages="$2"
output="$3"
python3 "$root/scripts/check-policy.py" --release "$release"
: "$NODALIX_PACKAGE_GPG_KEY"
[[ -n "$NODALIX_PACKAGE_GPG_KEY" ]] || { echo 'NODALIX_PACKAGE_GPG_KEY is required' >&2; exit 1; }
for command in gpg repo-add pacman sha256sum; do
  command -v "$command" >/dev/null || { echo "Missing signing tool: $command" >&2; exit 1; }
done

packages="$(cd -- "$packages" && pwd -P)"
(cd "$packages" && sha256sum --check SHA256SUMS)
pkgver="$(sed -n 's/^pkgver=//p' "$root/PKGBUILD")"
pkgrel="$(sed -n 's/^pkgrel=//p' "$root/PKGBUILD")"
version="$pkgver-$pkgrel"
kernel="$packages/linux-nodalix-$version-x86_64.pkg.tar.zst"
headers="$packages/linux-nodalix-headers-$version-x86_64.pkg.tar.zst"
for package in "$kernel" "$headers"; do
  [[ -f "$package" && ! -L "$package" && -s "$package" ]] || { echo "Missing package: $package" >&2; exit 1; }
  read -r installed_name installed_version < <(pacman -Qp -- "$package")
  [[ "$installed_version" = "$version" ]] || exit 1
done
[[ "$(pacman -Qp -- "$kernel" | awk '{print $1}')" = linux-nodalix ]]
[[ "$(pacman -Qp -- "$headers" | awk '{print $1}')" = linux-nodalix-headers ]]

gpg --batch --list-secret-keys -- "$NODALIX_PACKAGE_GPG_KEY" >/dev/null
mkdir -p -- "$output"
output="$(cd -- "$output" && pwd -P)"
target="$output/nodalix-os-$release"
[[ ! -e "$target" ]] || { echo "Signed release already exists; do not overwrite it." >&2; exit 1; }
stage="$(mktemp -d "$output/.linux-nodalix-stage.XXXXXXXX")"
trap 'rm -r -- "$stage"' EXIT
cp -- "$kernel" "$headers" "$stage/"
cd "$stage"
for file in *.pkg.tar.zst; do
  gpg --batch --yes --local-user "$NODALIX_PACKAGE_GPG_KEY" \
    --detach-sign --output "$file.sig" "$file"
  gpg --batch --verify "$file.sig" "$file"
done
repo-add --sign --key "$NODALIX_PACKAGE_GPG_KEY" nodalix-kernel.db.tar.gz ./*.pkg.tar.zst
gpg --batch --verify nodalix-kernel.db.tar.gz.sig nodalix-kernel.db.tar.gz
sha256sum -- *pkg.tar.zst > SHA256SUMS
mv -- "$stage" "$target"
trap - EXIT
echo "Signed repository staged at $target (not published)."
