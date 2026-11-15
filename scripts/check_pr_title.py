"""Validate pull request titles against the repository's commit convention."""

import os
import sys

from scripts.commit_messages import is_conventional_subject


def is_valid_title(title: str) -> bool:
    """Return whether a title uses the accepted Conventional Commit format."""
    return is_conventional_subject(title)


def main() -> int:
    title = os.environ.get("PR_TITLE", "")
    if is_valid_title(title):
        print("PR title follows the required format.")
        return 0

    print(
        "Invalid PR title. Use "
        "'<lowercase-type>(<optional-scope>)<optional-!>: <description>'.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
