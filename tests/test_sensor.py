"""Unit tests for sensor platform in Shade Complete."""

from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE

from custom_components.shade_complete.const import (
    CONF_BATTERY_MAX,
    CONF_BATTERY_MIN,
    CONF_BATTERY_MODE,
    CONF_BATTERY_SENSOR,
    CONF_NAME,
    CONF_TARGET_COVER,
)
from custom_components.shade_complete.sensor import (
    CalibratedBatterySensor,
    async_setup_entry,
)


@pytest.fixture
def mock_config_entry():
    """Create a mock ConfigEntry with battery parameters."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_batt"
    entry.data = {
        CONF_NAME: "Guest Room Shade",
        CONF_TARGET_COVER: "cover.guest_shade",
        CONF_BATTERY_SENSOR: "sensor.guest_shade_voltage",
        CONF_BATTERY_MODE: "voltage",
        CONF_BATTERY_MIN: 6.4,
        CONF_BATTERY_MAX: 8.4,
        "battery_auto_learn": True,
        "battery_smoothing_factor": 0.5,
    }
    entry.options = {}
    return entry


async def test_battery_sensor_properties_and_updates(mock_hass, mock_config_entry):
    """Test battery sensor properties, value calculation, and attributes."""
    sensor = CalibratedBatterySensor(
        mock_hass,
        mock_config_entry,
        "cover.guest_shade",
        "sensor.guest_shade_voltage",
        "Guest Room Shade",
    )
    sensor.async_write_ha_state = MagicMock()

    assert sensor.name == "Guest Room Shade Battery"
    assert sensor.unique_id == "test_entry_batt_cover.guest_shade_battery"
    assert sensor.device_class == SensorDeviceClass.BATTERY
    assert sensor.native_unit_of_measurement == PERCENTAGE
    assert sensor.native_value is None

    # Simulate raw voltage update: 7.4 V (midpoint between 6.4 and 8.4)
    event = MagicMock()
    event.data = {"new_state": MagicMock(state="7.4")}
    mock_hass.states.get.return_value = MagicMock(state="open")  # Not moving

    sensor._async_battery_state_changed(event)
    assert sensor.native_value == 50
    assert sensor.async_write_ha_state.called

    attrs = sensor.extra_state_attributes
    assert attrs["raw_battery"] == 7.4
    assert attrs["calibrated_percent"] == 50
    assert attrs["learned_min"] == 6.4
    assert attrs["learned_max"] == 8.4
    assert attrs["calibration_samples"] == 1


async def test_battery_sensor_motor_movement_inhibit(mock_hass, mock_config_entry):
    """Test that voltage sag during motor movement does not corrupt battery percentage."""
    sensor = CalibratedBatterySensor(
        mock_hass,
        mock_config_entry,
        "cover.guest_shade",
        "sensor.guest_shade_voltage",
        "Guest Room Shade",
    )
    sensor.async_write_ha_state = MagicMock()

    # Initial stable state at 7.4 V (50%)
    mock_hass.states.get.return_value = MagicMock(state="open")
    sensor._async_battery_state_changed(MagicMock(data={"new_state": MagicMock(state="7.4")}))
    assert sensor.native_value == 50

    # Motor starts moving, state becomes "closing", voltage drops to 6.2 V
    mock_hass.states.get.return_value = MagicMock(state="closing")
    sensor._async_battery_state_changed(MagicMock(data={"new_state": MagicMock(state="6.2")}))

    # Percentage must remain 50%, not drop to 0%
    assert sensor.native_value == 50


async def test_battery_sensor_manual_calibration_service(mock_hass, mock_config_entry):
    """Test manual calibration adjustments via service call."""
    sensor = CalibratedBatterySensor(
        mock_hass,
        mock_config_entry,
        "cover.guest_shade",
        "sensor.guest_shade_voltage",
        "Guest Room Shade",
    )
    sensor.async_write_ha_state = MagicMock()

    # Feed 7.0 V
    mock_hass.states.get.return_value = MagicMock(state="open")
    sensor._async_battery_state_changed(MagicMock(data={"new_state": MagicMock(state="7.0")}))

    # Manually re-calibrate range to 6.0 - 8.0 V
    sensor.set_calibration(6.0, 8.0)
    assert sensor.engine.learned_min == 6.0
    assert sensor.engine.learned_max == 8.0
    # 7.0 is exactly 50% between 6.0 and 8.0
    assert sensor.native_value == 50
    assert sensor.async_write_ha_state.called


async def test_sensor_async_setup_entry(mock_hass, mock_config_entry):
    """Test setup entry registers entity when battery sensor is configured."""
    async_add = MagicMock()
    await async_setup_entry(mock_hass, mock_config_entry, async_add)
    assert async_add.called
    assert isinstance(async_add.call_args[0][0][0], CalibratedBatterySensor)

    # Omitted battery sensor -> no entities added
    async_add.reset_mock()
    mock_config_entry.data[CONF_BATTERY_SENSOR] = None
    await async_setup_entry(mock_hass, mock_config_entry, async_add)
    assert not async_add.called
