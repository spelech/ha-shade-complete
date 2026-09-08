"""UI Config Flow and Options Flow for Shade Complete."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    BATTERY_MODE_PERCENTAGE,
    BATTERY_MODE_VOLTAGE,
    CONF_AUTO_CLOSE_TIME,
    CONF_AUTO_OPEN_POSITION,
    CONF_AUTO_OPEN_TIME,
    CONF_AZIMUTH_TOLERANCE,
    CONF_BATTERY_AUTO_LEARN,
    CONF_BATTERY_LOW_THRESHOLD,
    CONF_BATTERY_MAX,
    CONF_BATTERY_MIN,
    CONF_BATTERY_MODE,
    CONF_BATTERY_SENSOR,
    CONF_ELEVATION_HIGH,
    CONF_ELEVATION_LOW,
    CONF_ENABLE_AUTO_CLOSE,
    CONF_ENABLE_AUTO_OPEN,
    CONF_ENABLE_OVERRIDE_TIMEOUT,
    CONF_ENABLE_TILT_INTERCEPT,
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
    DEFAULT_AUTO_CLOSE_TIME,
    DEFAULT_AUTO_OPEN_POSITION,
    DEFAULT_AUTO_OPEN_TIME,
    DEFAULT_AZIMUTH_TOLERANCE,
    DEFAULT_BATTERY_AUTO_LEARN,
    DEFAULT_BATTERY_LOW_THRESHOLD,
    DEFAULT_BATTERY_MAX_VOLTAGE,
    DEFAULT_BATTERY_MIN_VOLTAGE,
    DEFAULT_BATTERY_MODE,
    DEFAULT_ELEVATION_HIGH,
    DEFAULT_ELEVATION_LOW,
    DEFAULT_ENABLE_AUTO_CLOSE,
    DEFAULT_ENABLE_AUTO_OPEN,
    DEFAULT_ENABLE_TILT_INTERCEPT,
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

DIRECTION_OPTIONS = [
    {"value": "N", "label": "North (0°)"},
    {"value": "NNE", "label": "North-Northeast (22.5°)"},
    {"value": "NE", "label": "Northeast (45°)"},
    {"value": "ENE", "label": "East-Northeast (67.5°)"},
    {"value": "E", "label": "East (90°)"},
    {"value": "ESE", "label": "East-Southeast (112.5°)"},
    {"value": "SE", "label": "Southeast (135°)"},
    {"value": "SSE", "label": "South-Southeast (157.5°)"},
    {"value": "S", "label": "South (180°)"},
    {"value": "SSW", "label": "South-Southwest (202.5°)"},
    {"value": "SW", "label": "Southwest (225°)"},
    {"value": "WSW", "label": "West-Southwest (247.5°)"},
    {"value": "W", "label": "West (270°)"},
    {"value": "WNW", "label": "West-Northwest (292.5°)"},
    {"value": "NW", "label": "Northwest (315°)"},
    {"value": "NNW", "label": "North-Northwest (337.5°)"},
]


class ShadeCompleteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shade Complete."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._mode: str = MODE_SMART_SHADE

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return dynamic options flow handler."""
        return ShadeCompleteOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Present mode selection menu."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["smart_shade", "tilt_only", "group"],
        )

    async def async_step_smart_shade(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure a full smart sun-tracking shade with schedule and battery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_MODE] = MODE_SMART_SHADE
            title = user_input.get(CONF_NAME, "Smart Shade")
            return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Smart Shade"): selector.TextSelector(),
                vol.Required(CONF_TARGET_COVER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="cover")
                ),
                vol.Optional(
                    CONF_WINDOW_DIRECTION, default=DEFAULT_WINDOW_DIRECTION
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=DIRECTION_OPTIONS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_AZIMUTH_TOLERANCE, default=DEFAULT_AZIMUTH_TOLERANCE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5.0, max=90.0, step=0.5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_ELEVATION_LOW, default=DEFAULT_ELEVATION_LOW
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-10.0, max=90.0, step=0.5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_ELEVATION_HIGH, default=DEFAULT_ELEVATION_HIGH
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-10.0, max=90.0, step=0.5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_TRACKING_START_TIME, default=DEFAULT_TRACKING_START_TIME
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_TRACKING_END_TIME, default=DEFAULT_TRACKING_END_TIME
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_POSITION_SENSITIVITY, default=DEFAULT_POSITION_SENSITIVITY
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=50, step=1, mode=selector.NumberSelectorMode.SLIDER
                    )
                ),
                vol.Optional(
                    CONF_POSITION_OFFSET, default=DEFAULT_POSITION_OFFSET
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-50, max=50, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(
                    CONF_TRAVEL_TIME_SECONDS, default=DEFAULT_TRAVEL_TIME_SECONDS
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=3, max=180, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_ENABLE_OVERRIDE_TIMEOUT, default=True
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_OVERRIDE_TIMEOUT_MINUTES, default=DEFAULT_OVERRIDE_TIMEOUT_MINUTES
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=1440, step=5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                # Scheduled closing & opening
                vol.Optional(
                    CONF_ENABLE_AUTO_CLOSE, default=DEFAULT_ENABLE_AUTO_CLOSE
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_AUTO_CLOSE_TIME, default=DEFAULT_AUTO_CLOSE_TIME
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_ENABLE_AUTO_OPEN, default=DEFAULT_ENABLE_AUTO_OPEN
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_AUTO_OPEN_TIME, default=DEFAULT_AUTO_OPEN_TIME
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_AUTO_OPEN_POSITION, default=DEFAULT_AUTO_OPEN_POSITION
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=100, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                # Tilt interception
                vol.Optional(
                    CONF_ENABLE_TILT_INTERCEPT, default=DEFAULT_ENABLE_TILT_INTERCEPT
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_TILT_INTERCEPT_THRESHOLD, default=DEFAULT_TILT_INTERCEPT_THRESHOLD
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=15, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                # Battery monitoring
                vol.Optional(CONF_BATTERY_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_BATTERY_MODE, default=DEFAULT_BATTERY_MODE
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": BATTERY_MODE_VOLTAGE, "label": "Voltage (V)"},
                            {
                                "value": BATTERY_MODE_PERCENTAGE,
                                "label": "Manufacturer Percentage (%)",
                            },
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_BATTERY_MIN, default=DEFAULT_BATTERY_MIN_VOLTAGE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0, max=100.0, step=0.1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_BATTERY_MAX, default=DEFAULT_BATTERY_MAX_VOLTAGE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0, max=100.0, step=0.1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_BATTERY_AUTO_LEARN, default=DEFAULT_BATTERY_AUTO_LEARN
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_BATTERY_LOW_THRESHOLD, default=DEFAULT_BATTERY_LOW_THRESHOLD
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=50, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )

        return self.async_show_form(step_id="smart_shade", data_schema=schema, errors=errors)

    async def async_step_tilt_only(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure a standalone virtual tilt entity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_MODE] = MODE_TILT_ONLY
            title = user_input.get(CONF_NAME, "Tilt Cover")
            return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Tilt Cover"): selector.TextSelector(),
                vol.Required(CONF_TARGET_COVER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="cover")
                ),
            }
        )

        return self.async_show_form(step_id="tilt_only", data_schema=schema, errors=errors)

    async def async_step_group(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure a synchronized group of shades."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_MODE] = MODE_GROUP
            title = user_input.get(CONF_NAME, "Shade Group")
            return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Shade Group"): selector.TextSelector(),
                vol.Required(CONF_TARGET_COVERS): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="cover", multiple=True)
                ),
                vol.Optional(
                    CONF_WINDOW_DIRECTION, default=DEFAULT_WINDOW_DIRECTION
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=DIRECTION_OPTIONS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_AZIMUTH_TOLERANCE, default=DEFAULT_AZIMUTH_TOLERANCE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5.0, max=90.0, step=0.5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_ELEVATION_LOW, default=DEFAULT_ELEVATION_LOW
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-10.0, max=90.0, step=0.5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_ELEVATION_HIGH, default=DEFAULT_ELEVATION_HIGH
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-10.0, max=90.0, step=0.5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_TRACKING_START_TIME, default=DEFAULT_TRACKING_START_TIME
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_TRACKING_END_TIME, default=DEFAULT_TRACKING_END_TIME
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_POSITION_SENSITIVITY, default=DEFAULT_POSITION_SENSITIVITY
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=50, step=1, mode=selector.NumberSelectorMode.SLIDER
                    )
                ),
                vol.Optional(
                    CONF_POSITION_OFFSET, default=DEFAULT_POSITION_OFFSET
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-50, max=50, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(
                    CONF_TRAVEL_TIME_SECONDS, default=DEFAULT_TRAVEL_TIME_SECONDS
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=3, max=180, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_ENABLE_OVERRIDE_TIMEOUT, default=True
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_OVERRIDE_TIMEOUT_MINUTES, default=DEFAULT_OVERRIDE_TIMEOUT_MINUTES
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=1440, step=5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                # Scheduled closing & opening
                vol.Optional(
                    CONF_ENABLE_AUTO_CLOSE, default=DEFAULT_ENABLE_AUTO_CLOSE
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_AUTO_CLOSE_TIME, default=DEFAULT_AUTO_CLOSE_TIME
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_ENABLE_AUTO_OPEN, default=DEFAULT_ENABLE_AUTO_OPEN
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_AUTO_OPEN_TIME, default=DEFAULT_AUTO_OPEN_TIME
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_AUTO_OPEN_POSITION, default=DEFAULT_AUTO_OPEN_POSITION
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=100, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                # Tilt interception
                vol.Optional(
                    CONF_ENABLE_TILT_INTERCEPT, default=DEFAULT_ENABLE_TILT_INTERCEPT
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_TILT_INTERCEPT_THRESHOLD, default=DEFAULT_TILT_INTERCEPT_THRESHOLD
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=15, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )

        return self.async_show_form(step_id="group", data_schema=schema, errors=errors)


class ShadeCompleteOptionsFlow(config_entries.OptionsFlow):
    """Dynamic Options Flow for runtime tuning without integration re-creation."""

    def __init__(self, config_entry: config_entries.ConfigEntry | None = None) -> None:
        """Initialize options flow."""
        super().__init__()
        self._entry = config_entry
        if config_entry is not None:
            self.handler = getattr(config_entry, "entry_id", "test_entry")

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the config entry."""
        if getattr(self, "_entry", None) is not None:
            return self._entry
        return super().config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage runtime options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = {**self.config_entry.data, **self.config_entry.options}
        mode = data.get(CONF_MODE, MODE_SMART_SHADE)

        if mode == MODE_TILT_ONLY:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_TARGET_COVER, default=data.get(CONF_TARGET_COVER)
                        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="cover")),
                    }
                ),
            )

        if mode == MODE_GROUP:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_TARGET_COVERS, default=data.get(CONF_TARGET_COVERS, [])
                        ): selector.EntitySelector(
                            selector.EntitySelectorConfig(domain="cover", multiple=True)
                        ),
                        vol.Optional(
                            CONF_WINDOW_DIRECTION,
                            default=data.get(CONF_WINDOW_DIRECTION, DEFAULT_WINDOW_DIRECTION),
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=DIRECTION_OPTIONS,
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                        vol.Optional(
                            CONF_AZIMUTH_TOLERANCE,
                            default=float(
                                data.get(CONF_AZIMUTH_TOLERANCE, DEFAULT_AZIMUTH_TOLERANCE)
                            ),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=5.0,
                                max=90.0,
                                step=0.5,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Optional(
                            CONF_ELEVATION_LOW,
                            default=float(data.get(CONF_ELEVATION_LOW, DEFAULT_ELEVATION_LOW)),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=-10.0,
                                max=90.0,
                                step=0.5,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Optional(
                            CONF_ELEVATION_HIGH,
                            default=float(data.get(CONF_ELEVATION_HIGH, DEFAULT_ELEVATION_HIGH)),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=-10.0,
                                max=90.0,
                                step=0.5,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Optional(
                            CONF_TRACKING_START_TIME,
                            default=data.get(CONF_TRACKING_START_TIME, DEFAULT_TRACKING_START_TIME),
                        ): selector.TimeSelector(),
                        vol.Optional(
                            CONF_TRACKING_END_TIME,
                            default=data.get(CONF_TRACKING_END_TIME, DEFAULT_TRACKING_END_TIME),
                        ): selector.TimeSelector(),
                        vol.Optional(
                            CONF_POSITION_SENSITIVITY,
                            default=int(
                                data.get(
                                    CONF_POSITION_SENSITIVITY,
                                    DEFAULT_POSITION_SENSITIVITY,
                                )
                            ),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=50,
                                step=1,
                                mode=selector.NumberSelectorMode.SLIDER,
                            )
                        ),
                        vol.Optional(
                            CONF_POSITION_OFFSET,
                            default=int(data.get(CONF_POSITION_OFFSET, DEFAULT_POSITION_OFFSET)),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=-50,
                                max=50,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Optional(
                            CONF_WEATHER_ENTITY,
                            default=data.get(CONF_WEATHER_ENTITY, ""),
                        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
                        vol.Optional(
                            CONF_TRAVEL_TIME_SECONDS,
                            default=int(
                                data.get(
                                    CONF_TRAVEL_TIME_SECONDS,
                                    DEFAULT_TRAVEL_TIME_SECONDS,
                                )
                            ),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=3,
                                max=180,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Optional(
                            CONF_ENABLE_OVERRIDE_TIMEOUT,
                            default=bool(data.get(CONF_ENABLE_OVERRIDE_TIMEOUT, True)),
                        ): selector.BooleanSelector(),
                        vol.Optional(
                            CONF_OVERRIDE_TIMEOUT_MINUTES,
                            default=int(
                                data.get(
                                    CONF_OVERRIDE_TIMEOUT_MINUTES,
                                    DEFAULT_OVERRIDE_TIMEOUT_MINUTES,
                                )
                            ),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=1440,
                                step=5,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Optional(
                            CONF_ENABLE_AUTO_CLOSE,
                            default=bool(
                                data.get(CONF_ENABLE_AUTO_CLOSE, DEFAULT_ENABLE_AUTO_CLOSE)
                            ),
                        ): selector.BooleanSelector(),
                        vol.Optional(
                            CONF_AUTO_CLOSE_TIME,
                            default=data.get(CONF_AUTO_CLOSE_TIME, DEFAULT_AUTO_CLOSE_TIME),
                        ): selector.TimeSelector(),
                        vol.Optional(
                            CONF_ENABLE_AUTO_OPEN,
                            default=bool(data.get(CONF_ENABLE_AUTO_OPEN, DEFAULT_ENABLE_AUTO_OPEN)),
                        ): selector.BooleanSelector(),
                        vol.Optional(
                            CONF_AUTO_OPEN_TIME,
                            default=data.get(CONF_AUTO_OPEN_TIME, DEFAULT_AUTO_OPEN_TIME),
                        ): selector.TimeSelector(),
                        vol.Optional(
                            CONF_AUTO_OPEN_POSITION,
                            default=int(
                                data.get(CONF_AUTO_OPEN_POSITION, DEFAULT_AUTO_OPEN_POSITION)
                            ),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=100,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                        vol.Optional(
                            CONF_ENABLE_TILT_INTERCEPT,
                            default=bool(
                                data.get(
                                    CONF_ENABLE_TILT_INTERCEPT,
                                    DEFAULT_ENABLE_TILT_INTERCEPT,
                                )
                            ),
                        ): selector.BooleanSelector(),
                        vol.Optional(
                            CONF_TILT_INTERCEPT_THRESHOLD,
                            default=int(
                                data.get(
                                    CONF_TILT_INTERCEPT_THRESHOLD,
                                    DEFAULT_TILT_INTERCEPT_THRESHOLD,
                                )
                            ),
                        ): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=15,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        ),
                    }
                ),
            )

        # Smart Shade Options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_WINDOW_DIRECTION,
                        default=data.get(CONF_WINDOW_DIRECTION, DEFAULT_WINDOW_DIRECTION),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=DIRECTION_OPTIONS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_AZIMUTH_TOLERANCE,
                        default=float(data.get(CONF_AZIMUTH_TOLERANCE, DEFAULT_AZIMUTH_TOLERANCE)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=5.0,
                            max=90.0,
                            step=0.5,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_ELEVATION_LOW,
                        default=float(data.get(CONF_ELEVATION_LOW, DEFAULT_ELEVATION_LOW)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-10.0,
                            max=90.0,
                            step=0.5,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_ELEVATION_HIGH,
                        default=float(data.get(CONF_ELEVATION_HIGH, DEFAULT_ELEVATION_HIGH)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-10.0,
                            max=90.0,
                            step=0.5,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_TRACKING_START_TIME,
                        default=data.get(CONF_TRACKING_START_TIME, DEFAULT_TRACKING_START_TIME),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TRACKING_END_TIME,
                        default=data.get(CONF_TRACKING_END_TIME, DEFAULT_TRACKING_END_TIME),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_POSITION_SENSITIVITY,
                        default=int(
                            data.get(
                                CONF_POSITION_SENSITIVITY,
                                DEFAULT_POSITION_SENSITIVITY,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=50,
                            step=1,
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(
                        CONF_POSITION_OFFSET,
                        default=int(data.get(CONF_POSITION_OFFSET, DEFAULT_POSITION_OFFSET)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-50,
                            max=50,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_WEATHER_ENTITY,
                        default=data.get(CONF_WEATHER_ENTITY, ""),
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
                    vol.Optional(
                        CONF_TRAVEL_TIME_SECONDS,
                        default=int(
                            data.get(CONF_TRAVEL_TIME_SECONDS, DEFAULT_TRAVEL_TIME_SECONDS)
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=3,
                            max=180,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_ENABLE_OVERRIDE_TIMEOUT,
                        default=bool(data.get(CONF_ENABLE_OVERRIDE_TIMEOUT, True)),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_OVERRIDE_TIMEOUT_MINUTES,
                        default=int(
                            data.get(
                                CONF_OVERRIDE_TIMEOUT_MINUTES,
                                DEFAULT_OVERRIDE_TIMEOUT_MINUTES,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=1440,
                            step=5,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_ENABLE_AUTO_CLOSE,
                        default=bool(data.get(CONF_ENABLE_AUTO_CLOSE, DEFAULT_ENABLE_AUTO_CLOSE)),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_AUTO_CLOSE_TIME,
                        default=data.get(CONF_AUTO_CLOSE_TIME, DEFAULT_AUTO_CLOSE_TIME),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_ENABLE_AUTO_OPEN,
                        default=bool(data.get(CONF_ENABLE_AUTO_OPEN, DEFAULT_ENABLE_AUTO_OPEN)),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_AUTO_OPEN_TIME,
                        default=data.get(CONF_AUTO_OPEN_TIME, DEFAULT_AUTO_OPEN_TIME),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_AUTO_OPEN_POSITION,
                        default=int(data.get(CONF_AUTO_OPEN_POSITION, DEFAULT_AUTO_OPEN_POSITION)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=100,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_ENABLE_TILT_INTERCEPT,
                        default=bool(
                            data.get(CONF_ENABLE_TILT_INTERCEPT, DEFAULT_ENABLE_TILT_INTERCEPT)
                        ),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_TILT_INTERCEPT_THRESHOLD,
                        default=int(
                            data.get(
                                CONF_TILT_INTERCEPT_THRESHOLD,
                                DEFAULT_TILT_INTERCEPT_THRESHOLD,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=15,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_BATTERY_AUTO_LEARN,
                        default=bool(data.get(CONF_BATTERY_AUTO_LEARN, DEFAULT_BATTERY_AUTO_LEARN)),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_BATTERY_LOW_THRESHOLD,
                        default=int(
                            data.get(CONF_BATTERY_LOW_THRESHOLD, DEFAULT_BATTERY_LOW_THRESHOLD)
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=50,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
