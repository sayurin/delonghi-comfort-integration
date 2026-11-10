"""Verify exact archive layout and tag/version consistency using local Git only."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_release.py"
SPEC = importlib.util.spec_from_file_location("build_release", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    """Package only committed distribution files, never local plans or credentials."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        self.git("init", "--initial-branch=main")
        integration = self.repository / release.INTEGRATION
        integration.mkdir(parents=True)
        (integration / "manifest.json").write_text(json.dumps({"version": "1.2.3"}))
        (integration / "__init__.py").write_text('"""Test integration."""\n')
        (integration / "translations").mkdir()
        (integration / "translations/en.json").write_text("{}")
        (integration / "__pycache__").mkdir()
        (integration / "__pycache__/stale.pyc").write_bytes(b"stale")
        for document in release.DOCUMENTS:
            (self.repository / document).write_text(document)
        (self.repository / "INTEGRATION-REBUILD-PLAN.md").write_text("Private plan")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "-m", "Test release")
        self.git("tag", "v1.2.3")
        (integration / "manifest.json").write_text(json.dumps({"version": "9.9.9"}))
        (integration / "untracked.py").write_text("untracked")
        self.output = self.root / "dist"

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.repository), *args], stderr=subprocess.STDOUT
        )

    def test_exact_layout_uses_tagged_tree_and_ignores_local_files(self):
        integration, complete = release.build_release(
            self.repository, "v1.2.3", self.output
        )
        with ZipFile(integration) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"__init__.py", "manifest.json", "translations/en.json"},
            )
            self.assertEqual(
                json.loads(archive.read("manifest.json"))["version"],
                "1.2.3",
            )
        with ZipFile(complete) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {f"{release.INTEGRATION}/__init__.py",
                 f"{release.INTEGRATION}/manifest.json",
                 f"{release.INTEGRATION}/translations/en.json", *release.DOCUMENTS},
            )
            self.assertNotIn("INTEGRATION-REBUILD-PLAN.md", archive.namelist())
        first = integration.read_bytes(), complete.read_bytes()
        release.build_release(self.repository, "v1.2.3", self.output)
        self.assertEqual(first, (integration.read_bytes(), complete.read_bytes()))

    def test_marketplace_asset_configuration_and_direct_extraction(self):
        manifest = json.loads((SCRIPT.parents[1] / "hacs.json").read_text())
        integration, _ = release.build_release(
            self.repository, "v1.2.3", self.output
        )
        self.assertIs(manifest["zip_release"], True)
        self.assertIs(manifest["hide_default_branch"], True)
        self.assertEqual(manifest["filename"], integration.name)
        destination = self.root / "config/custom_components/delonghi_comfort"
        with ZipFile(integration) as archive:
            archive.extractall(destination)
        self.assertEqual(
            json.loads((destination / "manifest.json").read_text())["version"],
            "1.2.3",
        )
        self.assertTrue((destination / "__init__.py").is_file())
        self.assertTrue((destination / "translations/en.json").is_file())
        self.assertFalse((destination / "delonghi_comfort").exists())

    def test_mismatch_and_invalid_tags_produce_no_artifacts(self):
        self.git("tag", "v1.2.4")
        for tag in ("v1.2.4", "1.2.3", "v1.2.3/../../other", "v1.2.3;exit"):
            with self.subTest(tag=tag):
                with self.assertRaises(ValueError):
                    release.build_release(self.repository, tag, self.output)
                self.assertFalse(self.output.exists())

    def test_missing_tag_fails_without_packaging_head(self):
        with self.assertRaises(subprocess.CalledProcessError):
            release.build_release(self.repository, "v8.8.8", self.output)
        self.assertFalse(self.output.exists())
