"""Config flow for Curb Update Server."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN


def _schema(host: str, port: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PORT, default=port): vol.All(
                int, vol.Range(min=1, max=65535)
            ),
            vol.Optional(CONF_HOST, default=host): str,
        }
    )


class CurbUpdateServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Curb Update Server."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=_schema(DEFAULT_HOST, DEFAULT_PORT)
            )

        return self.async_create_entry(
            title="Curb Update Server", data=user_input
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow handler."""
        return CurbUpdateServerOptionsFlow()


class CurbUpdateServerOptionsFlow(OptionsFlow):
    """Handle Curb Update Server options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                current.get(CONF_HOST, DEFAULT_HOST),
                current.get(CONF_PORT, DEFAULT_PORT),
            ),
        )
