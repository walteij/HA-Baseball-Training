"""Buttons for controlling the active training session."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TrainingCoordinator
from .const import DOMAIN

BUTTONS = [
    ButtonEntityDescription(key="start_training", translation_key="start_training"),
    ButtonEntityDescription(key="voltooi_training", translation_key="voltooi_training"),
    ButtonEntityDescription(key="volgende_drill", translation_key="volgende_drill"),
    ButtonEntityDescription(
        key="genereer_planning", translation_key="genereer_planning"
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: Any, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: TrainingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TrainingButton(coordinator, entry.entry_id, description)
        for description in BUTTONS
    )


class TrainingButton(CoordinatorEntity[TrainingCoordinator], ButtonEntity):
    """An action button for session operations."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: TrainingCoordinator,
        entry_id: str,
        description: ButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_has_entity_name = True

    async def async_press(self) -> None:
        try:
            match self.entity_description.key:
                case "start_training":
                    await self.coordinator.async_start_session()
                case "voltooi_training":
                    await self.coordinator.async_complete_session()
                case "volgende_drill":
                    await self.coordinator.async_next_drill()
                case "genereer_planning":
                    await self.coordinator.async_generate_season()
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
