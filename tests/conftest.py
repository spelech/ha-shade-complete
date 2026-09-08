"""Test configuration and fixtures for Shade Complete."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance with event bus and services."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}

    mock_loop = MagicMock()
    mock_loop.call_later.return_value = MagicMock()
    mock_loop.time.return_value = 1000.0
    hass.loop = mock_loop

    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.services.async_register = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_listen_once = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()

    return hass
