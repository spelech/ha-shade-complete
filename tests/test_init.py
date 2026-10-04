"""Unit tests for integration setup, unload, and custom services."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from custom_components.shade_complete import (
    async_reload_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.shade_complete.const import (
    DOMAIN,
    SERVICE_CALIBRATE_BATTERY,
    SERVICE_RESET_OVERRIDE,
    SERVICE_TRIGGER_AUTO_CLOSE,
    SERVICE_TRIGGER_AUTO_OPEN,
)


async def test_async_setup_and_services(mock_hass):
    """Test setup registers domain services and dispatches events."""
    assert await async_setup(mock_hass, {}) is True
    assert DOMAIN in mock_hass.data

    # Check services registered
    assert mock_hass.services.async_register.call_count == 4
    calls = [call[0][1] for call in mock_hass.services.async_register.call_args_list]
    assert SERVICE_CALIBRATE_BATTERY in calls
    assert SERVICE_RESET_OVERRIDE in calls
    assert SERVICE_TRIGGER_AUTO_CLOSE in calls
    assert SERVICE_TRIGGER_AUTO_OPEN in calls

    # Test calibrate_battery handler
    handler_map = {
        call[0][1]: call[0][2] for call in mock_hass.services.async_register.call_args_list
    }

    cal_call = MagicMock(data={"entity_id": "sensor.shade_battery", "min_val": 6.2, "max_val": 8.4})
    await handler_map[SERVICE_CALIBRATE_BATTERY](cal_call)
    mock_hass.bus.async_fire.assert_called_with(
        f"{DOMAIN}_service_calibrate_battery",
        {"entity_id": "sensor.shade_battery", "min_val": 6.2, "max_val": 8.4},
    )

    # Test reset_manual_override handler
    reset_call = MagicMock(data={"entity_id": "cover.office_shade"})
    await handler_map[SERVICE_RESET_OVERRIDE](reset_call)
    mock_hass.bus.async_fire.assert_called_with(
        f"{DOMAIN}_service_reset_override",
        {"entity_id": "cover.office_shade"},
    )

    # Test trigger_auto_close handler
    close_call = MagicMock(data={"entity_id": "cover.office_shade"})
    await handler_map[SERVICE_TRIGGER_AUTO_CLOSE](close_call)
    mock_hass.bus.async_fire.assert_called_with(
        f"{DOMAIN}_service_trigger_auto_close",
        {"entity_id": "cover.office_shade"},
    )

    # Test trigger_auto_open handler
    open_call = MagicMock(data={"entity_id": "cover.office_shade"})
    await handler_map[SERVICE_TRIGGER_AUTO_OPEN](open_call)
    mock_hass.bus.async_fire.assert_called_with(
        f"{DOMAIN}_service_trigger_auto_open",
        {"entity_id": "cover.office_shade"},
    )


async def test_async_setup_and_unload_entry(mock_hass):
    """Test config entry setup, forwarding, and unloading."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_456"
    entry.data = {"test": "data"}
    entry.options = {}

    assert await async_setup_entry(mock_hass, entry) is True
    assert mock_hass.data[DOMAIN]["test_entry_456"] == {"test": "data"}
    mock_hass.config_entries.async_forward_entry_setups.assert_called_with(
        entry, [Platform.COVER, Platform.SENSOR]
    )

    # Unload
    assert await async_unload_entry(mock_hass, entry) is True
    assert "test_entry_456" not in mock_hass.data[DOMAIN]


async def test_async_reload_entry(mock_hass):
    """Test reloading an entry upon options update."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_789"

    await async_reload_entry(mock_hass, entry)
    mock_hass.config_entries.async_reload.assert_called_with("test_entry_789")


async def test_multi_entity_services(mock_hass):
    """Test services handle multiple target entity IDs."""
    await async_setup(mock_hass, {})
    handler_map = {
        call[0][1]: call[0][2] for call in mock_hass.services.async_register.call_args_list
    }

    mock_hass.bus.async_fire.reset_mock()
    call = MagicMock(data={"entity_id": ["cover.shade_1", "cover.shade_2"]})
    await handler_map[SERVICE_RESET_OVERRIDE](call)
    assert mock_hass.bus.async_fire.call_count == 2
    mock_hass.bus.async_fire.assert_any_call(
        f"{DOMAIN}_service_reset_override", {"entity_id": "cover.shade_1"}
    )
    mock_hass.bus.async_fire.assert_any_call(
        f"{DOMAIN}_service_reset_override", {"entity_id": "cover.shade_2"}
    )

