"""The DOMEO EVO, as one object over its components."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Literal

from modbus_connection.model import Device, Raw, UpdateReport, read_optional

from .controls import Controls
from .enums import AirSensType, Model, Variant
from .limits import FLOW_LIMITS, FlowLimits, check_range
from .readings import AirSensProbes, Identity, Readings, _check_probe
from .settings import HumiditySettings, Settings
from .status import Status

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

# What each update method reads, by attribute name.
READINGS = ("readings", "status", "controls", "probes")
SETTINGS = ("settings", "humidity_settings")
ALL = ("identity", *READINGS, *SETTINGS)

# Quiet time around each request, for the RS485 turnaround behind a gateway.
MESSAGE_SPACING = 0.05

# The highest firmware version the unit can report (xx.x, times ten).
_MAX_FIRMWARE = 999
# The highest airflow the unit can report.
_MAX_AIRFLOW = 500

# The integrated humidity sensor, or one of the five AIRSENS probe slots.
type Source = Literal["sensor"] | int

# Thresholds by sensor type: (minimum level range, maximum level range).
_HUMIDITY_LEVELS = ((60, 89), (60, 90))  # %RH
_PPM_LEVELS = ((400, 2000), (400, 2000))  # CO2 or VOC, ppm


class NotADomeoEvoError(Exception):
    """The device answers Modbus, but not like a DOMEO EVO."""


class DomeoEvo(Device):
    """An S&P DOMEO EVO heat recovery ventilation unit.

    The unit reports neither its size nor its variant, so the caller states
    both. The size sets the airflow ranges a write accepts. The variant
    decides whether the humidity regulation registers are read.
    """

    readings_components = READINGS
    settings_components = SETTINGS

    def __init__(
        self,
        unit: ModbusUnit,
        model: Model = Model.DOMEO_EVO_225,
        variant: Variant = Variant.FL,
    ) -> None:
        super().__init__(unit)
        unit.set_message_spacing(MESSAGE_SPACING)
        self.model = Model(model)
        self.variant = Variant(variant)

        self.identity = Identity(unit)
        self.readings = Readings(unit)
        self.status = Status(unit)
        self.controls = Controls(unit)
        self.settings = Settings(unit)

        # Settled at setup: only present when the unit serves them.
        self.probes: AirSensProbes | None = None
        self.humidity_settings: HumiditySettings | None = None
        self.connected_probes: tuple[int, ...] = ()

    @property
    def name(self) -> str:
        """The commercial name of the unit."""
        return f"DOMEO EVO {self.model.value} {self.variant.name}"

    @property
    def flow_limits(self) -> FlowLimits:
        """The airflow ranges this unit size accepts."""
        return FLOW_LIMITS[self.model]

    @property
    def regulates_humidity(self) -> bool:
        """Whether this variant regulates on humidity or air quality."""
        return self.variant in (Variant.DHU, Variant.SERENITE)

    async def _async_setup(self) -> None:
        """Read the firmware versions and settle which probes are fitted."""
        await self.identity.async_update(notify=False)
        await self.status.async_update(notify=False)
        self.connected_probes = self.status.connected_probes
        if self.connected_probes:
            self.probes = await read_optional(AirSensProbes(self.modbus_unit))
        if self.regulates_humidity:
            self.humidity_settings = await read_optional(
                HumiditySettings(self.modbus_unit)
            )

    async def async_validate(self) -> None:
        """Check the unit answers like a DOMEO EVO, or raise.

        Raises ``NotADomeoEvoError`` when the values make no sense for this
        unit, and ``ModbusError`` when the unit cannot be read.
        """
        await self.async_ensure_setup()
        await self.readings.async_update(notify=False)
        firmware = self.identity._unit_firmware
        if firmware is None or firmware > _MAX_FIRMWARE:
            raise NotADomeoEvoError(f"unexpected firmware version {firmware!r}")
        if self.readings.operating_mode is None:
            raise NotADomeoEvoError("unexpected operating mode")
        airflow = self.readings.airflow
        if airflow is None or airflow > _MAX_AIRFLOW:
            raise NotADomeoEvoError(f"unexpected airflow {airflow!r}")
        # The previous Domeo range (210, DHU/Hygro, Flexeo, Ideo, Atacama) has
        # another register table: there, 30017 holds the current airflow and
        # 30022 a temperature, not values from 0 to 2 (chpego/ha-domeo-modbus#7).
        if self.readings.bypass_limit_switch is None:
            raise NotADomeoEvoError("unexpected bypass limit switch state")
        if self.readings.control_panel is None:
            raise NotADomeoEvoError("unexpected control panel")

    async def async_update_readings(self) -> UpdateReport:
        """Refresh what the unit measures and the state of its switches."""
        return await self.async_poll(READINGS)

    async def async_update_settings(self) -> UpdateReport:
        """Refresh the unit's configuration."""
        return await self.async_poll(SETTINGS)

    async def async_update(self) -> UpdateReport:
        """Refresh everything."""
        report = await self.async_poll(READINGS)
        return await self.async_poll(SETTINGS, report)

    async def async_read_raw(self, names: Iterable[str] = ALL) -> Raw:
        """Every register this unit reads, undecoded, for diagnostics."""
        return await super().async_read_raw(names)

    # Airflows, checked against the range of this unit size.

    async def async_set_low_flow(self, value: int) -> None:
        """Set the low (nominal) airflow, in m³/h."""
        check_range("low airflow", value, self.flow_limits.low)
        await self.settings.write("low_flow", value)

    async def async_set_high_flow(self, value: int) -> None:
        """Set the high (boost) airflow, in m³/h."""
        check_range("high airflow", value, self.flow_limits.high)
        await self.settings.write("high_flow", value)

    async def async_set_freecooling_flow(self, value: int) -> None:
        """Set the airflow while the bypass is open, in m³/h."""
        check_range("freecooling airflow", value, self.flow_limits.freecooling)
        await self.settings.write("freecooling_flow", value)

    # Humidity and air-quality regulation (DHU and SERENITE only).

    def level_unit(self, source: Source) -> str | None:
        """The unit of a source's thresholds: ``"%"``, ``"ppm"``, or ``None``."""
        sensor_type = self._source_type(source)
        if sensor_type is AirSensType.HUMIDITY:
            return "%"
        if sensor_type in (AirSensType.CO2, AirSensType.VOC):
            return "ppm"
        return None

    def level_limits(
        self, source: Source, which: Literal["minimum", "maximum"]
    ) -> tuple[int, int] | None:
        """The range a source's threshold accepts, or ``None`` if unknown."""
        sensor_type = self._source_type(source)
        index = 0 if which == "minimum" else 1
        if sensor_type is AirSensType.HUMIDITY:
            return _HUMIDITY_LEVELS[index]
        if sensor_type in (AirSensType.CO2, AirSensType.VOC):
            return _PPM_LEVELS[index]
        return None

    async def async_set_regulation_flow(
        self, source: Source, which: Literal["minimum", "maximum"], value: int
    ) -> None:
        """Set the airflow a source regulates down to, or up to, in m³/h."""
        limits = (
            self.flow_limits.low if which == "minimum" else self.flow_limits.maximum
        )
        check_range(f"{which} airflow", value, limits)
        await self._humidity_settings().write(f"{_prefix(source)}_{which}_flow", value)

    async def async_set_regulation_level(
        self, source: Source, which: Literal["minimum", "maximum"], value: int
    ) -> None:
        """Set the level, in %RH or ppm, a source regulates from or up to."""
        limits = self.level_limits(source, which)
        if limits is None:
            raise ValueError(f"no known sensor type for {source!r}")
        check_range(f"{which} level", value, limits)
        await self._humidity_settings().write(f"{_prefix(source)}_{which}_level", value)

    def _humidity_settings(self) -> HumiditySettings:
        """The humidity regulation, or raise if this unit has none."""
        if self.humidity_settings is None:
            raise ValueError(f"{self.name} has no humidity regulation")
        return self.humidity_settings

    def _source_type(self, source: Source) -> AirSensType | None:
        """The kind of sensor behind a source."""
        if source == "sensor":
            return AirSensType.HUMIDITY
        if self.probes is None:
            return None
        return self.probes.probe_type(source)


def _prefix(source: Source) -> str:
    """The field name prefix of a source."""
    if source == "sensor":
        return "sensor"
    _check_probe(source)
    return f"probe_{source}"
