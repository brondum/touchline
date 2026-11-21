"""Diagnostics support for Roth Touchline controllers."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import TouchlineConfigEntry

TO_REDACT = {
    CONF_HOST,
    "hostname",
    "ip_address",
    "mac_address",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: TouchlineConfigEntry,
) -> dict[str, Any]:
    """Return redacted diagnostics for a Roth Touchline config entry."""
    coordinator = entry.runtime_data
    state_dict = asdict(coordinator.data) if coordinator.data is not None else None
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "state": async_redact_data(state_dict, TO_REDACT),
    }
