"""Base CoordinatorEntity classes for Roth Touchline Hub and Room devices."""

from __future__ import annotations

from pytouchline_extended import ControllerStatus, RoomStatus

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import TouchlineDataUpdateCoordinator


class TouchlineControllerEntity(CoordinatorEntity[TouchlineDataUpdateCoordinator]):
    """Base entity bound to a Roth Touchline Controller Hub device."""

    _attr_has_entity_name = True

    @property
    def controller_status(self) -> ControllerStatus:
        """Return the latest controller snapshot from the coordinator."""
        return self.coordinator.data.controller

    @property
    def device_info(self) -> DeviceInfo:
        """Return DeviceInfo for the Roth Touchline Controller Hub."""
        return self.coordinator.build_hub_device_info()


class TouchlineRoomEntity(CoordinatorEntity[TouchlineDataUpdateCoordinator]):
    """Base entity bound to an individual Roth Touchline Room Thermostat device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TouchlineDataUpdateCoordinator,
        room: RoomStatus,
    ) -> None:
        """Initialize a room thermostat entity."""
        super().__init__(coordinator)
        self._room_unique_id = room.unique_id
        self._fallback_index = room.index
        self._initial_name = room.name
        self.room_uid = (
            room.unique_id
            if room.unique_id is not None
            else f"{coordinator.hub_id}-room-{room.index}"
        )

    @property
    def room(self) -> RoomStatus | None:
        """Return the latest snapshot for this room thermostat."""
        return self.coordinator.get_room(self._room_unique_id, self._fallback_index)

    @property
    def available(self) -> bool:
        """Return True if coordinator is available and room is present."""
        return super().available and self.room is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return DeviceInfo linking this room thermostat to its Controller Hub."""
        current_room = self.room
        room_name = (
            (current_room.name if current_room and current_room.name else None)
            or self._initial_name
            or f"Room {self._fallback_index + 1}"
        )
        info = DeviceInfo(
            identifiers={(DOMAIN, f"room_{self.room_uid}")},
            name=room_name,
            manufacturer=MANUFACTURER,
            model="Touchline Room Thermostat",
        )
        if self.coordinator.hub_device_id is not None:
            info["via_device_id"] = self.coordinator.hub_device_id
        return info
