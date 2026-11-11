"""Typed data structures used by the integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, NotRequired, TypedDict

from .const import DEFAULT_EQUIPMENT


class YouTube(TypedDict):
    url: str
    title: str
    channel: str
    verified_on: str
    match_quality: str
    language: NotRequired[str]


class Drill(TypedDict):
    id: str
    name_nl: str
    category: str
    description: str
    coach_cues: list[str]
    equipment_required: list[str]
    youtube: YouTube
    duration_minutes: dict[str, int]
    selection: dict[str, Any]
    skills: NotRequired[list[str]]
    safety_notes: NotRequired[list[str]]


@dataclass(slots=True)
class TrainingSession:
    uid: str
    start: datetime
    end: datetime
    week: int
    themes: list[str]
    blocks: dict[str, list[str]]
    durations: dict[str, int]
    drill_durations: dict[str, int] = field(default_factory=dict)
    completed: bool = False
    status: str = "gepland"

    def as_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "week": self.week,
            "themes": self.themes,
            "blocks": self.blocks,
            "durations": self.durations,
            "drill_durations": self.drill_durations,
            "completed": self.completed,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingSession:
        return cls(
            uid=str(data["uid"]),
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]),
            week=int(data["week"]),
            themes=list(data["themes"]),
            blocks={key: list(value) for key, value in data["blocks"].items()},
            durations={key: int(value) for key, value in data["durations"].items()},
            drill_durations={
                key: int(value)
                for key, value in data.get("drill_durations", {}).items()
            },
            completed=bool(data.get("completed", False)),
            status=str(data.get("status", "gepland")),
        )


@dataclass(slots=True)
class Catalog:
    drills: list[Drill]
    warmup: dict[str, Any] = field(default_factory=dict)
    by_id: dict[str, Drill] = field(init=False)

    def __post_init__(self) -> None:
        self.by_id = {drill["id"]: drill for drill in self.drills}


@dataclass(slots=True)
class TeamSettings:
    team_name: str
    training_days: list[int]
    training_time: str
    session_minutes: int
    warmup_minutes: int
    start_date: date
    weeks: int
    equipment: list[str] = field(default_factory=list)
    room_size: str = "medium"
    floor_type: str = "sportvloer"
    hard_balls_allowed: bool = False
    max_throwing_distance_m: int = 20
    hitting_lanes: int = 1
    focus_override: str = ""
    youtube_language: str = "nl"
    theme_override: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamSettings:
        return cls(
            team_name=str(data["team_name"]),
            training_days=[int(day) for day in data.get("training_days", [1, 4])],
            training_time=str(data.get("training_time", "19:00")),
            session_minutes=int(data.get("session_minutes", 90)),
            warmup_minutes=int(data.get("warmup_minutes", 20)),
            start_date=date.fromisoformat(str(data["start_date"])),
            weeks=int(data.get("weeks", 8)),
            equipment=list(data.get("equipment", DEFAULT_EQUIPMENT)),
            room_size=str(data.get("room_size", "medium")),
            floor_type=str(data.get("floor_type", "sportvloer")),
            hard_balls_allowed=bool(data.get("hard_balls_allowed", False)),
            max_throwing_distance_m=int(data.get("max_throwing_distance_m", 20)),
            hitting_lanes=int(data.get("hitting_lanes", 1)),
            focus_override=str(data.get("focus_override", "")),
            youtube_language=str(data.get("youtube_language", "nl")),
            theme_override=str(data.get("theme_override", "")),
        )


@dataclass(slots=True)
class IntegrationState:
    settings: TeamSettings
    sessions: list[TrainingSession] = field(default_factory=list)
    usage: dict[str, list[str]] = field(default_factory=dict)
    active_session_uid: str | None = None
    active_block_index: int = 0
    focus: str = ""
    theme_override: str | None = None
    settings_signature: str = ""


def session_to_data(session: TrainingSession) -> dict[str, Any]:
    return session.as_dict()
