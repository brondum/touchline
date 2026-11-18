"""Config flow for Roth Touchline floor heating controller."""

from __future__ import annotations

import re
from typing import Any

from pytouchline_extended import PyTouchline, TouchlineError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client

from .const import _LOGGER, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

RESULT_SUCCESS = "success"
RESULT_CANNOT_CONNECT = "cannot_connect"


async def _async_try_connect_and_fetch_basic_info(
    hass: HomeAssistant, host: str
) -> dict[str, Any]:
    """Attempt to connect and, if successful, fetch number of devices."""
    client = get_async_client(hass, verify_ssl=False)
    py_touchline = PyTouchline(url=host, client=client)
    result: dict[str, Any] = {"type": None, "data": {}}
    number_of_devices = None
    device = PyTouchline(id=0, url=host, client=client)
    try:
        number_of_devices = await py_touchline.get_number_of_devices_async()
        if number_of_devices:
            await device.update_async()
            result["data"] = device.get_controller_id()
            if result["data"] is not None:
                result["type"] = RESULT_SUCCESS
            return result
    except TouchlineError as e:
        _LOGGER.debug(
            "Failed to connect to device %s: %s. Check the IP address "
            "as well as whether the device is connected to power and network",
            host,
            e,
        )
        result["type"] = RESULT_CANNOT_CONNECT
    _LOGGER.debug(
        "Number of devices found: %s",
        number_of_devices,
    )
    return result


class TouchlineConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roth Touchline."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors = {}
        result = {"type": None, "data": {}}

        if user_input is not None:

            # Abort if an entry with same host is present.
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            errors = self._validate_input(user_input)
            if errors:
                return self.async_show_form(
                    step_id="user", data_schema=DATA_SCHEMA, errors=errors
                )

            result = await _async_try_connect_and_fetch_basic_info(
                self.hass, user_input[CONF_HOST]
            )

            if result["type"] != RESULT_SUCCESS:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(result["data"])
                self._abort_if_unique_id_configured()
                _LOGGER.debug("Host: %s", user_input[CONF_HOST])
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
        
        return self.async_show_form(
            step_id="user", 
            data_schema=DATA_SCHEMA,
            errors = errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import a configuration from yaml configuration."""
        result = await _async_try_connect_and_fetch_basic_info(
            self.hass, user_input[CONF_HOST]
        )

        if result["type"] != RESULT_SUCCESS:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(result["data"])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    def _validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate the user input."""
        errors = {}
        host = user_input[CONF_HOST]
        # Remove HTTPS and HTTP schema from URL.
        pattern = "https?://"
        host = re.sub(pattern, "", host)
        host = "http://" + host
        user_input[CONF_HOST] = host
        if not cv.url(host):
            errors["base"] = "invalid_input"
        else:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
        return errors
