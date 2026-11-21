"""Climate platform for Roth Touchline floor heating controller."""

from __future__ import annotations

from typing import Any, NamedTuple

from pytouchline_extended import (
    RoomOperationMode,
    RoomStatus,
    TemperatureUnit,
    TouchlineError,
    WeekProgram,
)
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import ATTR_TEMPERATURE, CONF_HOST, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    _LOGGER,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_TEMP_STEP,
    DOMAIN,
)
from .coordinator import TouchlineConfigEntry, TouchlineDataUpdateCoordinator
from .entity import TouchlineRoomEntity

PARALLEL_UPDATES = 0


class PresetMode(NamedTuple):
    """Settings for a Touchline room preset mode."""

    mode: RoomOperationMode
    program: WeekProgram


PRESET_MODES: dict[str, PresetMode] = {
    "Normal": PresetMode(mode=RoomOperationMode.NORMAL, program=WeekProgram.OFF),
    "Night": PresetMode(mode=RoomOperationMode.NIGHT, program=WeekProgram.OFF),
    "Holiday": PresetMode(mode=RoomOperationMode.HOLIDAY, program=WeekProgram.OFF),
    "Pro 1": PresetMode(mode=RoomOperationMode.NORMAL, program=WeekProgram.PRO_1),
    "Pro 2": PresetMode(mode=RoomOperationMode.NORMAL, program=WeekProgram.PRO_2),
    "Pro 3": PresetMode(mode=RoomOperationMode.NORMAL, program=WeekProgram.PRO_3),
}

TOUCHLINE_HA_PRESETS: dict[tuple[int, int], str] = {
    (int(settings.mode), int(settings.program)): preset
    for preset, settings in PRESET_MODES.items()
}

WEEK_PROGRAM_PRESETS: dict[int, str] = {
    int(WeekProgram.PRO_1): "Pro 1",
    int(WeekProgram.PRO_2): "Pro 2",
    int(WeekProgram.PRO_3): "Pro 3",
}

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string})


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import legacy YAML climate platform configuration into config entries."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.source == SOURCE_IMPORT:
            return

    host = config.get(CONF_HOST)
    if not host:
        _LOGGER.error("No Roth Touchline host configured")
        return

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: host},
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TouchlineConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roth Touchline room climate entities from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        TouchlineClimate(coordinator, room) for room in coordinator.data.rooms
    )


class TouchlineClimate(TouchlineRoomEntity, ClimateEntity):
    """Representation of a Roth Touchline room thermostat."""

    _attr_name = None
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_preset_modes = list(PRESET_MODES)

    def __init__(
        self,
        coordinator: TouchlineDataUpdateCoordinator,
        room: RoomStatus,
    ) -> None:
        """Initialize a Touchline room climate entity."""
        super().__init__(coordinator, room)
        self._attr_unique_id = self.room_uid

    def _require_room(self) -> RoomStatus:
        """Return the current RoomStatus or raise HomeAssistantError if unavailable."""
        if (room := self.room) is None:
            raise HomeAssistantError("Room thermostat is currently unavailable")
        return room

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement configured on the thermostat."""
        if (
            (room := self.room) is not None
            and room.temperature_unit == TemperatureUnit.FAHRENHEIT
        ):
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def min_temp(self) -> float:
        """Return the minimum allowed setpoint configured for this room."""
        if (room := self.room) is not None and room.min_temperature is not None:
            return room.min_temperature
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum allowed setpoint configured for this room."""
        if (room := self.room) is not None and room.max_temperature is not None:
            return room.max_temperature
        return DEFAULT_MAX_TEMP

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        if (room := self.room) is not None and room.temperature_step is not None:
            return room.temperature_step
        return DEFAULT_TEMP_STEP

    @property
    def current_temperature(self) -> float | None:
        """Return the current measured room temperature at 0.01 °C resolution."""
        return room.temperature if (room := self.room) is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target room setpoint temperature."""
        return room.target_temperature if (room := self.room) is not None else None

    @property
    def preset_mode(self) -> str | None:
        """Return the active Touchline preset mode."""
        if (room := self.room) is None or room.operation_mode is None:
            return None
        program = int(room.week_program) if room.week_program is not None else 0
        if program in WEEK_PROGRAM_PRESETS:
            return WEEK_PROGRAM_PRESETS[program]
        return TOUCHLINE_HA_PRESETS.get((int(room.operation_mode), program))

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode (OFF when in Holiday mode without a schedule)."""
        if (
            (room := self.room) is not None
            and room.operation_mode == RoomOperationMode.HOLIDAY
            and room.week_program in (None, WeekProgram.OFF)
        ):
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Estimate HVAC action from target vs current room temperature."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        room = self.room
        if (
            room is None
            or room.temperature is None
            or room.target_temperature is None
        ):
            return None
        if room.target_temperature > room.temperature:
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target room temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        room = self._require_room()
        try:
            ok = await self.coordinator.controller.set_room_target_temperature_async(
                room.index, float(temperature)
            )
        except TouchlineError as err:
            raise HomeAssistantError(
                f"Failed to set target temperature for {room.name or self.entity_id}: {err}"
            ) from err
        if not ok:
            raise HomeAssistantError(
                f"Controller rejected target temperature {temperature} for {room.name or self.entity_id}"
            )
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a new Touchline preset mode (Normal, Night, Holiday, Pro 1..3)."""
        if (preset := PRESET_MODES.get(preset_mode)) is None:
            raise HomeAssistantError(f"Unsupported preset mode: {preset_mode}")
        room = self._require_room()
        try:
            ok_mode = await self.coordinator.controller.set_room_operation_mode_async(
                room.index, preset.mode
            )
            ok_prog = await self.coordinator.controller.set_room_week_program_async(
                room.index, preset.program
            )
        except TouchlineError as err:
            raise HomeAssistantError(
                f"Failed to set preset mode {preset_mode} for {room.name or self.entity_id}: {err}"
            ) from err
        if not (ok_mode and ok_prog):
            raise HomeAssistantError(
                f"Controller rejected preset mode {preset_mode} for {room.name or self.entity_id}"
            )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Switch room between HVACMode.HEAT (Normal) and HVACMode.OFF (Holiday)."""
        room = self._require_room()
        try:
            if hvac_mode == HVACMode.OFF:
                ok_mode = (
                    await self.coordinator.controller.set_room_operation_mode_async(
                        room.index, RoomOperationMode.HOLIDAY
                    )
                )
                ok_prog = True
                if room.week_program not in (None, WeekProgram.OFF):
                    ok_prog = (
                        await self.coordinator.controller.set_room_week_program_async(
                            room.index, WeekProgram.OFF
                        )
                    )
                if not (ok_mode and ok_prog):
                    raise HomeAssistantError(
                        f"Controller rejected turning off {room.name or self.entity_id}"
                    )
            elif hvac_mode == HVACMode.HEAT:
                if room.operation_mode == RoomOperationMode.HOLIDAY:
                    ok_mode = (
                        await self.coordinator.controller.set_room_operation_mode_async(
                            room.index, RoomOperationMode.NORMAL
                        )
                    )
                    if not ok_mode:
                        raise HomeAssistantError(
                            f"Controller rejected enabling heating on {room.name or self.entity_id}"
                        )
            else:
                raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        except TouchlineError as err:
            raise HomeAssistantError(
                f"Failed to set HVAC mode {hvac_mode} for {room.name or self.entity_id}: {err}"
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the room thermostat on (Heat / Normal)."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the room thermostat off (Holiday / Frost protection)."""
        await self.async_set_hvac_mode(HVACMode.OFF)
