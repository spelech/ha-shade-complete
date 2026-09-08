"""Unit tests for the Config Flow and Options Flow in Shade Complete."""

from unittest.mock import MagicMock

from homeassistant import data_entry_flow
from homeassistant.config_entries import ConfigEntry

from custom_components.shade_complete.config_flow import (
    ShadeCompleteConfigFlow,
    ShadeCompleteOptionsFlow,
)
from custom_components.shade_complete.const import (
    CONF_MODE,
    CONF_NAME,
    CONF_TARGET_COVER,
    CONF_TARGET_COVERS,
    MODE_GROUP,
    MODE_SMART_SHADE,
    MODE_TILT_ONLY,
)


async def test_config_flow_menu(mock_hass):
    """Test initial user menu step."""
    flow = ShadeCompleteConfigFlow()
    flow.hass = mock_hass

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "smart_shade" in result["menu_options"]
    assert "tilt_only" in result["menu_options"]
    assert "group" in result["menu_options"]


async def test_config_flow_smart_shade_success(mock_hass):
    """Test creating a Smart Tracking Shade entry."""
    flow = ShadeCompleteConfigFlow()
    flow.hass = mock_hass

    # Show form
    form = await flow.async_step_smart_shade()
    assert form["type"] == data_entry_flow.FlowResultType.FORM
    assert form["step_id"] == "smart_shade"

    # Submit valid user input
    user_input = {
        CONF_NAME: "Living Room Shade",
        CONF_TARGET_COVER: "cover.living_room_motor",
        "window_direction": "S",
        "azimuth_tolerance": 25.0,
        "elevation_low_threshold": 5.0,
        "elevation_high_threshold": 45.0,
        "tracking_start_time": "08:30:00",
        "tracking_end_time": "20:30:00",
        "position_change_sensitivity": 8,
        "position_offset": 5,
        "travel_time_seconds": 12,
        "enable_override_timeout": True,
        "override_timeout_minutes": 90,
        "enable_auto_close": True,
        "auto_close_time": "21:00:00",
        "battery_sensor": "sensor.shade_battery",
        "battery_mode": "voltage",
        "battery_min": 6.2,
        "battery_max": 8.4,
        "battery_auto_learn": True,
    }

    result = await flow.async_step_smart_shade(user_input)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room Shade"
    assert result["data"][CONF_MODE] == MODE_SMART_SHADE
    assert result["data"][CONF_TARGET_COVER] == "cover.living_room_motor"


async def test_config_flow_tilt_only_success(mock_hass):
    """Test creating a virtual Tilt Cover entry."""
    flow = ShadeCompleteConfigFlow()
    flow.hass = mock_hass

    user_input = {
        CONF_NAME: "Patio Tilt",
        CONF_TARGET_COVER: "cover.patio_physical",
    }

    result = await flow.async_step_tilt_only(user_input)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Patio Tilt"
    assert result["data"][CONF_MODE] == MODE_TILT_ONLY


async def test_config_flow_group_success(mock_hass):
    """Test creating a synchronized Group Cover entry."""
    flow = ShadeCompleteConfigFlow()
    flow.hass = mock_hass

    user_input = {
        CONF_NAME: "Master Bedroom Shades",
        CONF_TARGET_COVERS: ["cover.shade_1", "cover.shade_2"],
    }

    result = await flow.async_step_group(user_input)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Master Bedroom Shades"
    assert result["data"][CONF_MODE] == MODE_GROUP


async def test_options_flow_smart_shade(mock_hass):
    """Test modifying runtime options for a smart shade entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        CONF_MODE: MODE_SMART_SHADE,
        CONF_NAME: "Kitchen Shade",
        CONF_TARGET_COVER: "cover.kitchen",
    }
    entry.options = {}

    options_flow = ShadeCompleteOptionsFlow(entry)
    options_flow.hass = mock_hass

    # Show options form
    form = await options_flow.async_step_init()
    assert form["type"] == data_entry_flow.FlowResultType.FORM
    assert form["step_id"] == "init"

    # Submit updated options
    new_options = {
        "window_direction": "W",
        "azimuth_tolerance": 30.0,
        "elevation_low_threshold": 8.0,
        "elevation_high_threshold": 40.0,
        "position_change_sensitivity": 12,
        "enable_auto_close": True,
        "auto_close_time": "22:00:00",
    }
    result = await options_flow.async_step_init(new_options)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["window_direction"] == "W"
    assert result["data"]["auto_close_time"] == "22:00:00"


async def test_options_flow_tilt_and_group(mock_hass):
    """Test options flow initialization for tilt and group entries."""
    # Tilt entry
    entry_tilt = MagicMock(spec=ConfigEntry)
    entry_tilt.data = {CONF_MODE: MODE_TILT_ONLY, CONF_TARGET_COVER: "cover.tilt_target"}
    entry_tilt.options = {}
    tilt_options = ShadeCompleteOptionsFlow(entry_tilt)
    tilt_options.hass = mock_hass

    form_tilt = await tilt_options.async_step_init()
    assert form_tilt["type"] == data_entry_flow.FlowResultType.FORM

    # Group entry
    entry_group = MagicMock(spec=ConfigEntry)
    entry_group.data = {CONF_MODE: MODE_GROUP, CONF_TARGET_COVERS: ["cover.a", "cover.b"]}
    entry_group.options = {}
    group_options = ShadeCompleteOptionsFlow(entry_group)
    group_options.hass = mock_hass

    form_group = await group_options.async_step_init()
    assert form_group["type"] == data_entry_flow.FlowResultType.FORM
