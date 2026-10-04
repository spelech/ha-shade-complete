"""Cover entity implementations for Shade Complete."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
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
    ATTR_AZIMUTH_TOLERANCE,
    ATTR_INACTIVE_REASON,
    ATTR_IS_MOVING,
    ATTR_LAST_COMMAND_TIME,
    ATTR_MANUAL_OVERRIDE,
    ATTR_PROXIED_ENTITY,
    ATTR_SOLAR_AZIMUTH,
    ATTR_SOLAR_ELEVATION,
    ATTR_TARGET_POSITION,
    ATTR_TRACKING_STATUS,
    ATTR_WINDOW_AZIMUTH,
    CONF_AUTO_CLOSE_MODE,
    CONF_AUTO_CLOSE_SUNSET_OFFSET,
    CONF_AUTO_CLOSE_TIME,
    CONF_AUTO_OPEN_MODE,
    CONF_AUTO_OPEN_POSITION,
    CONF_AUTO_OPEN_SUNRISE_OFFSET,
    CONF_AUTO_OPEN_TIME,
    CONF_AZIMUTH_TOLERANCE,
    CONF_ELEVATION_HIGH,
    CONF_ELEVATION_LOW,
    CONF_ENABLE_AUTO_CLOSE,
    CONF_ENABLE_AUTO_OPEN,
    CONF_ENABLE_OVERRIDE_TIMEOUT,
    CONF_ENABLE_SUN_TRACKING,
    CONF_ENABLE_TILT_INTERCEPT,
    CONF_HIDE_UNDERLYING,
    CONF_MODE,
    CONF_OVERRIDE_TIMEOUT_MINUTES,
    CONF_POSITION_OFFSET,
    CONF_POSITION_SENSITIVITY,
    CONF_TARGET_COVER,
    CONF_TARGET_COVERS,
    CONF_TILT_INTERCEPT_THRESHOLD,
    CONF_TRACKING_END_TIME,
    CONF_TRACKING_START_TIME,
    CONF_TRAVEL_TIME_SECONDS,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_DIRECTION,
    DEFAULT_AUTO_CLOSE_SUNSET_OFFSET,
    DEFAULT_AUTO_CLOSE_TIME,
    DEFAULT_AUTO_OPEN_POSITION,
    DEFAULT_AUTO_OPEN_SUNRISE_OFFSET,
    DEFAULT_AUTO_OPEN_TIME,
    DEFAULT_AZIMUTH_TOLERANCE,
    DEFAULT_ELEVATION_HIGH,
    DEFAULT_ELEVATION_LOW,
    DEFAULT_ENABLE_AUTO_CLOSE,
    DEFAULT_ENABLE_AUTO_OPEN,
    DEFAULT_ENABLE_SUN_TRACKING,
    DEFAULT_ENABLE_TILT_INTERCEPT,
    DEFAULT_HIDE_UNDERLYING,
    DEFAULT_OVERRIDE_TIMEOUT_MINUTES,
    DEFAULT_POSITION_OFFSET,
    DEFAULT_POSITION_SENSITIVITY,
    DEFAULT_TILT_INTERCEPT_THRESHOLD,
    DEFAULT_TRACKING_END_TIME,
    DEFAULT_TRACKING_START_TIME,
    DEFAULT_TRAVEL_TIME_SECONDS,
    DEFAULT_WINDOW_DIRECTION,
    DOMAIN,
    MODE_GROUP,
    MODE_SMART_SHADE,
    MODE_TILT_ONLY,
)
from .device import async_get_device_info_for_target, async_set_entity_hidden_state
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
            has_tilt = False
            for t in targets:
                target_state = hass.states.get(t)
                if target_state:
                    feat = target_state.attributes.get("supported_features", 0)
                    if feat and (
                        feat & (CoverEntityFeature.OPEN_TILT | CoverEntityFeature.SET_TILT_POSITION)
                    ):
                        has_tilt = True
                        break
                    if "current_tilt_position" in target_state.attributes:
                        has_tilt = True
                        break
            if has_tilt or data.get(CONF_ENABLE_TILT_INTERCEPT, False):
                entities.append(TiltCoverEntity(hass, config_entry, targets, name))
    else:
        # Default: MODE_SMART_SHADE
        target = data.get(CONF_TARGET_COVER)
        if target:
            entities.append(SmartTrackingShadeCover(hass, config_entry, target, name))
            # Auto-create TiltCoverEntity if target supports tilt or tilt intercept is enabled
            target_state = hass.states.get(target)
            has_tilt = False
            if target_state:
                feat = target_state.attributes.get("supported_features", 0)
                if feat and (
                    feat & (CoverEntityFeature.OPEN_TILT | CoverEntityFeature.SET_TILT_POSITION)
                ):
                    has_tilt = True
                elif "current_tilt_position" in target_state.attributes:
                    has_tilt = True
            if has_tilt or data.get(CONF_ENABLE_TILT_INTERCEPT, False):
                entities.append(TiltCoverEntity(hass, config_entry, target, name))

    async_add_entities(entities, True)
    return True


class BaseShadeCover(CoverEntity):
    """Base cover entity providing solar tracking, scheduling, and override arbitration."""

    _attr_device_class = CoverDeviceClass.SHADE

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize the base shade cover."""
        self.hass = hass
        self._config_entry = config_entry
        self._custom_name = name

        self._current_position: int | None = None
        self._target_position: int | None = None
        self._last_set_position: int | None = None
        self._requested_position: int | None = None
        self._is_moving: bool = False
        self._is_manual_override: bool = False
        self._tracking_active: bool = False
        self._inactive_reason: str = "Initializing"
        self._last_command_time: datetime | None = None
        self._last_position_change_time: datetime | None = None

        self._travel_unsub: Any = None
        self._override_unsub: Any = None
        self._initialized: bool = False

        self._schedule_engine = ScheduleClosingEngine(
            close_enabled=self._config.get(CONF_ENABLE_AUTO_CLOSE, DEFAULT_ENABLE_AUTO_CLOSE),
            close_mode=self._config.get(CONF_AUTO_CLOSE_MODE, "time"),
            close_time=self._config.get(CONF_AUTO_CLOSE_TIME, DEFAULT_AUTO_CLOSE_TIME),
            sunset_offset_minutes=int(
                self._config.get(CONF_AUTO_CLOSE_SUNSET_OFFSET, DEFAULT_AUTO_CLOSE_SUNSET_OFFSET)
            ),
            open_enabled=self._config.get(CONF_ENABLE_AUTO_OPEN, DEFAULT_ENABLE_AUTO_OPEN),
            open_mode=self._config.get(CONF_AUTO_OPEN_MODE, "time"),
            open_time=self._config.get(CONF_AUTO_OPEN_TIME, DEFAULT_AUTO_OPEN_TIME),
            sunrise_offset_minutes=int(
                self._config.get(CONF_AUTO_OPEN_SUNRISE_OFFSET, DEFAULT_AUTO_OPEN_SUNRISE_OFFSET)
            ),
            open_position=int(
                self._config.get(CONF_AUTO_OPEN_POSITION, DEFAULT_AUTO_OPEN_POSITION)
            ),
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
    def is_closed(self) -> bool | None:
        """Return if shade is closed."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    @property
    def _target_entities(self) -> list[str]:
        """Return list of underlying entity IDs controlled."""
        raise NotImplementedError

    @property
    def _hiding_target(self) -> str | list[str]:
        """Return target format for hide/unhide helper."""
        return self._target_entities

    @property
    def _proxied_entity_attr(self) -> str:
        """Return string representation of proxied entity for attributes."""
        raise NotImplementedError

    @property
    def _intercepted_reason_prefix(self) -> str:
        """Return prefix for intercepted motion override reason."""
        return "Movement intercepted"

    @property
    def _tilt_service_target(self) -> str | list[str]:
        """Return entity or entities to target for tilt services."""
        return self._target_entities if len(self._target_entities) > 1 else self._target_entities[0]

    @property
    def _supports_tilt(self) -> bool:
        """Check if any member shade supports tilt."""
        for ent in self._target_entities:
            st = self.hass.states.get(ent)
            if st and (
                st.attributes.get("supported_features", 0)
                & (CoverEntityFeature.OPEN_TILT | CoverEntityFeature.SET_TILT_POSITION)
                or "current_tilt_position" in st.attributes
            ):
                return True
        return False

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Return the supported features."""
        feat = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
        if self._supports_tilt:
            feat |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )
        return feat

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return target or aggregate tilt position."""
        positions: list[int] = []
        for ent in self._target_entities:
            st = self.hass.states.get(ent)
            if st:
                tilt_pos = st.attributes.get("current_tilt_position")
                if tilt_pos is not None:
                    try:
                        positions.append(int(tilt_pos))
                    except (ValueError, TypeError):
                        pass
        if not positions:
            return None
        return int(round(sum(positions) / len(positions)))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic state attributes including real-time solar geometry."""
        sun_state = self.hass.states.get("sun.sun")
        solar_elevation = None
        solar_azimuth = None
        if sun_state and sun_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                elev = sun_state.attributes.get("elevation")
                if elev is not None:
                    solar_elevation = round(float(elev), 1)
            except (ValueError, TypeError):
                pass
            try:
                azim = sun_state.attributes.get("azimuth")
                if azim is not None:
                    solar_azimuth = round(float(azim), 1)
            except (ValueError, TypeError):
                pass

        try:
            azim_tol = float(self._config.get(CONF_AZIMUTH_TOLERANCE, DEFAULT_AZIMUTH_TOLERANCE))
        except (ValueError, TypeError):
            azim_tol = DEFAULT_AZIMUTH_TOLERANCE

        win_dir = self._config.get(CONF_WINDOW_DIRECTION, DEFAULT_WINDOW_DIRECTION)
        win_azim = SunTrackingEngine.parse_window_azimuth(win_dir)

        is_tracking_enabled = bool(
            self._config.get(CONF_ENABLE_SUN_TRACKING, DEFAULT_ENABLE_SUN_TRACKING)
        )
        if not is_tracking_enabled:
            tracking_status = "Disabled"
        elif self._tracking_active:
            tracking_status = "Active"
        else:
            tracking_status = "Inactive"

        return {
            ATTR_PROXIED_ENTITY: self._proxied_entity_attr,
            ATTR_TRACKING_STATUS: tracking_status,
            ATTR_INACTIVE_REASON: self._inactive_reason,
            ATTR_TARGET_POSITION: self._target_position,
            ATTR_MANUAL_OVERRIDE: self._is_manual_override,
            ATTR_IS_MOVING: self._is_moving,
            ATTR_LAST_COMMAND_TIME: (
                self._last_command_time.isoformat() if self._last_command_time else None
            ),
            ATTR_SOLAR_ELEVATION: solar_elevation,
            ATTR_SOLAR_AZIMUTH: solar_azimuth,
            ATTR_WINDOW_AZIMUTH: win_azim,
            ATTR_AZIMUTH_TOLERANCE: azim_tol,
        }

    def _matches_service_target(self, target: str) -> bool:
        """Check if a service target matches this entity or members."""
        raise NotImplementedError

    def _async_setup_target_tracking(self) -> None:
        """Subscribe to target state change events."""
        raise NotImplementedError

    @callback
    def _async_sync_physical_state(self) -> None:
        """Sync position from physical entity/entities."""
        raise NotImplementedError

    def _record_commanded_position(self, clamped: int) -> None:
        """Record commanded position in tracking cache."""
        pass

    async def _async_dispatch_move(self, clamped: int) -> None:
        """Dispatch move command to physical entity/entities."""
        raise NotImplementedError

    async def _async_dispatch_stop(self) -> None:
        """Dispatch stop command to physical entity/entities."""
        raise NotImplementedError

    async def _async_command_tilt(self, tilt_position: int) -> None:
        """Command shade tilt directly."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Subscribe to entity state changes and interval timers."""
        self._async_setup_target_tracking()

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

        # Minute ticker for scheduled closing, opening, and solar re-checks
        self.async_on_remove(
            async_track_time_interval(self.hass, self._async_periodic_check, timedelta(minutes=1))
        )

        # Domain service event listeners
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_service_reset_override", self._async_handle_reset_service
            )
        )
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_service_trigger_auto_close", self._async_handle_close_service
            )
        )
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_service_trigger_auto_open", self._async_handle_open_service
            )
        )

        # Immediate sync with physical shade if already available
        self._async_sync_physical_state()
        if self._current_position is not None:
            self._last_set_position = self._current_position
            self._initialized = True

        if getattr(self.hass, "is_running", False) is True:
            self.hass.async_create_task(self._async_initial_update())
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, self._async_initial_update)

        # Hide underlying physical shade(s) from UI and voice assistants if enabled
        if self._config.get(CONF_HIDE_UNDERLYING, DEFAULT_HIDE_UNDERLYING):
            async_set_entity_hidden_state(self.hass, self._hiding_target, hidden=True)

    async def async_will_remove_from_hass(self) -> None:
        """Restore underlying cover visibility upon removal."""
        await super().async_will_remove_from_hass()
        async_set_entity_hidden_state(self.hass, self._hiding_target, hidden=False)

    async def _async_handle_reset_service(self, event: Any) -> None:
        """Handle reset override service event."""
        target = event.data.get("entity_id")
        if self._matches_service_target(target):
            await self._async_reset_manual_override()

    async def _async_handle_close_service(self, event: Any) -> None:
        """Handle manual trigger auto close service."""
        target = event.data.get("entity_id")
        if self._matches_service_target(target):
            _LOGGER.info("Manual trigger auto-close requested for %s", self.name)
            self._inactive_reason = "Service triggered close"
            await self._async_command_move(0)

    async def _async_handle_open_service(self, event: Any) -> None:
        """Handle manual trigger auto open service."""
        target = event.data.get("entity_id")
        if self._matches_service_target(target):
            _LOGGER.info("Manual trigger auto-open requested for %s", self.name)
            self._inactive_reason = "Service triggered open"
            await self._async_command_move(self._schedule_engine.open_position)

    async def _async_initial_update(self, event: Any = None) -> None:
        """Synchronize baseline state after HA starts."""
        self._async_sync_physical_state()
        self._last_set_position = self._current_position
        self._initialized = True
        await self._async_evaluate_sun_tracking()
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

        if self.hass is not None and getattr(self, "entity_id", None):
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
        """Command target shade(s) to position with travel verification."""
        clamped = max(0, min(100, int(position)))
        self._requested_position = clamped
        self._last_set_position = clamped
        self._record_commanded_position(clamped)
        self._is_moving = True
        self._last_command_time = dt_util.utcnow()
        self._last_position_change_time = dt_util.utcnow()

        if self._travel_unsub:
            self._travel_unsub()

        travel_time = int(self._config.get(CONF_TRAVEL_TIME_SECONDS, DEFAULT_TRAVEL_TIME_SECONDS))
        self._travel_unsub = async_call_later(self.hass, travel_time, self._async_verify_movement)

        await self._async_dispatch_move(clamped)

    async def _async_verify_movement(self, now: Any = None) -> None:
        """Verify the shade reached commanded position after travel duration."""
        self._travel_unsub = None
        self._async_sync_physical_state()

        if self._current_position is None or self._requested_position is None:
            self._is_moving = False
            return

        sensitivity = int(self._config.get(CONF_POSITION_SENSITIVITY, DEFAULT_POSITION_SENSITIVITY))
        tolerance = max(sensitivity, 10)

        # Reached commanded position within tolerance
        if abs(self._current_position - self._requested_position) <= tolerance:
            self._is_moving = False
            self._last_set_position = self._current_position
            self._async_sync_physical_state()
            self.async_write_ha_state()
            return

        # Target not reached yet - check if any target cover is still actively opening or closing
        for ent in self._target_entities:
            target_state = self.hass.states.get(ent)
            if target_state and target_state.state in ("opening", "closing"):
                _LOGGER.debug(
                    "Target %s still reported in transit (%s); extending verification",
                    ent,
                    target_state.state,
                )
                self._travel_unsub = async_call_later(self.hass, 10, self._async_verify_movement)
                return

        # Check if position was updated recently (within last 6 seconds)
        if self._last_position_change_time is not None:
            time_since_last_change = (
                dt_util.utcnow() - self._last_position_change_time
            ).total_seconds()
            if time_since_last_change < 6.0:
                _LOGGER.debug(
                    "Target %s recently changed position (%.1fs ago); extending verification",
                    self.name,
                    time_since_last_change,
                )
                self._travel_unsub = async_call_later(self.hass, 10, self._async_verify_movement)
                return

        # Motor stopped moving and didn't reach target: movement was halted or intercepted
        self._is_moving = False
        _LOGGER.warning(
            "Motion intercepted for %s! Requested %s%%, stopped at %s%%",
            self.name,
            self._requested_position,
            self._current_position,
        )
        reason = (
            f"{self._intercepted_reason_prefix} (Req: {self._requested_position}%, "
            f"at: {self._current_position}%)"
        )
        await self._async_trigger_manual_override(reason)
        self.async_write_ha_state()

    async def _async_sun_state_changed(self, event: Any) -> None:
        """Handle sun state change event."""
        await self._async_evaluate_sun_tracking()

    async def _async_periodic_check(self, now: datetime) -> None:
        """Periodic check for scheduled auto-closing, auto-opening, and sun updates."""
        # 1. Evaluate scheduled closing
        if self._schedule_engine.should_trigger_close(
            current_dt=now,
            is_closed=bool(self.is_closed),
        ):
            _LOGGER.info("Scheduled evening auto-close triggered for %s", self.name)
            self._inactive_reason = "Scheduled evening close"
            await self._async_command_move(0)
            return

        # 2. Evaluate scheduled opening
        if self._schedule_engine.should_trigger_open(
            current_dt=now,
            current_position=self.current_cover_position,
        ):
            _LOGGER.info("Scheduled morning auto-open triggered for %s", self.name)
            self._inactive_reason = "Scheduled morning open"
            await self._async_command_move(self._schedule_engine.open_position)
            return

        # 3. Re-evaluate sun tracking
        await self._async_evaluate_sun_tracking()

    async def _async_evaluate_sun_tracking(self) -> None:
        """Run the pure SunTrackingEngine against current sensor state."""
        if not self._config.get(CONF_ENABLE_SUN_TRACKING, DEFAULT_ENABLE_SUN_TRACKING):
            self._tracking_active = False
            self._inactive_reason = "Sun tracking disabled"
            self._target_position = None
            self.async_write_ha_state()
            return

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

        cur = self.current_cover_position

        # If sun is below horizon, ensure shade is closed and reset daily override
        if sun_state.state == "below_horizon":
            if self._is_manual_override:
                await self._async_reset_manual_override()
            if cur is not None and cur > 0:
                await self._async_command_move(0)
            self.async_write_ha_state()
            return

        # If not manually overridden, within tracking hours and position delta exceeds
        # sensitivity, command motion
        sensitivity = int(self._config.get(CONF_POSITION_SENSITIVITY, DEFAULT_POSITION_SENSITIVITY))
        if (
            not self._is_manual_override
            and not self._is_moving
            and self._target_position is not None
            and cur is not None
            and not self._inactive_reason.startswith("Outside tracking hours")
        ):
            if abs(cur - self._target_position) >= sensitivity:
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
        await self._async_trigger_manual_override("Manual open")
        await self._async_command_move(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the shade."""
        await self._async_trigger_manual_override("Manual close")
        await self._async_command_move(0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop shade motion."""
        await self._async_trigger_manual_override("Manual stop")
        self._is_moving = False
        if self._travel_unsub:
            self._travel_unsub()
            self._travel_unsub = None
        await self._async_dispatch_stop()
        if self.hass is not None and getattr(self, "entity_id", None):
            self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open shade tilt."""
        await self.hass.services.async_call(
            "cover",
            "open_cover_tilt",
            {"entity_id": self._tilt_service_target},
            blocking=True,
            context=self._context,
        )

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close shade tilt."""
        await self.hass.services.async_call(
            "cover",
            "close_cover_tilt",
            {"entity_id": self._tilt_service_target},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set shade tilt position."""
        tilt_position = kwargs.get(ATTR_TILT_POSITION, 0)
        await self.hass.services.async_call(
            "cover",
            "set_cover_tilt_position",
            {
                "entity_id": self._tilt_service_target,
                "tilt_position": max(0, min(100, int(tilt_position))),
            },
            blocking=True,
            context=self._context,
        )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop shade tilt movement."""
        await self.hass.services.async_call(
            "cover",
            "stop_cover_tilt",
            {"entity_id": self._tilt_service_target},
            blocking=True,
            context=self._context,
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set position with low-percentage tilt interception."""
        pos = kwargs.get(ATTR_POSITION)
        if pos is None:
            return

        await self._async_trigger_manual_override(f"Manual position {pos}%")

        tilt_intercept = self._config.get(CONF_ENABLE_TILT_INTERCEPT, DEFAULT_ENABLE_TILT_INTERCEPT)
        tilt_threshold = int(
            self._config.get(CONF_TILT_INTERCEPT_THRESHOLD, DEFAULT_TILT_INTERCEPT_THRESHOLD)
        )

        if tilt_intercept and 0 < pos <= tilt_threshold:
            scaled_tilt = int(round((pos / tilt_threshold) * 100))
            scaled_tilt = max(0, min(100, scaled_tilt))
            _LOGGER.info(
                "Low position %s%% intercepted on %s -> converted to tilt %s%%",
                pos,
                self.name,
                scaled_tilt,
            )
            await self._async_command_tilt(scaled_tilt)
            return

        await self._async_command_move(pos)


class SmartTrackingShadeCover(BaseShadeCover):
    """Smart sun tracking cover entity with manual override arbitration and auto-close."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        target_entity_id: str,
        name: str,
    ) -> None:
        """Initialize the tracking cover."""
        super().__init__(hass, config_entry, name)
        self._target_entity_id = target_entity_id
        self._attr_unique_id = f"{config_entry.entry_id}_{target_entity_id}_smart"

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
    def _target_entities(self) -> list[str]:
        """Return list of underlying entity IDs controlled."""
        return [self._target_entity_id]

    @property
    def _hiding_target(self) -> str:
        """Return string entity_id for hide/unhide helper."""
        return self._target_entity_id

    @property
    def _proxied_entity_attr(self) -> str:
        """Return string representation of proxied entity for attributes."""
        return self._target_entity_id

    def _matches_service_target(self, target: str) -> bool:
        """Check if a service target matches this entity or target."""
        return target in (self.entity_id, self._attr_unique_id, self._target_entity_id)

    def _async_setup_target_tracking(self) -> None:
        """Subscribe to target state change events."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._target_entity_id], self._async_target_state_changed
            )
        )

    @callback
    def _async_sync_physical_state(self) -> None:
        """Sync position from physical entity."""
        target_state = self.hass.states.get(self._target_entity_id)
        if target_state and target_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            pos = target_state.attributes.get(
                ATTR_CURRENT_POSITION, target_state.attributes.get(ATTR_POSITION)
            )
            if pos is not None:
                try:
                    self._current_position = int(pos)
                except (ValueError, TypeError):
                    pass

    async def _async_dispatch_move(self, clamped: int) -> None:
        """Dispatch move command to physical entity."""
        await self.hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": self._target_entity_id, "position": clamped},
            blocking=False,
            context=self._context,
        )

    async def _async_dispatch_stop(self) -> None:
        """Dispatch stop command to physical entity."""
        await self.hass.services.async_call(
            "cover",
            "stop_cover",
            {"entity_id": self._target_entity_id},
            blocking=True,
            context=self._context,
        )

    async def _async_command_tilt(self, tilt_position: int) -> None:
        """Command target shade tilt directly."""
        clamped = max(0, min(100, int(tilt_position)))
        await self.hass.services.async_call(
            "cover",
            "set_cover_tilt_position",
            {"entity_id": self._target_entity_id, "tilt_position": clamped},
            blocking=False,
            context=self._context,
        )

    async def _async_target_state_changed(self, event: Any) -> None:
        """Handle physical shade position updates and detect manual intervention."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        new_pos = new_state.attributes.get(
            ATTR_CURRENT_POSITION, new_state.attributes.get(ATTR_POSITION)
        )
        if new_pos is None:
            return

        try:
            pos_int = int(new_pos)
        except (ValueError, TypeError):
            return

        if self._current_position != pos_int:
            self._last_position_change_time = dt_util.utcnow()
        self._current_position = pos_int

        if not self._initialized:
            return

        # Handle state during our own commanded motion
        if self._is_moving:
            sensitivity = int(
                self._config.get(CONF_POSITION_SENSITIVITY, DEFAULT_POSITION_SENSITIVITY)
            )
            if (
                self._requested_position is not None
                and abs(pos_int - self._requested_position) <= max(sensitivity, 5)
            ):
                _LOGGER.debug(
                    "Commanded movement completed early for %s (pos: %s, target: %s)",
                    self.name,
                    pos_int,
                    self._requested_position,
                )
                self._is_moving = False
                self._last_set_position = pos_int
                if self._travel_unsub:
                    self._travel_unsub()
                    self._travel_unsub = None
            self.async_write_ha_state()
            return

        sensitivity = int(
            self._config.get(CONF_POSITION_SENSITIVITY, DEFAULT_POSITION_SENSITIVITY)
        )
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


class GroupShadeCover(BaseShadeCover):
    """Synchronized group controller aggregating multiple shades with sun tracking and schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        member_entities: list[str],
        name: str,
    ) -> None:
        """Initialize the group cover."""
        super().__init__(hass, config_entry, name)
        self._member_entities = member_entities
        self._attr_unique_id = f"{config_entry.entry_id}_group"
        self._last_member_positions: dict[str, int] = {}

    @property
    def device_info(self) -> DeviceInfo:
        """Co-locate on the group device card."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._config_entry.entry_id}_group")},
            name=self._custom_name,
            manufacturer="Shade Complete",
            model="Smart Shade Group",
        )

    @property
    def _target_entities(self) -> list[str]:
        """Return list of underlying member entity IDs."""
        return self._member_entities

    @property
    def _hiding_target(self) -> list[str]:
        """Return list of entity_ids for hide/unhide helper."""
        return self._member_entities

    @property
    def _proxied_entity_attr(self) -> str:
        """Return string representation of member entities for attributes."""
        return ", ".join(self._member_entities)

    @property
    def _intercepted_reason_prefix(self) -> str:
        """Return prefix for intercepted motion override reason."""
        return "Group motion intercepted"

    @property
    def current_cover_position(self) -> int | None:
        """Calculate average position across all member shades."""
        positions: list[int] = []
        for ent in self._member_entities:
            st = self.hass.states.get(ent)
            if st:
                pos = st.attributes.get(
                    ATTR_CURRENT_POSITION, st.attributes.get(ATTR_POSITION)
                )
                if pos is not None:
                    try:
                        positions.append(int(pos))
                    except (ValueError, TypeError):
                        pass
        if not positions:
            return None
        return int(round(sum(positions) / len(positions)))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic state attributes with member list."""
        attrs = super().extra_state_attributes
        attrs["member_entities"] = self._member_entities
        return attrs

    def _matches_service_target(self, target: str) -> bool:
        """Check if a service target matches this group or members."""
        return target in (self.entity_id, self._attr_unique_id) or target in self._member_entities

    def _async_setup_target_tracking(self) -> None:
        """Subscribe to member state change events."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._member_entities, self._async_member_state_changed
            )
        )

    @callback
    def _async_sync_physical_state(self) -> None:
        """Sync positions from member entities."""
        for ent in self._member_entities:
            st = self.hass.states.get(ent)
            if st and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                pos = st.attributes.get(
                    ATTR_CURRENT_POSITION, st.attributes.get(ATTR_POSITION)
                )
                if pos is not None:
                    try:
                        self._last_member_positions[ent] = int(pos)
                    except (ValueError, TypeError):
                        pass
        self._current_position = self.current_cover_position

    def _record_commanded_position(self, clamped: int) -> None:
        """Record commanded position in group member cache."""
        for ent in self._member_entities:
            self._last_member_positions[ent] = clamped

    async def _async_dispatch_move(self, clamped: int) -> None:
        """Dispatch move command to all member covers concurrently."""
        tasks = [
            self.hass.services.async_call(
                "cover",
                "set_cover_position",
                {"entity_id": ent, "position": clamped},
                blocking=False,
                context=self._context,
            )
            for ent in self._member_entities
        ]
        await asyncio.gather(*tasks)

    async def _async_dispatch_stop(self) -> None:
        """Dispatch stop command to all member covers concurrently."""
        tasks = [
            self.hass.services.async_call(
                "cover", "stop_cover", {"entity_id": ent}, blocking=True
            )
            for ent in self._member_entities
        ]
        await asyncio.gather(*tasks)

    async def _async_command_tilt(self, tilt_position: int) -> None:
        """Command all member shades tilt position concurrently."""
        clamped = max(0, min(100, int(tilt_position)))
        tasks = [
            self.hass.services.async_call(
                "cover",
                "set_cover_tilt_position",
                {"entity_id": ent, "tilt_position": clamped},
                blocking=False,
                context=self._context,
            )
            for ent in self._member_entities
        ]
        await asyncio.gather(*tasks)

    async def _async_member_state_changed(self, event: Any) -> None:
        """Update aggregate state on member change and detect manual override."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        new_pos = new_state.attributes.get(
            ATTR_CURRENT_POSITION, new_state.attributes.get(ATTR_POSITION)
        )
        if new_pos is not None:
            try:
                pos_int = int(new_pos)
            except (ValueError, TypeError):
                pos_int = None

            if pos_int is not None and self._initialized:
                if self._last_member_positions.get(entity_id) != pos_int:
                    self._last_position_change_time = dt_util.utcnow()

                if self._is_moving:
                    self._last_member_positions[entity_id] = pos_int
                    self._current_position = self.current_cover_position
                    sensitivity = int(
                        self._config.get(CONF_POSITION_SENSITIVITY, DEFAULT_POSITION_SENSITIVITY)
                    )
                    if (
                        self._requested_position is not None
                        and self._current_position is not None
                        and abs(self._current_position - self._requested_position)
                        <= max(sensitivity, 5)
                    ):
                        _LOGGER.debug(
                            "Group movement completed early for %s (pos: %s, target: %s)",
                            self.name,
                            self._current_position,
                            self._requested_position,
                        )
                        self._is_moving = False
                        self._last_set_position = self._current_position
                        if self._travel_unsub:
                            self._travel_unsub()
                            self._travel_unsub = None
                    self.async_write_ha_state()
                    return

                sensitivity = int(
                    self._config.get(CONF_POSITION_SENSITIVITY, DEFAULT_POSITION_SENSITIVITY)
                )
                last_pos = self._last_member_positions.get(entity_id)
                if last_pos is not None:
                    delta = abs(pos_int - last_pos)
                    if delta > sensitivity:
                        _LOGGER.info(
                            "Manual override detected on group member %s (Was: %s, Now: %s)",
                            entity_id,
                            last_pos,
                            pos_int,
                        )
                        await self._async_trigger_manual_override(
                            f"Manual move detected on {entity_id} ({pos_int}%)"
                        )
                self._last_member_positions[entity_id] = pos_int

        self._current_position = self.current_cover_position
        self.async_write_ha_state()


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
        target_entity_id: str | list[str],
        name: str,
    ) -> None:
        """Initialize the virtual tilt entity."""
        self.hass = hass
        self._config_entry = config_entry
        if isinstance(target_entity_id, list):
            self._target_entity_ids = target_entity_id
            self._target_entity_id = target_entity_id[0] if target_entity_id else ""
            self._is_group = True
            self._attr_unique_id = f"{config_entry.entry_id}_group_tilt"
        else:
            self._target_entity_ids = [target_entity_id]
            self._target_entity_id = target_entity_id
            self._is_group = False
            self._attr_unique_id = f"{config_entry.entry_id}_{target_entity_id}_tilt"

        self._custom_name = f"{name} Tilt" if not name.endswith("Tilt") else name

    @property
    def name(self) -> str:
        """Return the name."""
        return self._custom_name

    @property
    def device_info(self) -> DeviceInfo:
        """Co-locate on the physical device card or group card."""
        if self._is_group:
            return DeviceInfo(
                identifiers={(DOMAIN, f"{self._config_entry.entry_id}_group")},
                name=self._custom_name,
                manufacturer="Shade Complete",
                model="Smart Shade Group",
            )
        return async_get_device_info_for_target(
            self.hass,
            self._target_entity_id,
            self._custom_name,
            self._config_entry.entry_id,
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return current position mapped to target tilt position."""
        positions: list[int] = []
        for target in self._target_entity_ids:
            target_state = self.hass.states.get(target)
            if target_state:
                tilt_pos = target_state.attributes.get("current_tilt_position")
                if tilt_pos is not None:
                    try:
                        positions.append(int(tilt_pos))
                    except (ValueError, TypeError):
                        pass
        if not positions:
            return None
        return int(round(sum(positions) / len(positions)))

    @property
    def is_closed(self) -> bool | None:
        """Return if closed."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    @property
    def _config(self) -> dict[str, Any]:
        """Merge entry data and dynamic options."""
        return {**self._config_entry.data, **self._config_entry.options}

    async def async_added_to_hass(self) -> None:
        """Track state changes and optionally hide underlying cover in tilt-only mode."""
        if (
            self._config.get(CONF_HIDE_UNDERLYING, DEFAULT_HIDE_UNDERLYING)
            and self._config.get(CONF_MODE) == MODE_TILT_ONLY
        ):
            async_set_entity_hidden_state(self.hass, self._target_entity_ids, hidden=True)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._target_entity_ids, self._async_target_state_changed
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Restore underlying cover visibility upon removal."""
        await super().async_will_remove_from_hass()
        if self._config.get(CONF_MODE) == MODE_TILT_ONLY:
            async_set_entity_hidden_state(self.hass, self._target_entity_ids, hidden=False)

    @callback
    def _async_target_state_changed(self, event: Any) -> None:
        """Write state on target update."""
        self.async_write_ha_state()

    @property
    def _service_target(self) -> str | list[str]:
        """Return the target for service calls."""
        return self._target_entity_ids if self._is_group else self._target_entity_id

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open tilt."""
        await self.hass.services.async_call(
            "cover",
            "open_cover_tilt",
            {"entity_id": self._service_target},
            blocking=True,
            context=self._context,
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close tilt."""
        await self.hass.services.async_call(
            "cover",
            "close_cover_tilt",
            {"entity_id": self._service_target},
            blocking=True,
            context=self._context,
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop tilt."""
        await self.hass.services.async_call(
            "cover",
            "stop_cover_tilt",
            {"entity_id": self._service_target},
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
                {"entity_id": self._service_target, "tilt_position": pos},
                blocking=True,
                context=self._context,
            )
