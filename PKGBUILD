# Maintained by Nodalix. CachyOS base and every source are pinned for this release.
# This recipe intentionally NEVER selects the latest upstream tag or branch.
pkgbase=linux-nodalix
pkgname=(linux-nodalix linux-nodalix-headers)
pkgver=7.3.1
pkgrel=1
pkgdesc='Nodalix Linux kernel based on a pinned CachyOS revision'
arch=('x86_64')
url='https://github.com/danielmigueltejedor/linux-nodalix'
license=('GPL-2.0-only')
makedepends=('base-devel' 'bc' 'clang' 'cpio' 'flex' 'bison' 'git' 'libelf'
             'lld' 'llvm' 'openssl' 'pahole' 'patch' 'perl' 'rust'
             'rust-bindgen' 'rust-src' 'zstd')
options=('!strip' '!debug' '!lto')

# Retained from the tested 7.3.1 recipe in nodalix-os.
_kernel_commit=36ae4c219cfbd02576048c7ca1d366cea5db8034
_config_commit=66666177b78f29c32670ba4f78f882bc0b9cc03d
_xpadneo_commit=e8f103a77f777c2c54536dd947969cf228699c13

source=(
  "cachyos-$pkgver.tar.gz::https://codeload.github.com/CachyOS/linux/tar.gz/$_kernel_commit"
  "cachyos.config::https://raw.githubusercontent.com/CachyOS/linux-cachyos/$_config_commit/linux-cachyos/config"
  "xpadneo::git+https://github.com/atar-axis/xpadneo.git#commit=$_xpadneo_commit"
  'preserve-ble-identity.patch'
)
sha256sums=(
  'ee5f3f2dd4a04bfae77c10a603857c1d99a3af20270b424ae018b98426f8d9f6'
  '81fb56fe326612a0dc4705fc5ec309d04bcfffb487db0cb5843918fe92951927'
  'SKIP' # The git source is pinned to the exact 40-character commit above.
  '67383a24e884464b285cf936abafae2151eb94a2cab5f550d1707e168980668f'
)

_srcname="linux-$_kernel_commit"

prepare() {
  patch --directory="$srcdir/xpadneo" --fuzz=0 -Np1 \
    -i "$srcdir/preserve-ble-identity.patch"

  cd "$srcdir/$_srcname"

  # Integrate the audited controller driver into the pinned source tree.
  install -dm755 drivers/hid/xpadneo
  install -m644 "$srcdir/xpadneo"/hid-xpadneo/src/xpadneo/*.[ch] drivers/hid/xpadneo/
  sed -e 's/$(VERSION)/v0.10.5/' \
      -e 's/^obj-m /obj-$(CONFIG_HID_XPADNEO) /' \
      -e 's|xpadneo/||g' \
      "$srcdir/xpadneo/hid-xpadneo/src/Makefile" > drivers/hid/xpadneo/Makefile
  printf '\nobj-$(CONFIG_HID_XPADNEO) += xpadneo/\n' >> drivers/hid/Makefile
  cat >> drivers/hid/Kconfig <<'KCONFIG'

config HID_XPADNEO
	bool "Nodalix xpadneo Xbox Bluetooth controller"
	depends on HID=y
	select CRC16
	select INPUT_FF_MEMLESS
	help
	  Support Xbox Bluetooth controllers with the Nodalix xpadneo driver.
KCONFIG

  # Fail closed if the pinned driver changes its verified identity behavior.
  sed -i 's/^static bool param_disable_pid_spoofing;$/static bool param_disable_pid_spoofing = true;/' \
    drivers/hid/xpadneo/core.c
  grep -Fxq 'static bool param_disable_pid_spoofing = true;' drivers/hid/xpadneo/core.c

  cp "$srcdir/cachyos.config" .config
  scripts/config --set-str LOCALVERSION "-$pkgrel-nodalix" \
    --disable LOCALVERSION_AUTO \
    --enable HID_XPADNEO --enable UHID --enable MODULE_SIG_ALL \
    --enable LOCK_DOWN_KERNEL_FORCE_INTEGRITY \
    --disable LOCK_DOWN_KERNEL_FORCE_NONE

  make LLVM=1 olddefconfig
  local required
  for required in \
    'CONFIG_GENERIC_CPU=y' \
    'CONFIG_X86_64_VERSION=1' \
    'CONFIG_HID_XPADNEO=y' \
    'CONFIG_UHID=y' \
    'CONFIG_RUST=y' \
    'CONFIG_MODULE_SIG_ALL=y' \
    'CONFIG_LOCK_DOWN_KERNEL_FORCE_INTEGRITY=y'; do
    grep -Fxq "$required" .config || {
      printf 'Required kernel setting missing: %s\n' "$required" >&2
      return 1
    }
  done
  [[ "$(make -s LLVM=1 kernelrelease)" = "$pkgver-$pkgrel-nodalix" ]]
}

build() {
  cd "$srcdir/$_srcname"
  # The private module-signing key is generated in the disposable build tree.
  # A release signature / Secure Boot signing key is a different trust domain.
  umask 077
  make LLVM=1 bzImage modules
}

package_linux-nodalix() {
  pkgdesc='Nodalix x86-64 kernel (pinned CachyOS base)'
  depends=('coreutils' 'kmod' 'mkinitcpio')
  optdepends=('linux-firmware: firmware for supported hardware'
              'sbctl: locally enrolled Secure Boot signing key')
  cd "$srcdir/$_srcname"
  local release modules
  release="$(make -s LLVM=1 kernelrelease)"
  [[ "$release" = "$pkgver-$pkgrel-nodalix" ]] || return 1
  modules="$pkgdir/usr/lib/modules/$release"

  # NEVER strip signed kernel modules: stripping invalidates module signatures.
  make LLVM=1 modules_install MODLIB="$modules" INSTALL_MOD_STRIP=0 \
    DEPMOD=/doesnt/exist
  grep -Fxq 'kernel/drivers/hid/xpadneo/hid-xpadneo.ko' \
    "$modules/modules.builtin"
  rm -f "$modules/build" "$modules/source"

  install -Dm644 arch/x86/boot/bzImage "$modules/vmlinuz"
  printf '%s\n' "$pkgbase" > "$modules/pkgbase"
  install -Dm644 .config "$pkgdir/usr/share/doc/$pkgbase/config"
  install -Dm644 COPYING "$pkgdir/usr/share/licenses/$pkgname/COPYING"
}

package_linux-nodalix-headers() {
  pkgdesc='Headers and build scripts for Linux Nodalix external modules'
  depends=("linux-nodalix=$pkgver-$pkgrel" 'binutils' 'glibc'
           'libelf' 'openssl' 'pahole' 'zlib' 'zstd')
  cd "$srcdir/$_srcname"
  local release builddir
  release="$(make -s LLVM=1 kernelrelease)"
  [[ "$release" = "$pkgver-$pkgrel-nodalix" ]] || return 1
  builddir="$pkgdir/usr/lib/modules/$release/build"

  # A matching Module.symvers is essential for DKMS symbol version checks.
  install -Dt "$builddir" -m644 .config Makefile Module.symvers System.map vmlinux
  [[ ! -f version ]] || install -Dm644 version "$builddir/version"
  install -Dt "$builddir/kernel" -m644 kernel/Makefile
  install -Dt "$builddir/arch/x86" -m644 arch/x86/Makefile
  cp -a scripts "$builddir/"
  cp -a include "$builddir/"
  install -d "$builddir/arch/x86"
  cp -a arch/x86/include "$builddir/arch/x86/"
  install -Dt "$builddir/arch/x86/kernel" -m644 arch/x86/kernel/asm-offsets.s

  # External-module preparation uses the in-tree compiled host utilities.
  if [[ -f tools/objtool/objtool ]]; then
    install -Dm755 tools/objtool/objtool "$builddir/tools/objtool/objtool"
  fi
  if [[ -f tools/bpf/resolve_btfids/resolve_btfids ]]; then
    install -Dm755 tools/bpf/resolve_btfids/resolve_btfids \
      "$builddir/tools/bpf/resolve_btfids/resolve_btfids"
  fi
  install -Dm644 COPYING "$pkgdir/usr/share/licenses/$pkgname/COPYING"
}
