"""Shared Conventional Commit subject validation."""

import re

SUBJECT_PATTERN = re.compile(
    r"(?P<type>[a-z][a-z0-9-]*)(?:\([^()\r\n]+\))?!?: \S[^\r\n]*"
)
ALLOWED_TYPES = frozenset(
    {
        "feat",
        "fix",
        "perf",
        "deps",
        "revert",
        "docs",
        "style",
        "chore",
        "refactor",
        "test",
        "build",
        "ci",
    }
)


def is_conventional_subject(subject: str) -> bool:
    """Return whether a commit subject follows the Conventional Commits format."""
    match = SUBJECT_PATTERN.fullmatch(subject)
    return match is not None and match.group("type") in ALLOWED_TYPES
