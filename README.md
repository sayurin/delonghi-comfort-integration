# De'Longhi Comfort for Home Assistant

[日本語](README.ja.md) |
[![Validate](https://github.com/sayurin/delonghi-comfort-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/sayurin/delonghi-comfort-integration/actions/workflows/validate.yml)

An independently maintained fork of
[philm5/delonghi-comfort-integration](https://github.com/philm5/delonghi-comfort-integration)
for De'Longhi Multi Dynamic Heaters. Requires **Home Assistant 2026.11.0+**,
a De'Longhi Comfort account and internet access.

**Public releases remain on hold** pending the license/API review below.
This project is not listed in the Marketplace default catalog. It uses an
unofficial cloud API that may change or stop working.

## Features and limits

- Only `DL-heater` devices receive entities: heat/off, 10–28 °C target in 0.5 °C
  steps, presets, power limit, room temperature, display brightness, Eco and lock.
- English and Japanese UI. Polling is configurable from **5–300 seconds**,
  default 5 per device. Expired credentials use HA's reauthentication flow.
- Power controls currently **set the maximum but display current output**.
  These may differ during temperature regulation; separating them is pending.
- Weekly schedules, OFF timers and alarm/unit controls are not exposed.
  Unknown models receive no controls; unsupported-only accounts cannot be added.
- Human checks covered MDHAA15WIFI-BK, reload and English/Japanese operation.
  Sanitized 32-property captures for API models `MDH Wifi` and `MDH15 Wifi` are
  in `tests/fixtures/`. Not all variants or credential-expiry/recovery paths
  have real-device validation.

## Installation

After an approved release is **published**:

1. In **Marketplace > overflow menu > Custom repositories**, add
   `https://github.com/sayurin/delonghi-comfort-integration` as **Integration**.
2. Install **De'Longhi Comfort** and restart HA.
3. Under **Settings > Devices & services**, add **De'Longhi Comfort** and enter
   your account details.

Marketplace uses `delonghi_comfort.zip` via the legacy-named `hacs.json`.
Draft releases/default-branch snapshots are not installable through this route.
For manual installation, extract the release ZIP **inside**
`config/custom_components/delonghi_comfort/`; `manifest.json` is at ZIP root.
For development, copy that directory from the checkout instead.
Do not install two integrations with the same `delonghi_comfort` domain.

## Upgrading and diagnostics

Account/entity unique IDs are preserved. Back up HA before upgrading.
Update automations/templates that use these old raw climate values:

| Previous value | New value |
| --- | --- |
| `Day mode`, `Night mode`, `Antifrost`, `Manual` | `day_mode`, `night_mode`, `antifrost`, `manual` |
| `0%`, `20%`, `40%`, `60%`, `80%`, `100%` | `"0"`, `"20"`, `"40"`, `"60"`, `"80"`, `"100"` |

Power values are strings: quote them in YAML. English display labels are unchanged.
Raw cloud `extra_state_attributes` were removed; use standard climate attributes,
dedicated entities or diagnostics instead. Existing registry names are not
forcibly renamed. The account language is separate from HA's UI language.

Download diagnostics from an account or device menu. Account diagnostics read
all its devices, including unsupported ones; device diagnostics read only that
device. Requests do not control/register devices. Identifiers, credentials and
unknown text are excluded/redacted; numeric telemetry and selected model/version
text remain. Per-device failures appear as errors; account/authentication failures
abort the download. Review the **entire file** before sharing or extracting fixtures.

Report problems in [Issues](https://github.com/sayurin/delonghi-comfort-integration/issues)
with versions, model, expected behavior and sanitized logs. Never share credentials,
tokens, email, DSNs or serials. Config Entry storage is not an encryption guarantee;
protect HA configuration, backups and logs.

## Development and releases

Use Python 3.14 in a virtual environment. From this repository's root:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

For runtime checks, install the integration in a separate Home Assistant test
instance. CI tests minimum/latest HA, hassfest and the legacy-named HACS validator.
Offline tests do not replace hardware checks.

Releases use Conventional Commits (`fix:`, `feat:`, `feat!:` with breaking-change
details). Every push to `main` maintains a release-please PR with version/CHANGELOG
updates. `version.txt`, the release manifest and integration version stay aligned.
The existing release-tag baseline is 0.1.1; the next release is 0.2.0.
Use `ci:` or `chore:` for automation-only changes, not `feat:`.

Use Conventional Commits for **PR titles** too, for example
`fix: handle expired sessions`, `feat: add a heater sensor`, or
`docs: clarify installation`. Normally use **Squash and merge**, keeping the PR
title as the squash commit subject. Preserve breaking-change details
(`BREAKING CHANGE:`) and any intentional `Release-As:` footer in the final commit
body; use a merge commit when a PR explicitly requires retaining its commits.

Merging the release PR creates a draft Release, and a
separate job tests its immutable commit, verifies versions and attaches the single
Marketplace ZIP (with LICENSE/NOTICE). GitHub supplies source archives automatically.
If packaging fails, use **Re-run failed jobs** on that run. Never publish a failed
or asset-less draft. Review assets/notes and **publish manually**. No tag-triggered
duplicate release workflow is used.

Release clearance still requires resolving ECAMpy-derived code permissions
([NOTICE](NOTICE)), and establishing provenance/permitted use of the fixed
API/client/app values. Existing public code is not proof of permission.
Complete remaining hardware checks and a clean Marketplace ZIP installation
before publication. CI success does not resolve these prerequisites.

## License

[Apache-2.0](LICENSE), subject to unresolved third-party provenance in
[NOTICE](NOTICE); no license is inferred for others' code. Derived from philm5,
rtfpessoa/delonghi-comfort-client and authentication work attributed to ECAMpy.
Code and the original generic radiator artwork used AI assistance. Unofficial,
without manufacturer endorsement or warranty; never replace appliance safety controls.
