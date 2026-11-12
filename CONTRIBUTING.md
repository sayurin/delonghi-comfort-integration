# Contributing

## Commit messages and pull request titles

Use English Conventional Commit headers for commit messages and pull request
titles:

```text
<type>(<optional-scope>)<optional-!>: <description>
```

Use a lowercase type from `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`,
`refactor`, `revert`, `style`, or `test`. The scope and `!` are optional. Use
`!` to mark a breaking change. Keep the description concise and start it with
a verb.

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
When squash-merging, use the pull request title as the squash commit subject so
the merged commit follows the same convention.
