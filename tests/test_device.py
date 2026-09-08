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
