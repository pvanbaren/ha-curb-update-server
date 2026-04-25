"""Switch entity that starts and stops the Curb Update Server on demand."""

from __future__ import annotations

import errno
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CurbUpdateServer
from .const import DOMAIN, state_signal


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the server switch entity for this config entry."""
    server: CurbUpdateServer = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CurbUpdateServerSwitch(entry, server)])


class CurbUpdateServerSwitch(SwitchEntity):
    """Toggle the Curb Update Server HTTP listener."""

    _attr_has_entity_name = False
    _attr_name = "Curb Update Server"
    _attr_icon = "mdi:server-network"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, server: CurbUpdateServer) -> None:
        """Initialize the switch."""
        self._entry = entry
        self._server = server
        self._attr_unique_id = f"{entry.entry_id}_server"

    @property
    def is_on(self) -> bool:
        """Return True if the listener is currently bound."""
        return self._server.is_running

    async def async_added_to_hass(self) -> None:
        """Subscribe to start/stop dispatcher signals."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                state_signal(self._entry.entry_id),
                self._handle_state_changed,
            )
        )

    @callback
    def _handle_state_changed(self) -> None:
        """Refresh state when the server starts or stops."""
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the server."""
        try:
            await self._server.async_start()
        except OSError as err:
            host, port = self._server.host, self._server.port
            if err.errno == errno.EACCES:
                msg = (
                    f"Permission denied binding to {host}:{port}. Pick a "
                    "higher port in the integration's options and forward "
                    "port 80 to it at your router."
                )
            elif err.errno in (errno.EADDRINUSE, errno.EADDRNOTAVAIL):
                msg = f"Address {host}:{port} is unavailable: {err}"
            else:
                msg = f"Failed to bind to {host}:{port}: {err}"
            raise HomeAssistantError(msg) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the server."""
        await self._server.async_stop()
