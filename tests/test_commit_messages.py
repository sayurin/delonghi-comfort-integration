"""Tests for commit and pull request title validation."""

import pytest

from scripts.check_commit_messages import is_conventional_subject, main


@pytest.mark.parametrize(
    "subject",
    (
        "fix: handle expired sessions",
        "feat(config-flow): add reauthentication",
        "feat!: remove legacy authentication",
        "fix(auth)!: reject expired tokens",
        "deps: update a runtime dependency",
        "chore(main): release 0.2.1",
    ),
)
def test_accepts_conventional_commit_subjects(subject):
    assert is_conventional_subject(subject)


@pytest.mark.parametrize(
    "subject",
    (
        "Fix: handle expired sessions",
        "release: publish a draft",
        "fix:",
        "feat(): add reauthentication",
        "feat: add reauthentication\nBREAKING CHANGE: details",
    ),
)
def test_rejects_malformed_commit_subjects(subject):
    assert not is_conventional_subject(subject)


def test_cli_checks_non_merge_commits_and_pull_request_title(mocker):
    run = mocker.patch("scripts.check_commit_messages.subprocess.run")
    run.return_value.stdout = "fix: correct behavior\nnot conventional\n"
    mocker.patch(
        "sys.argv",
        [
            "check_commit_messages.py",
            "base",
            "head",
            "--title",
            "feat: add feature",
        ],
    )

    assert main() == 1
    assert "--no-merges" in run.call_args.args[0]


def test_cli_passes_when_commits_and_title_are_valid(mocker):
    run = mocker.patch("scripts.check_commit_messages.subprocess.run")
    run.return_value.stdout = "fix: correct behavior\n"
    mocker.patch(
        "sys.argv",
        [
            "check_commit_messages.py",
            "base",
            "head",
            "--title",
            "feat: add feature",
        ],
    )

    assert main() == 0
