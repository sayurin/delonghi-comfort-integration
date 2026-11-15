# Contributing

## Commit messages and pull request titles

Use English Conventional Commit headers for commit messages and pull request
titles:

```text
<type>(<optional-scope>)<optional-!>: <description>
```

Use any lowercase type name; the examples below are not an exhaustive list.
The scope and `!` are optional. Use `!` to mark a breaking change. Keep the
description concise and start it with a verb.

Examples:

```text
fix: handle expired sessions
feat(config-flow): add reauthentication
docs: clarify Marketplace installation
feat!: remove legacy authentication
```

Release Please uses commit messages on `main` to determine the next version:
`fix` indicates a patch, `feat` a minor release, and `!` a breaking change.
Use other types for changes that do not add a user-facing feature or fix.

Pull request titles must follow the same format and pass the **PR title** check.
Any lowercase Conventional Commit type is accepted; the check does not limit
the type list. Non-merge commits in a pull request are checked as well. When
squash-merging, use the pull request title as the squash commit subject so the
merged commit follows the same convention.

## Development checks

Use Python 3.14.2 and uv 0.13.1 or later. The two test environments keep the
minimum supported Home Assistant release and the latest locked release separate:

```shell
uv sync --locked --extra dev --extra ha-minimum
uv run --locked --extra dev --extra ha-minimum pytest
uv sync --locked --extra dev --extra ha-latest
uv run --locked --extra dev --extra ha-latest pytest
uv run --locked --extra dev --extra ha-latest prek run --all-files
uv audit --locked
gh actions-lock
```

The uv project is development-only (`package = false`); its placeholder project
version is not the integration version. Release Please continues to update the
integration manifest and `version.txt`.

The Home Assistant test plugin version is locked to the corresponding Home
Assistant release. Upgrade those versions together when refreshing the
development lockfile. Install the `gh actions-lock` extension at v0.4.1 to
update workflow pins; do not edit `.github/workflows/actions.lock` by hand.
Pytest runs the existing `unittest.TestCase` regressions as well as native
pytest lifecycle tests using the plugin's `hass` and `MockConfigEntry` helpers.

## Draft release recovery

The Release workflow normally creates a draft from a Release Please PR. To
rebuild a missing or invalid ZIP, manually run the workflow with the existing
draft tag (for example, `v0.2.1`). The workflow verifies the tag, committed
manifest/version, and draft status before replacing `delonghi_comfort.zip`.
The same-named asset is replaced with `--clobber`; do not run recovery while
someone is publishing the release. Published releases are not valid recovery
targets, and publication remains a human action.
