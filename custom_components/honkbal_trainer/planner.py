"""Catalog validation, drill filtering, and season planning."""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

import jsonschema

from .const import BLOCK_LABELS, REPEAT_GAP_DAYS, THEME_LABELS
from .models import Catalog, Drill, TeamSettings, TrainingSession

DATA_DIR = Path(__file__).parent / "data"
RandomSource = Callable[[int, int], int]
LOCALIZED_DRILL_FIELDS = (
    "name_nl",
    "description",
    "short_description",
    "setup",
    "execution",
    "coach_cues",
    "coaching_points",
    "common_mistakes",
    "safety_notes",
    "variations",
)


def _localized_theme(theme: str) -> str:
    return " + ".join(
        THEME_LABELS.get(item.strip(), item.strip()) for item in theme.split("+")
    )


def _warmup_block_durations(warmup: dict[str, Any], total_minutes: int) -> list[int]:
    durations = [
        round(block["duration_minutes"] * total_minutes / warmup["duration_minutes"])
        for block in warmup["blocks"][:-1]
    ]
    durations.append(total_minutes - sum(durations))
    return durations


def allocate_drill_durations(
    total_minutes: int, drill_ids: list[str], catalog: Catalog
) -> dict[str, int]:
    """Distribute a fixed block duration evenly within each drill's limits."""
    if not drill_ids:
        return {}
    base, remainder = divmod(total_minutes, len(drill_ids))
    allocations = {
        drill_id: base + (index < remainder) for index, drill_id in enumerate(drill_ids)
    }
    for drill_id, duration in allocations.items():
        bounds = catalog.by_id[drill_id]["duration_minutes"]
        if not bounds["minimum"] <= duration <= bounds["maximum"]:
            raise ValueError("Het blok past niet binnen de duurgrenzen van de drills")
    return allocations


def load_catalog(data_dir: Path = DATA_DIR, language: str = "en") -> Catalog:
    """Load and validate the catalog, applying translations for the given language."""
    language_code = language.replace("_", "-").split("-", maxsplit=1)[0].lower()
    localized_dir = data_dir / language_code
    schema = json.loads((data_dir / "schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    categories = json.loads((data_dir / "categories.json").read_text(encoding="utf-8"))
    summary = json.loads(
        (data_dir / "catalog_summary.json").read_text(encoding="utf-8")
    )
    warmup_path = localized_dir / "warmup.json"
    if not warmup_path.is_file():
        warmup_path = data_dir / "warmup.json"
    warmup = json.loads(warmup_path.read_text(encoding="utf-8"))
    foundation = json.loads(
        (data_dir / "blocks_foundation.json").read_text(encoding="utf-8")
    )
    closing = json.loads((data_dir / "blocks_closing.json").read_text(encoding="utf-8"))
    program = json.loads((data_dir / "programs.json").read_text(encoding="utf-8"))
    if (
        sum(block["duration_minutes"] for block in warmup["blocks"])
        != warmup["duration_minutes"]
    ):
        raise ValueError("De warming-upblokken tellen niet op tot de totale duur")
    if foundation["duration_minutes"] != 15 or closing["duration_minutes"] != 15:
        raise ValueError("Foundation- en afsluitblokken moeten 15 minuten duren")
    known_categories = set(categories)
    if (
        len(program["weeks"]) != 8
        or any(
            category not in known_categories
            for week in program["weeks"]
            for category in week
        )
        or any(
            category not in known_categories for category in foundation["categories"]
        )
        or any(category not in known_categories for category in closing["categories"])
    ):
        raise ValueError("Programma of blokdata verwijst naar een onbekende categorie")
    drills: list[Drill] = []
    seen: set[str] = set()
    for path in sorted(data_dir.glob("drills_*.json")):
        source_drills = json.loads(path.read_text(encoding="utf-8"))
        localized_path = localized_dir / path.name
        if localized_path.is_file():
            localized_drills = json.loads(localized_path.read_text(encoding="utf-8"))
            localized_by_id: dict[str, dict[str, Any]] = {}
            for translated in localized_drills:
                validator.validate(translated)
                translated_id = translated["id"]
                if translated_id in localized_by_id:
                    raise ValueError(
                        f"Dubbel vertaald drill-ID aangetroffen: {translated_id}"
                    )
                localized_by_id[translated_id] = translated
            source_ids = {drill["id"] for drill in source_drills}
            if source_ids != localized_by_id.keys():
                raise ValueError(
                    f"Vertaalde catalogus wijkt af voor bestand {path.name}"
                )
            for drill in source_drills:
                translated = localized_by_id[drill["id"]]
                drill.update(
                    {
                        field: translated[field]
                        for field in LOCALIZED_DRILL_FIELDS
                        if field in translated
                    }
                )
        for drill in source_drills:
            validator.validate(drill)
            drill_id = drill["id"]
            if drill_id in seen:
                raise ValueError(f"Dubbel drill-ID aangetroffen: {drill_id}")
            seen.add(drill_id)
            drills.append(drill)
    if len(drills) != summary["total_drills"]:
        raise ValueError(
            f"Catalogus bevat {len(drills)} drills; verwacht {summary['total_drills']}"
        )
    actual_counts: dict[str, int] = {}
    for drill in drills:
        if drill["category"] not in categories:
            raise ValueError(f"Onbekende drillcategorie in {drill['id']}")
        actual_counts[drill["category"]] = actual_counts.get(drill["category"], 0) + 1
    if actual_counts != summary["counts"]:
        raise ValueError("Catalogusverdeling wijkt af van catalog_summary.json")
    return Catalog(drills, warmup)


def _requirements_met(
    drill: Drill, settings: TeamSettings, prior_dates: list[datetime], at: datetime
) -> bool:
    equipment = set(settings.equipment)
    required = set(drill.get("equipment_required", []))
    if not required.issubset(equipment):
        return False
    if (
        "balls" in required
        and not settings.hard_balls_allowed
        and "wiffle_balls" not in equipment
    ):
        return False
    if not drill.get("indoor_friendly", False):
        return False
    if drill["category"] == "batting" and (
        settings.hitting_lanes < 1 or "net" not in equipment
    ):
        return False
    required_balls = set(drill.get("equipment_required", []))
    if not settings.hard_balls_allowed and (
        drill.get("hard_balls_required", False)
        or bool(required_balls.intersection({"hard_ball", "hard_balls"}))
    ):
        return False
    required_space = drill.get("space_required_m")
    if required_space is not None:
        room_capacity = {"small": 15, "medium": 25, "large": 60}.get(
            settings.room_size, 0
        )
        if float(required_space) > room_capacity:
            return False
    else:
        required_size = drill.get("space_required")
        room_sizes = {"small": 0, "medium": 1, "large": 2}
        if (
            required_size in room_sizes
            and room_sizes.get(settings.room_size, -1) < room_sizes[required_size]
        ):
            return False
    max_distance = drill.get("max_throwing_distance_m")
    if (
        max_distance is not None
        and float(max_distance) > settings.max_throwing_distance_m
    ):
        return False
    skills = set(drill.get("skills", []))
    if "sliding" in skills and settings.floor_type not in {
        "dirt",
        "grass",
        "aarde",
        "gras",
    }:
        return False
    if "blocking" in skills and not {
        "catcher_mask",
        "chest_protector",
        "shin_guards",
    }.issubset(equipment):
        return False
    required_gap = max(
        REPEAT_GAP_DAYS,
        int(drill.get("selection", {}).get("minimum_repeat_gap_days", 0)),
    )
    return not any(
        abs((at.date() - used.date()).days) < required_gap for used in prior_dates
    )


def _score(
    drill: Drill,
    theme: str,
    secondary: str,
    settings: TeamSettings,
    use_count: int,
    rng: RandomSource,
) -> int:
    score = 0
    score += 30 if drill.get("indoor_friendly") else 0
    score += 25 if drill["category"] == theme else 0
    score += 15 if drill["category"] == secondary else 0
    score += 20
    score += 10 if drill.get("difficulty") == "beginner" else 0
    score += 10 if drill.get("suitable_for_beginner_adults") else 0
    score -= 3 * use_count
    return score + rng(0, 5)


def select_drill(
    catalog: Catalog,
    settings: TeamSettings,
    theme: str,
    secondary: str,
    at: datetime,
    usage: dict[str, list[str]],
    selected: list[Drill],
    rng: RandomSource = random.randint,
    block: str = "theme_1",
) -> Drill:
    """Select the highest-scoring drill after applying all safety filters."""
    high_throwers = sum(item.get("throwing_intensity") == "high" for item in selected)
    candidates: list[tuple[int, Drill]] = []
    for drill in catalog.drills:
        if drill in selected:
            continue
        if block in {"foundation", "theme_1", "theme_2"} and block not in drill.get(
            "selection", {}
        ).get("preferred_session_blocks", [block]):
            continue
        prior_dates = [
            datetime.fromisoformat(value) for value in usage.get(drill["id"], [])
        ]
        if not _requirements_met(drill, settings, prior_dates, at):
            continue
        if high_throwers and drill.get("throwing_intensity") == "high":
            continue
        if block == "foundation" and drill["category"] not in {
            "throwing",
            "infield",
            "pitching",
        }:
            continue
        if block == "closing" and drill["category"] != "situational":
            continue
        candidates.append(
            (
                _score(
                    drill,
                    theme,
                    secondary,
                    settings,
                    len(usage.get(drill["id"], [])),
                    rng,
                ),
                drill,
            )
        )
    if not candidates:
        raise ValueError(f"Geen veilige drill beschikbaar voor blok {block!r}")
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    best_score = candidates[0][0]
    tied = [item for score, item in candidates if score == best_score]
    return tied[0] if len(tied) == 1 else tied[rng(0, len(tied) - 1)]


def plan_season(
    catalog: Catalog,
    settings: TeamSettings,
    usage: dict[str, list[str]] | None = None,
    rng: RandomSource = random.randint,
) -> list[TrainingSession]:
    """Generate an eight-week schedule with distinct drills for both sessions."""
    if settings.session_minutes - settings.warmup_minutes - 30 < 16:
        raise ValueError("Sessie is te kort voor warming-up en vaste blokken")
    themed_minutes = settings.session_minutes - settings.warmup_minutes - 30
    if themed_minutes % 2:
        raise ValueError("Resterende sessieduur moet gelijk over thema's deelbaar zijn")
    usage = {key: list(value) for key, value in (usage or {}).items()}
    start = datetime.combine(
        settings.start_date, time.fromisoformat(settings.training_time)
    )
    initial_dates = sorted(
        start + timedelta(days=(day - start.weekday()) % 7)
        for day in set(settings.training_days)
    )
    while len(initial_dates) < 2:
        next_date = max(initial_dates) + timedelta(days=1)
        while next_date.weekday() not in settings.training_days:
            next_date += timedelta(days=1)
        initial_dates.append(next_date)
    first_two_dates = initial_dates[:2]
    schedule: list[TrainingSession] = []
    previous_week_ids: dict[int, set[str]] = {}
    program = json.loads((DATA_DIR / "programs.json").read_text(encoding="utf-8"))[
        "weeks"
    ]
    for week_index in range(settings.weeks):
        themes = list(program[week_index % len(program)])
        if settings.theme_override:
            themes[0] = settings.theme_override
        week_dates = [value + timedelta(weeks=week_index) for value in first_two_dates]
        for session_index, session_start in enumerate(week_dates[:2]):
            selected: list[Drill] = []
            existing_week = previous_week_ids.setdefault(week_index + 1, set())
            if len(themes) == 3:
                session_themes = [f"{themes[0]} + {themes[1]}", themes[2]]
                first_pair = (themes[0], themes[1])
                second_pair = (themes[2], themes[1])
            else:
                session_themes = themes[:2]
                first_pair = (session_themes[0], session_themes[1])
                second_pair = (session_themes[1], session_themes[0])
            durations = {
                "warmup": settings.warmup_minutes,
                "foundation": 15,
                "theme_1": themed_minutes // 2,
                "theme_2": themed_minutes // 2,
                "closing": 15,
            }
            blocks: dict[str, list[str]] = {}
            drill_durations: dict[str, int] = {}
            for block, theme, secondary in [
                ("foundation", "throwing", "infield"),
                ("theme_1", *first_pair),
                ("theme_2", *second_pair),
                ("closing", "situational", first_pair[0]),
            ]:
                block_ids: list[str] = []
                drill_count = max(1, (durations[block] + 19) // 20)
                for _ in range(drill_count):
                    drill = select_drill(
                        catalog,
                        settings,
                        theme,
                        secondary,
                        session_start,
                        usage,
                        selected,
                        rng,
                        block,
                    )
                    selected.append(drill)
                    block_ids.append(drill["id"])
                blocks[block] = block_ids
                drill_durations.update(
                    allocate_drill_durations(durations[block], block_ids, catalog)
                )
            if session_index == 1 and existing_week.intersection(
                item["id"] for item in selected
            ):
                raise ValueError("Training 1 en 2 gebruiken dezelfde drill in de week")
            existing_week.update(item["id"] for item in selected)
            for drill in selected:
                usage.setdefault(drill["id"], []).append(session_start.isoformat())
            session_end = session_start + timedelta(minutes=settings.session_minutes)
            schedule.append(
                TrainingSession(
                    uid=f"honkbal-{session_start.date().isoformat()}-{session_index + 1}",
                    start=session_start,
                    end=session_end,
                    week=week_index + 1,
                    themes=session_themes,
                    blocks=blocks,
                    durations=durations,
                    drill_durations=drill_durations,
                )
            )
    return schedule


def session_description(session: TrainingSession, catalog: Catalog) -> str:
    """Build the complete plain-text description used by the calendar."""
    warmup = catalog.warmup
    lines = [
        f"Thema: {' + '.join(_localized_theme(theme) for theme in session.themes)}",
        f"Warming-up ({session.durations['warmup']} min):",
    ]
    scaled_durations = _warmup_block_durations(warmup, session.durations["warmup"])
    for warmup_block, duration in zip(warmup["blocks"], scaled_durations, strict=True):
        lines.append(
            f"- {warmup_block['name']} ({duration} min): "
            + ", ".join(warmup_block["items"])
        )
    for block, ids in session.blocks.items():
        name = BLOCK_LABELS[block]
        lines.append(f"{name} ({session.durations[block]} min):")
        for drill_id in ids:
            drill = catalog.by_id[drill_id]
            lines.extend(
                [
                    (
                        f"- {drill['name_nl']} "
                        f"({session.drill_durations.get(drill_id, session.durations[block] // len(ids))} min)"
                    ),
                    drill["description"],
                ]
            )
            for label, key in [
                ("Opstelling", "setup"),
                ("Uitvoering", "execution"),
                ("Coach-cues", "coach_cues"),
                ("Veiligheid", "safety_notes"),
            ]:
                value = drill.get(key)
                if value:
                    if isinstance(value, list):
                        value = "; ".join(str(item) for item in value)
                    elif isinstance(value, dict):
                        value = json.dumps(value, ensure_ascii=False)
                    lines.append(f"{label}: {value}")
            lines.append(f"YouTube: {drill['youtube']['url']}")
    return "\n".join(lines)


def calendar_event_payload(
    session: TrainingSession, catalog: Catalog, team_name: str
) -> dict[str, Any]:
    """Create the content shared by HA calendar events and export tests."""
    return {
        "uid": session.uid,
        "start": session.start,
        "end": session.end,
        "summary": f"{team_name}: "
        + " + ".join(_localized_theme(theme) for theme in session.themes),
        "description": session_description(session, catalog),
    }


def whatsapp_export(session: TrainingSession, catalog: Catalog) -> str:
    """Format a session as plain Unicode text for sharing in WhatsApp."""
    warmup = catalog.warmup
    lines = [
        f"⚾ Honkbaltraining — {session.start:%d-%m-%Y}",
        f"Thema: {' + '.join(_localized_theme(theme) for theme in session.themes)}",
        f"\nWarming-up · {session.durations['warmup']} min",
    ]
    for warmup_block, duration in zip(
        warmup["blocks"],
        _warmup_block_durations(warmup, session.durations["warmup"]),
        strict=True,
    ):
        lines.append(
            f"\n{warmup_block['name']} · {duration} min — "
            + ", ".join(warmup_block["items"])
        )
    for block, ids in session.blocks.items():
        duration = session.durations[block]
        lines.append(f"\n{BLOCK_LABELS[block]} · {duration} min")
        for drill_id in ids:
            drill = catalog.by_id[drill_id]
            cues = drill.get("coach_cues", [])[:2]
            lines.append(
                f"— {drill['name_nl']} · "
                f"{session.drill_durations.get(drill_id, duration // len(ids))} min"
            )
            lines.append(drill.get("short_description") or drill["description"])
            lines.extend(f"• {cue}" for cue in cues)
            lines.append(drill["youtube"]["url"])
    return "\n".join(lines)
