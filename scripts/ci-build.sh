#!/usr/bin/env bash
# CI-only build, intentionally never invoked by an end-user updater.
set -euo pipefail
[[ "$NODALIX_CI_CONTAINER" = 1 ]] || { echo 'Disposable CI container required' >&2; exit 1; }
[[ $# = 1 ]] || { echo 'usage: ci-build.sh NODALIX_OS_RELEASE' >&2; exit 2; }

pacman -Syu --needed --noconfirm \
  base-devel bc bison clang cpio flex git libelf lld llvm \
  mkinitcpio openssl pahole patch perl rust rust-bindgen rust-src zstd

useradd -m builder
install -d -o builder -g builder /src/dist/packages
jobs="$(nproc)"
if (( jobs > 4 )); then jobs=4; fi

runuser -u builder -- env MAKEFLAGS="-j$jobs" \
  bash /src/scripts/build.sh "$1" /src/dist/packages

cd /src/dist/packages
sha256sum --check SHA256SUMS

# Inspect the actual binary artifacts, not just a successful build exit code.
kernel="$(find . -maxdepth 1 -type f -name 'linux-nodalix-[0-9]*.pkg.tar.zst' -print -quit)"
headers="$(find . -maxdepth 1 -type f -name 'linux-nodalix-headers-[0-9]*.pkg.tar.zst' -print -quit)"
[[ -n "$kernel" && -n "$headers" ]] || exit 1
bsdtar -tf "$kernel" | grep -Eq '^usr/lib/modules/[^/]+/vmlinuz$'
bsdtar -tf "$headers" | grep -Eq '^usr/lib/modules/[^/]+/build/Module.symvers$'
bsdtar -tf "$headers" | grep -Eq '^usr/lib/modules/[^/]+/build/include/generated/autoconf.h$'

config="$(bsdtar -xOf "$kernel" usr/share/doc/linux-nodalix/config)"
grep -Fxq CONFIG_X86_64_VERSION=1 <<< "$config"
grep -Fxq CONFIG_LOCK_DOWN_KERNEL_FORCE_INTEGRITY=y <<< "$config"
grep -Fxq CONFIG_MODULE_SIG_ALL=y <<< "$config"

builtin="$(bsdtar -tf "$kernel" | grep -E '^usr/lib/modules/[^/]+/modules.builtin$')"
bsdtar -xOf "$kernel" "$builtin" | grep -Fxq kernel/drivers/hid/xpadneo/hid-xpadneo.ko
echo 'Kernel package and DKMS headers validated.'
