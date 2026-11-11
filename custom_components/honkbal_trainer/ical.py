"""RFC 5545 iCalendar serialization."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .models import Catalog, TrainingSession
from .planner import session_description


def escape_ical_text(value: str) -> str:
    """Escape RFC 5545 TEXT values."""
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold_line(line: str) -> str:
    """Fold a content line at 75 UTF-8 octets without splitting a code point."""
    chunks: list[str] = []
    current = ""
    limit = 75
    for character in line:
        encoded = character.encode("utf-8")
        if len(current.encode("utf-8")) + len(encoded) > limit:
            chunks.append(current)
            current = " "
            limit = 75
        current += character
    chunks.append(current)
    return "\r\n".join(chunks)


def _utc_datetime(value: datetime, timezone_name: str) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(timezone_name))
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def render_ical(
    sessions: list[TrainingSession], catalog: Catalog, timezone_name: str
) -> str:
    """Serialize a calendar using stable event UIDs and escaped descriptions."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Honkbal Trainer//NL",
        "CALSCALE:GREGORIAN",
    ]
    for session in sessions:
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{escape_ical_text(session.uid)}",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{_utc_datetime(session.start, timezone_name)}",
                f"DTEND:{_utc_datetime(session.end, timezone_name)}",
                f"SUMMARY:{escape_ical_text('Honkbaltraining: ' + ' + '.join(session.themes))}",
                f"DESCRIPTION:{escape_ical_text(session_description(session, catalog))}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold_line(line) for line in lines) + "\r\n"
