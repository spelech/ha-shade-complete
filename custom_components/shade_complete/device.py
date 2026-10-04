"""Device Registry cohabitation helper for Shade Complete."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def async_get_device_info_for_target(
    hass: HomeAssistant,
    target_entity_id: str,
    default_name: str,
    entry_id: str,
) -> DeviceInfo:
    """Retrieve existing DeviceInfo for target cover to co-locate on the physical device card."""
    try:
        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)

        entry = ent_reg.async_get(target_entity_id)
        if entry and entry.device_id:
            existing_device = dev_reg.async_get(entry.device_id)
            if existing_device and existing_device.identifiers:
                return DeviceInfo(
                    identifiers=existing_device.identifiers,
                    connections=existing_device.connections,
                )
    except Exception:
        # Gracefully degrade in test environments or if registries are uninitialized
        pass

    # Fallback to a unified virtual device under Shade Complete
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{target_entity_id}")},
        name=default_name,
        manufacturer="Shade Complete",
        model="Smart Shade Virtual Device",
    )


def async_set_entity_hidden_state(
    hass: HomeAssistant,
    entity_ids: list[str] | str,
    hidden: bool,
) -> None:
    """Set or clear hidden_by=INTEGRATION for target physical entities in entity registry."""
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    try:
        ent_reg = er.async_get(hass)
        target_hider = er.RegistryEntryHider.INTEGRATION if hidden else None
        for eid in entity_ids:
            entry = ent_reg.async_get(eid)
            if entry is not None:
                if hidden:
                    if entry.hidden_by != er.RegistryEntryHider.USER:
                        ent_reg.async_update_entity(eid, hidden_by=target_hider)
                else:
                    if entry.hidden_by == er.RegistryEntryHider.INTEGRATION:
                        ent_reg.async_update_entity(eid, hidden_by=None)
    except Exception:
        # Gracefully handle mock or uninitialized registries
        pass
