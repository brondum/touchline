"""Binary sensor platform for Roth Touchline Controller Hub alarms."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pytouchline_extended import ControllerStatus, TouchlineErrorCode

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TouchlineConfigEntry, TouchlineDataUpdateCoordinator
from .entity import TouchlineControllerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TouchlineBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Roth Touchline controller diagnostic binary sensor."""

    is_on_fn: Callable[[ControllerStatus], bool | None]


CONTROLLER_BINARY_SENSORS: tuple[TouchlineBinarySensorDescription, ...] = (
    TouchlineBinarySensorDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda ctrl: (
            None
            if (
                ctrl.error_code is None
                and ctrl.safety_tripped is None
                and ctrl.dew_point_active is None
            )
            else (
                ctrl.error_code not in (None, TouchlineErrorCode.NO_ERROR)
                or bool(ctrl.safety_tripped)
                or bool(ctrl.dew_point_active)
            )
        ),
    ),
    TouchlineBinarySensorDescription(
        key="rf_communication_problem",
        translation_key="rf_communication_problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda ctrl: (
            None
            if ctrl.error_code is None
            else ctrl.error_code == TouchlineErrorCode.RF_COMMUNICATION_INTERRUPTED
        ),
    ),
    TouchlineBinarySensorDescription(
        key="safety_tripped",
        translation_key="safety_tripped",
        device_class=BinarySensorDeviceClass.SAFETY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda ctrl: ctrl.safety_tripped,
    ),
    TouchlineBinarySensorDescription(
        key="dew_point_active",
        translation_key="dew_point_active",
        device_class=BinarySensorDeviceClass.MOISTURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda ctrl: ctrl.dew_point_active,
    ),
    TouchlineBinarySensorDescription(
        key="week_program_warning",
        translation_key="week_program_warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda ctrl: ctrl.week_program_warning,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TouchlineConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roth Touchline controller alarm binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        TouchlineControllerBinarySensor(coordinator, description)
        for description in CONTROLLER_BINARY_SENSORS
    )


class TouchlineControllerBinarySensor(TouchlineControllerEntity, BinarySensorEntity):
    """Diagnostic binary sensor on a Roth Touchline Controller Hub."""

    entity_description: TouchlineBinarySensorDescription

    def __init__(
        self,
        coordinator: TouchlineDataUpdateCoordinator,
        description: TouchlineBinarySensorDescription,
    ) -> None:
        """Initialize the controller binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.hub_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return True if the controller alarm flag is active."""
        return self.entity_description.is_on_fn(self.controller_status)
