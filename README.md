# De'Longhi Comfort for Home Assistant

[![English](https://img.shields.io/badge/lang-en-blue)](README.md)
[![日本語](https://img.shields.io/badge/lang-ja-lightgrey)](README.ja.md)
[![Validate](https://github.com/sayurin/delonghi-comfort-integration/actions/workflows/validate.yml/badge.svg)](https://github.com/sayurin/delonghi-comfort-integration/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/sayurin/delonghi-comfort-integration)](https://github.com/sayurin/delonghi-comfort-integration/blob/main/LICENSE)
[![Version](https://img.shields.io/github/v/release/sayurin/delonghi-comfort-integration)](https://github.com/sayurin/delonghi-comfort-integration/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/sayurin/delonghi-comfort-integration/latest/total)](https://github.com/sayurin/delonghi-comfort-integration/releases/latest)
[![Stars](https://img.shields.io/github/stars/sayurin/delonghi-comfort-integration?style=flat&color=gold)](https://github.com/sayurin/delonghi-comfort-integration)

An unofficial Home Assistant integration for De'Longhi Multi Dynamic Heaters.
It requires **Home Assistant 2026.11.0 or later**, a De'Longhi Comfort account,
and an internet connection.

This integration uses an unofficial cloud API, which may change or stop working.
It is not affiliated with or endorsed by De'Longhi and is provided without
warranty. Do not use it as a substitute for the heater's safety controls.

## Which De'Longhi integration?

Both integrations appear in Home Assistant as **De'Longhi Comfort**, but they
support different apps. This repository supports the original
**De'Longhi Comfort** app. The standard Marketplace listing
[comfort-hub/delonghi-comfort-ha](https://github.com/comfort-hub/delonghi-comfort-ha)
also calls itself **De'Longhi Comfort**, but despite the name, it does not
support the **De'Longhi Comfort** app; it supports the newer **My Comfort Hub**
app instead. They are not interchangeable, and both cannot be installed at the
same time because they use the same integration domain. Check which app an
integration supports before installing it.

## Features and limitations

- Controls supported `DL-heater` devices: heat/off, target temperature from
  10–28 °C in 0.5 °C steps, presets, power limit, room temperature, display
  brightness, Eco mode, and child lock.
- English and Japanese translations are included. Polling is configurable from
  **5 to 300 seconds** (60 seconds by default per device). Expired credentials
  can be renewed through Home Assistant's reauthentication flow.
- Power controls set the maximum output; the displayed output is the current
  value and may be lower while the heater regulates the temperature.
- Weekly schedules, OFF timers, alarms, and temperature-unit controls are not
  available in Home Assistant. Use the app or heater controls for these
  functions. Unsupported models do not receive controls, and setup is not
  available for accounts containing only unsupported models.
- Hardware testing has been performed with the MDHAA15WIFI-BK. Other models
  and credential-expiry/recovery scenarios have not all been tested with
  physical devices.

## Installation

This integration is not included in the Marketplace's standard catalog. To
install it through Home Assistant's built-in **Marketplace**, add it as a custom
repository:

1. Open **Marketplace > Integrations** and choose **Custom repositories**.
2. Add `https://github.com/sayurin/delonghi-comfort-integration` as an
   **Integration**.
3. Install **De'Longhi Comfort** and restart Home Assistant if prompted.
4. Go to **Settings > Devices & services > Add integration**, select
   **De'Longhi Comfort**, and enter your account details.

Do not install this integration alongside another integration with the
`delonghi_comfort` domain.

## Diagnostics and support

Download diagnostics from an account or device menu. Account diagnostics include
all devices on the account; device diagnostics include only the selected device.
Diagnostics do not control or register devices. Identifiers, credentials, and
unrecognized text are excluded or redacted, but numeric telemetry and selected
model/version text remain. Review the entire file before sharing it.

For help, open an
[issue](https://github.com/sayurin/delonghi-comfort-integration/issues) with
the Home Assistant and integration versions, device model, a description of the
problem, and sanitized logs. Do not share passwords, tokens, email addresses,
DSNs, or serial numbers. Home Assistant's Config Entry storage is not guaranteed
to be encrypted; protect your configuration, backups, and logs.

## License

See [LICENSE](LICENSE) and [NOTICE](NOTICE) for license and third-party
attribution information.
