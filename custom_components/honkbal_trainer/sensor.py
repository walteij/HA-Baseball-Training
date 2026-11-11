"""Sensors exposing training schedule and progress."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TrainingCoordinator
from .const import BLOCK_LABELS, DOMAIN


@dataclass(frozen=True, kw_only=True)
class TrainingSensorDescription(SensorEntityDescription):
    value_key: str


DESCRIPTIONS = [
    TrainingSensorDescription(
        key="volgende_training",
        translation_key="volgende_training",
        value_key="volgende_training",
    ),
    TrainingSensorDescription(
        key="huidig_thema", translation_key="huidig_thema", value_key="huidig_thema"
    ),
    TrainingSensorDescription(
        key="huidige_week", translation_key="huidige_week", value_key="huidige_week"
    ),
    TrainingSensorDescription(
        key="programma_voortgang",
        translation_key="programma_voortgang",
        value_key="programma_voortgang",
    ),
    TrainingSensorDescription(
        key="sessie_status", translation_key="sessie_status", value_key="sessie_status"
    ),
    TrainingSensorDescription(
        key="warming_up", translation_key="warming_up", value_key="warming_up"
    ),
    TrainingSensorDescription(
        key="basis_drill", translation_key="basis_drill", value_key="basis_drill"
    ),
    TrainingSensorDescription(
        key="drill_1", translation_key="drill_1", value_key="drill_1"
    ),
    TrainingSensorDescription(
        key="drill_2", translation_key="drill_2", value_key="drill_2"
    ),
    TrainingSensorDescription(
        key="afsluiting", translation_key="afsluiting", value_key="afsluiting"
    ),
    TrainingSensorDescription(
        key="totaal_trainingen",
        translation_key="totaal_trainingen",
        value_key="totaal_trainingen",
    ),
    TrainingSensorDescription(
        key="drill_catalogus_count",
        translation_key="drill_catalogus_count",
        value_key="drill_catalogus_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: Any, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: TrainingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TrainingSensor(coordinator, entry.entry_id, description)
        for description in DESCRIPTIONS
    )


class TrainingSensor(CoordinatorEntity[TrainingCoordinator], SensorEntity):
    """A read-only training status sensor."""

    entity_description: TrainingSensorDescription

    def __init__(
        self,
        coordinator: TrainingCoordinator,
        entry_id: str,
        description: TrainingSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> Any:
        return self.coordinator.get_sensor_value(self.entity_description.value_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.value_key != "sessie_status":
            return None
        active_drill = self.coordinator.active_drill()
        if active_drill is None:
            return None
        block, drill_id = active_drill
        drill = self.coordinator.catalog.by_id[drill_id]
        return {
            "huidig_blok": BLOCK_LABELS[block],
            "huidige_drill": drill["name_nl"],
            "coach_cues": drill.get("coach_cues", [])[:2],
        }
