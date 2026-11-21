"""Select platform for controller-wide Roth Touchline operating mode."""

from __future__ import annotations

from pytouchline_extended import ControllerOperationMode, TouchlineError

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TouchlineConfigEntry, TouchlineDataUpdateCoordinator
from .entity import TouchlineControllerEntity

PARALLEL_UPDATES = 0

MODE_TO_OPTION: dict[ControllerOperationMode, str] = {
    ControllerOperationMode.DAY: "day",
    ControllerOperationMode.NIGHT: "night",
    ControllerOperationMode.OFF_HOLIDAY: "off_holiday",
}
OPTION_TO_MODE: dict[str, ControllerOperationMode] = {
    option: mode for mode, option in MODE_TO_OPTION.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TouchlineConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the controller-wide operating mode select entity."""
    coordinator = entry.runtime_data
    async_add_entities([TouchlineControllerModeSelect(coordinator)])


class TouchlineControllerModeSelect(TouchlineControllerEntity, SelectEntity):
    """Select entity controlling R0.OPModeRegler across all paired rooms."""

    _attr_translation_key = "controller_operation_mode"
    _attr_options = list(OPTION_TO_MODE)
    _attr_icon = "mdi:home-thermometer-outline"

    def __init__(self, coordinator: TouchlineDataUpdateCoordinator) -> None:
        """Initialize the controller operating mode select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.hub_id}_operation_mode"

    @property
    def current_option(self) -> str | None:
        """Return the active controller-wide operating mode option."""
        mode = self.controller_status.operation_mode
        if isinstance(mode, ControllerOperationMode):
            return MODE_TO_OPTION.get(mode)
        return None

    async def async_select_option(self, option: str) -> None:
        """Apply a new controller-wide operating mode via R0.OPModeRegler."""
        if (mode := OPTION_TO_MODE.get(option)) is None:
            raise HomeAssistantError(f"Unsupported controller mode option: {option}")
        try:
            ok = await self.coordinator.controller.set_controller_operation_mode_async(
                mode
            )
        except TouchlineError as err:
            raise HomeAssistantError(
                f"Failed to set controller operating mode to {option}: {err}"
            ) from err
        if not ok:
            raise HomeAssistantError(
                f"Controller rejected operating mode change to {option}"
            )
        await self.coordinator.async_request_refresh()
