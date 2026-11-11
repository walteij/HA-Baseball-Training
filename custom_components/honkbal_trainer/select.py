"""Select entities for theme and practice focus."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TrainingCoordinator
from .const import DOMAIN, FOCUSES, THEMES


async def async_setup_entry(
    hass: HomeAssistant, entry: Any, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: TrainingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TrainingSelect(coordinator, entry.entry_id, "thema_override"),
            TrainingSelect(coordinator, entry.entry_id, "focus"),
        ]
    )


class TrainingSelect(CoordinatorEntity[TrainingCoordinator], SelectEntity):
    """A selection that updates the training configuration."""

    def __init__(
        self, coordinator: TrainingCoordinator, entry_id: str, selection: str
    ) -> None:
        super().__init__(coordinator)
        self._selection = selection
        self._attr_unique_id = f"{entry_id}_{selection}"
        self._attr_has_entity_name = True
        self._attr_translation_key = selection
        self._attr_options = (
            ["volgens_programma", *THEMES] if selection == "thema_override" else FOCUSES
        )

    @property
    def current_option(self) -> str:
        if self._selection == "focus":
            return self.coordinator.data.focus or "techniek"
        return self.coordinator.settings.theme_override or "volgens_programma"

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise ValueError(f"Ongeldige optie: {option}")
        if self._selection == "focus":
            self.coordinator.data.focus = option
        else:
            self.coordinator.settings.theme_override = (
                "" if option == "volgens_programma" else option
            )
            self.coordinator.data.theme_override = (
                self.coordinator.settings.theme_override
            )
            await self.coordinator.async_generate_season()
        await self.coordinator.async_save()
