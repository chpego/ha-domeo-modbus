"""Switches for the S&P DOMEO EVO integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DomeoEvoConfigEntry
from .domeo_evo_modbus import AnyDomeo, Domeo210, Domeo210Version, DomeoEvo
from .entity import DomeoEvoEntity, DomeoEvoEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class DomeoEvoSwitchEntityDescription[D: AnyDomeo = DomeoEvo](
    SwitchEntityDescription, DomeoEvoEntityDescription
):
    """Describe a switch of one range of units, or of both."""

    value_fn: Callable[[D], bool | None]
    write_fn: Callable[[D, bool], Awaitable[None]]


HOLIDAY_MODE = DomeoEvoSwitchEntityDescription[AnyDomeo](
    key="holiday_mode",
    translation_key="holiday_mode",
    component="controls",
    value_fn=lambda device: device.controls.holiday_mode,
    write_fn=lambda device, on: device.controls.async_set_holiday_mode(on),
)

# The Europe version of the Domeo 210 stops instead of halving its airflow.
STANDBY = DomeoEvoSwitchEntityDescription[Domeo210](
    key="standby",
    translation_key="standby",
    component="controls",
    value_fn=lambda device: device.controls.holiday_mode,
    write_fn=lambda device, on: device.controls.async_set_holiday_mode(on),
)

# The switches both ranges have, besides holiday mode.
COMMON_SWITCHES: tuple[DomeoEvoSwitchEntityDescription[AnyDomeo], ...] = (
    DomeoEvoSwitchEntityDescription[AnyDomeo](
        key="manual_bypass",
        translation_key="manual_bypass",
        component="controls",
        value_fn=lambda device: device.controls.manual_bypass,
        write_fn=lambda device, on: device.controls.async_set_manual_bypass(on),
    ),
    DomeoEvoSwitchEntityDescription[AnyDomeo](
        key="auto_bypass",
        translation_key="auto_bypass",
        component="controls",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.controls.auto_bypass,
        write_fn=lambda device, on: device.controls.async_set_auto_bypass(on),
    ),
)

# The switches only the DOMEO EVO has.
SWITCHES: tuple[DomeoEvoSwitchEntityDescription, ...] = (
    DomeoEvoSwitchEntityDescription(
        key="defrost_allowed",
        translation_key="defrost_allowed",
        component="controls",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.controls.defrost_allowed,
        write_fn=lambda device, on: device.controls.async_set_defrost_allowed(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DomeoEvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches of the unit."""
    runtime_data = entry.runtime_data
    device = runtime_data.device
    descriptions: list[DomeoEvoSwitchEntityDescription[Any]]
    if isinstance(device, Domeo210):
        europe = device.controls.version is Domeo210Version.EUROPE
        descriptions = [STANDBY if europe else HOLIDAY_MODE, *COMMON_SWITCHES]
    else:
        descriptions = [HOLIDAY_MODE, *COMMON_SWITCHES, *SWITCHES]
    async_add_entities(
        DomeoEvoSwitch(runtime_data, description) for description in descriptions
    )


class DomeoEvoSwitch(DomeoEvoEntity, SwitchEntity):
    """A switch of the unit."""

    entity_description: DomeoEvoSwitchEntityDescription[Any]

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.entity_description.value_fn(self.coordinator.device)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_write(
            self.entity_description.write_fn(self.coordinator.device, True)
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_write(
            self.entity_description.write_fn(self.coordinator.device, False)
        )
