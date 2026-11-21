"""Platform for Roth Touchline floor heating controller."""

from __future__ import annotations

from typing import Any

from pytouchline_extended import TouchlineController, TouchlineState

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import _LOGGER, DOMAIN
from .coordinator import TouchlineConfigEntry, TouchlineDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
]


async def _async_import(hass: HomeAssistant, base_config: ConfigType) -> None:
    """Import a config entry from configuration.yaml."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=base_config[DOMAIN],
    )
    if (
        result["type"] == FlowResultType.CREATE_ENTRY
        or result["reason"] == "single_instance_allowed"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Touchline",
            },
        )
        return
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_import_issue_{result['reason']}",
        breaks_in_ha_version="2024.10.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Touchline",
        },
    )


async def async_setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up the Touchline component."""
    if DOMAIN in base_config:
        hass.async_create_task(_async_import(hass, base_config))
    return True


async def _async_migrate_entity_registry(
    hass: HomeAssistant,
    entry: TouchlineConfigEntry,
    state: TouchlineState,
) -> None:
    """Migrate legacy integer climate unique_ids (controller_id + device_id) in place."""
    ent_reg = er.async_get(hass)
    legacy_map: dict[str, str] = {}
    ambiguous: set[str] = set()

    for room in state.rooms:
        if (
            room.controller_id is None
            or room.device_id is None
            or room.unique_id is None
        ):
            continue
        legacy_id = str(room.controller_id + room.device_id)
        if legacy_id in legacy_map and legacy_map[legacy_id] != room.unique_id:
            ambiguous.add(legacy_id)
        else:
            legacy_map[legacy_id] = room.unique_id

    for key in ambiguous:
        legacy_map.pop(key, None)

    if not legacy_map:
        return

    @callback
    def _migrate_callback(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        if entity_entry.domain != Platform.CLIMATE:
            return None
        current_uid = str(entity_entry.unique_id)
        new_uid = legacy_map.get(current_uid)
        if not new_uid or new_uid == current_uid:
            return None
        if ent_reg.async_get_entity_id(Platform.CLIMATE, DOMAIN, new_uid) is not None:
            return None
        _LOGGER.info(
            "Migrating %s unique_id from legacy %s to %s",
            entity_entry.entity_id,
            entity_entry.unique_id,
            new_uid,
        )
        return {"new_unique_id": new_uid}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate_callback)


async def async_setup_entry(hass: HomeAssistant, entry: TouchlineConfigEntry) -> bool:
    """Set up Roth Touchline from a config entry."""
    if entry.unique_id is not None and not isinstance(entry.unique_id, str):
        hass.config_entries.async_update_entry(entry, unique_id=str(entry.unique_id))

    host = entry.data[CONF_HOST]
    client = get_async_client(hass, verify_ssl=False)
    controller = TouchlineController(url=host, client=client)
    coordinator = TouchlineDataUpdateCoordinator(hass, entry, controller)

    await coordinator.async_config_entry_first_refresh()
    await _async_migrate_entity_registry(hass, entry, coordinator.data)

    hub_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **coordinator.build_hub_device_info(),
    )
    coordinator.hub_device_id = hub_device.id

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: TouchlineConfigEntry
) -> None:
    """Handle options or reconfigure updates."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TouchlineConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
