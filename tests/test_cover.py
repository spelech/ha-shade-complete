"""Unit tests for Cover entities in Shade Complete."""

from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from custom_components.shade_complete.const import (
    CONF_MODE,
    CONF_NAME,
    CONF_TARGET_COVER,
    CONF_TARGET_COVERS,
    MODE_GROUP,
    MODE_SMART_SHADE,
    MODE_TILT_ONLY,
)
from custom_components.shade_complete.cover import (
    GroupShadeCover,
    SmartTrackingShadeCover,
    TiltCoverEntity,
    async_setup_entry,
)


@pytest.fixture
def mock_config_entry():
    """Create a mock ConfigEntry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_123"
    entry.data = {
        CONF_MODE: MODE_SMART_SHADE,
        CONF_NAME: "Office Shade",
        CONF_TARGET_COVER: "cover.physical_blind",
        "position_change_sensitivity": 5,
        "travel_time_seconds": 10,
        "enable_override_timeout": True,
        "override_timeout_minutes": 60,
    }
    entry.options = {}
    return entry


async def test_smart_tracking_cover_properties(mock_hass, mock_config_entry):
    """Test standard cover attributes and features."""
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )

    assert shade.name == "Office Shade"
    assert shade.unique_id == "test_entry_123_cover.physical_blind_smart"
    assert shade.device_class == CoverDeviceClass.SHADE
    assert shade.supported_features & CoverEntityFeature.SET_POSITION
    assert shade.current_cover_position is None
    assert shade.is_closed is None

    shade._current_position = 0
    assert shade.is_closed is True
    shade._current_position = 50
    assert shade.is_closed is False

    attrs = shade.extra_state_attributes
    assert attrs["proxied_entity"] == "cover.physical_blind"
    assert attrs["manual_override"] is False


async def test_smart_tracking_command_move_and_verify(mock_hass, mock_config_entry):
    """Test commanding move and verifying travel arrival."""
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade.async_write_ha_state = MagicMock()

    with patch("custom_components.shade_complete.cover.async_call_later") as mock_call_later:
        await shade._async_command_move(75)

        assert shade._is_moving is True
        assert shade._requested_position == 75
        mock_hass.services.async_call.assert_called_with(
            "cover",
            "set_cover_position",
            {"entity_id": "cover.physical_blind", "position": 75},
            blocking=False,
            context=shade._context,
        )
        assert mock_call_later.called

    # Simulate arrival at target position
    target_state = MagicMock()
    target_state.state = "open"
    target_state.attributes = {ATTR_POSITION: 75}
    mock_hass.states.get.return_value = target_state

    await shade._async_verify_movement()
    assert shade._is_moving is False
    assert shade._last_set_position == 75
    assert shade._is_manual_override is False


async def test_smart_tracking_intercepted_movement(mock_hass, mock_config_entry):
    """Test detecting intercepted movement when stopped prematurely."""
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade.async_write_ha_state = MagicMock()
    shade._requested_position = 100

    # Stopped at 30% instead of 100%
    target_state = MagicMock()
    target_state.state = "open"
    target_state.attributes = {ATTR_POSITION: 30}
    mock_hass.states.get.return_value = target_state

    with patch("custom_components.shade_complete.cover.async_call_later") as mock_call_later:
        await shade._async_verify_movement()
        assert shade._is_moving is False
        assert shade._is_manual_override is True
        assert "Movement intercepted" in shade._inactive_reason
        assert mock_call_later.called


async def test_smart_tracking_manual_override_detection(mock_hass, mock_config_entry):
    """Test manual position change detection outside active commanding."""
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade._initialized = True
    shade._last_set_position = 50
    shade._is_moving = False
    shade.async_write_ha_state = MagicMock()

    # User adjusts shade with remote to 90%
    event = MagicMock()
    event.data = {"new_state": MagicMock(attributes={ATTR_POSITION: 90})}

    await shade._async_target_state_changed(event)
    assert shade._is_manual_override is True
    assert shade._current_position == 90
    assert "Manual move detected" in shade._inactive_reason

    # Reset override
    await shade._async_reset_manual_override()
    assert shade._is_manual_override is False


async def test_smart_tracking_early_arrival_clears_moving(mock_hass, mock_config_entry):
    """Test reaching target position early during commanded motion clears moving state cleanly."""
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade._initialized = True
    shade._is_moving = True
    shade._requested_position = 60
    shade._last_set_position = 60
    mock_unsub = MagicMock()
    shade._travel_unsub = mock_unsub
    shade.async_write_ha_state = MagicMock()

    # Intermediate event arrives: position reached 58% (within sensitivity 10)
    event = MagicMock()
    event.data = {"new_state": MagicMock(attributes={ATTR_POSITION: 58})}

    await shade._async_target_state_changed(event)
    assert shade._is_moving is False
    assert shade._last_set_position == 58
    assert shade._is_manual_override is False
    assert mock_unsub.called
    assert shade._travel_unsub is None


async def test_smart_tracking_verify_movement_reschedules_if_in_transit(
    mock_hass, mock_config_entry
):
    """Test that movement verification reschedules if physical cover reports opening/closing."""
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade._is_moving = True
    shade._requested_position = 70
    shade._current_position = 35  # Only partway there

    target_state = MagicMock()
    target_state.state = "opening"
    mock_hass.states.get.return_value = target_state

    with patch("custom_components.shade_complete.cover.async_call_later") as mock_call_later:
        await shade._async_verify_movement()
        assert shade._is_manual_override is False
        assert mock_call_later.called
        assert mock_call_later.call_args[0][1] == 10  # Rescheduled for 10 seconds


async def test_smart_tracking_verify_movement_reschedules_if_recently_moved(
    mock_hass, mock_config_entry
):
    """Test that movement verification reschedules if position was recently updated."""
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade._is_moving = True
    shade._requested_position = 70
    shade._current_position = 35  # Only partway there
    shade._last_position_change_time = dt_util.utcnow()  # Updated right now

    target_state = MagicMock()
    target_state.state = "open"  # Not opening or closing
    mock_hass.states.get.return_value = target_state

    with patch("custom_components.shade_complete.cover.async_call_later") as mock_call_later:
        await shade._async_verify_movement()
        assert shade._is_manual_override is False
        assert mock_call_later.called
        assert mock_call_later.call_args[0][1] == 10  # Rescheduled for 10 seconds


async def test_tilt_cover_entity_controls(mock_hass, mock_config_entry):
    """Test mapping standard cover controls to physical tilt."""
    tilt = TiltCoverEntity(mock_hass, mock_config_entry, "cover.living_blind", "Living Blind")
    tilt.async_write_ha_state = MagicMock()

    # Open tilt
    await tilt.async_open_cover()
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "open_cover_tilt",
        {"entity_id": "cover.living_blind"},
        blocking=True,
        context=tilt._context,
    )

    # Close tilt
    await tilt.async_close_cover()
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "close_cover_tilt",
        {"entity_id": "cover.living_blind"},
        blocking=True,
        context=tilt._context,
    )

    # Stop tilt
    await tilt.async_stop_cover()
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "stop_cover_tilt",
        {"entity_id": "cover.living_blind"},
        blocking=True,
        context=tilt._context,
    )

    # Set position
    await tilt.async_set_cover_position(position=45)
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": "cover.living_blind", "tilt_position": 45},
        blocking=True,
        context=tilt._context,
    )

    # Position reporting
    mock_hass.states.get.return_value = MagicMock(attributes={"current_tilt_position": 60})
    assert tilt.current_cover_position == 60
    assert tilt.is_closed is False


async def test_group_shade_cover(mock_hass, mock_config_entry):
    """Test synchronized group operations and position averaging."""
    members = ["cover.shade_left", "cover.shade_right"]
    group = GroupShadeCover(mock_hass, mock_config_entry, members, "Bay Windows")
    group.async_write_ha_state = MagicMock()

    # Left at 40%, Right at 60% -> Average = 50%
    st1 = MagicMock(attributes={ATTR_POSITION: 40})
    st2 = MagicMock(attributes={ATTR_POSITION: 60})
    mock_hass.states.get.side_effect = lambda ent: st1 if ent == "cover.shade_left" else st2

    assert group.current_cover_position == 50
    assert group.is_closed is False

    # Open all
    await group.async_open_cover()
    assert mock_hass.services.async_call.call_count == 2

    # Close all
    mock_hass.services.async_call.reset_mock()
    await group.async_close_cover()
    assert mock_hass.services.async_call.call_count == 2

    # Stop all
    mock_hass.services.async_call.reset_mock()
    await group.async_stop_cover()
    assert mock_hass.services.async_call.call_count == 2

    # Set position
    mock_hass.services.async_call.reset_mock()
    await group.async_set_cover_position(position=80)
    assert mock_hass.services.async_call.call_count == 2


async def test_async_setup_entry_dispatcher(mock_hass, mock_config_entry):
    """Test platform entry setup dispatches entities by configured mode."""
    async_add = MagicMock()

    # Smart shade
    await async_setup_entry(mock_hass, mock_config_entry, async_add)
    assert async_add.called
    assert isinstance(async_add.call_args[0][0][0], SmartTrackingShadeCover)

    # Tilt only
    async_add.reset_mock()
    mock_config_entry.data[CONF_MODE] = MODE_TILT_ONLY
    await async_setup_entry(mock_hass, mock_config_entry, async_add)
    assert isinstance(async_add.call_args[0][0][0], TiltCoverEntity)

    # Group
    async_add.reset_mock()
    mock_config_entry.data[CONF_MODE] = MODE_GROUP
    mock_config_entry.data[CONF_TARGET_COVERS] = ["cover.a", "cover.b"]
    await async_setup_entry(mock_hass, mock_config_entry, async_add)
    assert isinstance(async_add.call_args[0][0][0], GroupShadeCover)


async def test_smart_tracking_cover_open_close_stop(mock_hass, mock_config_entry):
    """Test standard cover actions (open, close, stop, set_position)."""
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade._async_command_move = AsyncMock()

    await shade.async_open_cover()
    shade._async_command_move.assert_called_with(100)

    await shade.async_close_cover()
    shade._async_command_move.assert_called_with(0)

    await shade.async_set_cover_position(position=60)
    shade._async_command_move.assert_called_with(60)

    await shade.async_stop_cover()
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "stop_cover",
        {"entity_id": "cover.physical_blind"},
        blocking=True,
        context=shade._context,
    )
    assert shade._is_manual_override is True


async def test_manual_close_prevents_sun_tracking_reopen(mock_hass, mock_config_entry):
    """Test that manual user close engages override and blocks sun tracking from reopening."""
    mock_config_entry.data["window_direction"] = "W"
    mock_config_entry.data["azimuth_tolerance"] = 60.0
    mock_config_entry.data["enable_sun_tracking"] = True

    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Bedside Shade"
    )
    shade.async_write_ha_state = MagicMock()
    shade._async_command_move = AsyncMock()
    shade._current_position = 0

    mock_sun = MagicMock()
    mock_sun.state = "above_horizon"
    mock_sun.attributes = {"azimuth": 270, "elevation": 30}
    mock_hass.states.get.return_value = mock_sun

    # User manually closes the shade
    await shade.async_close_cover()
    assert shade._is_manual_override is True
    assert "Manual close" in shade._inactive_reason
    shade._async_command_move.assert_called_with(0)

    # Next sun tracking evaluation arrives
    shade._async_command_move.reset_mock()
    await shade._async_evaluate_sun_tracking()

    # Sun tracking must NOT move the shade back open!
    shade._async_command_move.assert_not_called()



async def test_smart_tracking_periodic_check_auto_close(mock_hass, mock_config_entry):
    """Test auto-close execution during periodic check."""
    mock_config_entry.data["enable_auto_close"] = True
    mock_config_entry.data["auto_close_time"] = "20:00:00"
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade._current_position = 50
    shade._async_command_move = AsyncMock()
    shade._schedule_engine.should_trigger_close = MagicMock(return_value=True)

    from datetime import datetime

    await shade._async_periodic_check(datetime(2026, 9, 8, 20, 1, 0))
    shade._async_command_move.assert_called_with(0)
    assert shade._inactive_reason == "Scheduled evening close"


async def test_smart_tracking_sun_below_horizon(mock_hass, mock_config_entry):
    """Test sun below horizon forces shade closed and resets override."""
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade.async_write_ha_state = MagicMock()
    shade._is_manual_override = True
    shade._current_position = 40
    shade._async_command_move = AsyncMock()

    mock_sun = MagicMock()
    mock_sun.state = "below_horizon"
    mock_sun.attributes = {"azimuth": 0, "elevation": -20}
    mock_hass.states.get.return_value = mock_sun

    await shade._async_evaluate_sun_tracking()
    assert shade._is_manual_override is False
    shade._async_command_move.assert_called_with(0)


async def test_smart_tracking_periodic_check_auto_open(mock_hass, mock_config_entry):
    """Test auto-open execution during periodic check."""
    mock_config_entry.data["enable_auto_open"] = True
    mock_config_entry.data["auto_open_time"] = "07:30:00"
    mock_config_entry.data["auto_open_position"] = 90
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade._current_position = 0
    shade._async_command_move = AsyncMock()
    shade._schedule_engine.should_trigger_close = MagicMock(return_value=False)
    shade._schedule_engine.should_trigger_open = MagicMock(return_value=True)

    from datetime import datetime

    await shade._async_periodic_check(datetime(2026, 9, 8, 7, 31, 0))
    shade._async_command_move.assert_called_with(90)
    assert shade._inactive_reason == "Scheduled morning open"


async def test_smart_tracking_tilt_interception(mock_hass, mock_config_entry):
    """Test low percentage commands converted to tilt position when enabled."""
    mock_config_entry.data["enable_tilt_intercept"] = True
    mock_config_entry.data["tilt_intercept_threshold"] = 5
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade._async_command_move = AsyncMock()
    shade._async_command_tilt = AsyncMock()

    # Low percentage command: 4% with threshold 5 -> (4/5)*100 = 80% tilt
    await shade.async_set_cover_position(position=4)
    shade._async_command_tilt.assert_called_with(80)
    assert not shade._async_command_move.called

    # Percentage command above threshold: 25% -> normal shade move
    shade._async_command_tilt.reset_mock()
    await shade.async_set_cover_position(position=25)
    shade._async_command_move.assert_called_with(25)
    assert not shade._async_command_tilt.called


async def test_smart_tracking_tilt_controls(mock_hass, mock_config_entry):
    """Test smart tracking shade native tilt controls forwarding."""
    target_state = MagicMock()
    target_state.attributes = {
        "supported_features": CoverEntityFeature.OPEN_TILT | CoverEntityFeature.SET_TILT_POSITION,
        "current_tilt_position": 65,
    }
    mock_hass.states.get.return_value = target_state

    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    assert shade._supports_tilt is True
    assert shade.supported_features & CoverEntityFeature.SET_TILT_POSITION
    assert shade.current_cover_tilt_position == 65

    # Open tilt
    await shade.async_open_cover_tilt()
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "open_cover_tilt",
        {"entity_id": "cover.physical_blind"},
        blocking=True,
        context=shade._context,
    )

    # Close tilt
    await shade.async_close_cover_tilt()
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "close_cover_tilt",
        {"entity_id": "cover.physical_blind"},
        blocking=True,
        context=shade._context,
    )

    # Set tilt position
    await shade.async_set_cover_tilt_position(tilt_position=40)
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": "cover.physical_blind", "tilt_position": 40},
        blocking=True,
        context=shade._context,
    )

    # Stop tilt
    await shade.async_stop_cover_tilt()
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "stop_cover_tilt",
        {"entity_id": "cover.physical_blind"},
        blocking=True,
        context=shade._context,
    )


async def test_auto_create_tilt_entity_in_setup(mock_hass, mock_config_entry):
    """Test automatic creation of TiltCoverEntity when target supports tilt or intercept enabled."""
    async_add = MagicMock()

    # Target state has tilt supported
    target_state = MagicMock()
    target_state.attributes = {
        "supported_features": CoverEntityFeature.OPEN_TILT | CoverEntityFeature.SET_TILT_POSITION,
        "current_tilt_position": 50,
    }
    mock_hass.states.get.return_value = target_state

    await async_setup_entry(mock_hass, mock_config_entry, async_add)
    assert async_add.called
    created_entities = async_add.call_args[0][0]
    assert len(created_entities) == 2
    assert isinstance(created_entities[0], SmartTrackingShadeCover)
    assert isinstance(created_entities[1], TiltCoverEntity)


async def test_group_shade_tilt_interception(mock_hass, mock_config_entry):
    """Test low percentage tilt interception on synchronized group."""
    members = ["cover.shade_1", "cover.shade_2"]
    mock_config_entry.data["enable_tilt_intercept"] = True
    mock_config_entry.data["tilt_intercept_threshold"] = 5
    group = GroupShadeCover(mock_hass, mock_config_entry, members, "Bay Window Group")

    group._async_command_move = AsyncMock()
    group._async_command_tilt = AsyncMock()

    # 3% with threshold 5 -> (3/5)*100 = 60% tilt
    await group.async_set_cover_position(position=3)
    group._async_command_tilt.assert_called_with(60)
    assert not group._async_command_move.called

    # 50% -> normal group move
    group._async_command_tilt.reset_mock()
    await group.async_set_cover_position(position=50)
    group._async_command_move.assert_called_with(50)
    assert not group._async_command_tilt.called


async def test_group_shade_manual_override_on_member(mock_hass, mock_config_entry):
    """Test group detects manual override when any individual member shade moves."""
    members = ["cover.shade_1", "cover.shade_2"]
    group = GroupShadeCover(mock_hass, mock_config_entry, members, "Living Group")
    group._initialized = True
    group._is_moving = False
    group._last_member_positions = {"cover.shade_1": 10, "cover.shade_2": 10}
    group.async_write_ha_state = MagicMock()

    # shade_1 changes from 10% to 80% (delta 70% > sensitivity 5)
    event = MagicMock()
    event.data = {
        "entity_id": "cover.shade_1",
        "new_state": MagicMock(attributes={ATTR_POSITION: 80}),
    }
    await group._async_member_state_changed(event)

    assert group._is_manual_override is True
    assert "Manual move detected on cover.shade_1" in group._inactive_reason

    # Reset override
    await group._async_reset_manual_override()
    assert group._is_manual_override is False


async def test_group_shade_periodic_check(mock_hass, mock_config_entry):
    """Test group auto-close and auto-open routines."""
    members = ["cover.shade_1", "cover.shade_2"]
    group = GroupShadeCover(mock_hass, mock_config_entry, members, "Living Group")
    group._async_command_move = AsyncMock()
    group._schedule_engine.should_trigger_close = MagicMock(return_value=True)

    from datetime import datetime

    # Trigger auto close
    await group._async_periodic_check(datetime(2026, 9, 8, 21, 30, 0))
    group._async_command_move.assert_called_with(0)
    assert group._inactive_reason == "Scheduled evening close"

    # Trigger auto open
    group._schedule_engine.should_trigger_close.return_value = False
    group._schedule_engine.should_trigger_open = MagicMock(return_value=True)
    group._schedule_engine.open_position = 75
    await group._async_periodic_check(datetime(2026, 9, 8, 7, 30, 0))
    group._async_command_move.assert_called_with(75)
    assert group._inactive_reason == "Scheduled morning open"


async def test_smart_tracking_service_handlers(mock_hass, mock_config_entry):
    """Test smart tracking shade service handlers with real execution and target filtering."""
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade.entity_id = "cover.office_shade_smart"
    shade.async_write_ha_state = MagicMock()
    shade._is_manual_override = True
    shade._inactive_reason = "Manual move detected"
    shade._schedule_engine.open_position = 85

    # Non-matching entity: must NOT reset override
    await shade._async_handle_reset_service(
        MagicMock(data={"entity_id": "cover.unrelated_cover"})
    )
    assert shade._is_manual_override is True

    # Matching entity: resets override to False
    with patch("custom_components.shade_complete.cover.async_call_later"):
        await shade._async_handle_reset_service(
            MagicMock(data={"entity_id": "cover.office_shade_smart"})
        )
    assert shade._is_manual_override is False

    # Trigger close service event: commands real move to 0%
    mock_hass.services.async_call.reset_mock()
    with patch("custom_components.shade_complete.cover.async_call_later"):
        await shade._async_handle_close_service(
            MagicMock(data={"entity_id": "cover.office_shade_smart"})
        )
    assert shade._is_moving is True
    assert shade._requested_position == 0
    assert shade._inactive_reason == "Service triggered close"
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.physical_blind", "position": 0},
        blocking=False,
        context=shade._context,
    )

    # Trigger open service event: commands real move to open_position 85%
    mock_hass.services.async_call.reset_mock()
    with patch("custom_components.shade_complete.cover.async_call_later"):
        await shade._async_handle_open_service(
            MagicMock(data={"entity_id": "cover.office_shade_smart"})
        )
    assert shade._is_moving is True
    assert shade._requested_position == 85
    assert shade._inactive_reason == "Service triggered open"
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.physical_blind", "position": 85},
        blocking=False,
        context=shade._context,
    )


async def test_group_shade_service_handlers(mock_hass, mock_config_entry):
    """Test group shade service handlers with real execution and target filtering."""
    members = ["cover.shade_1", "cover.shade_2"]
    group = GroupShadeCover(mock_hass, mock_config_entry, members, "Living Group")
    group.entity_id = "cover.living_group"
    group.async_write_ha_state = MagicMock()
    group._is_manual_override = True
    group._schedule_engine.open_position = 70

    # Non-matching entity: must NOT reset
    await group._async_handle_reset_service(
        MagicMock(data={"entity_id": "cover.other_shade"})
    )
    assert group._is_manual_override is True

    # Matching member target: resets override
    with patch("custom_components.shade_complete.cover.async_call_later"):
        await group._async_handle_reset_service(
            MagicMock(data={"entity_id": "cover.shade_1"})
        )
    assert group._is_manual_override is False

    # Trigger close: moves all members to 0%
    mock_hass.services.async_call.reset_mock()
    with patch("custom_components.shade_complete.cover.async_call_later"):
        await group._async_handle_close_service(
            MagicMock(data={"entity_id": "cover.living_group"})
        )
    assert group._is_moving is True
    assert group._requested_position == 0
    assert mock_hass.services.async_call.call_count == 2

    # Trigger open: moves all members to 70%
    mock_hass.services.async_call.reset_mock()
    with patch("custom_components.shade_complete.cover.async_call_later"):
        await group._async_handle_open_service(
            MagicMock(data={"entity_id": "cover.living_group"})
        )
    assert group._is_moving is True
    assert group._requested_position == 70
    assert mock_hass.services.async_call.call_count == 2


async def test_group_shade_movement_verification(mock_hass, mock_config_entry):
    """Test movement verification on group shades."""
    members = ["cover.shade_1", "cover.shade_2"]
    group = GroupShadeCover(mock_hass, mock_config_entry, members, "Living Group")
    group.async_write_ha_state = MagicMock()
    group._requested_position = 80

    # Successful arrival: both at 80% -> average 80%
    st1 = MagicMock(attributes={ATTR_POSITION: 80})
    st2 = MagicMock(attributes={ATTR_POSITION: 80})
    mock_hass.states.get.side_effect = lambda ent: st1 if ent == "cover.shade_1" else st2

    await group._async_verify_movement()
    assert group._is_moving is False
    assert group._last_set_position == 80
    assert group._is_manual_override is False

    # Intercepted movement: shades stop at 40% instead of 80%
    group._requested_position = 80
    st1 = MagicMock(attributes={ATTR_POSITION: 40})
    st2 = MagicMock(attributes={ATTR_POSITION: 40})
    mock_hass.states.get.side_effect = lambda ent: st1 if ent == "cover.shade_1" else st2

    with patch("custom_components.shade_complete.cover.async_call_later") as mock_call_later:
        await group._async_verify_movement()
        assert group._is_manual_override is True
        assert "Group motion intercepted" in group._inactive_reason
        assert mock_call_later.called


async def test_group_shade_sun_tracking_evaluation(mock_hass, mock_config_entry):
    """Test solar tracking movement and horizon drop on group cover."""
    members = ["cover.shade_1", "cover.shade_2"]
    group = GroupShadeCover(mock_hass, mock_config_entry, members, "Solar Group")
    group.async_write_ha_state = MagicMock()
    group._async_command_move = AsyncMock()

    # Sun below horizon -> forces close
    mock_sun = MagicMock()
    mock_sun.state = "below_horizon"
    mock_sun.attributes = {"azimuth": 0, "elevation": -10}
    st1 = MagicMock(attributes={ATTR_POSITION: 60})
    st2 = MagicMock(attributes={ATTR_POSITION: 60})
    mock_hass.states.get.side_effect = lambda ent: (
        mock_sun if ent == "sun.sun" else (st1 if ent == "cover.shade_1" else st2)
    )

    await group._async_evaluate_sun_tracking()
    group._async_command_move.assert_called_with(0)


async def test_group_shade_sun_tracking_disabled(mock_hass, mock_config_entry):
    """Test that group shade does not track sun or command moves when disabled."""
    mock_config_entry.data["enable_sun_tracking"] = False
    members = ["cover.shade_1", "cover.shade_2"]
    group = GroupShadeCover(mock_hass, mock_config_entry, members, "Master Bedroom Shades")
    group.async_write_ha_state = MagicMock()
    group._async_command_move = AsyncMock()

    mock_sun = MagicMock()
    mock_sun.state = "above_horizon"
    mock_sun.attributes = {"azimuth": 240, "elevation": 20}
    mock_hass.states.get.return_value = mock_sun

    await group._async_evaluate_sun_tracking()
    group._async_command_move.assert_not_called()
    assert group._tracking_active is False
    assert group._inactive_reason == "Sun tracking disabled"
    assert group._target_position is None

    # Verify extra_state_attributes shows tracking_status == "Disabled"
    attrs = group.extra_state_attributes
    assert attrs["tracking_status"] == "Disabled"



async def test_shade_hiding_on_add_and_remove(mock_hass, mock_config_entry):
    """Test that physical shades are hidden when added and restored when removed."""
    with patch("custom_components.shade_complete.cover.async_set_entity_hidden_state") as mock_hide:
        shade = SmartTrackingShadeCover(mock_hass, mock_config_entry, "cover.physical", "Shade")
        shade.async_on_remove = MagicMock()
        await shade.async_added_to_hass()
        mock_hide.assert_called_with(mock_hass, "cover.physical", hidden=True)

        mock_hide.reset_mock()
        await shade.async_will_remove_from_hass()
        mock_hide.assert_called_with(mock_hass, "cover.physical", hidden=False)


async def test_group_shade_hiding_on_add_and_remove(mock_hass, mock_config_entry):
    """Test that group member shades are hidden when added and restored when removed."""
    members = ["cover.shade_1", "cover.shade_2"]
    with patch("custom_components.shade_complete.cover.async_set_entity_hidden_state") as mock_hide:
        group = GroupShadeCover(mock_hass, mock_config_entry, members, "Group")
        group.async_on_remove = MagicMock()
        await group.async_added_to_hass()
        mock_hide.assert_called_with(mock_hass, members, hidden=True)

        mock_hide.reset_mock()
        await group.async_will_remove_from_hass()
        mock_hide.assert_called_with(mock_hass, members, hidden=False)


async def test_group_tilt_controls(mock_hass, mock_config_entry):
    """Test group tilt features and controls forwarding to member shades."""
    members = ["cover.shade_1", "cover.shade_2"]
    st1 = MagicMock(attributes={"supported_features": 255, "current_tilt_position": 40})
    st2 = MagicMock(attributes={"supported_features": 255, "current_tilt_position": 60})
    mock_hass.states.get.side_effect = lambda ent: st1 if ent == "cover.shade_1" else st2

    group = GroupShadeCover(mock_hass, mock_config_entry, members, "Bay Window Shades")
    assert group._supports_tilt is True
    assert group.supported_features & CoverEntityFeature.SET_TILT_POSITION
    assert group.current_cover_tilt_position == 50

    # Group tilt open
    await group.async_open_cover_tilt()
    mock_hass.services.async_call.assert_called_with(
        "cover", "open_cover_tilt", {"entity_id": members}, blocking=True, context=group._context
    )

    # Group tilt entity
    group_tilt = TiltCoverEntity(mock_hass, mock_config_entry, members, "Bay Window Shades")
    assert group_tilt.unique_id == f"{mock_config_entry.entry_id}_group_tilt"
    assert group_tilt.current_cover_position == 50

    await group_tilt.async_set_cover_position(position=80)
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": members, "tilt_position": 80},
        blocking=True,
        context=group_tilt._context,
    )


async def test_daylight_sun_tracking_movement(mock_hass, mock_config_entry):
    """Test sun tracking adjusting shade when sun is shining on window."""
    mock_config_entry.data["window_direction"] = "E"
    mock_config_entry.data["azimuth_tolerance"] = 60.0
    mock_config_entry.data["tracking_start_time"] = "08:00:00"
    mock_config_entry.data["tracking_end_time"] = "20:00:00"

    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "East Shade"
    )
    shade._current_position = 0
    shade.async_write_ha_state = MagicMock()
    shade._async_command_move = AsyncMock()

    # Sun at 117.6° azimuth, 21.3° elevation (East window, morning sun)
    mock_sun = MagicMock()
    mock_sun.state = "above_horizon"
    mock_sun.attributes = {"azimuth": 117.6, "elevation": 21.3}
    mock_hass.states.get.return_value = mock_sun

    with patch("custom_components.shade_complete.cover.dt_util.now") as mock_now:
        mock_now.return_value.time.return_value = time(9, 0)
        await shade._async_evaluate_sun_tracking()

    assert shade._tracking_active is True
    assert shade._target_position > 0
    shade._async_command_move.assert_called_with(shade._target_position)


async def test_solar_geometry_attributes_parity(mock_hass, mock_config_entry):
    """Test solar geometry attributes parity across single and group cover entities."""
    mock_config_entry.data["window_direction"] = "E"
    mock_config_entry.data["azimuth_tolerance"] = 45.0

    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.single_shade", "East Shade"
    )
    group = GroupShadeCover(
        mock_hass, mock_config_entry, ["cover.shade_1", "cover.shade_2"], "East Group"
    )

    # When sun.sun is missing
    mock_hass.states.get.return_value = None
    attrs_single = shade.extra_state_attributes
    attrs_group = group.extra_state_attributes

    assert attrs_single["solar_elevation"] is None
    assert attrs_single["solar_azimuth"] is None
    assert attrs_single["window_azimuth"] == 90.0
    assert attrs_single["azimuth_tolerance"] == 45.0

    assert attrs_group["solar_elevation"] is None
    assert attrs_group["solar_azimuth"] is None
    assert attrs_group["window_azimuth"] == 90.0
    assert attrs_group["azimuth_tolerance"] == 45.0
    assert attrs_group["member_entities"] == ["cover.shade_1", "cover.shade_2"]

    # When sun.sun is present
    mock_sun = MagicMock()
    mock_sun.state = "above_horizon"
    mock_sun.attributes = {"azimuth": 120.45, "elevation": 32.78}
    mock_hass.states.get.return_value = mock_sun

    attrs_single = shade.extra_state_attributes
    attrs_group = group.extra_state_attributes

    assert attrs_single["solar_elevation"] == 32.8
    assert attrs_single["solar_azimuth"] == 120.5
    assert attrs_group["solar_elevation"] == 32.8
    assert attrs_group["solar_azimuth"] == 120.5


async def test_tilt_interception_exact_boundaries(mock_hass, mock_config_entry):
    """Test exact boundary transitions for tilt interception logic."""
    mock_config_entry.data["enable_tilt_intercept"] = True
    mock_config_entry.data["tilt_intercept_threshold"] = 5
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade.async_write_ha_state = MagicMock()

    # 1. Position 0%: must NOT be intercepted to tilt (regular cover close)
    mock_hass.services.async_call.reset_mock()
    with patch("custom_components.shade_complete.cover.async_call_later"):
        await shade.async_set_cover_position(position=0)
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.physical_blind", "position": 0},
        blocking=False,
        context=shade._context,
    )

    # 2. Position 1% (lowest positive with threshold 5): converts to (1/5)*100 = 20% tilt
    mock_hass.services.async_call.reset_mock()
    await shade.async_set_cover_position(position=1)
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": "cover.physical_blind", "tilt_position": 20},
        blocking=False,
        context=shade._context,
    )

    # 3. Position 5% (exact threshold boundary): converts to (5/5)*100 = 100% tilt
    mock_hass.services.async_call.reset_mock()
    await shade.async_set_cover_position(position=5)
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": "cover.physical_blind", "tilt_position": 100},
        blocking=False,
        context=shade._context,
    )

    # 4. Position 6% (threshold + 1): must NOT be intercepted (regular cover position 6)
    mock_hass.services.async_call.reset_mock()
    with patch("custom_components.shade_complete.cover.async_call_later"):
        await shade.async_set_cover_position(position=6)
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.physical_blind", "position": 6},
        blocking=False,
        context=shade._context,
    )

    # 5. When tilt intercept is disabled: 3% commands normal shade move 3%
    mock_config_entry.data["enable_tilt_intercept"] = False
    mock_hass.services.async_call.reset_mock()
    with patch("custom_components.shade_complete.cover.async_call_later"):
        await shade.async_set_cover_position(position=3)
    mock_hass.services.async_call.assert_called_with(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.physical_blind", "position": 3},
        blocking=False,
        context=shade._context,
    )


async def test_movement_verification_exact_boundaries(mock_hass, mock_config_entry):
    """Test exact arrival tolerance boundary conditions during movement verification."""
    mock_config_entry.data["position_change_sensitivity"] = 5  # tolerance = max(5, 10) = 10
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade.async_write_ha_state = MagicMock()

    # Case A: Requested 50%, arrived at 40% (delta = 10 == tolerance) -> ARRIVED
    shade._is_moving = True
    shade._requested_position = 50
    target_state = MagicMock(state="open", attributes={"current_position": 40})
    mock_hass.states.get.return_value = target_state

    await shade._async_verify_movement()
    assert shade._is_moving is False
    assert shade._is_manual_override is False
    assert shade._last_set_position == 40

    # Case B: Requested 50%, stopped at 39% (delta = 11 > tolerance) -> INTERCEPTED
    shade._is_moving = True
    shade._requested_position = 50
    target_state.attributes = {"current_position": 39}

    with patch("custom_components.shade_complete.cover.async_call_later"):
        await shade._async_verify_movement()
    assert shade._is_moving is False
    assert shade._is_manual_override is True
    assert "Movement intercepted" in shade._inactive_reason

    # Case C: Requested 50%, arrived at 60% (delta = 10 == tolerance) -> ARRIVED
    shade._is_manual_override = False
    shade._is_moving = True
    shade._requested_position = 50
    target_state.attributes = {"current_position": 60}

    await shade._async_verify_movement()
    assert shade._is_moving is False
    assert shade._is_manual_override is False
    assert shade._last_set_position == 60

    # Case D: Requested 50%, stopped at 61% (delta = 11 > tolerance) -> INTERCEPTED
    shade._is_moving = True
    shade._requested_position = 50
    target_state.attributes = {"current_position": 61}

    with patch("custom_components.shade_complete.cover.async_call_later"):
        await shade._async_verify_movement()
    assert shade._is_moving is False
    assert shade._is_manual_override is True


async def test_manual_override_sensitivity_exact_boundaries(mock_hass, mock_config_entry):
    """Test exact boundary transitions for manual override detection sensitivity."""
    mock_config_entry.data["position_change_sensitivity"] = 5
    shade = SmartTrackingShadeCover(
        mock_hass, mock_config_entry, "cover.physical_blind", "Office Shade"
    )
    shade._initialized = True
    shade._last_set_position = 50
    shade._is_moving = False
    shade.async_write_ha_state = MagicMock()

    # Move to 55 (delta = 5 <= sensitivity): within tolerance, NOT override
    event_55 = MagicMock(data={"new_state": MagicMock(attributes={"current_position": 55})})
    await shade._async_target_state_changed(event_55)
    assert shade._is_manual_override is False
    assert shade._last_set_position == 55

    # Move from 55 to 61 (delta = 6 > sensitivity): OVERRIDE TRIGGERED
    event_61 = MagicMock(data={"new_state": MagicMock(attributes={"current_position": 61})})
    with patch("custom_components.shade_complete.cover.async_call_later"):
        await shade._async_target_state_changed(event_61)
    assert shade._is_manual_override is True
    assert "Manual move detected" in shade._inactive_reason


async def test_group_shade_empty_or_unavailable_members(mock_hass, mock_config_entry):
    """Test group shade graceful degradation when members are empty or unavailable."""
    # 1. Group with empty member list
    empty_group = GroupShadeCover(mock_hass, mock_config_entry, [], "Empty Group")
    assert empty_group.current_cover_position is None
    assert empty_group.is_closed is None
    assert empty_group.current_cover_tilt_position is None

    # 2. Group with one available member (60%) and one unavailable member
    group = GroupShadeCover(
        mock_hass, mock_config_entry, ["cover.shade_1", "cover.shade_2"], "Bay Group"
    )
    st1 = MagicMock(attributes={"current_position": 60, "current_tilt_position": 40})
    st2 = None  # shade_2 is unavailable / missing in state machine
    mock_hass.states.get.side_effect = lambda ent: st1 if ent == "cover.shade_1" else st2

    assert group.current_cover_position == 60
    assert group.is_closed is False
    assert group.current_cover_tilt_position == 40



