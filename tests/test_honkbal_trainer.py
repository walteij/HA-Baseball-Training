"""Unit tests for Honkbal Trainer's catalog and planning logic."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import jsonschema
import pytest

from custom_components.honkbal_trainer.const import DEFAULT_EQUIPMENT
from custom_components.honkbal_trainer.ical import escape_ical_text, render_ical
from custom_components.honkbal_trainer.models import TeamSettings, TrainingSession
from custom_components.honkbal_trainer.planner import (
    DATA_DIR,
    _requirements_met,
    calendar_event_payload,
    load_catalog,
    plan_season,
    whatsapp_export,
)
from custom_components.honkbal_trainer.storage import migrate_storage_data


@pytest.fixture
def catalog():
    return load_catalog()


@pytest.fixture
def settings():
    return TeamSettings(
        team_name="Testteam",
        training_days=[1, 4],
        training_time="19:00",
        session_minutes=90,
        warmup_minutes=20,
        start_date=date(2026, 11, 11),
        weeks=8,
        equipment=[
            *DEFAULT_EQUIPMENT,
            "catcher_mask",
            "chest_protector",
            "shin_guards",
        ],
        room_size="medium",
        floor_type="sportvloer",
        hard_balls_allowed=False,
        max_throwing_distance_m=20,
        hitting_lanes=1,
    )


def test_catalog_is_135_deduplicated_drills(catalog):
    assert len(catalog.drills) == 135
    assert len(catalog.by_id) == 135


def test_catalog_uses_dutch_translations_for_home_assistant_language():
    catalog = load_catalog(language="nl-NL")
    drill = catalog.by_id["batting_tee_work_basic"]

    assert drill["name_nl"] == "Tee work basis"
    assert drill["description"] == (
        "Zuiver contact maken en leren waar de bal ten opzichte van het lichaam "
        "geraakt wordt."
    )
    assert drill["setup"][0] == (
        "Zet de slaglane af en plaats het net recht voor de slagman."
    )
    assert catalog.warmup["blocks"][0]["name"] == "Dynamische warming-up"


def test_catalog_falls_back_to_default_data_when_translation_is_unavailable():
    default_catalog = load_catalog(language="en")
    unsupported_language_catalog = load_catalog(language="fr")

    assert (
        unsupported_language_catalog.by_id["batting_tee_work_basic"]["description"]
        == default_catalog.by_id["batting_tee_work_basic"]["description"]
    )
    assert unsupported_language_catalog.warmup == default_catalog.warmup


def test_dutch_descriptions_are_used_in_calendar_and_whatsapp_exports(settings):
    catalog = load_catalog(language="nl")
    session = plan_season(catalog, settings, rng=lambda low, high: low)[0]
    drill_id = next(
        drill_id for drill_ids in session.blocks.values() for drill_id in drill_ids
    )
    description = catalog.by_id[drill_id]["description"]

    event = calendar_event_payload(session, catalog, settings.team_name)
    message = whatsapp_export(session, catalog)

    assert description in event["description"]
    assert description in message


def test_catalog_drills_validate_against_schema():
    schema = json.loads((DATA_DIR / "schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for path in DATA_DIR.glob("drills_*.json"):
        for drill in json.loads(path.read_text(encoding="utf-8")):
            validator.validate(drill)


def test_material_filter_excludes_drill_when_required_equipment_missing(
    catalog, settings
):
    batting = catalog.by_id["batting_tee_work_basic"]
    settings.equipment = ["balls", "gloves"]
    assert not _requirements_met(
        batting, settings, [], datetime(2026, 11, 11, tzinfo=timezone.utc)
    )


def test_hard_ball_prohibition_requires_safe_balls(catalog, settings):
    batting = catalog.by_id["batting_tee_work_basic"]
    settings.equipment = ["balls", "gloves", "bat", "net"]
    assert not _requirements_met(
        batting, settings, [], datetime(2026, 11, 11, tzinfo=timezone.utc)
    )
    settings.equipment.append("wiffle_balls")
    assert _requirements_met(
        batting, settings, [], datetime(2026, 11, 11, tzinfo=timezone.utc)
    )


@pytest.mark.parametrize(
    ("field", "required_space"),
    [("space_required_m", 16), ("space_required", "medium")],
)
def test_room_filter_excludes_drill_that_exceeds_room_capacity(
    settings, field, required_space
):
    drill = {
        "id": "test_space",
        "category": "infield",
        "equipment_required": [],
        "indoor_friendly": True,
        "selection": {"minimum_repeat_gap_days": 14},
    }
    drill[field] = required_space
    settings.room_size = "small"
    assert not _requirements_met(
        drill, settings, [], datetime(2026, 11, 11, tzinfo=timezone.utc)
    )


def test_repeat_gap_is_fourteen_days(settings):
    drill = {
        "id": "test_gap",
        "category": "infield",
        "equipment_required": [],
        "indoor_friendly": True,
        "selection": {"minimum_repeat_gap_days": 14},
    }
    recent = datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert not _requirements_met(
        drill, settings, [recent], datetime(2026, 11, 14, tzinfo=timezone.utc)
    )
    assert _requirements_met(
        drill, settings, [recent], datetime(2026, 11, 15, tzinfo=timezone.utc)
    )


def test_sessions_in_a_week_use_different_drills(catalog, settings):
    sessions = plan_season(catalog, settings, rng=lambda low, high: low)
    for session in sessions:
        for block, drill_ids in session.blocks.items():
            assert (
                sum(session.drill_durations[item] for item in drill_ids)
                == (session.durations[block])
            )
            assert all(8 <= session.drill_durations[item] <= 20 for item in drill_ids)
    for index in range(0, len(sessions), 2):
        first = {drill for ids in sessions[index].blocks.values() for drill in ids}
        second = {drill for ids in sessions[index + 1].blocks.values() for drill in ids}
        assert first.isdisjoint(second)


def test_rng_makes_season_reproducible(catalog, settings):
    first = plan_season(catalog, settings, rng=lambda low, high: low)
    second = plan_season(catalog, settings, rng=lambda low, high: low)
    assert [item.as_dict() for item in first] == [item.as_dict() for item in second]


def test_session_has_at_most_one_high_intensity_throwing_drill(catalog, settings):
    sessions = plan_season(catalog, settings, rng=lambda low, high: low)
    for session in sessions:
        high_intensity = [
            catalog.by_id[drill_id]
            for ids in session.blocks.values()
            for drill_id in ids
            if catalog.by_id[drill_id].get("throwing_intensity") == "high"
        ]
        assert len(high_intensity) <= 1


def test_storage_schema_migrates_v1_state():
    migrated = migrate_storage_data(
        {"schema_version": 1, "sessions": [], "usage": {"drill_a": ["2026-01-01"]}}
    )
    assert migrated["schema_version"] == 2
    assert migrated["active_session_uid"] is None
    assert migrated["focus"] == ""


def test_session_storage_round_trip(catalog, settings):
    session = plan_season(catalog, settings, rng=lambda low, high: low)[0]
    assert TrainingSession.from_dict(session.as_dict()) == session


def test_calendar_event_contains_full_session(catalog, settings):
    session = plan_season(catalog, settings, rng=lambda low, high: low)[0]
    event = calendar_event_payload(session, catalog, settings.team_name)
    assert event["uid"] == session.uid
    assert event["start"] == session.start
    assert event["end"] == session.end
    assert "slagtraining" in event["summary"]
    assert "Warming-up" in event["description"]
    assert "YouTube:" in event["description"]


def test_ical_escaping_and_stable_uid(catalog, settings):
    session = plan_season(catalog, settings, rng=lambda low, high: low)[0]
    assert escape_ical_text(r"a,b;c\d\nline") == r"a\,b\;c\\d\\nline"
    first = render_ical([session], catalog, "Europe/Amsterdam")
    second = render_ical([session], catalog, "Europe/Amsterdam")
    assert f"UID:{session.uid}" in first
    assert f"UID:{session.uid}" in second
    assert "DESCRIPTION:" in first
    assert "\r\n" in first


def test_whatsapp_export_is_plain_text(catalog, settings):
    session = plan_season(catalog, settings, rng=lambda low, high: low)[0]
    message = whatsapp_export(session, catalog)
    assert session.start.strftime("%d-%m-%Y") in message
    assert "Warming-up" in message
    assert "Band work en arm care" in message
    assert "Warming-up" in message
    assert "Band work en arm care" in message
    assert "min" in message
    assert "• " in message
    assert "https://www.youtube.com/watch?v=" in message
    assert "<a " not in message
