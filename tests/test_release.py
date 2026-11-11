"""Execute the workflow's actual ZIP step against isolated committed trees."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
BUILD = next(
    step["run"]
    for step in WORKFLOW["jobs"]["package"]["steps"]
    if step.get("name") == "Build integration ZIP"
)


class ReleaseTests(unittest.TestCase):
    """Keep the one Marketplace archive isolated from local files and metadata."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name)
        self.git("init", "--initial-branch=main")
        integration = self.repository / "custom_components/delonghi_comfort"
        integration.mkdir(parents=True)
        (integration / "manifest.json").write_text(json.dumps({"version": "1.2.3"}))
        (integration / "__init__.py").write_text('"""Test integration."""\n')
        (integration / "translations").mkdir()
        (integration / "translations/ja.json").write_text("{}")
        for name in ("LICENSE", "NOTICE"):
            (self.repository / name).write_text(name)
        (self.repository / "version.txt").write_text("1.2.3\n")
        (self.repository / "INTEGRATION-REBUILD-PLAN.md").write_text("Private plan")
        self.git("add", ".")
        self.commit()
        self.sha = self.git("rev-parse", "HEAD").decode().strip()
        (integration / "manifest.json").write_text(json.dumps({"version": "9.9.9"}))
        (integration / "local.py").write_text("untracked")
        (integration / "__pycache__").mkdir()
        (integration / "__pycache__/local.pyc").write_bytes(b"untracked")
        self.archive = self.repository / "dist/delonghi_comfort.zip"

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.repository), *args], stderr=subprocess.STDOUT
        )

    def commit(self):
        self.git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            "Test release",
        )

    def build(self, tag="v1.2.3", sha=None):
        return subprocess.run(
            ["bash", "-c", BUILD],
            cwd=self.repository,
            env={**os.environ, "RELEASE_TAG": tag, "RELEASE_SHA": sha or self.sha},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_exact_layout_uses_committed_revision_and_is_reproducible(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        with ZipFile(self.archive) as archive:
            self.assertEqual(
                {name for name in archive.namelist() if not name.endswith("/")},
                {
                    "manifest.json",
                    "__init__.py",
                    "translations/ja.json",
                    "LICENSE",
                    "NOTICE",
                },
            )
            self.assertEqual(
                json.loads(archive.read("manifest.json"))["version"], "1.2.3"
            )
            self.assertEqual(archive.read("LICENSE"), b"LICENSE")
            destination = self.repository / "config/custom_components/delonghi_comfort"
            archive.extractall(destination)
            self.assertTrue((destination / "manifest.json").is_file())
            self.assertFalse((destination / "delonghi_comfort").exists())
        first = self.archive.read_bytes()
        self.assertEqual(self.build().returncode, 0)
        self.assertEqual(self.archive.read_bytes(), first)

    def test_invalid_tag_revision_and_version_mismatch_fail(self):
        for tag, sha in (
            ("v1.2.4", self.sha),
            ("1.2.3", self.sha),
            ("v1.2.3;exit", self.sha),
            ("v1.2.3", "main"),
            ("v1.2.3", "f" * 40),
        ):
            with self.subTest(tag=tag, sha=sha):
                self.assertNotEqual(self.build(tag, sha).returncode, 0)
                self.assertFalse(self.archive.exists())

    def test_version_file_and_required_notices_are_checked(self):
        (
            self.repository / "custom_components/delonghi_comfort/manifest.json"
        ).write_text(json.dumps({"version": "1.2.3"}))
        self.git("add", "custom_components/delonghi_comfort/manifest.json")
        for path, content in (("version.txt", "8.0.0"), ("NOTICE", None)):
            with self.subTest(path=path):
                target = self.repository / path
                if content is None:
                    target.unlink()
                else:
                    target.write_text(content)
                self.git("add", path)
                self.commit()
                sha = self.git("rev-parse", "HEAD").decode().strip()
                result = self.build(sha=sha)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "version files disagree" if content is not None else "NOTICE",
                    result.stderr,
                )
                self.assertFalse(self.archive.exists())
                # Restore for the next independent failure case.
                target.write_text("1.2.3\n" if path == "version.txt" else path)
                self.git("add", path)
                self.commit()

    def test_tracked_bytecode_and_symlinks_are_rejected(self):
        integration = self.repository / "custom_components/delonghi_comfort"
        (integration / "manifest.json").write_text(json.dumps({"version": "1.2.3"}))
        for path in (integration / "stale.pyc", integration / "linked.py"):
            with self.subTest(path=path.name):
                if path.suffix == ".pyc":
                    path.write_bytes(b"tracked bytecode")
                else:
                    path.symlink_to("__init__.py")
                self.git(
                    "add",
                    "custom_components/delonghi_comfort/manifest.json",
                    str(path.relative_to(self.repository)),
                )
                self.commit()
                sha = self.git("rev-parse", "HEAD").decode().strip()
                result = self.build(sha=sha)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Unexpected integration archive member", result.stderr)
                path.unlink()
                self.git("add", str(path.relative_to(self.repository)))
                self.commit()

    def test_release_configuration_and_hold_are_consistent(self):
        manifest = json.loads(
            (ROOT / "custom_components/delonghi_comfort/manifest.json").read_text()
        )
        baseline = json.loads((ROOT / ".release-please-manifest.json").read_text())
        self.assertEqual(manifest["version"], baseline["."])
        self.assertEqual(
            manifest["version"], (ROOT / "version.txt").read_text().strip()
        )
        config = json.loads((ROOT / "release-please-config.json").read_text())
        self.assertTrue(config["packages"]["."]["draft"])
        self.assertFalse(config["packages"]["."]["include-component-in-tag"])
        self.assertEqual(
            config["packages"]["."]["extra-files"],
            [
                {
                    "type": "json",
                    "path": "custom_components/delonghi_comfort/manifest.json",
                    "jsonpath": "$.version",
                }
            ],
        )
        steps = WORKFLOW["jobs"]["release"]["steps"]
        release = next(step for step in steps if step.get("id") == "release")
        self.assertEqual(
            release["with"]["skip-github-release"],
            "${{ vars.DELONGHI_RELEASE_APPROVED != 'true' }}",
        )
        hacs = json.loads((ROOT / "hacs.json").read_text())
        self.assertTrue(hacs["zip_release"])
        self.assertEqual(hacs["filename"], self.archive.name)

    def test_missing_app_configuration_fails_without_exposing_secrets(self):
        require_app = WORKFLOW["jobs"]["release"]["steps"][0]["run"]
        for app_id, private_key in (("", ""), ("123", ""), ("", "private-test-value")):
            with self.subTest(app_id=app_id, has_key=bool(private_key)):
                result = subprocess.run(
                    ["bash", "-c", require_app],
                    env={
                        **os.environ,
                        "APP_ID": app_id,
                        "APP_PRIVATE_KEY": private_key,
                    },
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("private-test-value", result.stdout + result.stderr)

    def test_release_event_and_packaging_are_wired_to_one_immutable_commit(self):
        # PyYAML's YAML 1.1 loader treats the unquoted GitHub Actions "on" key as True.
        events = WORKFLOW[True]
        self.assertEqual(events["push"]["branches"], ["main"])
        self.assertNotIn("tags", events["push"])
        jobs = WORKFLOW["jobs"]
        self.assertEqual(jobs["package"]["needs"], "release")
        self.assertEqual(
            jobs["package"]["if"], "needs.release.outputs.release_created == 'true'"
        )
        checkout = jobs["package"]["steps"][0]
        self.assertEqual(checkout["with"]["ref"], "${{ needs.release.outputs.sha }}")
        self.assertEqual(
            jobs["release"]["outputs"]["sha"], "${{ steps.release.outputs.sha }}"
        )
        upload = jobs["package"]["steps"][-1]
        self.assertIn("--json isDraft", upload["run"])
        self.assertIn("gh release upload", upload["run"])
        self.assertNotIn("gh release create", upload["run"])
