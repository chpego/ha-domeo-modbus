"""Numbers for the S&P DOMEO EVO integration."""

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any, Literal, override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DomeoEvoConfigEntry, DomeoEvoRuntimeData
from .domeo_evo_modbus import AnyDomeo, Domeo210, DomeoEvo, Source
from .entity import DomeoEvoEntity, DomeoEvoEntityDescription

PARALLEL_UPDATES = 1

_FLOW = UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR


@dataclass(frozen=True, kw_only=True)
class DomeoEvoNumberEntityDescription[D: AnyDomeo = DomeoEvo](
    NumberEntityDescription, DomeoEvoEntityDescription
):
    """Describe a number of one range of units, or of both."""

    limits_fn: Callable[[D], tuple[int, int]]
    value_fn: Callable[[D], float | None]
    write_fn: Callable[[D, int], Awaitable[None]]


def _airflow(
    key: str,
    limits_fn: Callable[[AnyDomeo], tuple[int, int]],
    write_fn: Callable[[AnyDomeo, int], Awaitable[None]],
) -> DomeoEvoNumberEntityDescription[AnyDomeo]:
    """Describe one of the three airflow settings."""
    return DomeoEvoNumberEntityDescription[AnyDomeo](
        key=key,
        translation_key=key,
        component="settings",
        device_class=NumberDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=_FLOW,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        limits_fn=limits_fn,
        value_fn=lambda device: getattr(device.settings, key),
        write_fn=write_fn,
    )


def _setting(
    key: str,
    low: int,
    high: int,
    unit: str,
    *,
    device_class: NumberDeviceClass | None = None,
    enabled_default: bool = True,
) -> DomeoEvoNumberEntityDescription[AnyDomeo]:
    """Describe a setting with a fixed range, written as-is."""
    return DomeoEvoNumberEntityDescription[AnyDomeo](
        key=key,
        translation_key=key,
        component="settings",
        device_class=device_class,
        native_unit_of_measurement=unit,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=enabled_default,
        mode=NumberMode.BOX,
        limits_fn=lambda device: (low, high),
        value_fn=lambda device: getattr(device.settings, key),
        write_fn=lambda device, value: device.settings.write(key, value),
    )


# The numbers both ranges have, with the same ranges except for airflows.
COMMON_NUMBERS: tuple[DomeoEvoNumberEntityDescription[AnyDomeo], ...] = (
    _airflow(
        "low_flow",
        lambda device: device.flow_limits.low,
        lambda device, value: device.async_set_low_flow(value),
    ),
    _airflow(
        "high_flow",
        lambda device: device.flow_limits.high,
        lambda device, value: device.async_set_high_flow(value),
    ),
    _airflow(
        "freecooling_flow",
        lambda device: device.flow_limits.freecooling,
        lambda device, value: device.async_set_freecooling_flow(value),
    ),
    _setting(
        "bypass_outdoor_minimum",
        11,
        20,
        UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    _setting(
        "bypass_indoor_minimum",
        21,
        30,
        UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    _setting(
        "manual_bypass_duration",
        1,
        24,
        UnitOfTime.HOURS,
        device_class=NumberDeviceClass.DURATION,
    ),
    _setting("filter_interval", 1, 24, UnitOfTime.MONTHS),
)

# The numbers only the DOMEO EVO has.
NUMBERS: tuple[DomeoEvoNumberEntityDescription[AnyDomeo], ...] = (
    _setting(
        "flow_correction",
        -15,
        15,
        _FLOW,
        device_class=NumberDeviceClass.VOLUME_FLOW_RATE,
        enabled_default=False,
    ),
    _setting("flow_offset", -15, 15, PERCENTAGE, enabled_default=False),
)

# The numbers only the Domeo 210 has.
NUMBERS_210: tuple[DomeoEvoNumberEntityDescription[AnyDomeo], ...] = (
    _setting("flow_unbalance", -15, 15, PERCENTAGE, enabled_default=False),
)


def _humidity_210(
    field: str, unit: str, limits_fn: Callable[[Domeo210], tuple[int, int]]
) -> DomeoEvoNumberEntityDescription[Domeo210]:
    """Describe one of the four humidity regulation settings of the 210 DHU.

    The entity offers the table's full range; the library refuses a value
    that comes too close to the other bound.
    """
    key = f"sensor_{field}"
    return DomeoEvoNumberEntityDescription[Domeo210](
        key=key,
        translation_key=key,
        component="humidity_settings",
        device_class=(NumberDeviceClass.VOLUME_FLOW_RATE if unit == _FLOW else None),
        native_unit_of_measurement=unit,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        limits_fn=limits_fn,
        value_fn=lambda device: getattr(device.humidity_settings, field),
        write_fn=lambda device, value: device.async_set_humidity_setting(field, value),
    )


# The humidity regulation of the Domeo 210 DHU, named like the DOMEO EVO's.
HUMIDITY_NUMBERS_210: tuple[DomeoEvoNumberEntityDescription[Domeo210], ...] = (
    _humidity_210("minimum_flow", _FLOW, lambda d: d.flow_limits.maximum),
    _humidity_210("maximum_flow", _FLOW, lambda d: d.flow_limits.maximum),
    _humidity_210("minimum_level", PERCENTAGE, lambda d: (60, 90)),
    _humidity_210("maximum_level", PERCENTAGE, lambda d: (60, 90)),
)


def _regulation_numbers(
    device: DomeoEvo,
) -> Iterable[DomeoEvoNumberEntityDescription]:
    """Describe the regulation settings of each source the unit regulates on."""
    if device.humidity_settings is None:
        return
    sources: list[Source] = ["sensor", *device.connected_probes]
    for source in sources:
        if (unit := device.level_unit(source)) is None:
            continue
        name = "sensor" if source == "sensor" else "probe"
        prefix = "sensor" if source == "sensor" else f"probe_{source}"
        placeholders = {} if source == "sensor" else {"probe": str(source)}
        for which in ("minimum", "maximum"):
            yield _regulation_flow(source, which, name, prefix, placeholders)
            yield _regulation_level(source, which, name, prefix, placeholders, unit)


def _regulation_flow(
    source: Source,
    which: Literal["minimum", "maximum"],
    name: str,
    prefix: str,
    placeholders: dict[str, str],
) -> DomeoEvoNumberEntityDescription:
    """Describe the airflow a source regulates down to, or up to."""
    field = f"{prefix}_{which}_flow"
    return DomeoEvoNumberEntityDescription(
        key=field,
        translation_key=f"{name}_{which}_flow",
        translation_placeholders=placeholders,
        component="humidity_settings",
        device_class=NumberDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=_FLOW,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        limits_fn=lambda device: (
            device.flow_limits.low if which == "minimum" else device.flow_limits.maximum
        ),
        value_fn=lambda device: getattr(device.humidity_settings, field),
        write_fn=lambda device, value: device.async_set_regulation_flow(
            source, which, value
        ),
    )


def _regulation_level(
    source: Source,
    which: Literal["minimum", "maximum"],
    name: str,
    prefix: str,
    placeholders: dict[str, str],
    unit: str,
) -> DomeoEvoNumberEntityDescription:
    """Describe the level a source regulates from, or up to."""
    field = f"{prefix}_{which}_level"
    return DomeoEvoNumberEntityDescription(
        key=field,
        translation_key=f"{name}_{which}_level",
        translation_placeholders=placeholders,
        component="humidity_settings",
        native_unit_of_measurement=unit,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        # level_unit() returned a unit, so the limits are known.
        limits_fn=lambda device: device.level_limits(source, which) or (0, 0),
        value_fn=lambda device: getattr(device.humidity_settings, field),
        write_fn=lambda device, value: device.async_set_regulation_level(
            source, which, value
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DomeoEvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the numbers of the unit."""
    runtime_data = entry.runtime_data
    device = runtime_data.device
    descriptions: list[DomeoEvoNumberEntityDescription[Any]] = list(COMMON_NUMBERS)
    if isinstance(device, Domeo210):
        descriptions += NUMBERS_210
        if device.humidity_settings is not None:
            descriptions += HUMIDITY_NUMBERS_210
    else:
        descriptions += (*NUMBERS, *_regulation_numbers(device))
    async_add_entities(
        DomeoEvoNumber(runtime_data, description) for description in descriptions
    )


class DomeoEvoNumber(DomeoEvoEntity, NumberEntity):
    """A number of the unit."""

    _attr_native_step = 1
    entity_description: DomeoEvoNumberEntityDescription[Any]

    def __init__(
        self,
        runtime_data: DomeoEvoRuntimeData,
        entity_description: DomeoEvoNumberEntityDescription[Any],
    ) -> None:
        """Initialize the number with the range this unit accepts."""
        super().__init__(runtime_data, entity_description)
        low, high = entity_description.limits_fn(runtime_data.device)
        self._attr_native_min_value = low
        self._attr_native_max_value = high

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.device)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write a new value to the unit."""
        await self._async_write(
            self.entity_description.write_fn(self.coordinator.device, int(value))
        )
