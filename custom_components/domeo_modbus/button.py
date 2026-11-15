"""Buttons for the S&P DOMEO EVO integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import DomeoEvoConfigEntry
from .domeo_evo_modbus import AnyDomeo, Domeo210, DomeoEvo
from .entity import DomeoEvoEntity, DomeoEvoEntityDescription

PARALLEL_UPDATES = 1

# 0.2.0-beta.1 had a stop boost button, but a boost cannot be stopped over
# Modbus (issue #6). Its registry entry is removed so it does not linger.
REMOVED_BUTTONS = ("stop_boost",)


async def _async_start_boost(device: DomeoEvo) -> None:
    """Start a boost, unless holiday mode would make the unit ignore it.

    Real units leave the boost request unanswered while holiday mode is on
    (issue #6), so the press fails with a reason instead of doing nothing.
    Holiday mode is read again first: the panel may have changed it since the
    last poll.
    """
    await device.controls.async_update()
    if device.controls.holiday_mode:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="boost_in_holiday_mode",
        )
    await device.settings.async_start_boost()


@dataclass(frozen=True, kw_only=True)
class DomeoEvoButtonEntityDescription[D: AnyDomeo = DomeoEvo](
    ButtonEntityDescription, DomeoEvoEntityDescription
):
    """Describe a button of one range of units, or of both."""

    press_fn: Callable[[D], Awaitable[None]]


START_BOOST = DomeoEvoButtonEntityDescription(
    key="start_boost",
    translation_key="start_boost",
    component="readings",
    press_fn=_async_start_boost,
)

# Holiday mode does not block it as far as anyone knows. The Europe version
# has no boost: the same register picks one of three speeds.
START_BOOST_210 = DomeoEvoButtonEntityDescription[Domeo210](
    key="start_boost",
    translation_key="start_boost",
    component="readings",
    press_fn=lambda device: device.async_start_boost(),
)

RESET_FILTER_ALARM = DomeoEvoButtonEntityDescription[AnyDomeo](
    key="reset_filter_alarm",
    translation_key="reset_filter_alarm",
    component="status",
    press_fn=lambda device: device.controls.async_reset_filter_alarm(),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DomeoEvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons of the unit."""
    entity_registry = er.async_get(hass)
    for key in REMOVED_BUTTONS:
        if entity_id := entity_registry.async_get_entity_id(
            Platform.BUTTON, DOMAIN, f"{entry.entry_id}_{key}"
        ):
            entity_registry.async_remove(entity_id)
    runtime_data = entry.runtime_data
    device = runtime_data.device
    descriptions: list[DomeoEvoButtonEntityDescription[Any]]
    if isinstance(device, Domeo210):
        descriptions = [START_BOOST_210] if device.has_boost else []
    else:
        descriptions = [START_BOOST]
    descriptions.append(RESET_FILTER_ALARM)
    async_add_entities(
        DomeoEvoButton(runtime_data, description) for description in descriptions
    )


class DomeoEvoButton(DomeoEvoEntity, ButtonEntity):
    """A button of the unit."""

    entity_description: DomeoEvoButtonEntityDescription[Any]

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._async_write(
            self.entity_description.press_fn(self.coordinator.device)
        )
