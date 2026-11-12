"""Validate pull request titles against the repository's commit convention."""

import os
import re
import sys

TITLE_PATTERN = re.compile(
    r"(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\([a-z0-9][a-z0-9._/-]*\))?!?: \S[^\r\n]*"
)


def is_valid_title(title: str) -> bool:
    """Return whether a title uses the accepted Conventional Commit format."""
    return TITLE_PATTERN.fullmatch(title) is not None


def main() -> int:
    title = os.environ.get("PR_TITLE", "")
    if is_valid_title(title):
        print("PR title follows the required format.")
        return 0

    print(
        "Invalid PR title. Use "
        "'<type>(<optional-scope>)<optional-!>: <description>' "
        "with an allowed lowercase type.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
