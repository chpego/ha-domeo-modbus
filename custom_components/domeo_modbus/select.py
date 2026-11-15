"""Selects for the S&P DOMEO EVO integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DomeoEvoConfigEntry, DomeoEvoRuntimeData
from .domeo_evo_modbus import AutoMode, ClpContact, DomeoEvo
from .entity import DomeoEvoEntity, DomeoEvoEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class DomeoEvoSelectEntityDescription(
    SelectEntityDescription, DomeoEvoEntityDescription
):
    """Describe a DOMEO EVO select."""

    options_enum: type[IntEnum]
    value_fn: Callable[[DomeoEvo], IntEnum | None]
    write_fn: Callable[[DomeoEvo, int], Awaitable[None]]


SELECTS: tuple[DomeoEvoSelectEntityDescription, ...] = (
    DomeoEvoSelectEntityDescription(
        key="auto_mode",
        translation_key="auto_mode",
        component="controls",
        entity_category=EntityCategory.CONFIG,
        options=[member.name.lower() for member in AutoMode],
        options_enum=AutoMode,
        value_fn=lambda device: device.controls.auto_mode,
        write_fn=lambda device, value: device.controls.async_set_auto_mode(
            AutoMode(value)
        ),
    ),
    DomeoEvoSelectEntityDescription(
        key="clp_contact",
        translation_key="clp_contact",
        component="controls",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options=[member.name.lower() for member in ClpContact],
        options_enum=ClpContact,
        value_fn=lambda device: device.controls.clp_contact,
        write_fn=lambda device, value: device.controls.async_set_clp_contact(
            ClpContact(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DomeoEvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DOMEO EVO selects. The Domeo 210 has none."""
    runtime_data = entry.runtime_data
    device = runtime_data.device
    if not isinstance(device, DomeoEvo):
        return
    async_add_entities(
        DomeoEvoSelect(runtime_data, description, device) for description in SELECTS
    )


class DomeoEvoSelect(DomeoEvoEntity, SelectEntity):
    """A DOMEO EVO select."""

    entity_description: DomeoEvoSelectEntityDescription

    def __init__(
        self,
        runtime_data: DomeoEvoRuntimeData,
        entity_description: DomeoEvoSelectEntityDescription,
        device: DomeoEvo,
    ) -> None:
        """Initialize the select for a DOMEO EVO, the only range with selects."""
        super().__init__(runtime_data, entity_description)
        self._device = device

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected option."""
        value = self.entity_description.value_fn(self._device)
        return None if value is None else value.name.lower()

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the unit."""
        value = self.entity_description.options_enum[option.upper()]
        await self._async_write(self.entity_description.write_fn(self._device, value))
