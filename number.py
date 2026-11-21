"""Number platform for per-room Roth Touchline min/max setpoint limits."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pytouchline_extended import (
    RoomStatus,
    TemperatureUnit,
    TouchlineController,
    TouchlineError,
)

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_TEMP_STEP
from .coordinator import TouchlineConfigEntry, TouchlineDataUpdateCoordinator
from .entity import TouchlineRoomEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TouchlineRoomNumberDescription(NumberEntityDescription):
    """Describes a writable Roth Touchline room temperature limit number entity."""

    value_fn: Callable[[RoomStatus], float | None]
    set_value_fn: Callable[[TouchlineController, int, float], Awaitable[bool]]


ROOM_NUMBER_DESCRIPTIONS: tuple[TouchlineRoomNumberDescription, ...] = (
    TouchlineRoomNumberDescription(
        key="min_temperature",
        translation_key="min_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=5.0,
        native_max_value=30.0,
        native_step=DEFAULT_TEMP_STEP,
        value_fn=lambda room: room.min_temperature,
        set_value_fn=lambda ctrl, idx, val: ctrl.set_room_min_temperature_async(
            idx, val
        ),
    ),
    TouchlineRoomNumberDescription(
        key="max_temperature",
        translation_key="max_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=5.0,
        native_max_value=40.0,
        native_step=DEFAULT_TEMP_STEP,
        value_fn=lambda room: room.max_temperature,
        set_value_fn=lambda ctrl, idx, val: ctrl.set_room_max_temperature_async(
            idx, val
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TouchlineConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up per-room min/max setpoint limit NumberEntities."""
    coordinator = entry.runtime_data
    async_add_entities(
        TouchlineRoomSetpointLimitNumber(coordinator, room, description)
        for room in coordinator.data.rooms
        for description in ROOM_NUMBER_DESCRIPTIONS
    )


class TouchlineRoomSetpointLimitNumber(TouchlineRoomEntity, NumberEntity):
    """Configurable min or max setpoint limit on a Roth Touchline room thermostat."""

    entity_description: TouchlineRoomNumberDescription

    def __init__(
        self,
        coordinator: TouchlineDataUpdateCoordinator,
        room: RoomStatus,
        description: TouchlineRoomNumberDescription,
    ) -> None:
        """Initialize the room setpoint limit number entity."""
        super().__init__(coordinator, room)
        self.entity_description = description
        self._attr_unique_id = f"{self.room_uid}_{description.key}"

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the temperature unit configured on the room thermostat."""
        if (
            (room := self.room) is not None
            and room.temperature_unit == TemperatureUnit.FAHRENHEIT
        ):
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return the current room min or max setpoint limit."""
        if (room := self.room) is None:
            return None
        return self.entity_description.value_fn(room)

    async def async_set_native_value(self, value: float) -> None:
        """Write a new room min or max setpoint limit to the controller."""
        if (room := self.room) is None:
            raise HomeAssistantError("Room thermostat is currently unavailable")
        try:
            ok = await self.entity_description.set_value_fn(
                self.coordinator.controller, room.index, value
            )
        except TouchlineError as err:
            raise HomeAssistantError(
                f"Failed to set {self.entity_description.key} for {room.name or self.entity_id}: {err}"
            ) from err
        if not ok:
            raise HomeAssistantError(
                f"Controller rejected {self.entity_description.key}={value} for {room.name or self.entity_id}"
            )
        await self.coordinator.async_request_refresh()
