"""Shared Conventional Commit subject validation."""

import re

SUBJECT_PATTERN = re.compile(r"[a-z][a-z0-9-]*(?:\([^\()\r\n]+\))?!?: \S[^\r\n]*")


def is_conventional_subject(subject: str) -> bool:
    """Return whether a commit subject follows the Conventional Commits format."""
    return SUBJECT_PATTERN.fullmatch(subject) is not None
