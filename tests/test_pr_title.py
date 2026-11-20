"""Tests for pull request title validation."""

import pytest

from scripts.check_pr_title import is_valid_title


@pytest.mark.parametrize(
    "title",
    (
        "fix: handle expired sessions",
        "feat(config-flow): add reauthentication",
        "feat!: remove legacy authentication",
        "fix(auth)!: reject expired tokens",
        "docs: clarify Marketplace installation",
        "deps: update a dependency",
        "chore(scope with spaces): describe the change",
    ),
)
def test_accepts_conventional_commit_titles(title):
    assert is_valid_title(title)


def test_rejects_unsupported_commit_type():
    assert not is_valid_title("release: publish a preview")


@pytest.mark.parametrize(
    "title",
    (
        "Handle expired sessions",
        "Fix: handle expired sessions",
        "fix:",
        "feat(): add reauthentication",
        "feat: add reauthentication\nBREAKING CHANGE: details",
    ),
)
def test_rejects_nonconforming_titles(title):
    assert not is_valid_title(title)
