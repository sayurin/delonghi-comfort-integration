"""Home Assistant lifecycle tests using the official pytest fixtures."""

import json
from pathlib import Path

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.delonghi_comfort.const import DOMAIN

FIXTURE_DIR = Path(__file__).parent / "fixtures"


async def test_config_entry_sets_up_heater_entities(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    entity_registry: er.EntityRegistry,
    mocker,
) -> None:
    """Load the integration in Home Assistant and register its entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test@example.invalid", "password": "test-password"},
    )
    entry.add_to_hass(hass)

    api = mocker.MagicMock()
    api.authenticate = mocker.AsyncMock(return_value=True)
    api.get_devices = mocker.AsyncMock(
        return_value=[
            {"device": {"dsn": "test-dsn", "oem_model": "DL-heater"}},
        ]
    )
    api.get_device_properties = mocker.AsyncMock(
        return_value=json.loads((FIXTURE_DIR / "heater_properties.json").read_text())
    )

    mocker.patch("custom_components.delonghi_comfort.DeLonghiAPI", return_value=api)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    for platform, unique_id in (
        ("climate", "delonghi_heater_test-dsn"),
        ("select", "delonghi_heater_test-dsn_brightness"),
        ("sensor", "delonghi_heater_test-dsn_temperature"),
        ("switch", "delonghi_heater_test-dsn_eco"),
        ("switch", "delonghi_heater_test-dsn_lock"),
    ):
        entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
        assert entity_id is not None
        assert hass.states.get(entity_id) is not None
