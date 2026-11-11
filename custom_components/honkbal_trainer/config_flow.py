"""Config and options flows for Honkbal Trainer."""

from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_SESSION_MINUTES,
    DEFAULT_WARMUP_MINUTES,
    DEFAULT_WEEKS,
    DOMAIN,
    WEEKDAYS,
)

_EQUIPMENT_LABELS = {
    "Ballen": "balls",
    "Safety-/wiffleballen": "wiffle_balls",
    "Handschoenen": "gloves",
    "Pionnen": "cones",
    "Knuppel": "bat",
    "Slagnet": "net",
    "Catcher-masker": "catcher_mask",
    "Borstbeschermer": "chest_protector",
    "Scheenbeschermers": "shin_guards",
    "Weerstandsbanden": "resistance_bands",
}
_YOUTUBE_LANGUAGES = {"Nederlands": "nl", "Engels": "en"}


def _base_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    values = defaults or {}
    default_days = [
        next((label for label, day in WEEKDAYS.items() if day == value), "dinsdag")
        for value in values.get("training_days", [1, 4])
    ]
    return vol.Schema(
        {
            vol.Required(
                "team_name", default=values.get("team_name", "Ons team")
            ): vol.All(str, vol.Length(min=1, max=80)),
            vol.Required("training_days", default=default_days): vol.All(
                [vol.In(list(WEEKDAYS))], vol.Length(min=2, max=2)
            ),
            vol.Required(
                "training_time", default=values.get("training_time", "19:00")
            ): str,
            vol.Required(
                "session_minutes",
                default=values.get("session_minutes", DEFAULT_SESSION_MINUTES),
            ): vol.All(vol.Coerce(int), vol.Range(min=60, max=180)),
            vol.Required(
                "warmup_minutes",
                default=values.get("warmup_minutes", DEFAULT_WARMUP_MINUTES),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=40)),
            vol.Required(
                "start_date",
                default=values.get("start_date", dt_util.now().date().isoformat()),
            ): str,
            vol.Required("weeks", default=values.get("weeks", DEFAULT_WEEKS)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=52)
            ),
        }
    )


def _options_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    values = defaults or {}
    default_equipment = [
        label
        for label, value in _EQUIPMENT_LABELS.items()
        if value
        in values.get(
            "equipment",
            [
                "balls",
                "wiffle_balls",
                "gloves",
                "cones",
                "bat",
                "net",
                "resistance_bands",
            ],
        )
    ]
    return vol.Schema(
        {
            vol.Required("equipment", default=default_equipment): vol.All(
                [vol.In(list(_EQUIPMENT_LABELS))],
                vol.Length(max=len(_EQUIPMENT_LABELS)),
            ),
            vol.Required(
                "room_size",
                default={
                    "small": "Klein",
                    "medium": "Middelgroot",
                    "large": "Groot",
                }.get(values.get("room_size", "medium"), "Middelgroot"),
            ): vol.In(["Klein", "Middelgroot", "Groot"]),
            vol.Required(
                "floor_type", default=values.get("floor_type", "sportvloer")
            ): vol.In(["sportvloer", "hout", "gras", "aarde"]),
            vol.Required(
                "hard_balls_allowed",
                default=values.get("hard_balls_allowed", False),
            ): bool,
            vol.Required(
                "max_throwing_distance_m",
                default=values.get("max_throwing_distance_m", 20),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
            vol.Required(
                "hitting_lanes", default=values.get("hitting_lanes", 1)
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
            vol.Required(
                "focus_override",
                default={
                    "": "Geen voorkeur",
                    "techniek": "Techniek",
                    "spelplezier": "Spelplezier",
                    "conditie": "Conditie",
                    "herstel": "Herstel",
                }.get(values.get("focus_override", ""), "Geen voorkeur"),
            ): vol.In(
                ["Geen voorkeur", "Techniek", "Spelplezier", "Conditie", "Herstel"]
            ),
            vol.Required(
                "youtube_language",
                default={
                    "nl": "Nederlands",
                    "en": "Engels",
                }.get(values.get("youtube_language", "nl"), "Nederlands"),
            ): vol.In(list(_YOUTUBE_LANGUAGES)),
        }
    )


class HonkbalTrainerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a user setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if self._async_current_entries():
                return self.async_abort(reason="single_instance_allowed")
            try:
                date.fromisoformat(user_input["start_date"])
                hours, minutes = map(int, user_input["training_time"].split(":"))
                if hours not in range(24) or minutes not in range(60):
                    raise ValueError
                theme_duration = (
                    user_input["session_minutes"] - user_input["warmup_minutes"] - 30
                )
                if theme_duration < 16 or theme_duration % 2:
                    errors["base"] = "invalid_session_duration"
                elif len(set(user_input["training_days"])) != 2:
                    errors["base"] = "invalid_training_days"
                else:
                    user_input["training_days"] = [
                        WEEKDAYS[day] for day in user_input["training_days"]
                    ]
                    return self.async_create_entry(
                        title=user_input["team_name"], data=user_input
                    )
            except (ValueError, KeyError):
                errors["base"] = "invalid_date_or_time"
        return self.async_show_form(
            step_id="user", data_schema=_base_schema(user_input), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HonkbalTrainerOptionsFlow:
        return HonkbalTrainerOptionsFlow(config_entry)


class HonkbalTrainerOptionsFlow(config_entries.OptionsFlow):
    """Manage environment and drill selection options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            if "Weerstandsbanden" not in user_input["equipment"]:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_options_schema(
                        {**self.config_entry.data, **self.config_entry.options}
                    ),
                    errors={"base": "resistance_bands_required"},
                )
            user_input["equipment"] = [
                _EQUIPMENT_LABELS[label] for label in user_input["equipment"]
            ]
            user_input["room_size"] = {
                "Klein": "small",
                "Middelgroot": "medium",
                "Groot": "large",
            }[user_input["room_size"]]
            user_input["focus_override"] = {
                "Geen voorkeur": "",
                "Techniek": "techniek",
                "Spelplezier": "spelplezier",
                "Conditie": "conditie",
                "Herstel": "herstel",
            }[user_input["focus_override"]]
            user_input["youtube_language"] = _YOUTUBE_LANGUAGES[
                user_input["youtube_language"]
            ]
            return self.async_create_entry(title="", data=user_input)
        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(defaults)
        )
