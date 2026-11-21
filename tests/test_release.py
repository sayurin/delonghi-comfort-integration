"""Execute the workflow's actual ZIP step against isolated committed trees."""

import json
import os
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
BUILD_SCRIPT = ROOT / "scripts/build_release.py"


def git(repository, *args):
    return subprocess.check_output(
        ["git", "-C", str(repository), *args], stderr=subprocess.STDOUT
    )


def commit(repository):
    git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "Test release",
    )


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "--initial-branch=main")
    integration = tmp_path / "custom_components/delonghi_comfort"
    integration.mkdir(parents=True)
    (integration / "manifest.json").write_bytes(
        (ROOT / "custom_components/delonghi_comfort/manifest.json").read_bytes()
    )
    (integration / "__init__.py").write_text('"""Test integration."""\n')
    (integration / "translations").mkdir()
    (integration / "translations/ja.json").write_text("{}")
    for name in ("LICENSE", "NOTICE"):
        (tmp_path / name).write_text(name)
    (tmp_path / "version.txt").write_text("1.2.3\n")
    (tmp_path / ".release-please-manifest.json").write_text(json.dumps({".": "1.2.3"}))
    (tmp_path / "INTEGRATION-REBUILD-PLAN.md").write_text("Private plan")
    git(tmp_path, "add", ".")
    commit(tmp_path)

    (integration / "manifest.json").write_text(json.dumps({"version": "9.9.9"}))
    (integration / "local.py").write_text("untracked")
    (integration / "__pycache__").mkdir()
    (integration / "__pycache__/local.pyc").write_bytes(b"untracked")
    return tmp_path


@pytest.fixture
def release_sha(repository):
    return git(repository, "rev-parse", "HEAD").decode().strip()


@pytest.fixture
def archive(repository):
    return repository / "dist/delonghi_comfort.zip"


def build(repository, tag="v1.2.3", sha=None, release_sha=None):
    return subprocess.run(
        [sys.executable, str(BUILD_SCRIPT)],
        cwd=repository,
        env={
            **os.environ,
            "RELEASE_TAG": tag,
            "RELEASE_SHA": sha or release_sha,
        },
        capture_output=True,
        text=True,
        check=False,
    )


def test_exact_layout_uses_committed_revision_and_is_reproducible(
    repository,
    release_sha,
    archive,
):
    result = build(repository, release_sha=release_sha)
    assert result.returncode == 0, result.stderr

    with ZipFile(archive) as zip_file:
        assert {name for name in zip_file.namelist() if not name.endswith("/")} == {
            "manifest.json",
            "__init__.py",
            "translations/ja.json",
            "LICENSE",
            "NOTICE",
        }
        assert json.loads(zip_file.read("manifest.json"))["version"] == "1.2.3"
        committed_manifest = git(
            repository,
            "show",
            f"{release_sha}:custom_components/delonghi_comfort/manifest.json",
        )
        assert zip_file.read("manifest.json") == committed_manifest.replace(
            b'"version": "0.0.0"', b'"version": "1.2.3"'
        )
        assert zip_file.read("LICENSE") == b"LICENSE"
        destination = repository / "config/custom_components/delonghi_comfort"
        zip_file.extractall(destination)
        assert (destination / "manifest.json").is_file()
        assert not (destination / "delonghi_comfort").exists()

    first = archive.read_bytes()
    assert build(repository, release_sha=release_sha).returncode == 0
    assert archive.read_bytes() == first


@pytest.mark.parametrize(
    ("tag", "sha"),
    (
        ("v1.2.4", None),
        ("1.2.3", None),
        ("v1.2.3;exit", None),
        ("v1.2.3", "main"),
        ("v1.2.3", "f" * 40),
    ),
)
def test_invalid_tag_revision_and_version_mismatch_fail(
    repository,
    release_sha,
    archive,
    tag,
    sha,
):
    assert build(repository, tag, sha, release_sha).returncode != 0
    assert not archive.exists()


@pytest.mark.parametrize(
    ("path", "content", "expected_error"),
    (
        ("version.txt", "8.0.0", "version files disagree"),
        (".release-please-manifest.json", '{".": "1.2.2"}', "version files disagree"),
        ("NOTICE", None, "NOTICE"),
    ),
)
def test_version_file_and_required_notices_are_checked(
    repository,
    archive,
    path,
    content,
    expected_error,
):
    target = repository / path
    if content is None:
        target.unlink()
    else:
        target.write_text(content)
    git(repository, "add", path)
    commit(repository)
    sha = git(repository, "rev-parse", "HEAD").decode().strip()

    result = build(repository, sha=sha)

    assert result.returncode != 0
    assert expected_error in result.stderr
    assert not archive.exists()


@pytest.mark.parametrize(
    ("content", "error"),
    (
        ('{\n  "version": "1.2.3"\n}\n', "Committed manifest version must be 0.0.0"),
        (
            '{\n  "version": "0.0.0",\n  "version": "0.0.0"\n}\n',
            "Expected exactly one manifest version placeholder",
        ),
    ),
)
def test_invalid_manifest_placeholder_fails(repository, archive, content, error):
    (repository / "custom_components/delonghi_comfort/manifest.json").write_text(
        content
    )
    git(repository, "add", "custom_components/delonghi_comfort/manifest.json")
    commit(repository)
    sha = git(repository, "rev-parse", "HEAD").decode().strip()

    result = build(repository, sha=sha)

    assert result.returncode != 0
    assert error in result.stderr
    assert not archive.exists()


@pytest.mark.parametrize("member", ("bytecode", "symlink", "backslash"))
def test_tracked_bytecode_symlinks_and_unsafe_paths_are_rejected(
    repository,
    archive,
    member,
):
    integration = repository / "custom_components/delonghi_comfort"
    (integration / "manifest.json").write_bytes(
        (ROOT / "custom_components/delonghi_comfort/manifest.json").read_bytes()
    )
    if member == "bytecode":
        path = integration / "stale.pyc"
        path.write_bytes(b"tracked bytecode")
    elif member == "symlink":
        path = integration / "linked.py"
        path.symlink_to("__init__.py")
    else:
        path = integration / "..\\escape.py"
        path.write_text("outside")

    git(repository, "add", "custom_components/delonghi_comfort/manifest.json")
    git(repository, "add", str(path.relative_to(repository)))
    commit(repository)
    sha = git(repository, "rev-parse", "HEAD").decode().strip()

    result = build(repository, sha=sha)

    assert result.returncode != 0
    assert "Unexpected integration archive member" in result.stderr
    assert not archive.exists()


def test_release_configuration_publishes_a_prerelease(archive):
    manifest = json.loads(
        (ROOT / "custom_components/delonghi_comfort/manifest.json").read_text()
    )
    baseline = json.loads((ROOT / ".release-please-manifest.json").read_text())
    assert manifest["version"] == "0.0.0"
    assert baseline["."] == (ROOT / "version.txt").read_text().strip()
    config = json.loads((ROOT / "release-please-config.json").read_text())
    assert not config["packages"]["."]["draft"]
    assert config["packages"]["."]["prerelease"]
    assert config["packages"]["."]["force-tag-creation"]
    assert not config["packages"]["."]["include-component-in-tag"]
    assert "extra-files" not in config["packages"]["."]
    assert WORKFLOW["jobs"]["release"]["if"] == "github.event_name == 'push'"
    steps = WORKFLOW["jobs"]["release"]["steps"]
    release = next(step for step in steps if step.get("id") == "release")
    assert "skip-github-release" not in release["with"]
    assert "DELONGHI_RELEASE_APPROVED" not in json.dumps(WORKFLOW)
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["zip_release"]
    assert hacs["filename"] == archive.name


@pytest.mark.parametrize(
    ("client_id", "private_key"),
    (("", ""), ("test-client-id", ""), ("", "private-test-value")),
)
def test_missing_app_configuration_fails_without_exposing_secrets(
    client_id,
    private_key,
):
    require_app = WORKFLOW["jobs"]["release"]["steps"][0]["run"]
    result = subprocess.run(
        ["bash", "-c", require_app],
        env={
            **os.environ,
            "APP_CLIENT_ID": client_id,
            "APP_PRIVATE_KEY": private_key,
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "private-test-value" not in result.stdout + result.stderr


def test_existing_tag_history_uses_an_explicit_migration_boundary():
    config = json.loads((ROOT / "release-please-config.json").read_text())
    assert "bootstrap-sha" not in config
    assert config["last-release-sha"] == "7e7549741e1fdbcbd4e70559c494365f847c3949"


def test_release_and_packaging_are_wired_to_one_immutable_commit():
    # PyYAML's YAML 1.1 loader treats the unquoted GitHub Actions "on" key as True.
    events = WORKFLOW[True]
    assert events["push"]["branches"] == ["main"]
    assert "tags" not in events["push"]
    jobs = WORKFLOW["jobs"]
    assert jobs["package"]["needs"] == ["release", "recover"]
    assert "always()" in jobs["package"]["if"]
    assert "github.event_name == 'workflow_dispatch'" in jobs["package"]["if"]
    assert "needs.recover.result == 'success'" in jobs["package"]["if"]
    assert jobs["recover"]["if"] == (
        "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'"
    )
    assert jobs["recover"]["steps"][0]["with"]["ref"] == "${{ github.sha }}"
    checkout = jobs["package"]["steps"][0]
    assert (
        checkout["with"]["ref"]
        == "${{ needs.recover.outputs.sha || needs.release.outputs.sha }}"
    )
    assert jobs["release"]["outputs"]["sha"] == "${{ steps.release.outputs.sha }}"
    events = WORKFLOW[True]
    assert events["workflow_dispatch"]["inputs"]["release_tag"]["required"]
    steps = jobs["package"]["steps"]
    verify = next(
        step
        for step in steps
        if step.get("name") == "Verify published pre-release and tag revision"
    )
    assert "isPrerelease" in verify["run"]
    assert "isDraft" in verify["run"]
    upload = steps[-1]
    assert "gh release upload" in upload["run"]
    assert "gh release download" in upload["run"]
    assert "cmp --silent" in upload["run"]
    assert "--clobber" not in json.dumps(WORKFLOW)
    assert "gh release create" not in json.dumps(WORKFLOW)
    build = next(step for step in steps if step.get("name") == "Build integration ZIP")
    assert "python scripts/build_release.py" in build["run"]
    assert "isPrerelease" in jobs["recover"]["steps"][1]["run"]
