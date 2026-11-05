"""Release policy regressions: no rolling kernel, drift, or unverified patches."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "nodalix_kernel_policy", ROOT / "scripts/check-policy.py"
)
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


class ReleasePinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "pins").mkdir()
        for path in ("PKGBUILD", "preserve-ble-identity.patch", "pins/0.5.0.json"):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)

    def test_original_kernel_source_is_frozen_for_nodalix_050(self):
        pin = POLICY.validate(self.root, "0.5.0")
        self.assertEqual(pin["kernel"]["kernel_release"], "7.3.1-1-nodalix")
        self.assertFalse(pin["policy"]["upstream_auto_upgrade"])
        self.assertTrue(pin["policy"]["package_signature_required_before_distribution"])

    def test_future_release_cannot_silently_use_current_pin(self):
        with self.assertRaises(POLICY.PolicyError):
            POLICY.validate(self.root, "0.6.0")
        for invalid in ("../0.5.0", "--help", "0.5.0/../../etc"):
            with self.subTest(invalid=invalid), self.assertRaises(POLICY.PolicyError):
                POLICY.validate(self.root, invalid)

    def test_package_version_and_commits_cannot_drift(self):
        spec = self.root / "PKGBUILD"
        original = spec.read_text()
        for before, after in [
            ("pkgver=7.3.1", "pkgver=7.4.0"),
            ("pkgrel=1", "pkgrel=2"),
            ("36ae4c219cfbd02576048c7ca1d366cea5db8034", "0" * 40),
            ("'CONFIG_HID_XPADNEO=y'", "'CONFIG_HID_XPADNEO=n'"),
            ("INSTALL_MOD_STRIP=0", "INSTALL_MOD_STRIP=1"),
        ]:
            with self.subTest(before=before):
                spec.write_text(original.replace(before, after))
                with self.assertRaises(POLICY.PolicyError):
                    POLICY.validate(self.root, "0.5.0")
        spec.write_text(original)

    def test_patch_hash_is_enforced(self):
        patch = self.root / "preserve-ble-identity.patch"
        patch.write_bytes(patch.read_bytes() + b"# unexpected change\n")
        with self.assertRaisesRegex(POLICY.PolicyError, "SHA-256"):
            POLICY.validate(self.root, "0.5.0")

    def test_must_stay_nonrolling_and_signed(self):
        path = self.root / "pins/0.5.0.json"
        original = json.loads(path.read_text())
        for key, value in [
            ("upstream_auto_upgrade", True),
            ("package_signature_required_before_distribution", False),
            ("build_target", "x86_64-v3"),
        ]:
            modified = json.loads(json.dumps(original))
            modified["policy"][key] = value
            path.write_text(json.dumps(modified))
            with self.subTest(key=key), self.assertRaises(POLICY.PolicyError):
                POLICY.validate(self.root, "0.5.0")


if __name__ == "__main__":
    unittest.main()
