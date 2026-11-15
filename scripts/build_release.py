"""Build the reproducible Marketplace ZIP for a committed release."""

import json
import os
import re
import subprocess
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

    manifest = json.loads(committed(revision, f"{INTEGRATION_PATH}/manifest.json"))
    if manifest["version"] != tag.removeprefix("v"):
        raise ValueError("Release tag does not match the committed manifest version")
    if committed(revision, "version.txt").decode().strip() != manifest["version"]:
        raise ValueError("Release version files disagree")
    documents = {name: committed(revision, name) for name in REQUIRED_DOCUMENTS}

    try:
        subprocess.run(
            [
                "git",
                "archive",
                "--format=zip",
                "--mtime=1980-01-01T00:00:00Z",
                f"--output={temporary}",
                f"{revision}:{INTEGRATION_PATH}",
            ],
            check=True,
        )
        with ZipFile(temporary, "a", compression=ZIP_DEFLATED) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Integration archive contains duplicate members")
            for info in archive.infolist():
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
