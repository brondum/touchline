"""DataUpdateCoordinator for Roth Touchline controllers."""

from __future__ import annotations

from typing import TypeAlias

from pytouchline_extended import (
    RoomStatus,
    TouchlineController,
    TouchlineError,
    TouchlineState,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DEFAULT_SCAN_INTERVAL, DOMAIN, MANUFACTURER

TouchlineConfigEntry: TypeAlias = ConfigEntry["TouchlineDataUpdateCoordinator"]


class TouchlineDataUpdateCoordinator(DataUpdateCoordinator[TouchlineState]):
    """Coordinator managing serialized chunked polling for one Touchline controller."""

    config_entry: TouchlineConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TouchlineConfigEntry,
        controller: TouchlineController,
    ) -> None:
        """Initialize the Touchline data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{controller.url}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.controller = controller
        self.host = controller.url
        self.hub_device_id: str | None = None

    @property
    def hub_id(self) -> str:
        """Return a stable identifier for the controller hub device."""
        if self.data is not None:
            ctrl = self.data.controller
            if ctrl.unique_id:
                return ctrl.unique_id
            if ctrl.controller_id is not None:
                return str(ctrl.controller_id)
        return self.config_entry.entry_id

    def build_hub_device_info(self) -> DeviceInfo:
        """Build DeviceInfo for the Roth Touchline Controller Hub."""
        ctrl = self.data.controller
        connections: set[tuple[str, str]] = set()
        if ctrl.mac_address:
            connections.add((CONNECTION_NETWORK_MAC, format_mac(ctrl.mac_address)))

        return DeviceInfo(
            identifiers={(DOMAIN, f"controller_{self.hub_id}")},
            connections=connections,
            name=ctrl.hostname or f"Roth Touchline ({self.host})",
            manufacturer=MANUFACTURER,
            model="Touchline Controller",
            serial_number=ctrl.unique_id,
            sw_version=ctrl.stm_app_version,
            hw_version=ctrl.actuator_app_version,
            configuration_url=self.host,
        )

    def get_room(
        self, room_unique_id: str | None, fallback_index: int
    ) -> RoomStatus | None:
        """Look up a room snapshot by persistent unique_id, falling back to slot index."""
        if self.data is None:
            return None
        if room_unique_id is not None:
            for room in self.data.rooms:
                if room.unique_id == room_unique_id:
                    return room
            return None
        for room in self.data.rooms:
            if room.index == fallback_index:
                return room
        return None

    async def _async_update_data(self) -> TouchlineState:
        """Fetch controller and room telemetry in serialized <1,100-byte XML chunks."""
        try:
            return await self.controller.fetch_async()
        except TouchlineError as err:
            raise UpdateFailed(
                f"Error communicating with Touchline controller at {self.host}: {err}"
            ) from err
