"""The Domeo 210, from the S&P (Unelvent) range before the DOMEO EVO.

Two S&P tables of 24 October 2017 describe it, one per variant:

- FL: "PARÁMETROS MODBUS RECUPERADOR DOMEO 210 velocidad constante".
- DHU (humidity detection, France): "PARÁMETROS MODBUS RECUPERADOR DOMEO
  HUMEDAD PARA FRANCIA". It gives each register's number next to its Modbus
  address (number + 1), so the numbers are the protocol (PDU) addresses.

They share nothing with the DOMEO EVO's table: the same addresses hold other
values (chpego/ha-domeo-modbus#7). Only the registers both tables document are
read, plus the humidity regulation of the DHU. A Domeo 210 YAML in use since
2021 reads them at those addresses (HACF topic 3947).

The older table of the same board ("DOMEO - FLEXEO - IDEO 450", 2014) documents
a few more input registers, which only this unit's extras read. Where it
disagrees with both 2017 tables (input registers 22 and 23 swapped, coils 7, 8
and 12 on at 0), the 2017 tables and the YAML in use since 2021 are followed.
Still unconfirmed on a real unit (chpego/ha-domeo-modbus#15).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import IntEnum
from typing import TYPE_CHECKING

from modbus_connection import IllegalDataAddressError, IllegalFunctionError
from modbus_connection.model import (
    Component,
    Device,
    Raw,
    UpdateReport,
    coil,
    discrete_input,
    enum,
    gauge,
    integer,
    read_optional,
)

from .enums import ClpContact, Variant
from .limits import FlowLimits, check_range, int_range
from .readings import _version
from .settings import BAUDRATES, PARITIES

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

# What each update method reads, by attribute name.
READINGS_210 = ("readings", "status", "controls", "extras")
SETTINGS_210 = ("settings", "humidity_settings")
ALL_210 = ("identity", *READINGS_210, *SETTINGS_210)

# Quiet time around each request, for the RS485 turnaround behind a gateway.
MESSAGE_SPACING = 0.05

# Holding 9 to 11, by variant. The DHU table also bounds its humidity
# regulation airflows (holding 18 and 19) to 60-210.
FLOW_LIMITS_210: dict[Variant, FlowLimits] = {
    Variant.FL: FlowLimits(
        low=(60, 150), high=(120, 210), freecooling=(120, 210), maximum=(120, 210)
    ),
    Variant.DHU: FlowLimits(
        low=(60, 210), high=(60, 210), freecooling=(60, 210), maximum=(60, 210)
    ),
}
# Every airflow either variant accepts.
_ANY_FLOW = int_range(60, 210)

# The highest airflow the unit can report, in m³/h (input 16: 0-210 in the FL
# table, 0-500 in the DHU table).
_MAX_AIRFLOW = 500

# Holding 18 to 21 (DHU): how far apart the minimum and maximum must stay.
_HUMIDITY_FLOW_GAP = 5  # m³/h
_HUMIDITY_LEVEL_GAP = 10  # %RH
_HUMIDITY_LEVELS = (60, 90)  # %RH
# The highest firmware version the table documents (xx.x, times ten).
_MAX_FIRMWARE = 999

# Holding 15 in the France version: writing 1 runs the boost airflow for
# 30 minutes, then the unit returns to its low airflow on its own.
BOOST_START = 1


class NotADomeo210Error(Exception):
    """The device answers Modbus, but not like a Domeo 210."""


class Domeo210Version(IntEnum):
    """Coil 6: what the holiday coil and the airflow command do."""

    FRANCE = 0
    """Boost and holiday mode."""

    EUROPE = 1
    """Three speeds and standby (the German version)."""


class BypassState(IntEnum):
    """Input register 25: the bypass."""

    CLOSED = 0
    OPEN = 1
    ERROR = 2


class HeaterState(IntEnum):
    """Input registers 26 and 27: an optional heating battery."""

    OFF = 0
    ON = 1
    PROBE_1_ERROR = 2
    PROBE_2_ERROR = 3
    TRIAC_ERROR = 4
    THERMAL_PROTECTION = 5


class DefrostType(IntEnum):
    """Coil 14: how the unit protects its exchanger from frost."""

    DIBT = 0
    PASSIVHAUS = 1


class Identity210(Component):
    """The firmware version, read once at setup."""

    register_space = "input"
    register_ranges = ((6, 6),)

    _unit_firmware = integer(6, signed=False)

    @property
    def unit_firmware(self) -> str | None:
        """The firmware version of the unit's main board."""
        return _version(self._unit_firmware)

    @property
    def panel_firmware(self) -> str | None:
        """The 2017 table has no control panel firmware."""
        return None


class Readings210(Component):
    """The current airflow, the four temperatures and the bypass state."""

    register_space = "input"
    register_ranges = ((16, 16), (21, 27))

    airflow = integer(16, signed=False, unit="m³/h")
    """The current airflow."""

    extract_temperature = gauge(21, 0.1, unit="°C")
    """The air extracted from the dwelling."""

    exhaust_temperature = gauge(22, 0.1, unit="°C")
    """The air rejected outside."""

    outdoor_temperature = gauge(23, 0.1, unit="°C")
    """The fresh air taken in from outside."""

    supply_temperature = gauge(24, 0.1, unit="°C")
    """The air blown into the dwelling."""

    bypass_state = enum(25, BypassState)
    """Whether the bypass is open."""

    preheater_state = enum(26, HeaterState)
    """The optional pre-heating battery."""

    postheater_state = enum(27, HeaterState)
    """The optional post-heating battery."""


class Extras210(Component):
    """Input registers only the 2014 table documents, read when the unit has them.

    The 2017 table leaves them out, so the unit may refuse them.
    """

    register_space = "input"
    register_ranges = ((7, 10), (12, 17), (19, 20))

    _panel_firmware = integer(7, signed=False)
    _console_firmware = integer(8, signed=False)
    _unit_type = integer(9, signed=False)  # 0 = Domeo 210 FL
    _control_type = integer(10, signed=False)
    _flow_unbalance = integer(12)
    _low_flow = integer(13, signed=False)
    _boost_flow = integer(14, signed=False)
    _freecooling_flow = integer(15, signed=False)
    _current_flow = integer(16, signed=False)
    _voltage_input = integer(17, signed=False)  # mV

    extract_motor_speed = integer(19, signed=False, unit="rpm")
    """The speed of the extract fan."""

    supply_motor_speed = integer(20, signed=False, unit="rpm")
    """The speed of the supply fan."""


class Status210(Component):
    """Alarms and faults, from the discrete inputs (FC02)."""

    discrete_ranges = ((5, 7), (10, 14))

    defrost_active = discrete_input(5)
    """Whether the unit is defrosting."""

    extract_motor_fault = discrete_input(6)
    supply_motor_fault = discrete_input(7)

    extract_probe_fault = discrete_input(10)
    exhaust_probe_fault = discrete_input(11)
    outdoor_probe_fault = discrete_input(12)
    supply_probe_fault = discrete_input(13)

    filter_alarm = discrete_input(14)
    """Whether the filters are due for replacement."""


class _Commands210(Component):
    """The write-only coils. They are never read.

    Coil 13 (restore the factory settings) is deliberately not modelled.
    """

    coil_ranges = ((12, 12),)

    _filter_reset = coil(12, writable=True)


class Controls210(Component):
    """Holiday mode and the bypass, from the coils (FC01 / FC05).

    The coils that describe the installation (2 to 4, 6 and 14) are read but
    never written. Coil 1 (air quality sensor) is in the FL table only, so it
    is not read.
    """

    coil_ranges = ((2, 4), (6, 9), (14, 14))

    preheater_installed = coil(2)
    postheater_installed = coil(3)
    _clp_contact = coil(4)
    _version = coil(6)
    _holiday_mode = coil(7, writable=True)
    _auto_bypass = coil(8, writable=True)
    _manual_bypass = coil(9, writable=True)
    _defrost_type = coil(14)

    def __init__(self, unit: ModbusUnit) -> None:
        super().__init__(unit)
        self._commands = _Commands210(unit)

    @property
    def version(self) -> Domeo210Version | None:
        """Whether this is the France (boost) or Europe (speeds) version."""
        raw = self._version
        return None if raw is None else Domeo210Version(int(raw))

    @property
    def clp_contact(self) -> ClpContact | None:
        """The wiring of the external contact."""
        raw = self._clp_contact
        return None if raw is None else ClpContact(int(raw))

    @property
    def defrost_type(self) -> DefrostType | None:
        """How the unit protects its exchanger from frost."""
        raw = self._defrost_type
        return None if raw is None else DefrostType(int(raw))

    @property
    def holiday_mode(self) -> bool | None:
        """Whether holiday mode is on (standby in the Europe version)."""
        return self._holiday_mode

    @property
    def auto_bypass(self) -> bool | None:
        """Whether the bypass opens automatically."""
        return self._auto_bypass

    @property
    def manual_bypass(self) -> bool | None:
        """Whether the bypass is forced open."""
        return self._manual_bypass

    async def async_set_holiday_mode(self, on: bool) -> None:
        """Turn holiday mode (standby in the Europe version) on or off."""
        await self.write("_holiday_mode", bool(on))

    async def async_set_auto_bypass(self, on: bool) -> None:
        """Let the bypass open automatically, or not."""
        await self.write("_auto_bypass", bool(on))

    async def async_set_manual_bypass(self, on: bool) -> None:
        """Force the bypass open, or release it."""
        await self.write("_manual_bypass", bool(on))

    async def async_reset_filter_alarm(self) -> None:
        """Acknowledge the filter alarm and restart its countdown."""
        await self._commands.write("_filter_reset", True)


class Settings210(Component):
    """Airflows, bypass thresholds and the filter interval (FC03 / FC06).

    Holding 0 to 2 set the unit's own Modbus address, speed and parity. They
    are read so a diagnostics dump shows them, but they are never writable.
    The heating battery settings are read for diagnostics only. The 0-10 V
    settings (holding 16, 17, 32 and 33) are in the FL table only: not read.
    The airflows accept the range of either variant; the device narrows a
    write to the range of its own.
    """

    register_ranges = ((0, 2), (8, 11), (15, 15), (22, 28), (31, 31))

    _modbus_address = integer(0, signed=False)
    _modbus_baudrate = integer(1, signed=False)
    _modbus_parity = integer(2, signed=False)

    flow_unbalance = integer(8, writable=int_range(-15, 15), unit="%")
    """How much the supply airflow differs from the extract airflow."""

    low_flow = integer(9, signed=False, writable=_ANY_FLOW, unit="m³/h")
    """The low (nominal) airflow."""

    high_flow = integer(10, signed=False, writable=_ANY_FLOW, unit="m³/h")
    """The boost airflow."""

    freecooling_flow = integer(11, signed=False, writable=_ANY_FLOW, unit="m³/h")
    """The airflow while the bypass is open."""

    _flow_command = integer(
        15, signed=False, writable=int_range(BOOST_START, BOOST_START)
    )

    bypass_outdoor_minimum = integer(22, writable=int_range(11, 20), unit="°C")
    """The outdoor temperature below which the automatic bypass stays shut."""

    bypass_indoor_minimum = integer(23, writable=int_range(21, 30), unit="°C")
    """The indoor temperature above which the automatic bypass may open."""

    manual_bypass_duration = integer(
        24, signed=False, writable=int_range(1, 24), unit="h"
    )
    """How long a manual bypass stays open."""

    _preheater_on = integer(25)
    _preheater_off = integer(26)
    _preheater_setpoint = integer(27)
    _postheater_setpoint = integer(28)

    filter_interval = integer(31, signed=False, writable=int_range(1, 24), unit="month")
    """How often the filter alarm comes back."""

    @property
    def modbus_address(self) -> int | None:
        """The unit's own Modbus address."""
        return self._modbus_address

    @property
    def modbus_baudrate(self) -> int | None:
        """The unit's line speed, in baud."""
        raw = self._modbus_baudrate
        return None if raw is None else BAUDRATES.get(raw)

    @property
    def modbus_parity(self) -> str | None:
        """The unit's parity: ``"N"``, ``"O"`` or ``"E"``."""
        raw = self._modbus_parity
        return None if raw is None else PARITIES.get(raw)

    async def async_start_boost(self) -> None:
        """Run the boost airflow for 30 minutes (France version only)."""
        await self.write("_flow_command", BOOST_START)


class HumiditySettings210(Component):
    """The humidity regulation of the DHU variant (holding 18 to 21).

    The unit raises its airflow from the minimum to the maximum as the
    humidity it measures rises from the minimum to the maximum level.
    """

    register_ranges = ((18, 21),)

    minimum_flow = integer(18, signed=False, writable=_ANY_FLOW, unit="m³/h")
    maximum_flow = integer(19, signed=False, writable=_ANY_FLOW, unit="m³/h")
    minimum_level = integer(
        20, signed=False, writable=int_range(*_HUMIDITY_LEVELS), unit="%"
    )
    maximum_level = integer(
        21, signed=False, writable=int_range(*_HUMIDITY_LEVELS), unit="%"
    )


class Domeo210(Device):
    """A Domeo 210 heat recovery ventilation unit, from the previous range.

    The unit does not report its variant, so the caller states it: FL, or DHU
    (humidity detection). It sets the airflow ranges a write accepts and
    whether the humidity regulation is read.
    """

    readings_components = READINGS_210
    settings_components = SETTINGS_210

    def __init__(self, unit: ModbusUnit, variant: Variant = Variant.FL) -> None:
        variant = Variant(variant)
        if variant not in FLOW_LIMITS_210:
            raise ValueError(f"the Domeo 210 has no {variant.name} variant")
        super().__init__(unit)
        unit.set_message_spacing(MESSAGE_SPACING)
        self.variant = variant

        self.identity = Identity210(unit)
        self.readings = Readings210(unit)
        self.status = Status210(unit)
        self.controls = Controls210(unit)
        self.settings = Settings210(unit)

        # Settled at setup: only present when the unit serves them.
        self.extras: Extras210 | None = None
        self.humidity_settings: HumiditySettings210 | None = None

    @property
    def name(self) -> str:
        """The commercial name of the unit."""
        return f"Domeo 210 {self.variant.name}"

    @property
    def flow_limits(self) -> FlowLimits:
        """The airflow ranges this variant accepts."""
        return FLOW_LIMITS_210[self.variant]

    @property
    def regulates_humidity(self) -> bool:
        """Whether this variant regulates on humidity."""
        return self.variant is Variant.DHU

    @property
    def has_boost(self) -> bool:
        """Whether the airflow command starts a boost (France version)."""
        return self.controls.version is not Domeo210Version.EUROPE

    async def _async_setup(self) -> None:
        """Read the firmware and the version, and settle the extras."""
        await self.identity.async_update(notify=False)
        await self.controls.async_update(notify=False)
        self.extras = await read_optional(Extras210(self.modbus_unit))
        if self.regulates_humidity:
            self.humidity_settings = await read_optional(
                HumiditySettings210(self.modbus_unit)
            )

    async def async_validate(self) -> None:
        """Check the unit answers like a Domeo 210, or raise.

        Raises ``NotADomeo210Error`` when the values make no sense for this
        unit, and ``ModbusError`` when the unit cannot be read.
        """
        try:
            await self.async_ensure_setup()
            await self.readings.async_update(notify=False)
            await self.settings.async_update(notify=False)
        except (IllegalDataAddressError, IllegalFunctionError) as err:
            # A DOMEO EVO refuses input register 6, undocumented on its table.
            raise NotADomeo210Error(f"refused a documented register: {err}") from err
        firmware = self.identity._unit_firmware
        if firmware is None or firmware > _MAX_FIRMWARE:
            raise NotADomeo210Error(f"unexpected firmware version {firmware!r}")
        airflow = self.readings.airflow
        if airflow is None or airflow > _MAX_AIRFLOW:
            raise NotADomeo210Error(f"unexpected airflow {airflow!r}")
        # On a DOMEO EVO, holding 9 is the boost command (0 or 1), well below
        # any low airflow.
        # The union of both variants' ranges is checked, so a unit added with
        # the wrong variant is not mistaken for another device.
        settings = self.settings
        for name, value in (
            ("low airflow", settings.low_flow),
            ("boost airflow", settings.high_flow),
            ("freecooling airflow", settings.freecooling_flow),
        ):
            limits = FLOW_LIMITS_210[Variant.DHU].low
            if value is None or not limits[0] <= value <= limits[1]:
                raise NotADomeo210Error(f"unexpected {name} {value!r}")
        # The temperatures are not checked: a faulty or missing probe may read
        # anything, and the airflows already tell a DOMEO EVO apart.

    async def async_update_readings(self) -> UpdateReport:
        """Refresh what the unit measures and the state of its switches."""
        return await self.async_poll(READINGS_210)

    async def async_update_settings(self) -> UpdateReport:
        """Refresh the unit's configuration."""
        return await self.async_poll(SETTINGS_210)

    async def async_update(self) -> UpdateReport:
        """Refresh everything."""
        report = await self.async_poll(READINGS_210)
        return await self.async_poll(SETTINGS_210, report)

    async def async_read_raw(self, names: Iterable[str] = ALL_210) -> Raw:
        """Every register this unit reads, undecoded, for diagnostics."""
        return await super().async_read_raw(names)

    async def async_start_boost(self) -> None:
        """Run the boost airflow for 30 minutes, then return to low airflow.

        Raises ``ValueError`` on the Europe version, where the same register
        picks one of three speeds instead.
        """
        if not self.has_boost:
            raise ValueError("the Europe version of the Domeo 210 has no boost")
        await self.settings.async_start_boost()

    async def async_set_low_flow(self, value: int) -> None:
        """Set the low (nominal) airflow, in m³/h."""
        check_range("low airflow", value, self.flow_limits.low)
        await self.settings.write("low_flow", value)

    async def async_set_high_flow(self, value: int) -> None:
        """Set the boost airflow, in m³/h."""
        check_range("boost airflow", value, self.flow_limits.high)
        await self.settings.write("high_flow", value)

    async def async_set_freecooling_flow(self, value: int) -> None:
        """Set the airflow while the bypass is open, in m³/h."""
        check_range("freecooling airflow", value, self.flow_limits.freecooling)
        await self.settings.write("freecooling_flow", value)

    # Humidity regulation (DHU only).

    def humidity_limits(self, field: str) -> tuple[int, int]:
        """The range a humidity regulation setting accepts now.

        The table keeps the minimum airflow 5 m³/h below the maximum, and the
        minimum level 10 %RH below the maximum, so each bound depends on the
        other one's current value.
        """
        settings = self._humidity_settings()
        low_flow, high_flow = self.flow_limits.maximum
        low_level, high_level = _HUMIDITY_LEVELS
        if field == "minimum_flow":
            top = settings.maximum_flow
            return low_flow, high_flow if top is None else top - _HUMIDITY_FLOW_GAP
        if field == "maximum_flow":
            bottom = settings.minimum_flow
            return (
                low_flow if bottom is None else bottom + _HUMIDITY_FLOW_GAP,
                high_flow,
            )
        if field == "minimum_level":
            top = settings.maximum_level
            return low_level, high_level if top is None else top - _HUMIDITY_LEVEL_GAP
        if field == "maximum_level":
            bottom = settings.minimum_level
            return (
                low_level if bottom is None else bottom + _HUMIDITY_LEVEL_GAP,
                high_level,
            )
        raise ValueError(f"unknown humidity regulation setting {field!r}")

    async def async_set_humidity_setting(self, field: str, value: int) -> None:
        """Set one of the four humidity regulation settings."""
        check_range(field.replace("_", " "), value, self.humidity_limits(field))
        await self._humidity_settings().write(field, value)

    def _humidity_settings(self) -> HumiditySettings210:
        """The humidity regulation, or raise if this unit has none."""
        if self.humidity_settings is None:
            raise ValueError(f"{self.name} has no humidity regulation")
        return self.humidity_settings
