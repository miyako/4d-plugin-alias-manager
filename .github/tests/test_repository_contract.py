"""Alias Manager authority, topology and byte-preservation evidence."""

import importlib.util
from pathlib import Path
import re
import stat
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
BASE = "55bbd50be1db4adddc9a35604784f2f7e60822bd"
INTRODUCTION = "7107c0bee2b6aa6a1697b886376d0e724e6b3122"
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location(
    "contract_source", ROOT / ".github/scripts/source_version.py"
)
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


def original(path, revision=BASE):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{revision}:{path}"])


class RepositoryContractTests(unittest.TestCase):
    def test_explicit_header_controls_marketing_first_implementation(self):
        path = ".github/workflows/bump-version.yml"
        bump = original(path).decode()
        self.assertEqual(original(path, INTRODUCTION), original(path))
        history = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "--follow", "--format=%H", BASE, "--", path],
            text=True,
        ).splitlines()
        self.assertEqual(history, [INTRODUCTION])
        header, body = bump.split("name: Bump version", 1)
        self.assertIn("MARKETING_VERSION/CURRENT_PROJECT_VERSION AND Info.plist", header)
        self.assertIn("CFBundleShortVersionString/CFBundleVersion", header)
        self.assertIn('KEY="MARKETING_VERSION"', body)
        self.assertIn('KEY="CURRENT_PROJECT_VERSION"', body)

    def test_original_triggers_and_actual_mac_only_topology(self):
        release = original(".github/workflows/release.yml").decode()
        self.assertIn("  push:\n    tags:\n      - 'v*.*.*'", release)
        self.assertIn("  workflow_dispatch:\n    inputs:\n      tag:", release)
        self.assertNotIn("pull_request:", release)
        self.assertNotIn("branches:", release)
        self.assertNotIn("build-windows:", release)
        self.assertNotIn("msbuild ", release)
        self.assertNotIn("upload-artifact", release)
        self.assertNotIn("download-artifact", release)
        self.assertIn("Builds the plugin for Windows", release)
        bump = original(".github/workflows/bump-version.yml").decode()
        self.assertNotIn("\n  push:", bump)
        self.assertNotIn("pull_request:", bump)
        self.assertIn("  workflow_dispatch:", bump)

    def test_only_existing_authorized_source_version_tokens_change(self):
        current = source.read(ROOT)
        self.assertEqual(source.SETTING_COUNT, 6)
        for path in source.SOURCE_PATHS:
            with self.subTest(path=path):
                before = original(path)
                if path == source.PROJECT:
                    self.assertEqual(before.count(b"MARKETING_VERSION = 3.0.6;"), 6)
                    self.assertEqual(before.count(b"CURRENT_PROJECT_VERSION = 3.0.2;"), 6)
                    expected = before.replace(
                        b"MARKETING_VERSION = 3.0.6;",
                        f"MARKETING_VERSION = {current};".encode(),
                    ).replace(
                        b"CURRENT_PROJECT_VERSION = 3.0.2;",
                        f"CURRENT_PROJECT_VERSION = {current};".encode(),
                    )
                elif path == source.LOCALIZED:
                    self.assertEqual(before.count(b"3.0.1"), 2)
                    self.assertNotIn(b"\n", before)
                    self.assertIn(b"\r", before)
                    expected = before.replace(b"3.0.1", current.encode())
                else:
                    expected = before
                self.assertEqual((ROOT / path).read_bytes(), expected)
                self.assertEqual(stat.S_IMODE((ROOT / path).stat().st_mode), 0o644)
        self.assertNotIn(b"<key>CFBundleVersion</key>", (ROOT / source.PLIST).read_bytes())

    def test_all_unrelated_original_bytes_and_modes_preserved(self):
        entries = subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-tree", "-r", BASE], text=True,
        ).splitlines()
        allowed = {*map(str, source.SOURCE_PATHS), "README.md",
                   ".github/workflows/bump-version.yml", ".github/workflows/release.yml",
                   "support/4DPlugin-JSON.cpp", "support/4DPlugin-JSON.h"}
        for entry in entries:
            metadata, name = entry.split("\t", 1)
            if name in allowed:
                continue
            with self.subTest(path=name):
                self.assertEqual((ROOT / name).read_bytes(), original(name))
                mode = int(metadata.split()[0], 8) & 0o777
                self.assertEqual(stat.S_IMODE((ROOT / name).stat().st_mode), mode)

    def test_native_steps_secrets_and_original_empty_notes_policy(self):
        before = original(".github/workflows/release.yml").decode()
        after = (ROOT / ".github/workflows/release.yml").read_text()

        def block(workflow, name):
            return workflow.split(f"      - name: {name}\n", 1)[1].split(
                "\n      - name:", 1
            )[0].rstrip()

        for name in ("import Developer ID certificate", "store notarytool credentials",
                     "codesign"):
            self.assertEqual(block(before, name), block(after, name))
        secrets = r"\$\{\{ secrets\.([A-Z_]+) \}\}"
        self.assertEqual(re.findall(secrets, before), re.findall(secrets, after))
        original_release = block(before, "create GitHub Release")
        self.assertIn("uses: softprops/action-gh-release@v2", original_release)
        self.assertNotIn("body:", original_release)
        self.assertNotIn("generate_release_notes:", original_release)
        self.assertNotIn("body_path:", original_release)
        for token in ('ARCHS="arm64 x86_64"', "-configuration Default",
                      "ONLY_ACTIVE_ARCH=NO", "MACOS_DEPLOYMENT_TARGET: '11.0'",
                      'codesign --verify --deep --strict --verbose=2 "$BUNDLE_PATH"',
                      'xcrun stapler staple "$DMG_PATH"'):
            self.assertIn(token, before)
            self.assertIn(token, after)
        project = (ROOT / source.PROJECT).read_text()
        self.assertEqual(project.count('CONFIGURATION_BUILD_DIR = "$(BUILD_DIR)";'), 3)
        self.assertEqual(project.count('SYMROOT = "$(SRCROOT)/test/Plugins";'), 3)
        self.assertIn('CONFIGURATION_BUILD_DIR="$PWD/$PLUGINS_DIR"', after)
        self.assertNotIn('rm -rf "${PLUGINS_DIR:?}/Default"', after)


if __name__ == "__main__":
    unittest.main()
