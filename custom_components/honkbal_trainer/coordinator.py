"""Coordinator and session lifecycle management."""

from __future__ import annotations

import json
import logging
import random
from dataclasses import asdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .models import Catalog, IntegrationState, TeamSettings, TrainingSession
from .planner import (
    _localized_theme,
    _requirements_met,
    allocate_drill_durations,
    plan_season,
)
from .storage import TrainingStorage

_LOGGER = logging.getLogger(__name__)


class TrainingCoordinator(DataUpdateCoordinator[IntegrationState]):
    """Owns the local schedule and persists every state transition."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        catalog: Catalog,
        settings: TeamSettings,
        rng: Any = random.randint,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.catalog = catalog
        self.settings = settings
        self.storage = TrainingStorage(hass, entry_id)
        self.rng = rng

    async def async_initialize(self) -> None:
        self.data = await self.storage.async_load(self.settings)
        if self.data.theme_override is None:
            self.data.theme_override = self.settings.theme_override
        else:
            self.settings.theme_override = self.data.theme_override
        signature = self._settings_signature()
        settings_changed = self.data.settings_signature != signature
        if settings_changed or not self.data.focus:
            self.data.focus = self.settings.focus_override or "techniek"
        self.data.settings_signature = signature
        if not self.data.sessions or settings_changed:
            await self.async_generate_season()
        else:
            await self.async_save()

    def _settings_signature(self) -> str:
        return json.dumps(asdict(self.settings), sort_keys=True, default=str)

    async def async_save(self) -> None:
        await self.storage.async_save(self.data)
        self.async_set_updated_data(self.data)

    async def async_generate_season(self) -> None:
        now = dt_util.now().replace(tzinfo=None)
        timezone = ZoneInfo(self.hass.config.time_zone)
        previous_sessions = list(self.data.sessions)
        active_session_uid = self.data.active_session_uid
        preserved_sessions = [
            session
            for session in previous_sessions
            if session.start < now
            or session.completed
            or session.uid == active_session_uid
        ]
        historical_usage: dict[str, list[str]] = {}
        for drill_id, dates in self.data.usage.items():
            for value in dates:
                used = datetime.fromisoformat(value)
                if used.tzinfo is not None:
                    used = used.astimezone(timezone).replace(tzinfo=None)
                if used < now:
                    historical_usage.setdefault(drill_id, []).append(value)
        for session in preserved_sessions:
            for drill_ids in session.blocks.values():
                for drill_id in drill_ids:
                    used_dates = historical_usage.setdefault(drill_id, [])
                    if session.start.isoformat() not in used_dates:
                        used_dates.append(session.start.isoformat())
        sessions = plan_season(self.catalog, self.settings, historical_usage, self.rng)
        preserved_uids = {session.uid for session in preserved_sessions}
        generated_sessions = [
            session
            for session in sessions
            if session.uid not in preserved_uids
            and (
                not previous_sessions
                or session.start >= now
                or session.uid == active_session_uid
            )
        ]
        self.data.sessions = sorted(
            [*preserved_sessions, *generated_sessions], key=lambda item: item.start
        )
        self.data.usage = historical_usage
        for session in generated_sessions:
            for ids in session.blocks.values():
                for drill_id in ids:
                    self.data.usage.setdefault(drill_id, []).append(
                        session.start.isoformat()
                    )
        self.data.settings_signature = self._settings_signature()
        if self.get_session(active_session_uid) is None:
            self.data.active_session_uid = None
            self.data.active_block_index = 0
        await self.async_save()

    async def async_start_session(self, session_uid: str | None = None) -> None:
        if self.active_session() is not None:
            raise ValueError("Er is al een actieve training")
        session = self.get_session(session_uid) if session_uid else self.next_session()
        if session is None:
            raise ValueError("Er is geen geplande training beschikbaar")
        session.status = "bezig"
        self.data.active_session_uid = session.uid
        self.data.active_block_index = 0
        await self.async_save()

    async def async_complete_session(self) -> None:
        session = self.active_session()
        if session is None:
            raise ValueError("Er is geen actieve training")
        session.status = "voltooid"
        session.completed = True
        self.data.active_session_uid = None
        self.data.active_block_index = 0
        await self.async_save()

    async def async_next_drill(self) -> None:
        session = self.active_session()
        if session is None:
            raise ValueError("Er is geen actieve training")
        blocks = list(session.blocks.values())
        flattened_count = sum(len(ids) for ids in blocks)
        if self.data.active_block_index + 1 >= flattened_count:
            raise ValueError("De laatste drill van deze training is bereikt")
        self.data.active_block_index += 1
        await self.async_save()

    async def async_add_drill(
        self, session_uid: str, block: str, drill_id: str
    ) -> None:
        session = self.get_session(session_uid)
        drill = self.catalog.by_id.get(drill_id)
        if (
            session is None
            or session.completed
            or block not in session.blocks
            or drill is None
        ):
            raise ValueError("Sessie, blok of drill-ID is ongeldig")
        if drill_id in [item for ids in session.blocks.values() for item in ids]:
            raise ValueError("Deze drill staat al in de sessie")
        high_drills = [
            self.catalog.by_id[item]
            for ids in session.blocks.values()
            for item in ids
            if item in self.catalog.by_id
            and self.catalog.by_id[item].get("throwing_intensity") == "high"
        ]
        if drill.get("throwing_intensity") == "high" and high_drills:
            raise ValueError("Maximaal één drill met hoge werpintensiteit per sessie")
        allowed_categories = {
            "foundation": {"throwing", "infield", "pitching"},
            "closing": {"situational"},
        }
        categories = allowed_categories.get(block)
        if block in {"theme_1", "theme_2"}:
            categories = {
                category.strip()
                for theme in session.themes
                for category in theme.split("+")
            }
        if categories is not None and drill["category"] not in categories:
            raise ValueError("De drill past niet bij het sessieblok")
        prior_dates = [
            datetime.fromisoformat(value)
            for value in self.data.usage.get(drill_id, [])
            if datetime.fromisoformat(value).date() != session.start.date()
        ]
        if not _requirements_met(drill, self.settings, prior_dates, session.start):
            raise ValueError(
                "De drill voldoet niet aan de materiaal- of veiligheidsfilters"
            )
        updated_ids = [*session.blocks[block], drill_id]
        updated_durations = allocate_drill_durations(
            session.durations[block], updated_ids, self.catalog
        )
        session.blocks[block] = updated_ids
        self.data.drill_durations.update(updated_durations)
        self.data.usage.setdefault(drill_id, []).append(session.start.isoformat())
        await self.async_save()

    async def async_remove_drill(
        self, session_uid: str, block: str, drill_id: str
    ) -> None:
        session = self.get_session(session_uid)
        if session is None or session.completed or block not in session.blocks:
            raise ValueError("Sessie of blok is ongeldig")
        if drill_id not in session.blocks[block]:
            raise ValueError("De drill staat niet in dit blok")
        updated_ids = [item for item in session.blocks[block] if item != drill_id]
        if not updated_ids:
            raise ValueError("Een blok moet minimaal één drill bevatten")
        updated_durations = allocate_drill_durations(
            session.durations[block], updated_ids, self.catalog
        )
        session.blocks[block] = updated_ids
        self.data.drill_durations.pop(drill_id, None)
        self.data.drill_durations.update(updated_durations)
        usage = self.data.usage.get(drill_id, [])
        if session.start.isoformat() in usage:
            usage.remove(session.start.isoformat())
        await self.async_save()

    async def async_swap_drill(
        self, session_uid: str, block: str, old_drill_id: str, drill_id: str
    ) -> None:
        session = self.get_session(session_uid)
        if session is None or session.completed or block not in session.blocks:
            raise ValueError("Sessie of blok is ongeldig")
        old_ids = list(session.blocks[block])
        if old_drill_id not in old_ids:
            raise ValueError("De te vervangen drill staat niet in dit blok")
        if drill_id == old_drill_id:
            raise ValueError("De vervangende drill moet anders zijn")
        session.blocks[block] = [item for item in old_ids if item != old_drill_id]
        old_duration = self.data.drill_durations.pop(old_drill_id, None)
        old_usage = list(self.data.usage.get(old_drill_id, []))
        old_timestamp = session.start.isoformat()
        if old_timestamp in self.data.usage.get(old_drill_id, []):
            self.data.usage[old_drill_id].remove(old_timestamp)
        try:
            await self.async_add_drill(session_uid, block, drill_id)
        except ValueError:
            session.blocks[block] = old_ids
            if old_duration is not None:
                self.data.drill_durations[old_drill_id] = old_duration
            self.data.usage[old_drill_id] = old_usage
            raise

    def get_session(self, session_uid: str | None) -> TrainingSession | None:
        return next(
            (item for item in self.data.sessions if item.uid == session_uid), None
        )

    def active_session(self) -> TrainingSession | None:
        return self.get_session(self.data.active_session_uid)

    def active_drill(self) -> tuple[str, str] | None:
        session = self.active_session()
        if session is None:
            return None
        sequence = [
            (block, drill_id)
            for block, drill_ids in session.blocks.items()
            for drill_id in drill_ids
        ]
        if self.data.active_block_index >= len(sequence):
            return None
        return sequence[self.data.active_block_index]

    def next_session(self) -> TrainingSession | None:
        now = dt_util.now().replace(tzinfo=None)
        return next(
            (
                item
                for item in self.data.sessions
                if not item.completed and item.start >= now
            ),
            None,
        )

    def get_sensor_value(self, key: str) -> Any:
        session = self.active_session() or self.next_session()
        completed_count = sum(item.completed for item in self.data.sessions)
        if key == "volgende_training":
            return (
                self.next_session().start.isoformat() if self.next_session() else None
            )
        if key == "huidig_thema":
            return (
                " + ".join(_localized_theme(theme) for theme in session.themes)
                if session
                else None
            )
        if key == "huidige_week":
            return session.week if session else None
        if key == "programma_voortgang":
            return f"{completed_count}/{len(self.data.sessions)}"
        if key == "sessie_status":
            active = self.active_session()
            if active:
                return active.status
            return (
                self.next_session().status if self.next_session() else "geen planning"
            )
        if key == "warming_up":
            return f"{self.settings.warmup_minutes} min"
        block_by_key = {
            "basis_drill": "foundation",
            "drill_1": "theme_1",
            "drill_2": "theme_2",
            "afsluiting": "closing",
        }
        if key in block_by_key:
            ids = session.blocks.get(block_by_key[key], []) if session else []
            return self.catalog.by_id[ids[0]]["name_nl"] if ids else None
        if key == "totaal_trainingen":
            return len(self.data.sessions)
        if key == "drill_catalogus_count":
            return len(self.catalog.drills)
        return None
