# De'Longhi Comfort for Home Assistant

[![Validate](https://github.com/sayurin/delonghi-comfort-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/sayurin/delonghi-comfort-integration/actions/workflows/validate.yml)

An independently maintained custom integration for De'Longhi Multi Dynamic
Heaters, derived from
[philm5/delonghi-comfort-integration](https://github.com/philm5/delonghi-comfort-integration).
Upstream contributions remain welcome, but this fork does not require upstream
approval to maintain its own changes.

## Status and supported devices

**New releases are on hold pending the licensing and API-configuration review
described below.** A passing CI run does not resolve those questions.
This project is not advertised as part of the HACS default catalog.

- Only devices reporting `oem_model: DL-heater` are initialized.
- Unknown models, including previously enabled air conditioners and
  dehumidifiers, are skipped with a warning. An account with no supported devices
  cannot be configured. Existing registrations are not deleted automatically.
- The `delonghi_comfort` domain, account unique IDs and heater entity unique IDs
  remain unchanged. Back up your HA configuration before upgrading.
- Minimum Home Assistant: **2026.11.0**. Use the latest stable patch release.
  Earlier versions are no longer claimed as supported.
- A De'Longhi Comfort account with registered devices and internet access is
  required. This integration depends on unofficial cloud API behavior and can
  stop working if the vendor changes or withdraws that API.

### Heater entities

| Entity | Function |
| --- | --- |
| Climate | Heat/off; target temperature 10-28 C in 0.5 C steps |
| Climate presets | Day mode, Night mode, Antifrost, Manual |
| Climate power control | Existing fan-mode API labels: 0%, 20%, 40%, 60%, 80%, 100% |
| Temperature sensor | Room temperature |
| Display brightness select | Level 1, Level 2, Level 3 |
| Eco and child-lock switches | Enable/disable the corresponding device setting |

These are heater power levels, not a claim that the appliance has a fan.
Missing or unknown telemetry is reported as unknown rather than inventing a
valid preset, power level, or off state. Communication failures make entities
unavailable; failed commands raise a Home Assistant error instead of appearing
successful.

On 2026-11-10, the maintainer reported successful real-device checks on
**MDHAA15WIFI-BK** of readings, power, target temperature, presets, power levels,
brightness, Eco and child lock after the consent-signature fix. The rebuilt
integration was then checked after Core startup: display, operation and
integration reload were confirmed working. This is not a claim of testing every
`DL-heater` variant. Credential expiry and communication-loss recovery have
offline tests but have not been verified against the real service/device.
Test fixtures are synthetic, based on the existing implementation, not captured
device responses.

Additional models require documented properties and capabilities, sanitized test
fixtures, regression tests and an explicit record of hardware-tested versus
fixture-only behavior before being enabled.

## Installation

For development or an explicitly approved release:

1. In HACS, add `https://github.com/sayurin/delonghi-comfort-integration` as a
   custom repository with category **Integration**.
2. Install **De'Longhi Comfort** and restart Home Assistant.
3. Under **Settings > Devices & services**, add **De'Longhi Comfort**.
4. Enter your account email, password and language.

For manual installation, copy `custom_components/delonghi_comfort` into your
configuration's `custom_components` directory and restart HA. A release's
`delonghi_comfort.zip` contains the `delonghi_comfort/` directory; extract that
directory under `custom_components/`.

Do not install this copy alongside another integration using the same domain.
The generic radiator icon is original AI-assisted artwork, not a manufacturer
logo or an indication of endorsement.

## Configuration and troubleshooting

- The polling interval is an option: **5-300 seconds**, default **5 seconds per
  device**. Increase it to reduce cloud traffic.
- Expired credentials trigger HA's reauthentication flow. The replacement
  password is saved to the same entry; account and entity IDs do not change.
- Authentication failures, connection failures and unexpected API responses are
  reported separately. An empty successful device list is distinct from an
  outage.
- Account credentials are stored in the HA Config Entry, following HA's normal
  configuration model. That is not a guarantee of encryption. Protect your
  config directory, backups and logs; do not reuse production credentials in
  shared development configurations.
- Account credentials, API tokens, signatures, response bodies and device
  identifiers must not be included in logs or issue reports. Even when reporting
  an exception, review it and remove identifying information first.

Report reproducible problems using the
[issue tracker](https://github.com/sayurin/delonghi-comfort-integration/issues).
Include HA/integration versions, the product model, expected/actual behavior and
sanitized logs. Never include a password, token, email, serial number or DSN.

## Development and validation

Keep integration-specific changes and tests in this repository. Within the
`hass-dev` development workspace, use its normal Core venv and symlink:

```bash
# From hass-dev; stop HA before bootstrap or switching branches.
bash scripts/hass-dev.sh bootstrap
bash scripts/hass-dev.sh run delonghi python -m unittest discover -s tests -v
bash scripts/hass-dev.sh hass
```

DeLonghi is independent of the ECHONET Lite worktree sets and generator/release
workflow; do not combine `run delonghi` with `--set`. Do not install this
repository's `requirements.txt` over the workspace's Core venv: it already
provides the checked-out HA. For a standalone environment, `requirements.txt`
installs HA and its dependencies.

Offline tests cover authentication, token refresh, config/reauth/options flows,
setup and unload, model filtering, coordinator failures, heater telemetry and
commands, existing IDs, and release archives. They never access an account or
operate a heater. Unit tests do not replace human hardware checks.

CI runs those tests against the minimum HA version and latest stable HA,
plus official hassfest and HACS validation. HACS validation is a structural
check, not acceptance into the default catalog or legal clearance.

## Releases and unresolved prerequisites

No version bump, tag or release is implied by merging development changes.
The existing manifest version is retained until a separate release decision.

Before any independent release:

1. Resolve the third-party attribution/permission questions in [NOTICE](NOTICE).
   The integration and `rtfpessoa/delonghi-comfort-client` have Apache-2.0
   licenses. `duckwc/ECAMpy`, named as a source of authentication code, had no
   LICENSE file in its public repository when checked on 2026-11-10.
   Do not assume its code is Apache-2.0 or otherwise cleared for redistribution.
   Confirm the provenance of the used portions and obtain any required
   permission or a suitable replacement before release.
2. Resolve or explicitly document the provenance, permissions and vendor terms
   for the existing API/client/app configuration values. Their ownership and
   privilege level are not verified; they cannot currently be rotated by this
   maintainer. They are distinct from each user's login credentials. They have
   not been added to fixtures or copied into documentation, and moving them to
   an environment variable would not establish permission or secrecy. If any
   value is privileged or its use is not permitted, stop distribution and obtain
   a permitted authentication method.
3. Record the exact hardware model and validation scope, check restart/reload,
   authentication expiry, communication loss and recovery, and review CI results.
4. Update the manifest version in a reviewed commit and create a matching
   `v<version>` tag. The release builder reads the tag's committed tree and
   rejects tag/manifest mismatches; it never rewrites the manifest.
5. Only after explicit human approval, set the repository Actions variable
   `DELONGHI_RELEASE_APPROVED` to `true`. Until then the release workflow fails
   explicitly without publishing anything. The approved workflow creates a
   **draft** release for final human review, not an automatic public release.

The two archives contain only committed integration files and the documented
license/readme files, not local configuration, test output, bytecode, credentials
or private planning documents. Release notes are generated from the repository's
changes rather than claiming untested model support.

## License and acknowledgments

The original integration is distributed under [Apache-2.0](LICENSE).
Modifications to this fork are offered under the same license, subject to the
unresolved third-party provenance described above; this does not relicense code
owned by others. Existing third-party notices are retained in [NOTICE](NOTICE).

Thanks to [philm5](https://github.com/philm5),
[rtfpessoa/delonghi-comfort-client](https://github.com/rtfpessoa/delonghi-comfort-client),
[duckwc/ECAMpy](https://github.com/duckwc/ECAMpy) and other contributors.
Development and the generic brand icon have used AI assistance.

This unofficial integration is provided as-is, without warranty or manufacturer
endorsement. Review behavior before relying on it; never use it as a substitute
for an appliance's physical safety controls.
