"""Config flow for Roth Touchline floor heating controller."""

from __future__ import annotations

import re
from typing import Any

from pytouchline_extended import TouchlineController, TouchlineError, TouchlineState
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client

from .const import _LOGGER, DOMAIN


def _build_schema(default_host: str | None = None) -> vol.Schema:
    """Build the config/reconfigure schema for the controller URL."""
    if default_host:
        return vol.Schema({vol.Required(CONF_HOST, default=default_host): str})
    return vol.Schema({vol.Required(CONF_HOST): str})


def _normalize_host(raw_host: str) -> str:
    """Normalize a user-provided IP/hostname/URL into ``http://<host>``."""
    cleaned = re.sub(r"^https?://", "", raw_host.strip()).rstrip("/")
    return f"http://{cleaned}"


async def _async_fetch_controller_state(
    hass: HomeAssistant, host: str
) -> TouchlineState:
    """Connect to the Touchline controller and fetch its full initial snapshot."""
    client = get_async_client(hass, verify_ssl=False)
    controller = TouchlineController(url=host, client=client)
    return await controller.fetch_async()


class TouchlineConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roth Touchline."""

    VERSION = 1

    def _entry_matches_controller(
        self,
        state: TouchlineState,
        *,
        exclude_entry_id: str | None = None,
    ) -> bool:
        """Check whether an existing entry already represents the same physical controller."""
        ctrl = state.controller
        candidate_ids = {
            str(val)
            for val in (ctrl.unique_id, ctrl.controller_id)
            if val is not None and str(val) != ""
        }
        if not candidate_ids:
            return False

        for entry in self._async_current_entries():
            if exclude_entry_id and entry.entry_id == exclude_entry_id:
                continue
            if entry.unique_id is not None and str(entry.unique_id) in candidate_ids:
                return True
        return False

    def _validate_host(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Normalize and validate the controller host URL."""
        host = _normalize_host(user_input[CONF_HOST])
        user_input[CONF_HOST] = host
        try:
            cv.url(host)
        except vol.Invalid:
            return {"base": "invalid_input"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = self._validate_host(user_input)
            if not errors:
                host = user_input[CONF_HOST]
                self._async_abort_entries_match({CONF_HOST: host})

                try:
                    state = await _async_fetch_controller_state(self.hass, host)
                except TouchlineError as err:
                    _LOGGER.debug(
                        "Failed to connect to Touchline controller at %s: %s",
                        host,
                        err,
                    )
                    errors["base"] = "cannot_connect"
                else:
                    if self._entry_matches_controller(state):
                        return self.async_abort(reason="already_configured")

                    ctrl = state.controller
                    unique_id = ctrl.unique_id or (
                        str(ctrl.controller_id)
                        if ctrl.controller_id is not None
                        else None
                    )
                    if unique_id is not None:
                        await self.async_set_unique_id(unique_id)
                        self._abort_if_unique_id_configured()

                    title = ctrl.hostname or host
                    return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(
                user_input.get(CONF_HOST) if user_input else None
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguring the controller host/IP address."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = self._validate_host(user_input)
            if not errors:
                host = user_input[CONF_HOST]
                for entry in self._async_current_entries():
                    if (
                        entry.entry_id != reconfigure_entry.entry_id
                        and entry.data.get(CONF_HOST) == host
                    ):
                        return self.async_abort(reason="already_configured")

                try:
                    state = await _async_fetch_controller_state(self.hass, host)
                except TouchlineError as err:
                    _LOGGER.debug(
                        "Failed to connect to Touchline controller at %s: %s",
                        host,
                        err,
                    )
                    errors["base"] = "cannot_connect"
                else:
                    if self._entry_matches_controller(
                        state, exclude_entry_id=reconfigure_entry.entry_id
                    ):
                        return self.async_abort(reason="wrong_device")

                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data_updates={CONF_HOST: host},
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_schema(reconfigure_entry.data.get(CONF_HOST)),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import a configuration from configuration.yaml."""
        if self._validate_host(user_input):
            return self.async_abort(reason="invalid_input")

        host = user_input[CONF_HOST]
        self._async_abort_entries_match({CONF_HOST: host})

        try:
            state = await _async_fetch_controller_state(self.hass, host)
        except TouchlineError:
            return self.async_abort(reason="cannot_connect")

        if self._entry_matches_controller(state):
            return self.async_abort(reason="already_configured")

        ctrl = state.controller
        unique_id = ctrl.unique_id or (
            str(ctrl.controller_id) if ctrl.controller_id is not None else None
        )
        if unique_id is not None:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=ctrl.hostname or host,
            data={CONF_HOST: host},
        )
