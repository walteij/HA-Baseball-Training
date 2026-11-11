"""Home Assistant integration for planning indoor baseball training."""

from __future__ import annotations

import logging
from typing import Any

import jsonschema
import voluptuous as vol
from aiohttp import web
from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .coordinator import TrainingCoordinator
from .ical import render_ical
from .models import TeamSettings
from .planner import load_catalog, whatsapp_export

_LOGGER = logging.getLogger(__name__)
_BLOCKS = ["foundation", "theme_1", "theme_2", "closing"]


class CalendarExportView(HomeAssistantView):
    """Authenticated RFC 5545 download endpoint."""

    url = "/api/honkbal_trainer/{entry_id}/calendar.ics"
    name = "api:honkbal_trainer:calendar"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        coordinator = request.app["hass"].data.get(DOMAIN, {}).get(entry_id)
        if coordinator is None:
            raise web.HTTPNotFound()
        content = render_ical(
            coordinator.data.sessions,
            coordinator.catalog,
            request.app["hass"].config.time_zone,
        )
        return web.Response(
            text=content,
            content_type="text/calendar",
            headers={
                "Content-Disposition": 'attachment; filename="honkbal-training.ics"'
            },
        )


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> TrainingCoordinator:
    entries = hass.data.get(DOMAIN, {})
    entry_id = call.data.get("entry_id")
    if entry_id:
        result = entries.get(entry_id)
    else:
        result = next(iter(entries.values()), None)
    if result is None:
        raise HomeAssistantError("Geen Honkbal Trainer-configuratie gevonden")
    return result


async def _async_handle_service(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any] | None:
    coordinator = _coordinator(hass, call)
    data = call.data
    service = call.service
    try:
        if service == "genereer_seizoen":
            await coordinator.async_generate_season()
            return {"aantal_sessies": len(coordinator.data.sessions)}
        if service == "voeg_drill_toe":
            await coordinator.async_add_drill(
                data["session_uid"], data["block"], data["drill_id"]
            )
        elif service == "verwijder_drill":
            await coordinator.async_remove_drill(
                data["session_uid"], data["block"], data["drill_id"]
            )
        elif service == "wissel_drill":
            await coordinator.async_swap_drill(
                data["session_uid"],
                data["block"],
                data["old_drill_id"],
                data["drill_id"],
            )
        elif service == "exporteer_sessie":
            session = coordinator.get_session(data["session_uid"])
            if session is None:
                raise ValueError("Onbekende sessie-ID")
            return {"tekst": whatsapp_export(session, coordinator.catalog)}
        elif service == "exporteer_ical":
            return {
                "ical": render_ical(
                    coordinator.data.sessions,
                    coordinator.catalog,
                    hass.config.time_zone,
                )
            }
    except (KeyError, ValueError) as err:
        raise HomeAssistantError(str(err)) from err
    return None


def _register_services(hass: HomeAssistant) -> None:
    service_schemas: dict[str, vol.Schema] = {
        "genereer_seizoen": vol.Schema({vol.Optional("entry_id"): cv.string}),
        "voeg_drill_toe": vol.Schema(
            {
                vol.Optional("entry_id"): cv.string,
                vol.Required("session_uid"): cv.string,
                vol.Required("block"): vol.In(_BLOCKS),
                vol.Required("drill_id"): cv.string,
            }
        ),
        "verwijder_drill": vol.Schema(
            {
                vol.Optional("entry_id"): cv.string,
                vol.Required("session_uid"): cv.string,
                vol.Required("block"): vol.In(_BLOCKS),
                vol.Required("drill_id"): cv.string,
            }
        ),
        "wissel_drill": vol.Schema(
            {
                vol.Optional("entry_id"): cv.string,
                vol.Required("session_uid"): cv.string,
                vol.Required("block"): vol.In(_BLOCKS),
                vol.Required("old_drill_id"): cv.string,
                vol.Required("drill_id"): cv.string,
            }
        ),
        "exporteer_sessie": vol.Schema(
            {
                vol.Optional("entry_id"): cv.string,
                vol.Required("session_uid"): cv.string,
            }
        ),
        "exporteer_ical": vol.Schema({vol.Optional("entry_id"): cv.string}),
    }

    async def service_handler(call: ServiceCall) -> dict[str, Any] | None:
        return await _async_handle_service(hass, call)

    response_services = {"genereer_seizoen", "exporteer_sessie", "exporteer_ical"}
    for service, schema in service_schemas.items():
        hass.services.async_register(
            DOMAIN,
            service,
            service_handler,
            schema=schema,
            supports_response=(
                SupportsResponse.ONLY
                if service in response_services
                else SupportsResponse.NONE
            ),
        )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up HTTP export and services once."""
    hass.data.setdefault(DOMAIN, {})
    if not hass.data[DOMAIN]:
        _register_services(hass)
        hass.http.register_view(CalendarExportView())
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up a configured team and load/validate its data catalog."""
    try:
        catalog = load_catalog(language=hass.config.language)
        settings_data = {**entry.data, **entry.options}
        settings = TeamSettings.from_dict(settings_data)
        if "resistance_bands" not in settings.equipment:
            raise ValueError("Voor de vaste warming-up zijn weerstandsbanden nodig")
        coordinator = TrainingCoordinator(hass, entry.entry_id, catalog, settings)
        await coordinator.async_initialize()
    except (OSError, ValueError, KeyError, jsonschema.ValidationError) as err:
        _LOGGER.exception("Kon Honkbal Trainer niet initialiseren")
        raise HomeAssistantError(f"Catalogus of configuratie ongeldig: {err}") from err
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Reload after options have changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload the configured entities."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
