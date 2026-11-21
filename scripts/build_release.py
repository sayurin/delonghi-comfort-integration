"""Build the reproducible Marketplace ZIP for a committed release."""

import json
import os
import re
import subprocess
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

INTEGRATION_PATH = "custom_components/delonghi_comfort"
RELEASE_TAG_PATTERN = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
RELEASE_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
REQUIRED_DOCUMENTS = ("LICENSE", "NOTICE")


def committed(revision: str, path: str) -> bytes:
    """Read a file from the exact release commit."""
    return subprocess.check_output(["git", "show", f"{revision}:{path}"])


def main() -> None:
    """Validate release metadata and write a deterministic integration archive."""
    tag = os.environ["RELEASE_TAG"]
    revision = os.environ["RELEASE_SHA"]
    output = Path("dist/delonghi_comfort.zip")
    output.parent.mkdir(exist_ok=True)
    output.unlink(missing_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.unlink(missing_ok=True)

    if not RELEASE_TAG_PATTERN.fullmatch(tag):
        raise ValueError("Release tag must be vMAJOR.MINOR.PATCH")
    if not RELEASE_SHA_PATTERN.fullmatch(revision):
        raise ValueError("Release revision must be a full commit SHA")

    version = tag.removeprefix("v")
    manifest_data = committed(revision, f"{INTEGRATION_PATH}/manifest.json")
    manifest = json.loads(manifest_data)
    if manifest["version"] != "0.0.0":
        raise ValueError("Committed manifest version must be 0.0.0")
    if committed(revision, "version.txt").decode().strip() != version:
        raise ValueError("Release version files disagree")
    release_manifest = json.loads(committed(revision, ".release-please-manifest.json"))
    if release_manifest["."] != version:
        raise ValueError("Release version files disagree")
    manifest_data, replacements = re.subn(
        rb'(?m)^([ \t]*"version"[ \t]*:[ \t]*)"0\.0\.0"(?=[ \t]*,?[ \t]*\r?$)',
        lambda match: match.group(1) + json.dumps(version).encode(),
        manifest_data,
    )
    if replacements != 1:
        raise ValueError("Expected exactly one manifest version placeholder")
    manifest["version"] = version
    if json.loads(manifest_data) != manifest:
        raise ValueError("Updated manifest does not match the release version")
    documents = {name: committed(revision, name) for name in REQUIRED_DOCUMENTS}

    try:
        source = subprocess.check_output(
            [
                "git",
                "archive",
                "--format=zip",
                "--mtime=1980-01-01T00:00:00Z",
                f"{revision}:{INTEGRATION_PATH}",
            ],
        )
        with (
            ZipFile(BytesIO(source)) as source_archive,
            ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive,
        ):
            names = source_archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Integration archive contains duplicate members")
            for info in source_archive.infolist():
                path = PurePosixPath(info.filename)
                if (
                    path.is_absolute()
                    or "\\" in info.filename
                    or (path.parts and path.parts[0].endswith(":"))
                    or ".." in path.parts
                    or "__pycache__" in path.parts
                    or path.suffix in (".pyc", ".pyo")
                    or (info.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    raise ValueError("Unexpected integration archive member")
                content = (
                    manifest_data
                    if info.filename == "manifest.json"
                    else source_archive.read(info)
                )
                archive.writestr(info, content)
            for name, content in documents.items():
                if name in names:
                    raise ValueError(
                        "Duplicate license document in integration archive"
                    )
                info = ZipInfo(name)
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content)
            if not {"manifest.json", "__init__.py", *REQUIRED_DOCUMENTS} <= set(
                archive.namelist()
            ):
                raise ValueError("Required integration archive members are missing")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
