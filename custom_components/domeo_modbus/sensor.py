"""Sensors for the S&P DOMEO EVO integration."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DomeoEvoConfigEntry
from .domeo_evo_modbus import (
    AirSensType,
    AnyDomeo,
    BypassState,
    ControlPanel,
    Domeo210,
    DomeoEvo,
    HeaterState,
    LimitSwitchState,
    OperatingMode,
    PreheaterState,
)
from .entity import DomeoEvoEntity, DomeoEvoEntityDescription

PARALLEL_UPDATES = 0


def _options(enum_type: type[IntEnum]) -> list[str]:
    """The sensor options a device enum maps to."""
    return [member.name.lower() for member in enum_type]


def _option(value: IntEnum | None) -> str | None:
    """The sensor state of a device enum value."""
    return None if value is None else value.name.lower()


@dataclass(frozen=True, kw_only=True)
class DomeoEvoSensorEntityDescription[D: AnyDomeo = DomeoEvo](
    SensorEntityDescription, DomeoEvoEntityDescription
):
    """Describe a sensor of one range of units, or of both."""

    value_fn: Callable[[D], float | str | None]
    exists_fn: Callable[[D], bool] = lambda device: True


def _temperature[D: AnyDomeo](
    key: str,
    value_fn: Callable[[D], float | None],
    *,
    enabled_default: bool = True,
) -> DomeoEvoSensorEntityDescription[D]:
    """Describe one of the unit's temperature probes."""
    return DomeoEvoSensorEntityDescription[D](
        key=key,
        translation_key=key,
        component="readings",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=enabled_default,
        value_fn=value_fn,
    )


# The sensors both ranges have.
COMMON_SENSORS: tuple[DomeoEvoSensorEntityDescription[AnyDomeo], ...] = (
    DomeoEvoSensorEntityDescription[AnyDomeo](
        key="airflow",
        translation_key="airflow",
        component="readings",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        value_fn=lambda device: device.readings.airflow,
    ),
    _temperature("extract_temperature", lambda d: d.readings.extract_temperature),
    _temperature("exhaust_temperature", lambda d: d.readings.exhaust_temperature),
    _temperature("outdoor_temperature", lambda d: d.readings.outdoor_temperature),
    _temperature("supply_temperature", lambda d: d.readings.supply_temperature),
)

# The sensors only the DOMEO EVO has.
SENSORS: tuple[DomeoEvoSensorEntityDescription, ...] = (
    DomeoEvoSensorEntityDescription(
        key="humidity",
        component="readings",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.readings.humidity,
        # Units without the integrated sensor report a constant 54 %.
        exists_fn=lambda device: device.regulates_humidity,
    ),
    DomeoEvoSensorEntityDescription(
        key="operating_mode",
        translation_key="operating_mode",
        component="readings",
        device_class=SensorDeviceClass.ENUM,
        options=_options(OperatingMode),
        value_fn=lambda device: _option(device.readings.operating_mode),
    ),
    _temperature(
        "pre_exchanger_temperature",
        # Not every unit has this probe. One without it flags a fault and
        # reads a meaningless value (-30.0 °C on a real 225 FL).
        lambda d: (
            None
            if d.status.pre_exchanger_probe_fault
            else d.readings.pre_exchanger_temperature
        ),
        enabled_default=False,
    ),
    DomeoEvoSensorEntityDescription(
        key="voltage_input",
        translation_key="voltage_input",
        component="readings",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.readings.voltage_input,
    ),
    DomeoEvoSensorEntityDescription(
        key="bypass_limit_switch",
        translation_key="bypass_limit_switch",
        component="readings",
        device_class=SensorDeviceClass.ENUM,
        options=_options(LimitSwitchState),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: _option(device.readings.bypass_limit_switch),
    ),
    DomeoEvoSensorEntityDescription(
        key="preheater_state",
        translation_key="preheater_state",
        component="readings",
        device_class=SensorDeviceClass.ENUM,
        options=_options(PreheaterState),
        value_fn=lambda device: _option(device.readings.preheater_state),
        exists_fn=lambda device: bool(device.status.preheater_connected),
    ),
    DomeoEvoSensorEntityDescription(
        key="control_panel",
        translation_key="control_panel",
        component="readings",
        device_class=SensorDeviceClass.ENUM,
        options=_options(ControlPanel),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: _option(device.readings.control_panel),
    ),
)


def _heater_state(
    key: str,
    value_fn: Callable[[Domeo210], HeaterState | None],
    exists_fn: Callable[[Domeo210], bool],
) -> DomeoEvoSensorEntityDescription[Domeo210]:
    """Describe the state of one of the optional heating batteries."""
    return DomeoEvoSensorEntityDescription[Domeo210](
        key=key,
        translation_key=key,
        component="readings",
        device_class=SensorDeviceClass.ENUM,
        options=_options(HeaterState),
        value_fn=lambda device: _option(value_fn(device)),
        exists_fn=exists_fn,
    )


def _fan_speed(
    key: str, value_fn: Callable[[Domeo210], int | None]
) -> DomeoEvoSensorEntityDescription[Domeo210]:
    """Describe the speed of one of the two fans (2014 table only)."""
    return DomeoEvoSensorEntityDescription[Domeo210](
        key=key,
        translation_key=key,
        component="extras",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=value_fn,
        exists_fn=lambda device: device.extras is not None,
    )


# The sensors only the Domeo 210 has.
SENSORS_210: tuple[DomeoEvoSensorEntityDescription[Domeo210], ...] = (
    DomeoEvoSensorEntityDescription[Domeo210](
        key="bypass_state",
        translation_key="bypass_state",
        component="readings",
        device_class=SensorDeviceClass.ENUM,
        options=_options(BypassState),
        value_fn=lambda device: _option(device.readings.bypass_state),
    ),
    _heater_state(
        "preheater_battery",
        lambda device: device.readings.preheater_state,
        lambda device: bool(device.controls.preheater_installed),
    ),
    _heater_state(
        "postheater_battery",
        lambda device: device.readings.postheater_state,
        lambda device: bool(device.controls.postheater_installed),
    ),
    _fan_speed(
        "extract_fan_speed",
        lambda device: (
            None if device.extras is None else device.extras.extract_motor_speed
        ),
    ),
    _fan_speed(
        "supply_fan_speed",
        lambda device: (
            None if device.extras is None else device.extras.supply_motor_speed
        ),
    ),
)

_PROBE_DEVICE_CLASSES: dict[AirSensType, tuple[SensorDeviceClass, str]] = {
    AirSensType.HUMIDITY: (SensorDeviceClass.HUMIDITY, PERCENTAGE),
    AirSensType.CO2: (SensorDeviceClass.CO2, UnitOfRatio.PARTS_PER_MILLION),
    AirSensType.VOC: (
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        UnitOfRatio.PARTS_PER_MILLION,
    ),
}


def _probe_value(probe: int) -> Callable[[DomeoEvo], int | None]:
    """Read the value of one AIRSENS probe."""

    def _value(device: DomeoEvo) -> int | None:
        return None if device.probes is None else device.probes.probe_value(probe)

    return _value


def _probe_sensors(device: DomeoEvo) -> Iterable[DomeoEvoSensorEntityDescription]:
    """Describe a sensor for each connected AIRSENS probe of a known type."""
    if device.probes is None:
        return
    for probe in device.connected_probes:
        probe_type = device.probes.probe_type(probe)
        if probe_type not in _PROBE_DEVICE_CLASSES:
            continue
        device_class, unit = _PROBE_DEVICE_CLASSES[probe_type]
        yield DomeoEvoSensorEntityDescription(
            key=f"probe_{probe}",
            translation_key=f"probe_{probe_type.name.lower()}",
            translation_placeholders={"probe": str(probe)},
            component="probes",
            device_class=device_class,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=unit,
            value_fn=_probe_value(probe),
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DomeoEvoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of the unit."""
    runtime_data = entry.runtime_data
    device = runtime_data.device
    descriptions: list[DomeoEvoSensorEntityDescription[Any]] = list(COMMON_SENSORS)
    if isinstance(device, Domeo210):
        descriptions += (d for d in SENSORS_210 if d.exists_fn(device))
    else:
        descriptions += (
            d for d in (*SENSORS, *_probe_sensors(device)) if d.exists_fn(device)
        )
    async_add_entities(
        DomeoEvoSensor(runtime_data, description) for description in descriptions
    )


class DomeoEvoSensor(DomeoEvoEntity, SensorEntity):
    """A sensor of the unit."""

    entity_description: DomeoEvoSensorEntityDescription[Any]

    @property
    @override
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.device)
