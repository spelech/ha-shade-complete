"""The Shade Complete integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_CALIBRATE_BATTERY,
    SERVICE_RESET_OVERRIDE,
    SERVICE_TRIGGER_AUTO_CLOSE,
    SERVICE_TRIGGER_AUTO_OPEN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SENSOR]

CALIBRATE_BATTERY_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("min_val"): vol.Coerce(float),
        vol.Optional("max_val"): vol.Coerce(float),
    }
)

RESET_OVERRIDE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)

TRIGGER_AUTO_CLOSE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)

TRIGGER_AUTO_OPEN_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Shade Complete integration and register domain services."""
    hass.data.setdefault(DOMAIN, {})

    async def handle_calibrate_battery(call: ServiceCall) -> None:
        """Handle calibrate_battery service call."""
        entity_id = call.data["entity_id"]
        min_val = call.data.get("min_val")
        max_val = call.data.get("max_val")
        _LOGGER.info(
            "Service calibrate_battery called for %s (min: %s, max: %s)",
            entity_id,
            min_val,
            max_val,
        )
        # Dispatch event for entity to consume
        hass.bus.async_fire(
            f"{DOMAIN}_service_calibrate_battery",
            {"entity_id": entity_id, "min_val": min_val, "max_val": max_val},
        )

    async def handle_reset_override(call: ServiceCall) -> None:
        """Handle reset_manual_override service call."""
        entity_id = call.data["entity_id"]
        _LOGGER.info("Service reset_manual_override called for %s", entity_id)
        hass.bus.async_fire(
            f"{DOMAIN}_service_reset_override",
            {"entity_id": entity_id},
        )

    async def handle_trigger_auto_close(call: ServiceCall) -> None:
        """Handle trigger_auto_close service call."""
        entity_id = call.data["entity_id"]
        _LOGGER.info("Service trigger_auto_close called for %s", entity_id)
        hass.bus.async_fire(
            f"{DOMAIN}_service_trigger_auto_close",
            {"entity_id": entity_id},
        )

    async def handle_trigger_auto_open(call: ServiceCall) -> None:
        """Handle trigger_auto_open service call."""
        entity_id = call.data["entity_id"]
        _LOGGER.info("Service trigger_auto_open called for %s", entity_id)
        hass.bus.async_fire(
            f"{DOMAIN}_service_trigger_auto_open",
            {"entity_id": entity_id},
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CALIBRATE_BATTERY,
        handle_calibrate_battery,
        schema=CALIBRATE_BATTERY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_OVERRIDE,
        handle_reset_override,
        schema=RESET_OVERRIDE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_TRIGGER_AUTO_CLOSE,
        handle_trigger_auto_close,
        schema=TRIGGER_AUTO_CLOSE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_TRIGGER_AUTO_OPEN,
        handle_trigger_auto_open,
        schema=TRIGGER_AUTO_OPEN_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shade Complete from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Shade Complete config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry upon options update."""
    await hass.config_entries.async_reload(entry.entry_id)
