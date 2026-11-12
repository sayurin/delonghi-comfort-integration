"""Tests for pull request title validation."""

import unittest

from scripts.check_pr_title import is_valid_title


class PullRequestTitleTests(unittest.TestCase):
    """Validate accepted and rejected pull request title headers."""

    def test_accepts_conventional_commit_titles(self):
        for title in (
            "fix: handle expired sessions",
            "feat(config-flow): add reauthentication",
            "feat!: remove legacy authentication",
            "fix(auth)!: reject expired tokens",
            "docs: clarify Marketplace installation",
        ):
            with self.subTest(title=title):
                self.assertTrue(is_valid_title(title))

    def test_rejects_nonconforming_titles(self):
        for title in (
            "Handle expired sessions",
            "Fix: handle expired sessions",
            "feature: add a feature",
            "fix:",
            "feat(): add reauthentication",
            "feat: add reauthentication\nBREAKING CHANGE: details",
        ):
            with self.subTest(title=title):
                self.assertFalse(is_valid_title(title))
