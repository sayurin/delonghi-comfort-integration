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
                {"delonghi_comfort/__init__.py", "delonghi_comfort/manifest.json"},
            )
            self.assertEqual(
                json.loads(archive.read("delonghi_comfort/manifest.json"))["version"],
                "1.2.3",
            )
        with ZipFile(complete) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {f"{release.INTEGRATION}/__init__.py",
                 f"{release.INTEGRATION}/manifest.json", *release.DOCUMENTS},
            )
            self.assertNotIn("INTEGRATION-REBUILD-PLAN.md", archive.namelist())
        first = integration.read_bytes(), complete.read_bytes()
        release.build_release(self.repository, "v1.2.3", self.output)
        self.assertEqual(first, (integration.read_bytes(), complete.read_bytes()))

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
