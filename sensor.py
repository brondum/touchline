"""Sensor platform for Roth Touchline Controller alarms and Room temperatures."""

from __future__ import annotations

from typing import Any

from pytouchline_extended import RoomStatus, TemperatureUnit, TouchlineErrorCode

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TouchlineConfigEntry, TouchlineDataUpdateCoordinator
from .entity import TouchlineControllerEntity, TouchlineRoomEntity

PARALLEL_UPDATES = 0

ERROR_CODE_MAP: dict[TouchlineErrorCode, str] = {
    TouchlineErrorCode.NO_ERROR: "no_error",
    TouchlineErrorCode.HIGH_LIMIT_DEW_POINT: "high_limit_dew_point",
    TouchlineErrorCode.HIGH_LIMIT_SUPPLY_WATER: "high_limit_supply_water",
    TouchlineErrorCode.RF_COMMUNICATION_INTERRUPTED: "rf_communication_interrupted",
}
ERROR_CODE_OPTIONS: list[str] = [*ERROR_CODE_MAP.values(), "unknown"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TouchlineConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roth Touchline controller and room sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [TouchlineErrorCodeSensor(coordinator)]
    entities.extend(
        TouchlineRoomTemperatureSensor(coordinator, room)
        for room in coordinator.data.rooms
    )
    async_add_entities(entities)


class TouchlineErrorCodeSensor(TouchlineControllerEntity, SensorEntity):
    """Decoded alarm code sensor on the Roth Touchline Controller Hub."""

    _attr_translation_key = "error_code"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = ERROR_CODE_OPTIONS

    def __init__(self, coordinator: TouchlineDataUpdateCoordinator) -> None:
        """Initialize the controller error code sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.hub_id}_error_code"

    @property
    def native_value(self) -> str | None:
        """Return the active controller alarm state key."""
        code = self.controller_status.error_code
        if code is None:
            return None
        if isinstance(code, TouchlineErrorCode):
            return ERROR_CODE_MAP.get(code, "unknown")
        return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw integer R0.ErrorCode value."""
        code = self.controller_status.error_code
        return {"raw_error_code": int(code) if code is not None else None}


class TouchlineRoomTemperatureSensor(TouchlineRoomEntity, SensorEntity):
    """High-resolution (0.01 °C) room temperature sensor."""

    _attr_translation_key = "room_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: TouchlineDataUpdateCoordinator,
        room: RoomStatus,
    ) -> None:
        """Initialize the room temperature sensor."""
        super().__init__(coordinator, room)
        self._attr_unique_id = f"{self.room_uid}_temperature"

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
        """Return the measured room temperature at full 0.01 °C resolution."""
        return room.temperature if (room := self.room) is not None else None
