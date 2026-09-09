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


async def test_options_flow_smart_shade_menu(mock_hass):
    """Test options flow menu and category steps for a smart shade entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        CONF_MODE: MODE_SMART_SHADE,
        CONF_NAME: "Kitchen Shade",
        CONF_TARGET_COVER: "cover.kitchen",
    }
    entry.options = {}

    options_flow = ShadeCompleteOptionsFlow(entry)
    options_flow.hass = mock_hass

    # 1. Show options menu
    menu = await options_flow.async_step_init()
    assert menu["type"] == data_entry_flow.FlowResultType.MENU
    assert menu["step_id"] == "init"
    assert "solar_tracking" in menu["menu_options"]
    assert "schedules" in menu["menu_options"]
    assert "tilt_control" in menu["menu_options"]
    assert "battery" in menu["menu_options"]
    assert "shade_behavior" in menu["menu_options"]
    assert "all_settings" in menu["menu_options"]

    # 2. Test solar_tracking form and submission
    form_solar = await options_flow.async_step_solar_tracking()
    assert form_solar["type"] == data_entry_flow.FlowResultType.FORM
    assert form_solar["step_id"] == "solar_tracking"

    res_solar = await options_flow.async_step_solar_tracking(
        {"window_direction": "W", "azimuth_tolerance": 35.0}
    )
    assert res_solar["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert res_solar["data"]["window_direction"] == "W"
    assert res_solar["data"]["azimuth_tolerance"] == 35.0

    # 3. Test schedules form and submission
    form_sched = await options_flow.async_step_schedules()
    assert form_sched["type"] == data_entry_flow.FlowResultType.FORM
    res_sched = await options_flow.async_step_schedules(
        {"enable_auto_open": True, "auto_open_time": "07:15:00", "auto_open_position": 90}
    )
    assert res_sched["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert res_sched["data"]["auto_open_position"] == 90

    # 4. Test tilt_control form and submission
    form_tilt = await options_flow.async_step_tilt_control()
    assert form_tilt["type"] == data_entry_flow.FlowResultType.FORM
    res_tilt = await options_flow.async_step_tilt_control(
        {"enable_tilt_intercept": True, "tilt_intercept_threshold": 6}
    )
    assert res_tilt["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert res_tilt["data"]["tilt_intercept_threshold"] == 6

    # 5. Test battery form and submission
    form_bat = await options_flow.async_step_battery()
    assert form_bat["type"] == data_entry_flow.FlowResultType.FORM
    res_bat = await options_flow.async_step_battery(
        {"battery_auto_learn": True, "battery_low_threshold": 18}
    )
    assert res_bat["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert res_bat["data"]["battery_low_threshold"] == 18

    # 6. Test shade_behavior form and submission
    form_beh = await options_flow.async_step_shade_behavior()
    assert form_beh["type"] == data_entry_flow.FlowResultType.FORM
    res_beh = await options_flow.async_step_shade_behavior(
        {"travel_time_seconds": 18, "override_timeout_minutes": 45}
    )
    assert res_beh["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert res_beh["data"]["travel_time_seconds"] == 18

    # 7. Test all_settings form and submission
    form_all = await options_flow.async_step_all_settings()
    assert form_all["type"] == data_entry_flow.FlowResultType.FORM
    res_all = await options_flow.async_step_all_settings(
        {"window_direction": "SE", "auto_close_time": "22:30:00"}
    )
    assert res_all["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert res_all["data"]["auto_close_time"] == "22:30:00"


async def test_options_flow_tilt_and_group(mock_hass):
    """Test options flow initialization for tilt and group entries."""
    # Tilt entry -> shows form directly
    entry_tilt = MagicMock(spec=ConfigEntry)
    entry_tilt.data = {CONF_MODE: MODE_TILT_ONLY, CONF_TARGET_COVER: "cover.tilt_target"}
    entry_tilt.options = {}
    tilt_options = ShadeCompleteOptionsFlow(entry_tilt)
    tilt_options.hass = mock_hass

    form_tilt = await tilt_options.async_step_init()
    assert form_tilt["type"] == data_entry_flow.FlowResultType.FORM
    assert form_tilt["step_id"] == "init"

    # Group entry -> shows menu without battery
    entry_group = MagicMock(spec=ConfigEntry)
    entry_group.data = {CONF_MODE: MODE_GROUP, CONF_TARGET_COVERS: ["cover.a", "cover.b"]}
    entry_group.options = {}
    group_options = ShadeCompleteOptionsFlow(entry_group)
    group_options.hass = mock_hass

    menu_group = await group_options.async_step_init()
    assert menu_group["type"] == data_entry_flow.FlowResultType.MENU
    assert "battery" not in menu_group["menu_options"]
    assert "solar_tracking" in menu_group["menu_options"]
    assert "shade_behavior" in menu_group["menu_options"]

    # Group shade behavior form
    group_beh = await group_options.async_step_shade_behavior()
    assert group_beh["type"] == data_entry_flow.FlowResultType.FORM

    # Group all_settings form
    group_all = await group_options.async_step_all_settings()
    assert group_all["type"] == data_entry_flow.FlowResultType.FORM

    # Direct submission via async_step_init
    group_res = await group_options.async_step_init(
        {
            "window_direction": "SE",
            "enable_auto_open": True,
            "auto_open_time": "06:30:00",
            "auto_open_position": 85,
            "enable_tilt_intercept": True,
            "tilt_intercept_threshold": 4,
        }
    )
    assert group_res["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert group_res["data"]["enable_auto_open"] is True
    assert group_res["data"]["auto_open_position"] == 85
    assert group_res["data"]["enable_tilt_intercept"] is True


async def test_options_flow_smart_shade_direct_submission(mock_hass):
    """Test options flow with direct submission dictionary."""
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        CONF_MODE: MODE_SMART_SHADE,
        CONF_NAME: "Master Shade",
        CONF_TARGET_COVER: "cover.master",
    }
    entry.options = {}

    options_flow = ShadeCompleteOptionsFlow(entry)
    options_flow.hass = mock_hass

    new_options = {
        "enable_auto_open": True,
        "auto_open_time": "07:00:00",
        "auto_open_position": 100,
        "enable_tilt_intercept": True,
        "tilt_intercept_threshold": 5,
        "battery_low_threshold": 25,
    }
    result = await options_flow.async_step_init(new_options)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["enable_auto_open"] is True
    assert result["data"]["tilt_intercept_threshold"] == 5
    assert result["data"]["battery_low_threshold"] == 25
