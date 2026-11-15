"""Validate Conventional Commit subjects in a pull request."""

import argparse
import subprocess
import sys

from scripts.commit_messages import is_conventional_subject


def main() -> int:
    """Validate non-merge commit subjects and an optional pull request title."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("--title", help="pull request title to validate")
    args = parser.parse_args()

    subjects = subprocess.run(
        ["git", "log", "--format=%s", "--no-merges", f"{args.base}..{args.head}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    invalid_subjects = [
        subject for subject in subjects if not is_conventional_subject(subject)
    ]
    if args.title is not None and not is_conventional_subject(args.title):
        invalid_subjects.append(f"PR title: {args.title}")

    if invalid_subjects:
        for subject in invalid_subjects:
            print(f"Invalid Conventional Commit subject: {subject}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
