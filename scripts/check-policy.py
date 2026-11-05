#!/usr/bin/env python3
"""Offline release pin validation. Never fetches upstream or executes PKGBUILD."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-(?:beta|rc)\.[0-9]+)?$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class PolicyError(ValueError):
    pass


def shell_assignment(source: str, key: str) -> str:
    match = re.search(r"^" + re.escape(key) + r"=([^\n#]+)", source, re.MULTILINE)
    if not match:
        raise PolicyError(f"Missing PKGBUILD assignment: {key}")
    return match.group(1).strip().strip("'\"")


def validate(root: Path, release: str) -> dict:
    if not VERSION.fullmatch(release):
        raise PolicyError("Release must be a Nodalix OS version, e.g. 0.5.0")
    pinfile = root / "pins" / (release + ".json")
    try:
        pin = json.loads(pinfile.read_text(encoding="utf-8"))
        spec = (root / "PKGBUILD").read_text(encoding="utf-8")
        patch = (root / "preserve-ble-identity.patch").read_bytes()
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"Release definition cannot be read: {exc}") from exc

    if pin.get("schema_version") != 1 or pin.get("nodalix_os_version") != release:
        raise PolicyError("Release pin identity or schema is invalid")
    kernel = pin.get("kernel")
    if not isinstance(kernel, dict):
        raise PolicyError("Missing kernel pin")
    if kernel.get("package") != "linux-nodalix" or kernel.get("headers_package") != "linux-nodalix-headers":
        raise PolicyError("Unexpected kernel package names")
    try:
        pkgver = kernel["pkgver"]
        pkgrel = kernel["pkgrel"]
        provenance = kernel["source"]
        sha = kernel["sha256"]
    except (KeyError, TypeError) as exc:
        raise PolicyError("Incomplete release provenance") from exc
    if not isinstance(pkgver, str) or not re.fullmatch(r"\d+\.\d+\.\d+", pkgver):
        raise PolicyError("Invalid kernel version")
    if not isinstance(pkgrel, int) or isinstance(pkgrel, bool) or pkgrel < 1:
        raise PolicyError("Invalid package release")
    expected_release = f"{pkgver}-{pkgrel}-nodalix"
    if kernel.get("kernel_release") != expected_release:
        raise PolicyError("Kernel release and package version differ")

    for name, expected in [
        ("pkgbase", "linux-nodalix"),
        ("pkgver", pkgver),
        ("pkgrel", str(pkgrel)),
        ("_kernel_commit", provenance.get("cachyos_linux_commit")),
        ("_config_commit", provenance.get("cachyos_config_commit")),
        ("_xpadneo_commit", provenance.get("xpadneo_commit")),
    ]:
        if name.startswith("_") and (not isinstance(expected, str) or not HEX40.fullmatch(expected)):
            raise PolicyError(f"Unpinned or invalid source commit: {name}")
        if shell_assignment(spec, name) != expected:
            raise PolicyError(f"PKGBUILD {name} differs from Nodalix OS {release} pin")

    if not re.search(r"^pkgname=\(linux-nodalix linux-nodalix-headers\)$", spec, re.MULTILINE):
        raise PolicyError("Both the kernel and headers must be built")
    checks = re.search(r"^sha256sums=\((.*?)^\)", spec, re.MULTILINE | re.DOTALL)
    if not checks:
        raise PolicyError("SHA-256 source checksum array not found")
    sums = re.findall(r"'([^']+)'", checks.group(1))
    expected_sums = [
        sha.get("cachyos_source"),
        sha.get("cachyos_config"),
        "SKIP",  # Pinned git commit; external download checksums validated by makepkg.
        sha.get("preserve_ble_identity_patch"),
    ]
    if len(sums) != 4 or sums != expected_sums or not all(
        isinstance(value, str) and HEX64.fullmatch(value)
        for value in [expected_sums[0], expected_sums[1], expected_sums[3]]
    ):
        raise PolicyError("PKGBUILD checksums differ from pinned source provenance")
    if hashlib.sha256(patch).hexdigest() != expected_sums[3]:
        raise PolicyError("Local driver patch SHA-256 changed")
    if "git+https://github.com/atar-axis/xpadneo.git#commit=$_xpadneo_commit" not in spec:
        raise PolicyError("Xpadneo source is no longer commit-pinned")
    if "https://codeload.github.com/CachyOS/linux/tar.gz/$_kernel_commit" not in spec:
        raise PolicyError("CachyOS kernel source is no longer commit-pinned")
    if "https://raw.githubusercontent.com/CachyOS/linux-cachyos/$_config_commit/" not in spec:
        raise PolicyError("CachyOS configuration source is no longer commit-pinned")
    for required in (
        "CONFIG_X86_64_VERSION=1", "CONFIG_HID_XPADNEO=y",
        "CONFIG_MODULE_SIG_ALL=y", "CONFIG_LOCK_DOWN_KERNEL_FORCE_INTEGRITY=y",
        "INSTALL_MOD_STRIP=0", "package_linux-nodalix-headers()",
    ):
        if required not in spec:
            raise PolicyError(f"Required packaging/security setting was removed: {required}")

    policy = pin.get("policy")
    if not isinstance(policy, dict) or policy.get("upstream_auto_upgrade") is not False:
        raise PolicyError("Rolling upstream updates are forbidden")
    if policy.get("package_signature_required_before_distribution") is not True:
        raise PolicyError("Distributed packages must be signed")
    if policy.get("build_target") != "x86_64-v1":
        raise PolicyError("This release requires the generic x86-64 baseline")
    return pin


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, help="Pinned Nodalix OS version")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        data = validate(args.root, args.release)
    except PolicyError as exc:
        print(f"Linux Nodalix policy error: {exc}", file=sys.stderr)
        return 1
    print("OK:", args.release, "->", data["kernel"]["kernel_release"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
