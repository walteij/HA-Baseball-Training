"""Persistent integration state and storage migrations."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION
from .models import IntegrationState, TeamSettings, TrainingSession


def migrate_storage_data(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Upgrade prior persisted state to the current schema."""
    if data is None:
        return None
    version = int(data.get("schema_version", 1))
    if version == 1:
        data = {
            **data,
            "usage": data.get("usage", {}),
            "active_session_uid": data.get("active_session_uid"),
            "active_block_index": data.get("active_block_index", 0),
            "focus": data.get("focus", ""),
            "theme_override": data.get("theme_override"),
            "settings_signature": data.get("settings_signature", ""),
            "schema_version": STORAGE_VERSION,
        }
    elif version != STORAGE_VERSION:
        raise ValueError(f"Niet-ondersteunde opslagversie: {version}")
    else:
        data = {
            **data,
            "theme_override": data.get("theme_override"),
            "settings_signature": data.get("settings_signature", ""),
        }
    return data


class VersionedStore(Store[dict[str, Any]]):
    """Apply the integration data migration when HA reads an older store."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        if old_major_version not in {1, STORAGE_VERSION}:
            raise ValueError(f"Niet-ondersteunde opslagversie: {old_major_version}")
        migrated = migrate_storage_data(old_data)
        if migrated is None:
            raise ValueError("Lege opslag kan niet worden gemigreerd")
        return migrated


class TrainingStorage:
    """Versioned Home Assistant storage for generated sessions and progress."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = VersionedStore(
            hass, STORAGE_VERSION, f"{DOMAIN}_{entry_id}", minor_version=0
        )

    async def async_load(self, settings: TeamSettings) -> IntegrationState:
        data = migrate_storage_data(await self._store.async_load())
        if data is None:
            return IntegrationState(settings=settings)
        return IntegrationState(
            settings=settings,
            sessions=[
                TrainingSession.from_dict(item) for item in data.get("sessions", [])
            ],
            usage={key: list(values) for key, values in data.get("usage", {}).items()},
            active_session_uid=data.get("active_session_uid"),
            active_block_index=int(data.get("active_block_index", 0)),
            focus=str(data.get("focus", "")),
            theme_override=data.get("theme_override"),
            settings_signature=str(data.get("settings_signature", "")),
        )

    async def async_save(self, state: IntegrationState) -> None:
        await self._store.async_save(
            {
                "schema_version": STORAGE_VERSION,
                "sessions": [session.as_dict() for session in state.sessions],
                "usage": state.usage,
                "active_session_uid": state.active_session_uid,
                "active_block_index": state.active_block_index,
                "focus": state.focus,
                "theme_override": state.theme_override,
                "settings_signature": state.settings_signature,
            }
        )
