"""Sensor entity implementations for Shade Complete."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    ATTR_CALIBRATED_PERCENT,
    ATTR_CALIBRATION_SAMPLES,
    ATTR_IS_CHARGING,
    ATTR_LEARNED_MAX,
    ATTR_LEARNED_MIN,
    ATTR_RAW_BATTERY,
    CONF_BATTERY_AUTO_LEARN,
    CONF_BATTERY_MAX,
    CONF_BATTERY_MIN,
    CONF_BATTERY_MODE,
    CONF_BATTERY_SENSOR,
    CONF_BATTERY_SMOOTHING_FACTOR,
    CONF_NAME,
    CONF_TARGET_COVER,
    DEFAULT_BATTERY_AUTO_LEARN,
    DEFAULT_BATTERY_MAX_VOLTAGE,
    DEFAULT_BATTERY_MIN_VOLTAGE,
    DEFAULT_BATTERY_MODE,
    DEFAULT_BATTERY_SMOOTHING,
)
from .device import async_get_device_info_for_target
from .engine.battery_engine import BatteryCalibrationEngine

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up sensor entities from config entry."""
    data = {**config_entry.data, **config_entry.options}
    battery_sensor_id = data.get(CONF_BATTERY_SENSOR)
    target_cover_id = data.get(CONF_TARGET_COVER)
    name = data.get(CONF_NAME, "Shade Complete")

    entities: list[SensorEntity] = []

    if battery_sensor_id and target_cover_id:
        entities.append(
            CalibratedBatterySensor(
                hass,
                config_entry,
                target_cover_id,
                battery_sensor_id,
                name,
            )
        )

    if entities:
        async_add_entities(entities, True)
    return True


class CalibratedBatterySensor(SensorEntity):
    """Adaptive calibrated battery level sensor learning actual 0-100 discharge scale."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        target_cover_id: str,
        battery_sensor_id: str,
        name: str,
    ) -> None:
        """Initialize calibrated battery sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._target_cover_id = target_cover_id
        self._battery_sensor_id = battery_sensor_id
        self._custom_name = f"{name} Battery"

        self._attr_unique_id = f"{config_entry.entry_id}_{target_cover_id}_battery"

        # Initialize calibration engine from config options
        data = {**config_entry.data, **config_entry.options}
        mode = data.get(CONF_BATTERY_MODE, DEFAULT_BATTERY_MODE)
        nominal_min = float(data.get(CONF_BATTERY_MIN, DEFAULT_BATTERY_MIN_VOLTAGE))
        nominal_max = float(data.get(CONF_BATTERY_MAX, DEFAULT_BATTERY_MAX_VOLTAGE))
        auto_learn = bool(data.get(CONF_BATTERY_AUTO_LEARN, DEFAULT_BATTERY_AUTO_LEARN))
        smoothing = float(data.get(CONF_BATTERY_SMOOTHING_FACTOR, DEFAULT_BATTERY_SMOOTHING))

        self.engine = BatteryCalibrationEngine(
            mode=mode,
            nominal_min=nominal_min,
            nominal_max=nominal_max,
            auto_learn=auto_learn,
            smoothing_factor=smoothing,
        )

    @property
    def name(self) -> str:
        """Return sensor name."""
        return self._custom_name

    @property
    def device_info(self) -> DeviceInfo:
        """Co-locate on target physical shade device card."""
        return async_get_device_info_for_target(
            self.hass,
            self._target_cover_id,
            self._custom_name,
            self._config_entry.entry_id,
        )

    @property
    def native_value(self) -> int | None:
        """Return the calculated 0-100% calibrated battery level."""
        if self.engine.sample_count == 0:
            return None
        return self.engine.get_calibrated_percent()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rich calibration diagnostics."""
        state = self.engine.get_state()
        return {
            ATTR_RAW_BATTERY: state["raw_value"],
            "filtered_reading": state["filtered_value"],
            ATTR_CALIBRATED_PERCENT: state["calibrated_percent"],
            ATTR_LEARNED_MIN: state["learned_min"],
            ATTR_LEARNED_MAX: state["learned_max"],
            ATTR_CALIBRATION_SAMPLES: state["sample_count"],
            ATTR_IS_CHARGING: state["is_charging"],
            "source_entity": self._battery_sensor_id,
            "mode": self.engine.mode,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to raw battery state change events."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._battery_sensor_id],
                self._async_battery_state_changed,
            )
        )
        # Read initial state if available
        self._async_sync_state()

    @callback
    def _is_target_moving(self) -> bool:
        """Check if shade is currently in motion to avoid motor-sag drop."""
        target_state = self.hass.states.get(self._target_cover_id)
        if target_state:
            if target_state.state in ("opening", "closing"):
                return True
        return False

    @callback
    def _async_sync_state(self) -> None:
        """Read current value from raw battery entity."""
        state = self.hass.states.get(self._battery_sensor_id)
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            is_moving = self._is_target_moving()
            self.engine.update(state.state, is_moving=is_moving)

    @callback
    def _async_battery_state_changed(self, event: Any) -> None:
        """Process incoming raw battery sensor update."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        is_moving = self._is_target_moving()
        result = self.engine.update(new_state.state, is_moving=is_moving)
        if result is not None:
            self.async_write_ha_state()

    def set_calibration(self, min_val: float | None, max_val: float | None) -> None:
        """Service helper to manually adjust or reset learned bounds."""
        self.engine.set_calibration_bounds(min_val, max_val)
        self.async_write_ha_state()
