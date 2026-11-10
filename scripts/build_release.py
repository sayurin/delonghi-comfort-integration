"""Build reproducible release layouts from a version-matched Git tag."""

import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

INTEGRATION = "custom_components/delonghi_comfort"
DOCUMENTS = ("README.md", "LICENSE", "NOTICE")


def build_release(repository: Path, tag: str, output: Path) -> tuple[Path, Path]:
    """Package the tagged tree, never the dirty or untracked working directory."""
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Release tag must be vMAJOR.MINOR.PATCH")
    revision = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
        text=True,
    ).strip()
    archive = subprocess.check_output(
        ["git", "-C", str(repository), "archive", "--format=tar", revision, INTEGRATION, *DOCUMENTS]
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        files = {}
        for member in source:
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("Release sources must not contain links or special files")
            if "__pycache__" in Path(member.name).parts or member.name.endswith((".pyc", ".pyo")):
                continue
            stream = source.extractfile(member)
            if stream is None:
                raise ValueError("Unable to read a committed release file")
            files[member.name] = stream.read()
    manifest = json.loads(files[f"{INTEGRATION}/manifest.json"])
    if manifest["version"] != tag.removeprefix("v"):
        raise ValueError("Release tag does not match the committed manifest version")
    if any(document not in files for document in DOCUMENTS):
        raise ValueError("Release documentation or license notice is missing")

    output.mkdir(parents=True, exist_ok=True)
    integration_zip = output / "delonghi_comfort.zip"
    complete_zip = output / f"delonghi-comfort-integration-{tag}.zip"
    with (
        ZipFile(integration_zip, "w", compression=ZIP_DEFLATED) as integration,
        ZipFile(complete_zip, "w", compression=ZIP_DEFLATED) as complete,
    ):
        for path, content in sorted(files.items()):
            info = ZipInfo(path)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            complete.writestr(info, content)
            if path.startswith(f"{INTEGRATION}/"):
                info = ZipInfo(path.removeprefix("custom_components/"))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                integration.writestr(info, content)
    return integration_zip, complete_zip


def main() -> None:
    """Build archives or exit with the exact validation error."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    try:
        archives = build_release(repository, args.tag, args.output)
    except (ValueError, KeyError) as err:
        parser.exit(1, f"Release validation failed: {err}\n")
    for archive in archives:
        print(archive)


if __name__ == "__main__":
    main()
