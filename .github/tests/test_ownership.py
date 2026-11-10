"""Compile real first-party sources and the full, unchanged SDK; no 4D required."""

import hashlib
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("OWNERSHIP_SOURCE_ROOT", ROOT)).resolve()


@unittest.skipUnless(platform.system() == "Darwin", "macOS native engine shim")
class OwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="alias-ownership-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.binary = Path(cls.temp.name) / "ownership"
        sdk = SOURCE / "4D Plugin API"
        sources = [
            sdk / "4DPluginAPI.c",
            SOURCE / "support/4DPlugin-JSON.cpp",
            *(sdk / "Classes" / name for name in
              ("C_TEXT.cpp", "C_LONGINT.cpp", "ARRAY_TEXT.cpp", "C_BLOB.cpp")),
            ROOT / ".github/tests/native/ownership.cpp",
        ]
        result = subprocess.run(
            ["clang++", "-std=c++11", "-x", "objective-c++", "-fsyntax-only",
             "-Wno-deprecated-declarations", "-Wno-return-type-c-linkage",
             "-I", str(sdk), "-I", str(sdk / "Classes"),
             str(SOURCE / "4DPlugin-Alias-Manager.cpp")],
            text=True, capture_output=True, timeout=60,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        result = subprocess.run(
            ["clang++", "-std=c++11", "-x", "objective-c++", "-g",
             "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
             "-Wno-deprecated-declarations", "-Wno-multichar",
             "-Wno-return-type-c-linkage", "-Wno-writable-strings",
             "-I", str(sdk), "-I", str(sdk / "Classes"),
             "-I", str(SOURCE / "support"), *map(str, sources),
             "-framework", "Cocoa", "-framework", "CoreGraphics",
             "-o", str(cls.binary)],
            text=True, capture_output=True, timeout=120,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_case(self, name):
        result = subprocess.run(
            [str(self.binary), name], text=True, capture_output=True, timeout=30,
            env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0",
                 "UBSAN_OPTIONS": "halt_on_error=1"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS " + name, result.stdout)
        if name == "failed":
            self.assertEqual(result.stderr.count("PA_GetObjectProperty failed: -9966"), 5)

    def test_bundled_sdk_is_unchanged(self):
        expected = {
            "4DPluginAPI.c": "5bac571c5c4cafd280fa7f23d775458a23701287e8735be27d4a2190002f4e3f",
            "4DPluginAPI.h": "c845a8ae3b552f514e16598605727bf5008eaa28df2401950ac2b7881df61f02",
            "EntryPoints.h": "60afb0b833c95d6c47b88d2d0eba0fb212c2c6b53a44e3cfc0b4c6956d25d2dd",
            "Flags.h": "c39ca489cb5dacd2ebcbb95d914795c60d557b87acc2456f6abf3fd63d66850b",
            "PrivateTypes.h": "329a5ba0d0369b4e96ad9afe4d0261407164dbf4c1379c5bbe1685669d20a53f",
            "PublicTypes.h": "7b8c3959f24267a2a398680ddd114acc14b33082974b1debc2a940a82cdb6155",
        }
        for name, digest in expected.items():
            with self.subTest(path=name):
                self.assertEqual(
                    hashlib.sha256((SOURCE / "4D Plugin API" / name).read_bytes()).hexdigest(),
                    digest,
                )

    def test_string_setter_empty_owner(self):
        self.run_case("setters")

    def test_scalar_getter_owned_results(self):
        self.run_case("scalars")

    def test_reference_getter_mismatch_and_handoff(self):
        self.run_case("references")

    def test_failed_getter_unspecified_output(self):
        self.run_case("failed")

    def test_array_transfers_and_scalar_copies(self):
        self.run_case("arrays")

    def test_stringify_owning_return(self):
        self.run_case("stringify")


if __name__ == "__main__":
    unittest.main()
