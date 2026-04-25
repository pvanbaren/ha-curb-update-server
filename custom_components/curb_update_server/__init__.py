"""
Curb Update Server integration for Home Assistant.

Serves firmware update files for Curb Energy Monitors to enable root access.
The HTTP listener is started and stopped on demand via the Curb Update Server
switch and auto-stops after AUTO_STOP_SECONDS as a safety so it doesn't sit
listening indefinitely after the device has been updated.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from datetime import datetime

from homeassistant.components.persistent_notification import (
    async_create as async_create_notification,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .const import (
    AUTO_STOP_SECONDS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    REQUIRED_FILES,
    state_signal,
)

PLATFORMS: list[Platform] = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


def validate_curbed_directory(directory: Path) -> bool:
    """Validate that the curbed directory contains all required files."""
    if not directory.exists() or not directory.is_dir():
        return False

    for filename in REQUIRED_FILES:
        file_path = directory / filename
        if not file_path.exists():
            _LOGGER.debug("Missing file: %s", file_path)
            return False

        if file_path.stat().st_size == 0:
            _LOGGER.warning("File appears to be empty: %s", file_path)
            return False

    return True


class CurbUpdateServer:
    """Curb Update Server class."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        curbed_dir: Path,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ):
        """Initialize the server."""
        self.hass = hass
        self.entry = entry
        self.curbed_dir = curbed_dir
        self.host = host
        self.port = port
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._auto_stop_unsub = None

    @property
    def is_running(self) -> bool:
        """Return whether the HTTP listener is currently bound."""
        return self._site is not None

    async def async_start(self) -> None:
        """Start the update server. Raises OSError on bind failure."""
        if self.is_running:
            return

        app = web.Application()
        app.router.add_get("/api/firmware/{filename}", self._handle_firmware)
        app.router.add_get(
            "/api/firmware/{serial}/{filename}", self._handle_firmware
        )

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        try:
            await self._site.start()
        except OSError:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
            raise

        self._auto_stop_unsub = async_call_later(
            self.hass, AUTO_STOP_SECONDS, self._async_auto_stop
        )
        async_dispatcher_send(self.hass, state_signal(self.entry.entry_id))

        _LOGGER.info(
            "Curb Update Server started on %s:%d. "
            "Redirect 'updates.energycurb.com' to this Home Assistant instance. "
            "The server will auto-stop after %d seconds.",
            self.host,
            self.port,
            AUTO_STOP_SECONDS,
        )

    async def _async_auto_stop(self, _now: datetime) -> None:
        """Stop the server after the safety timer elapses."""
        self._auto_stop_unsub = None
        if self._site is None:
            return

        _LOGGER.warning(
            "Auto-stopping Curb Update Server after %d seconds. "
            "Toggle the switch back on if you still need to deliver the payload.",
            AUTO_STOP_SECONDS,
        )
        async_create_notification(
            self.hass,
            title="Curb Update Server auto-stopped",
            message=(
                f"The Curb Update Server has been stopped automatically "
                f"after {AUTO_STOP_SECONDS // 60} minutes for safety. Toggle "
                "the **Curb Update Server** switch back on if you still need "
                "to deliver the payload."
            ),
            notification_id=f"{DOMAIN}_auto_stopped_{self.entry.entry_id}",
        )
        await self.async_stop()

    async def _handle_firmware(self, request: web.Request) -> web.StreamResponse:
        """Serve firmware files.

        The Curb device requests files at either /api/firmware/<file> or
        /api/firmware/<serial>/<file> depending on its firmware revision; the
        serial segment is informational and discarded — every device gets the
        same payload.
        """
        filename = request.match_info["filename"]
        if filename not in REQUIRED_FILES:
            return web.Response(status=404)

        path = self.curbed_dir / filename
        if not path.is_file():
            return web.Response(status=404)

        client = request.remote or ""
        is_local = client in ("127.0.0.1", "::1")

        if not is_local and filename == "update.tar.gz.gpg":
            _LOGGER.info("Firmware delivered to %s; device will reboot", client)
            async_create_notification(
                self.hass,
                title="Curb device updated",
                message=(
                    f"Device `{client}` downloaded the firmware payload and "
                    "will reboot. Wait 2-3 minutes, then SSH in with:\n\n"
                    f"```\nssh root@{client}\n```\n\n"
                    "Use the default password from the integration's "
                    "documentation, then change it immediately with `passwd`."
                ),
                notification_id=(
                    f"{DOMAIN}_delivered_{self.entry.entry_id}_{client}"
                ),
            )
        elif is_local:
            _LOGGER.debug("Local request: %s %s", client, request.path)
        else:
            _LOGGER.info("%s %s", client, request.path)

        return web.FileResponse(path)

    async def async_stop(self) -> None:
        """Stop the update server."""
        if self._auto_stop_unsub is not None:
            self._auto_stop_unsub()
            self._auto_stop_unsub = None

        was_running = self.is_running

        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

        if was_running:
            async_dispatcher_send(self.hass, state_signal(self.entry.entry_id))
            _LOGGER.info("Curb Update Server stopped")


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the entry when options change so the new port/host take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Curb Update Server from a config entry.

    The HTTP listener is NOT started here — the user starts it on demand via
    the Curb Update Server switch, and it auto-stops after AUTO_STOP_SECONDS.
    """
    curbed_dir = Path(__file__).parent / "curbed"

    if not await hass.async_add_executor_job(
        validate_curbed_directory, curbed_dir
    ):
        _LOGGER.error(
            "curbed directory with required files not found: %s", curbed_dir
        )
        raise ConfigEntryNotReady("curbed directory not found")

    options = {**entry.data, **entry.options}
    host = options.get(CONF_HOST, DEFAULT_HOST)
    port = options.get(CONF_PORT, DEFAULT_PORT)

    server = CurbUpdateServer(hass, entry, curbed_dir, host, port)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = server

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    server = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not hass.data.get(DOMAIN):
        hass.data.pop(DOMAIN, None)

    if server is not None:
        try:
            await server.async_stop()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Error stopping Curb Update Server")
            return False

    return True
