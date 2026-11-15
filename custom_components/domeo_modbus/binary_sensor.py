"""Binary sensors for the S&P DOMEO EVO integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DomeoEvoConfigEntry
from .domeo_evo_modbus import AnyDomeo, Domeo210, DomeoEvo
from .entity import DomeoEvoEntity, DomeoEvoEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DomeoEvoBinarySensorEntityDescription[D: AnyDomeo = DomeoEvo](
    BinarySensorEntityDescription, DomeoEvoEntityDescription
):
    """Describe a binary sensor of one range of units, or of both."""

    value_fn: Callable[[D], bool | None]


def _probe_fault[D: AnyDomeo](
    key: str, value_fn: Callable[[D], bool | None]
) -> DomeoEvoBinarySensorEntityDescription[D]:
    """Describe the fault flag of one temperature probe."""
    return DomeoEvoBinarySensorEntityDescription[D](
        key=key,
        translation_key=key,
        component="status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=value_fn,
    )


# The binary sensors both ranges have.
COMMON_BINARY_SENSORS: tuple[DomeoEvoBinarySensorEntityDescription[AnyDomeo], ...] = (
    DomeoEvoBinarySensorEntityDescription[AnyDomeo](
        key="filter_alarm",
        translation_key="filter_alarm",
        component="status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: device.status.filter_alarm,
    ),
    DomeoEvoBinarySensorEntityDescription[AnyDomeo](
        key="defrost",
        translation_key="defrost",
        component="status",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda device: device.status.defrost_active,
    ),
    _probe_fault("extract_probe_fault", lambda d: d.status.extract_probe_fault),
    _probe_fault("exhaust_probe_fault", lambda d: d.status.exhaust_probe_fault),
    _probe_fault("outdoor_probe_fault", lambda d: d.status.outdoor_probe_fault),
    _probe_fault("supply_probe_fault", lambda d: d.status.supply_probe_fault),
)

# The binary sensors only the DOMEO EVO has.
BINARY_SENSORS: tuple[DomeoEvoBinarySensorEntityDescription, ...] = (
    DomeoEvoBinarySensorEntityDescription(
        key="motor_1_fault",
        translation_key="motor_1_fault",
        component="status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.status.motor_1_fault,
    ),
    DomeoEvoBinarySensorEntityDescription(
        key="motor_2_fault",
        translation_key="motor_2_fault",
        component="status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.status.motor_2_fault,
    ),
    DomeoEvoBinarySensorEntityDescription(
        # Jumper JP1: closed, the unit takes orders over Modbus; open, it
        # still answers reads but refuses every write.
        key="modbus_control",
        translation_key="modbus_control",
        component="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.status.modbus_control,
    ),
    DomeoEvoBinarySensorEntityDescription(
        key="clp",
        translation_key="clp",
        component="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.status.clp_active,
    ),
    _probe_fault(
        "pre_exchanger_probe_fault", lambda d: d.status.pre_exchanger_probe_fault
    ),
)


def _motor_fault(
    key: str, value_fn: Callable[[Domeo210], bool | None]
) -> DomeoEvoBinarySensorEntityDescription[Domeo210]:
    """Describe the fault flag of one of the two fans."""
    return DomeoEvoBinarySensorEntityDescription[Domeo210](
        key=key,
        translation_key=key,
        component="status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=value_fn,
    )


# The binary sensors only the Domeo 210 has: its table names the two motors.
BINARY_SENSORS_210: tuple[DomeoEvoBinarySensorEntityDescription[Domeo210], ...] = (
    _motor_fault("extract_motor_fault", lambda d: d.status.extract_motor_fault),
    _motor_fault("supply_motor_fault", lambda d: d.status.supply_motor_fault),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DomeoEvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors of the unit."""
    runtime_data = entry.runtime_data
    descriptions: list[DomeoEvoBinarySensorEntityDescription[Any]] = [
        *COMMON_BINARY_SENSORS,
        *(
            BINARY_SENSORS_210
            if isinstance(runtime_data.device, Domeo210)
            else BINARY_SENSORS
        ),
    ]
    async_add_entities(
        DomeoEvoBinarySensor(runtime_data, description) for description in descriptions
    )


class DomeoEvoBinarySensor(DomeoEvoEntity, BinarySensorEntity):
    """A binary sensor of the unit."""

    entity_description: DomeoEvoBinarySensorEntityDescription[Any]

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the flag."""
        return self.entity_description.value_fn(self.coordinator.device)
