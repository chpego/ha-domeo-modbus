"""The unit's configuration, from its holding registers (FC03 / FC06).

The S&P table numbers holding registers from 40001, so table register
``40000 + n`` is address ``n - 1``.

Holding 40001 to 40003 set the unit's own Modbus address, speed and parity.
They are read so a diagnostics dump shows them, but they are never writable:
one wrong value there cuts the link at the next power cycle.
"""

from __future__ import annotations

from modbus_connection.model import Component, enum, gauge, integer

from .enums import PreheatMode
from .limits import int_range

# Holding 40002: the line speed codes, in baud.
BAUDRATES = {5: 4800, 6: 9600, 8: 19200, 10: 38400}
# Holding 40003: the parity codes, as ModbusSerialParams spells them.
PARITIES = {0: "N", 1: "O", 2: "E"}

# Holding 40010 is a push button: writing 1 starts the boost, and the unit
# returns to its normal airflow on its own after 30 minutes. The table says
# writing 0 stops it early, but a real unit ignores it (FC06 or FC16), and
# S&P support confirmed a boost cannot be stopped over Modbus
# (chpego/ha-domeo-modbus#6).
BOOST_START = 1

# The union of the airflow ranges of every unit size. The device object
# narrows a write to the range of the configured size.
_ANY_FLOW = int_range(60, 395)
# %RH for a humidity sensor, ppm for a CO2 or VOC probe.
_ANY_LEVEL = int_range(60, 2000)


class Settings(Component):
    """Airflows, bypass thresholds, filter interval and defrost settings."""

    # The table documents only these addresses. Reads never cross the holes.
    register_ranges = ((0, 2), (4, 9), (38, 41), (44, 53))

    _modbus_address = integer(0, signed=False)  # 40001, never written
    _modbus_baudrate = integer(1, signed=False)  # 40002, never written
    _modbus_parity = integer(2, signed=False)  # 40003, never written

    flow_correction = integer(4, writable=int_range(-15, 15), unit="m³/h")  # 40005
    """A fixed correction added to every airflow."""

    flow_offset = integer(5, writable=int_range(-15, 15), unit="%")  # 40006
    """A relative offset applied to every airflow."""

    low_flow = integer(6, signed=False, writable=_ANY_FLOW, unit="m³/h")  # 40007
    """The low (nominal) airflow."""

    high_flow = integer(7, signed=False, writable=_ANY_FLOW, unit="m³/h")  # 40008
    """The high (boost) airflow."""

    freecooling_flow = integer(  # 40009
        8, signed=False, writable=_ANY_FLOW, unit="m³/h"
    )
    """The airflow while the bypass is open."""

    _flow_command = integer(  # 40010
        9, signed=False, writable=int_range(BOOST_START, BOOST_START)
    )

    bypass_outdoor_minimum = integer(  # 40039, T21
        38, writable=int_range(11, 20), unit="°C"
    )
    """The outdoor temperature below which the automatic bypass stays shut."""

    bypass_indoor_minimum = integer(  # 40040, T11
        39, writable=int_range(21, 30), unit="°C"
    )
    """The indoor temperature above which the automatic bypass may open."""

    manual_bypass_duration = integer(  # 40041
        40, signed=False, writable=int_range(1, 24), unit="h"
    )
    """How long a manual bypass stays open."""

    bypass_error_delay = integer(41, signed=False, unit="s")  # 40042
    """How long the bypass may take to move before the unit flags an error."""

    filter_interval = integer(  # 40045
        44, signed=False, writable=int_range(1, 24), unit="month"
    )
    """How often the filter alarm comes back."""

    defrost_temperature_limit = gauge(45, 0.1, unit="°C")  # 40046, in d°C
    defrost_flow = gauge(46, 0.1, signed=False, unit="V")  # 40047, in dV
    pre_defrost_time = integer(47, signed=False, unit="min")  # 40048
    warm_up_time = integer(48, signed=False, unit="min")  # 40049
    preheat_mode = enum(49, PreheatMode)  # 40050
    preheat_manual_level = integer(50, signed=False, unit="%")  # 40051
    preheat_exchanger_minimum = gauge(51, 0.1, unit="°C")  # 40052, in d°C
    preheat_minimum = gauge(52, 0.1, unit="°C")  # 40053, in d°C
    preheat_delay = integer(53, signed=False, unit="min")  # 40054

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
        """Run at high airflow for a while (the unit stops on its own)."""
        await self.write("_flow_command", BOOST_START)


class HumiditySettings(Component):
    """The humidity and air-quality regulation of the DHU and SERENITE variants.

    Each value exists for the integrated humidity sensor and for each of the
    five AIRSENS probe slots. A probe's thresholds are in %RH or ppm,
    depending on the type of probe in that slot.
    """

    register_ranges = ((10, 33),)

    sensor_minimum_flow = integer(10, signed=False, writable=_ANY_FLOW)  # 40011
    probe_1_minimum_flow = integer(11, signed=False, writable=_ANY_FLOW)  # 40012
    probe_2_minimum_flow = integer(12, signed=False, writable=_ANY_FLOW)  # 40013
    probe_3_minimum_flow = integer(13, signed=False, writable=_ANY_FLOW)  # 40014
    probe_4_minimum_flow = integer(14, signed=False, writable=_ANY_FLOW)  # 40015
    probe_5_minimum_flow = integer(15, signed=False, writable=_ANY_FLOW)  # 40016

    sensor_maximum_flow = integer(16, signed=False, writable=_ANY_FLOW)  # 40017
    probe_1_maximum_flow = integer(17, signed=False, writable=_ANY_FLOW)  # 40018
    probe_2_maximum_flow = integer(18, signed=False, writable=_ANY_FLOW)  # 40019
    probe_3_maximum_flow = integer(19, signed=False, writable=_ANY_FLOW)  # 40020
    probe_4_maximum_flow = integer(20, signed=False, writable=_ANY_FLOW)  # 40021
    probe_5_maximum_flow = integer(21, signed=False, writable=_ANY_FLOW)  # 40022

    sensor_minimum_level = integer(22, signed=False, writable=_ANY_LEVEL)  # 40023
    probe_1_minimum_level = integer(23, signed=False, writable=_ANY_LEVEL)  # 40024
    probe_2_minimum_level = integer(24, signed=False, writable=_ANY_LEVEL)  # 40025
    probe_3_minimum_level = integer(25, signed=False, writable=_ANY_LEVEL)  # 40026
    probe_4_minimum_level = integer(26, signed=False, writable=_ANY_LEVEL)  # 40027
    probe_5_minimum_level = integer(27, signed=False, writable=_ANY_LEVEL)  # 40028

    sensor_maximum_level = integer(28, signed=False, writable=_ANY_LEVEL)  # 40029
    probe_1_maximum_level = integer(29, signed=False, writable=_ANY_LEVEL)  # 40030
    probe_2_maximum_level = integer(30, signed=False, writable=_ANY_LEVEL)  # 40031
    probe_3_maximum_level = integer(31, signed=False, writable=_ANY_LEVEL)  # 40032
    probe_4_maximum_level = integer(32, signed=False, writable=_ANY_LEVEL)  # 40033
    probe_5_maximum_level = integer(33, signed=False, writable=_ANY_LEVEL)  # 40034
