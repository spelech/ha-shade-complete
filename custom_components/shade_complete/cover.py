"""Cover entity implementations for Shade Complete."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_INACTIVE_REASON,
    ATTR_IS_MOVING,
    ATTR_LAST_COMMAND_TIME,
    ATTR_MANUAL_OVERRIDE,
    ATTR_PROXIED_ENTITY,
    ATTR_TARGET_POSITION,
    ATTR_TRACKING_STATUS,
    CONF_AZIMUTH_TOLERANCE,
    CONF_ELEVATION_HIGH,
    CONF_ELEVATION_LOW,
    CONF_ENABLE_AUTO_CLOSE,
    CONF_ENABLE_OVERRIDE_TIMEOUT,
    CONF_MODE,
    CONF_OVERRIDE_TIMEOUT_MINUTES,
    CONF_POSITION_OFFSET,
    CONF_POSITION_SENSITIVITY,
    CONF_TARGET_COVER,
    CONF_TARGET_COVERS,
    CONF_TRACKING_END_TIME,
    CONF_TRACKING_START_TIME,
    CONF_TRAVEL_TIME_SECONDS,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_DIRECTION,
    DEFAULT_AZIMUTH_TOLERANCE,
    DEFAULT_ELEVATION_HIGH,
    DEFAULT_ELEVATION_LOW,
    DEFAULT_OVERRIDE_TIMEOUT_MINUTES,
    DEFAULT_POSITION_OFFSET,
    DEFAULT_POSITION_SENSITIVITY,
    DEFAULT_TRACKING_END_TIME,
    DEFAULT_TRACKING_START_TIME,
    DEFAULT_TRAVEL_TIME_SECONDS,
    DEFAULT_WINDOW_DIRECTION,
    MODE_GROUP,
    MODE_SMART_SHADE,
    MODE_TILT_ONLY,
)
from .device import async_get_device_info_for_target
from .engine.schedule_engine import ScheduleClosingEngine
from .engine.sun_engine import SunTrackingEngine

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the cover entities from a config entry."""
    data = {**config_entry.data, **config_entry.options}
    mode = data.get(CONF_MODE, MODE_SMART_SHADE)
    name = data.get(CONF_NAME, "Shade Complete")

    entities: list[CoverEntity] = []

    if mode == MODE_TILT_ONLY:
        target = data.get(CONF_TARGET_COVER)
        if target:
            entities.append(TiltCoverEntity(hass, config_entry, target, name))
    elif mode == MODE_GROUP:
        targets = data.get(CONF_TARGET_COVERS, [])
        if targets:
            entities.append(GroupShadeCover(hass, config_entry, targets, name))
    else:
        # Default: MODE_SMART_SHADE
        target = data.get(CONF_TARGET_COVER)
        if target:
            entities.append(SmartTrackingShadeCover(hass, config_entry, target, name))

    async_add_entities(entities, True)
    return True


class SmartTrackingShadeCover(CoverEntity):
    """Smart sun tracking cover entity with manual override arbitration and auto-close."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        target_entity_id: str,
        name: str,
    ) -> None:
        """Initialize the tracking cover."""
        self.hass = hass
        self._config_entry = config_entry
        self._target_entity_id = target_entity_id
        self._custom_name = name

        self._attr_unique_id = f"{config_entry.entry_id}_{target_entity_id}_smart"
        self._current_position: int | None = None
        self._target_position: int | None = None
        self._last_set_position: int | None = None
        self._requested_position: int | None = None
        self._is_moving: bool = False
        self._is_manual_override: bool = False
        self._tracking_active: bool = False
        self._inactive_reason: str = "Initializing"
        self._last_command_time: datetime | None = None

        self._travel_unsub: Any = None
        self._override_unsub: Any = None
        self._schedule_unsub: Any = None
        self._initialized: bool = False

        # Schedule engine
        self._schedule_engine = ScheduleClosingEngine(
            enabled=self._config.get(CONF_ENABLE_AUTO_CLOSE, False),
            target_time=self._config.get("auto_close_time", "21:30:00"),
        )

    @property
    def _config(self) -> dict[str, Any]:
        """Merge entry data and dynamic options."""
        return {**self._config_entry.data, **self._config_entry.options}

    @property
    def name(self) -> str:
        """Return friendly name."""
        return self._custom_name

    @property
    def device_info(self) -> DeviceInfo:
        """Co-locate on the physical device card."""
        return async_get_device_info_for_target(
            self.hass,
            self._target_entity_id,
            self._custom_name,
            self._config_entry.entry_id,
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return the current shade position."""
        return self._current_position

    @property
    def is_closed(self) -> bool | None:
        """Return if shade is closed."""
        if self._current_position is None:
            return None
        return self._current_position == 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic state attributes."""
        return {
            ATTR_PROXIED_ENTITY: self._target_entity_id,
            ATTR_TRACKING_STATUS: "Active" if self._tracking_active else "Inactive",
            ATTR_INACTIVE_REASON: self._inactive_reason,
            ATTR_TARGET_POSITION: self._target_position,
            ATTR_MANUAL_OVERRIDE: self._is_manual_override,
            ATTR_IS_MOVING: self._is_moving,
            ATTR_LAST_COMMAND_TIME: self._last_command_time.isoformat()
            if self._last_command_time
            else None,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to entity state changes and interval timers."""
        # Track physical shade state
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._target_entity_id], self._async_target_state_changed
            )
        )

        # Track sun position
        self.async_on_remove(
            async_track_state_change_event(self.hass, ["sun.sun"], self._async_sun_state_changed)
        )

        # Track weather if configured
        weather_ent = self._config.get(CONF_WEATHER_ENTITY)
        if weather_ent:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [weather_ent], self._async_sun_state_changed
                )
            )

        # Minute ticker for scheduled closing and solar re-checks
        self.async_on_remove(
            async_track_time_interval(self.hass, self._async_periodic_check, timedelta(minutes=1))
        )

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, self._async_initial_update)

    async def _async_initial_update(self, event: Any = None) -> None:
        """Synchronize baseline state after HA starts."""
        self._async_sync_physical_state()
        self._last_set_position = self._current_position
        self._initialized = True
        await self._async_evaluate_sun_tracking()
        self.async_write_ha_state()

    @callback
    def _async_sync_physical_state(self) -> None:
        """Sync position from physical entity."""
        target_state = self.hass.states.get(self._target_entity_id)
        if target_state and target_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            pos = target_state.attributes.get(ATTR_POSITION)
            if pos is not None:
                try:
                    self._current_position = int(pos)
                except (ValueError, TypeError):
                    pass

    async def _async_target_state_changed(self, event: Any) -> None:
        """Handle physical shade position updates and detect manual intervention."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        new_pos = new_state.attributes.get(ATTR_POSITION)
        if new_pos is None:
            return

        try:
            pos_int = int(new_pos)
        except (ValueError, TypeError):
            return

        self._current_position = pos_int

        if not self._initialized:
            return

        # Suppress override logic during our own commanded motion
        if self._is_moving:
            self.async_write_ha_state()
            return

        sensitivity = int(self._config.get(CONF_POSITION_SENSITIVITY, DEFAULT_POSITION_SENSITIVITY))
        if self._last_set_position is not None:
            delta = abs(pos_int - self._last_set_position)
            if delta > sensitivity:
                _LOGGER.info(
                    "Manual override detected for %s (Expected: %s, Current: %s, Delta: %s)",
                    self.name,
                    self._last_set_position,
                    pos_int,
                    delta,
                )
                await self._async_trigger_manual_override(
                    f"Manual move detected (Position {pos_int}%)"
                )
            else:
                self._last_set_position = pos_int
        else:
            self._last_set_position = pos_int

        self.async_write_ha_state()

    async def _async_trigger_manual_override(self, reason: str) -> None:
        """Engage manual override lock and schedule timeout."""
        self._is_manual_override = True
        self._tracking_active = False

        if self._override_unsub:
            self._override_unsub()
            self._override_unsub = None

        enable_timeout = self._config.get(CONF_ENABLE_OVERRIDE_TIMEOUT, True)
        if enable_timeout:
            duration = int(
                self._config.get(CONF_OVERRIDE_TIMEOUT_MINUTES, DEFAULT_OVERRIDE_TIMEOUT_MINUTES)
            )
            self._inactive_reason = f"{reason} - Resumes in {duration}m"
            self._override_unsub = async_call_later(
                self.hass, timedelta(minutes=duration), self._async_reset_manual_override
            )
        else:
            self._inactive_reason = reason

        self.async_write_ha_state()

    async def _async_reset_manual_override(self, now: Any = None) -> None:
        """Clear manual override and resume automatic solar tracking."""
        _LOGGER.info("Resetting manual override for %s", self.name)
        self._is_manual_override = False
        self._override_unsub = None
        self._async_sync_physical_state()
        self._last_set_position = self._current_position
        await self._async_evaluate_sun_tracking()
        self.async_write_ha_state()

    async def _async_command_move(self, position: int) -> None:
        """Command target shade to position with travel verification."""
        clamped = max(0, min(100, int(position)))
        self._requested_position = clamped
        self._is_moving = True
        self._last_command_time = dt_util.utcnow()

        if self._travel_unsub:
            self._travel_unsub()

        travel_time = int(self._config.get(CONF_TRAVEL_TIME_SECONDS, DEFAULT_TRAVEL_TIME_SECONDS))
        self._travel_unsub = async_call_later(self.hass, travel_time, self._async_verify_movement)

        await self.hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": self._target_entity_id, "position": clamped},
            blocking=False,
            context=self._context,
        )

    async def _async_verify_movement(self, now: Any = None) -> None:
        """Verify the shade reached commanded position after travel duration."""
        self._is_moving = False
        self._travel_unsub = None
        self._async_sync_physical_state()

        if self._current_position is None or self._requested_position is None:
            return

        # If difference > 5%, the movement was halted or intercepted
        if abs(self._current_position - self._requested_position) > 5:
            _LOGGER.warning(
                "Motion intercepted for %s! Requested %s%%, stopped at %s%%",
                self.name,
                self._requested_position,
                self._current_position,
            )
            reason = (
                f"Movement intercepted (Req: {self._requested_position}%, "
                f"at: {self._current_position}%)"
            )
            await self._async_trigger_manual_override(reason)
        else:
            self._last_set_position = self._current_position

        self.async_write_ha_state()

    async def _async_sun_state_changed(self, event: Any) -> None:
        """Handle sun state change event."""
        await self._async_evaluate_sun_tracking()

    async def _async_periodic_check(self, now: datetime) -> None:
        """Periodic check for scheduled auto-closing and sun updates."""
        # 1. Evaluate scheduled closing
        if self._schedule_engine.should_trigger_close(
            current_dt=now,
            is_closed=bool(self.is_closed),
        ):
            _LOGGER.info("Scheduled evening auto-close triggered for %s", self.name)
            self._inactive_reason = "Scheduled evening close"
            await self._async_command_move(0)
            return

        # 2. Re-evaluate sun tracking
        await self._async_evaluate_sun_tracking()

    async def _async_evaluate_sun_tracking(self) -> None:
        """Run the pure SunTrackingEngine against current sensor state."""
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state:
            self._tracking_active = False
            self._inactive_reason = "sun.sun entity unavailable"
            self.async_write_ha_state()
            return

        weather_state = None
        weather_ent = self._config.get(CONF_WEATHER_ENTITY)
        if weather_ent:
            w_obj = self.hass.states.get(weather_ent)
            if w_obj:
                weather_state = w_obj.state

        now_time = dt_util.now().time()
        start_t = dt_util.parse_time(
            self._config.get(CONF_TRACKING_START_TIME, DEFAULT_TRACKING_START_TIME)
        ) or dt_util.parse_time("08:00:00")
        end_t = dt_util.parse_time(
            self._config.get(CONF_TRACKING_END_TIME, DEFAULT_TRACKING_END_TIME)
        ) or dt_util.parse_time("21:00:00")

        result = SunTrackingEngine.evaluate(
            sun_state=sun_state.state,
            sun_azimuth=float(sun_state.attributes.get("azimuth", 0)),
            sun_elevation=float(sun_state.attributes.get("elevation", 0)),
            window_direction=self._config.get(CONF_WINDOW_DIRECTION, DEFAULT_WINDOW_DIRECTION),
            azimuth_tolerance=float(
                self._config.get(CONF_AZIMUTH_TOLERANCE, DEFAULT_AZIMUTH_TOLERANCE)
            ),
            elevation_low=float(self._config.get(CONF_ELEVATION_LOW, DEFAULT_ELEVATION_LOW)),
            elevation_high=float(self._config.get(CONF_ELEVATION_HIGH, DEFAULT_ELEVATION_HIGH)),
            current_time=now_time,
            tracking_start_time=start_t,
            tracking_end_time=end_t,
            weather_state=weather_state,
            is_manual_override=self._is_manual_override,
            position_offset=int(self._config.get(CONF_POSITION_OFFSET, DEFAULT_POSITION_OFFSET)),
        )

        self._tracking_active = result["active"]
        self._inactive_reason = result["reason"]
        self._target_position = result["target_position"]

        # If sun is below horizon, ensure shade is closed and reset daily override
        if sun_state.state == "below_horizon":
            if self._is_manual_override:
                await self._async_reset_manual_override()
            if self._current_position is not None and self._current_position > 0:
                await self._async_command_move(0)
            self.async_write_ha_state()
            return

        # If active and position delta exceeds sensitivity, command motion
        sensitivity = int(self._config.get(CONF_POSITION_SENSITIVITY, DEFAULT_POSITION_SENSITIVITY))
        if (
            self._tracking_active
            and not self._is_moving
            and self._target_position is not None
            and self._current_position is not None
        ):
            if abs(self._current_position - self._target_position) >= sensitivity:
                _LOGGER.info(
                    "Sun tracking moving %s to %s%% (%s)",
                    self.name,
                    self._target_position,
                    self._inactive_reason,
                )
                await self._async_command_move(self._target_position)

        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the shade."""
        await self._async_command_move(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the shade."""
        await self._async_command_move(0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop shade motion."""
        await self.hass.services.async_call(
            "cover",
            "stop_cover",
            {"entity_id": self._target_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set position."""
        pos = kwargs.get(ATTR_POSITION)
        if pos is not None:
            await self._async_command_move(pos)


class TiltCoverEntity(CoverEntity):
    """Virtual tilt entity mapping standard cover commands to physical tilt."""

    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        target_entity_id: str,
        name: str,
    ) -> None:
        """Initialize the virtual tilt entity."""
        self.hass = hass
        self._config_entry = config_entry
        self._target_entity_id = target_entity_id
        self._custom_name = f"{name} Tilt" if not name.endswith("Tilt") else name
        self._attr_unique_id = f"{config_entry.entry_id}_{target_entity_id}_tilt"

    @property
    def name(self) -> str:
        """Return the name."""
        return self._custom_name

    @property
    def device_info(self) -> DeviceInfo:
        """Co-locate on the physical device card."""
        return async_get_device_info_for_target(
            self.hass,
            self._target_entity_id,
            self._custom_name,
            self._config_entry.entry_id,
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return current position mapped to target tilt position."""
        target_state = self.hass.states.get(self._target_entity_id)
        if target_state:
            tilt_pos = target_state.attributes.get("current_tilt_position")
            if tilt_pos is not None:
                try:
                    return int(tilt_pos)
                except (ValueError, TypeError):
                    pass
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return if closed."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    async def async_added_to_hass(self) -> None:
        """Track state changes."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._target_entity_id], self._async_target_state_changed
            )
        )

    @callback
    def _async_target_state_changed(self, event: Any) -> None:
        """Write state on target update."""
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open tilt."""
        await self.hass.services.async_call(
            "cover",
            "open_cover_tilt",
            {"entity_id": self._target_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close tilt."""
        await self.hass.services.async_call(
            "cover",
            "close_cover_tilt",
            {"entity_id": self._target_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop tilt."""
        await self.hass.services.async_call(
            "cover",
            "stop_cover_tilt",
            {"entity_id": self._target_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set tilt position."""
        pos = kwargs.get(ATTR_POSITION)
        if pos is not None:
            await self.hass.services.async_call(
                "cover",
                "set_cover_tilt_position",
                {"entity_id": self._target_entity_id, "tilt_position": pos},
                blocking=True,
                context=self._context,
            )


class GroupShadeCover(CoverEntity):
    """Synchronized group controller aggregating multiple shades."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        member_entities: list[str],
        name: str,
    ) -> None:
        """Initialize the group cover."""
        self.hass = hass
        self._config_entry = config_entry
        self._member_entities = member_entities
        self._custom_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_group"

    @property
    def name(self) -> str:
        """Return the group name."""
        return self._custom_name

    @property
    def current_cover_position(self) -> int | None:
        """Calculate average position across all member shades."""
        positions: list[int] = []
        for ent in self._member_entities:
            st = self.hass.states.get(ent)
            if st:
                pos = st.attributes.get(ATTR_POSITION)
                if pos is not None:
                    try:
                        positions.append(int(pos))
                    except (ValueError, TypeError):
                        pass
        if not positions:
            return None
        return int(round(sum(positions) / len(positions)))

    @property
    def is_closed(self) -> bool | None:
        """Return True if all members are closed."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    async def async_added_to_hass(self) -> None:
        """Track member state changes."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._member_entities, self._async_member_state_changed
            )
        )

    @callback
    def _async_member_state_changed(self, event: Any) -> None:
        """Update aggregate state on member state change."""
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open all member covers concurrently."""
        tasks = [
            self.hass.services.async_call("cover", "open_cover", {"entity_id": ent}, blocking=True)
            for ent in self._member_entities
        ]
        await asyncio.gather(*tasks)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close all member covers concurrently."""
        tasks = [
            self.hass.services.async_call("cover", "close_cover", {"entity_id": ent}, blocking=True)
            for ent in self._member_entities
        ]
        await asyncio.gather(*tasks)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop all member covers concurrently."""
        tasks = [
            self.hass.services.async_call("cover", "stop_cover", {"entity_id": ent}, blocking=True)
            for ent in self._member_entities
        ]
        await asyncio.gather(*tasks)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set position for all member covers concurrently."""
        pos = kwargs.get(ATTR_POSITION)
        if pos is None:
            return
        tasks = [
            self.hass.services.async_call(
                "cover",
                "set_cover_position",
                {"entity_id": ent, "position": pos},
                blocking=True,
            )
            for ent in self._member_entities
        ]
        await asyncio.gather(*tasks)
