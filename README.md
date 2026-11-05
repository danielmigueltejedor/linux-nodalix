# Linux Nodalix

**Linux Nodalix** is Nodalix OS's kernel distribution, built from a **selected,
immutable CachyOS Linux revision**, with Nodalix changes and independent
versioned packaging. It is **not a rolling-release kernel**.

The first tracked kernel is **7.3.1-1-nodalix** for **Nodalix OS 0.5.0**.
These are the previously selected kernel source and configuration commits
already used by Nodalix OS, not a claim that this is CachyOS's newest kernel.

## Release model

| Nodalix OS | Kernel | Pin | Update policy |
| --- | --- | --- | --- |
| 0.5.0 | 7.3.1-1-nodalix | [pins/0.5.0.json](pins/0.5.0.json) | Fixed until reviewed release/security rebuild |

- Each OS release adds a **new reviewed pin file**. Existing pins are not
  automatically rewritten when CachyOS publishes a new version.
- A kernel security rebuild on the same OS branch is a deliberate human-reviewed
  change, not a silent upstream update.
- Nodalix OS selects packages using its **release/components.json** manifest.
  This repository supplies the build recipes and binaries, **not** the authority
  to change the installed OS's kernel by itself.
- Normal users never compile the kernel. Nodalix's trusted build infrastructure
  compiles it and publishes **signed binary packages** after validation.

## Repository layout

- [PKGBUILD](PKGBUILD): split package for **linux-nodalix** and
  **linux-nodalix-headers**, on a generic **x86-64-v1** CPU baseline.
- [preserve-ble-identity.patch](preserve-ble-identity.patch): tested Nodalix
  Xbox Bluetooth HID behavior; the audited upstream Xpadneo source is pinned.
- [pins/](pins/): reproducible OS-to-kernel mapping, exact source commits,
  checksums and signing policy.
- [scripts/check-policy.py](scripts/check-policy.py): offline, fail-closed pin
  validation.
- [scripts/build.sh](scripts/build.sh): build **both** binary packages in an
  isolated build workspace.
- [scripts/ci-build.sh](scripts/ci-build.sh): disposable Arch CI environment and
  package contents validation.
- [scripts/stage-signed-repo.sh](scripts/stage-signed-repo.sh): locally stage a
  signed pacman repository without publishing anything.
- [.github/workflows/validate.yml](.github/workflows/validate.yml): PR checks.
- [.github/workflows/build.yml](.github/workflows/build.yml): **manual** full
  compilation and upload of unsigned *candidate* packages. No automatic publish.

## Build the kernel on CI, not on Nodalix devices

1. Open **Actions → Build pinned Linux Nodalix (manual)**.
2. Enter the exact **Nodalix OS release** (currently 0.5.0).
3. The build validates its pin, fetches only the pinned source revisions,
   compiles in an isolated Arch Linux container and produces
   `linux-nodalix-7.3.1-1-x86_64.pkg.tar.zst` and
   `linux-nodalix-headers-7.3.1-1-x86_64.pkg.tar.zst`.
4. Review the checks, download the CI artifact, verify SHA-256 and pass it to
   **trusted release infrastructure** for GPG package and repository signing.
5. Validate an installed system (boot, graphics, Wi-Fi, Bluetooth, storage,
   suspend/resume, kernel lockdown, recovery and representative DKMS modules).
6. Publish only when the Nodalix OS release authorizes that kernel.

No schedule, latest-branch polling, or CachyOS release events are connected to
the build or publication pipeline.

### Locally reproduce on a dedicated builder

On an Arch Linux **build machine** with the build dependencies installed:

```sh
python3 scripts/check-policy.py --release 0.5.0
bash scripts/build.sh 0.5.0 ./dist/packages
```

On trusted signing infrastructure, after configuring and protecting a GPG
secret key, you can create a signed local repository directory:

```sh
export NODALIX_PACKAGE_GPG_KEY='KEY_FINGERPRINT'
bash scripts/stage-signed-repo.sh 0.5.0 ./dist/packages ./dist/staged
```

The signing script does **not** upload or publish anything. No signing key is
stored in this repository. An installing system must trust the Nodalix package
signing key and enforce package **and database** signature verification. This
step is distinct from signing the kernel for UEFI Secure Boot.

## Compatibility and trust

The kernel keeps the existing Nodalix naming convention
`7.3.1-1-nodalix` and installs its image under
`/usr/lib/modules/<kernelrelease>/vmlinuz`, allowing the normal mkinitcpio
and bootloader integration. The headers package installs the matching
`/usr/lib/modules/<kernelrelease>/build` tree for external module builds.

**Important:** Forced kernel integrity lockdown and module signature
enforcement can prevent unsigned DKMS modules from loading. External modules
must be compatible and correctly signed with a key trusted by the running
kernel. A signed pacman package does not by itself make its kernel modules
trusted. Kernel signing for Secure Boot is an additional separate requirement.

The generic baseline is intentional: optimizations must never make the
distribution unusable on older x86-64 processors merely because a developer's
PC supports newer instructions.

## Updating to a new CachyOS base

Open a PR; change the source commit, configuration commit, source SHA-256,
kernel version and policy pin **together**. Update patches explicitly, and
run full CI compilation and real-hardware validation. Do not change 0.5.0's
kernel pin merely because a newer CachyOS release is available.

The existing Nodalix OS repository initially retains its older kernel build
path. **Integrating its release pipeline with this new repository must be
reviewed separately and use an immutable reference**, so there can never be
two unsynchronised kernel sources of truth.

## License

Linux is GPL-2.0-only, with various other licenses in its source tree.
Third-party Xpadneo code and CachyOS modifications retain their original
licenses and attribution. This repository redistributes build instructions
and an upstream-derived patch, not the entire kernel source.
