# Contributing

## Commit messages and pull request titles

Use English Conventional Commit headers for commit messages and pull request
titles:

```text
<type>(<optional-scope>)<optional-!>: <description>
```

Use one of `feat`, `fix`, `perf`, `deps`, `revert`, `docs`, `style`, `chore`,
`refactor`, `test`, `build`, or `ci`.
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
Non-merge commits in a pull request are checked as well. When
squash-merging, use the pull request title as the squash commit subject so the
merged commit follows the same convention.

## Development checks

Use Python 3.14.2 and uv 0.13.1 or later:

```shell
uv sync --locked --extra dev
uv run --locked --extra dev pytest
uv run --locked --extra dev prek run --all-files
uv audit --locked
gh actions-lock
```

The uv project is development-only (`package = false`); its placeholder project
version is not the integration version. Release Please updates `version.txt`
and its own version manifest. The committed integration manifest stays at
`0.0.0`; the verified tag version is inserted into the release ZIP only.
Install the ZIP rather than the tag's source archive to obtain the release
version.

The Home Assistant test plugin and its matching Home Assistant version are
resolved in the development lockfile. The minimum supported Home Assistant
version is not separately tested. Install the `gh actions-lock` extension at
v0.4.1 to update workflow pins; do not edit `.github/workflows/actions.lock` by hand.
Tests use pytest functions, parametrization, and fixtures throughout. The
`pytest-mock` fixture provides mocks, while `pytest-homeassistant` supplies the
`hass` and `MockConfigEntry` helpers for Home Assistant lifecycle tests.

## Pre-release recovery

Set the release GitHub App's Client ID as the `APP_CLIENT_ID` Actions
variable and its private key as the `APP_PRIVATE_KEY` Actions secret.

Release Please creates a public pre-release and tag when its release PR is
merged. Before merging, review the release notes and state that pre-releases
may be delivered to HACS users who enable them. Do not mark the release as
latest; promote it to a stable release only after human verification.

To recover a missing ZIP, manually run the Release workflow on `main` with the
existing published pre-release tag (for example, `v0.2.1`). The workflow checks
out that tag and verifies its revision, version, and pre-release status before
building. It adds `delonghi_comfort.zip` only when missing; an existing asset
must match byte-for-byte or recovery fails. Never run recovery while someone
is promoting the release.
