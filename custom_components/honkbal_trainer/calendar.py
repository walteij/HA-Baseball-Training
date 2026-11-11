"""Home Assistant calendar entity for generated sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import TrainingCoordinator
from .const import DOMAIN
from .planner import calendar_event_payload


async def async_setup_entry(
    hass: HomeAssistant, entry: Any, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: TrainingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TrainingCalendar(coordinator, entry.entry_id)])


class TrainingCalendar(CoordinatorEntity[TrainingCoordinator], CalendarEntity):
    """Expose the complete season as a Home Assistant calendar."""

    _attr_translation_key = "training"
    _attr_has_entity_name = True

    def __init__(self, coordinator: TrainingCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        session = next(
            (
                item
                for item in self.coordinator.data.sessions
                if item.start <= now.replace(tzinfo=None) < item.end
            ),
            None,
        )
        return self._calendar_event(session) if session else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            self._calendar_event(session)
            for session in self.coordinator.data.sessions
            if session.start < end_date.replace(tzinfo=None)
            and session.end > start_date.replace(tzinfo=None)
        ]

    def _calendar_event(self, session: Any) -> CalendarEvent:
        timezone = ZoneInfo(self.coordinator.hass.config.time_zone)
        payload = calendar_event_payload(
            session, self.coordinator.catalog, self.coordinator.settings.team_name
        )
        start = payload["start"].replace(tzinfo=timezone)
        end = payload["end"].replace(tzinfo=timezone)
        return CalendarEvent(
            start=start,
            end=end,
            summary=payload["summary"],
            description=payload["description"],
            uid=payload["uid"],
        )
