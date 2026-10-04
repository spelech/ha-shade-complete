"""Unit tests for device registry cohabitation helper."""

from unittest.mock import MagicMock, patch

from custom_components.shade_complete.const import DOMAIN
from custom_components.shade_complete.device import async_get_device_info_for_target


def test_device_info_with_existing_device(mock_hass):
    """Test attaching to an existing device card in the device registry."""
    ent_entry = MagicMock()
    ent_entry.device_id = "device_123"

    dev_entry = MagicMock()
    dev_entry.identifiers = {("zwave_js", "node_5")}
    dev_entry.connections = {("mac", "AA:BB:CC:DD:EE:FF")}

    with (
        patch("homeassistant.helpers.entity_registry.async_get") as mock_er,
        patch("homeassistant.helpers.device_registry.async_get") as mock_dr,
    ):
        mock_er.return_value.async_get.return_value = ent_entry
        mock_dr.return_value.async_get.return_value = dev_entry

        info = async_get_device_info_for_target(
            mock_hass, "cover.living_room", "Living Room Shade", "entry_abc"
        )

        assert info["identifiers"] == {("zwave_js", "node_5")}
        assert info["connections"] == {("mac", "AA:BB:CC:DD:EE:FF")}


def test_device_info_fallback(mock_hass):
    """Test fallback to a virtual Shade Complete device when no physical device exists."""
    with (
        patch("homeassistant.helpers.entity_registry.async_get") as mock_er,
        patch("homeassistant.helpers.device_registry.async_get") as mock_dr,
    ):
        mock_er.return_value.async_get.return_value = None
        mock_dr.return_value.async_get.return_value = None

        info = async_get_device_info_for_target(
            mock_hass, "cover.virtual_shade", "Virtual Shade", "entry_xyz"
        )

        assert (DOMAIN, "entry_xyz_cover.virtual_shade") in info["identifiers"]
        assert info["name"] == "Virtual Shade"
        assert info["manufacturer"] == "Shade Complete"


def test_async_set_entity_hidden_state(mock_hass):
    """Test setting and clearing hidden_by=INTEGRATION in the entity registry."""
    from homeassistant.helpers.entity_registry import RegistryEntryHider

    from custom_components.shade_complete.device import async_set_entity_hidden_state

    entry1 = MagicMock()
    entry1.hidden_by = None

    entry2 = MagicMock()
    entry2.hidden_by = RegistryEntryHider.USER  # Should not be overridden

    entry3 = MagicMock()
    entry3.hidden_by = RegistryEntryHider.INTEGRATION

    mock_reg = MagicMock()

    def mock_get(eid):
        if eid == "cover.target1":
            return entry1
        if eid == "cover.target2":
            return entry2
        if eid == "cover.target3":
            return entry3
        return None

    mock_reg.async_get.side_effect = mock_get

    with patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_reg):
        # Hide target1 and target2
        async_set_entity_hidden_state(mock_hass, ["cover.target1", "cover.target2"], hidden=True)
        mock_reg.async_update_entity.assert_called_once_with(
            "cover.target1", hidden_by=RegistryEntryHider.INTEGRATION
        )

        mock_reg.async_update_entity.reset_mock()

        # Unhide target3 (hidden by integration) and target2 (user-hidden, untouched)
        async_set_entity_hidden_state(mock_hass, ["cover.target3", "cover.target2"], hidden=False)
        mock_reg.async_update_entity.assert_called_once_with("cover.target3", hidden_by=None)


def test_async_set_entity_hidden_state_graceful_exception(mock_hass):
    """Test that exceptions during registry access degrade gracefully without raising."""
    from custom_components.shade_complete.device import async_set_entity_hidden_state

    with patch("homeassistant.helpers.entity_registry.async_get", side_effect=RuntimeError("Boom")):
        # Should not raise
        async_set_entity_hidden_state(mock_hass, "cover.target", hidden=True)
