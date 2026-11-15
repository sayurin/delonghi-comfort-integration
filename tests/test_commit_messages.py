"""Tests for commit and pull request title validation."""

import unittest
from unittest.mock import patch

from scripts.check_commit_messages import is_conventional_subject, main


class CommitMessageTests(unittest.TestCase):
    """Accept any valid lowercase type and reject malformed subjects."""

    def test_accepts_conventional_commit_subjects(self):
        for subject in (
            "fix: handle expired sessions",
            "feat(config-flow): add reauthentication",
            "feat!: remove legacy authentication",
            "fix(auth)!: reject expired tokens",
            "release: publish a draft",
        ):
            with self.subTest(subject=subject):
                self.assertTrue(is_conventional_subject(subject))

    def test_rejects_malformed_subjects(self):
        for subject in (
            "Fix: handle expired sessions",
            "fix:",
            "feat(): add reauthentication",
            "feat: add reauthentication\nBREAKING CHANGE: details",
        ):
            with self.subTest(subject=subject):
                self.assertFalse(is_conventional_subject(subject))

    @patch("scripts.check_commit_messages.subprocess.run")
    def test_cli_checks_non_merge_commits_and_pull_request_title(self, run):
        run.return_value.stdout = "fix: correct behavior\nnot conventional\n"
        with (
            patch(
                "sys.argv",
                [
                    "check_commit_messages.py",
                    "base",
                    "head",
                    "--title",
                    "feat: add feature",
                ],
            ),
        ):
            self.assertEqual(main(), 1)

        self.assertIn("--no-merges", run.call_args.args[0])

    @patch("scripts.check_commit_messages.subprocess.run")
    def test_cli_passes_when_commits_and_title_are_valid(self, run):
        run.return_value.stdout = "fix: correct behavior\n"
        with patch(
            "sys.argv",
            [
                "check_commit_messages.py",
                "base",
                "head",
                "--title",
                "feat: add feature",
            ],
        ):
            self.assertEqual(main(), 0)
