"""Register images of a DOMEO EVO and a Domeo 210, for tests without hardware.

Load one into ``modbus_connection.mock`` with ``load_image``. Addresses are
protocol (PDU) addresses: on a DOMEO EVO, the S&P table number minus its base,
minus one; on a Domeo 210, the table number as it is.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _signed(value: int) -> int:
    """A negative value as it appears on the wire."""
    return value & 0xFFFF


# A factory-fresh DOMEO EVO 225 FL.
FACTORY_225_FL: dict[str, dict[int, Any]] = {
    "input": {
        0: 123,  # 30001: firmware 12.3
        1: 105,  # 30002: panel firmware 10.5
        2: 1,  # 30003: proportional mode
        3: 90,  # 30004: 90 m³/h
        4: 54,  # 30005: no humidity sensor fitted
        5: 37,  # 30006: 3.7 V
        10: 215,  # 30011: extract 21.5 °C
        11: 98,  # 30012: exhaust 9.8 °C
        12: _signed(-35),  # 30013: outdoor -3.5 °C
        13: 187,  # 30014: supply 18.7 °C
        14: _signed(-20),  # 30015: pre-exchanger -2.0 °C
        16: 1,  # 30017: limit switch open
        17: 0,  # 30018: preheater stopped
        21: 1,  # 30022: wired panel
    },
    "discrete": {
        7: True,  # 10008: no pre-exchanger probe on this unit
        9: True,  # 10010: Modbus control (JP1 closed)
        11: True,  # 10012-10016: no AIRSENS probes
        12: True,
        13: True,
        14: True,
        15: True,
        16: True,  # 10017: no preheat battery
    },
    "coil": {
        3: False,  # coil 4: holiday mode off
        4: True,  # coil 5: automatic bypass on
    },
    "holding": {
        0: 1,  # 40001: unit id 1
        1: 8,  # 40002: 19200 baud
        2: 2,  # 40003: even parity
        6: 60,  # 40007: low airflow
        7: 120,  # 40008: high airflow
        8: 225,  # 40009: freecooling airflow
        38: 12,  # 40039
        39: 24,  # 40040
        40: 8,  # 40041
        41: 60,  # 40042
        44: 6,  # 40045
        45: 55,  # 40046: 5.5 °C
        46: 12,  # 40047: 1.2 V
        48: 5,  # 40049
        49: 1,  # 40050: preheat on
        52: _signed(-130),  # 40053: -13.0 °C
        53: 30,  # 40054
        # 40011-40034, humidity regulation defaults.
        10: [60, 60, 60, 60, 60, 60],
        16: [225, 225, 225, 225, 225, 225],
        22: [60, 1000, 1000, 1000, 1000, 1000],
        28: [90, 2000, 2000, 2000, 2000, 2000],
    },
}

# A factory-fresh Domeo 210 FL, France version, from the previous range (S&P
# tables of 2014 and 2017). It is not a DOMEO EVO. Its tables leave input
# registers 0 to 5 undocumented; this image assumes they read 0, so it can
# also stand for a Domeo 210 read at the DOMEO EVO addresses.
PREVIOUS_DOMEO_210_FL: dict[str, dict[int, Any]] = {
    "input": {
        **dict.fromkeys(range(6), 0),
        6: 123,  # firmware 12.3
        7: 105,  # 2014 table: control panel firmware 10.5
        8: 0,  # 2014 table: programming console firmware
        9: 0,  # 2014 table: type of unit, Domeo 210 FL
        10: 1,  # 2014 table: type of control, constant airflow
        12: 0,  # 2014 table: airflow unbalance
        13: 60,  # 2014 table: low airflow
        14: 135,  # 2014 table: boost airflow
        15: 210,  # 2014 table: freecooling airflow
        16: 60,  # current airflow (30017 on a DOMEO EVO)
        17: 0,  # 2014 table: 0-10 V input, mV
        19: 1450,  # 2014 table: extract fan, rpm
        20: 1520,  # 2014 table: supply fan, rpm
        21: 215,  # extract 21.5 °C (30022 on a DOMEO EVO)
        22: 98,  # exhaust 9.8 °C
        23: _signed(-35),  # outdoor -3.5 °C
        24: 187,  # supply 18.7 °C
        25: 0,  # bypass closed
        26: 0,  # pre-heating battery off
        27: 0,  # post-heating battery off
    },
    "discrete": dict.fromkeys(range(17), False),
    "coil": {
        **dict.fromkeys(range(15), False),
        8: True,  # automatic bypass on
    },
    "holding": {
        0: 1,  # unit id 1
        1: 8,  # 19200 baud
        2: 2,  # even parity
        8: 0,  # airflow unbalance
        9: 60,  # low airflow
        10: 135,  # boost airflow
        11: 210,  # freecooling airflow
        15: 0,  # airflow command: low
        16: 60,  # FL table: 0-10 V minimum airflow
        17: 210,  # FL table: 0-10 V maximum airflow
        22: 12,  # bypass: outdoor minimum
        23: 24,  # bypass: indoor minimum
        24: 8,  # manual bypass duration, h
        25: 0,
        26: 5,
        27: 4,
        28: 18,
        31: 6,  # filter interval, months
        32: 0,  # FL table: 0-10 V minimum voltage
        33: 100,  # FL table: 0-10 V maximum voltage
    },
}

# A factory-fresh Domeo 210 DHU, France version (S&P "Domeo humedad para
# Francia" table of 2017): the FL image without the FL-only registers, plus
# the humidity regulation.
PREVIOUS_DOMEO_210_DHU: dict[str, dict[int, Any]] = deepcopy(PREVIOUS_DOMEO_210_FL)
for _address in (16, 17, 32, 33):
    del PREVIOUS_DOMEO_210_DHU["holding"][_address]
PREVIOUS_DOMEO_210_DHU["holding"].update(
    {
        18: 60,  # humidity regulation: minimum airflow
        19: 210,  # humidity regulation: maximum airflow
        20: 60,  # humidity regulation: minimum level, %RH
        21: 90,  # humidity regulation: maximum level, %RH
    }
)

# Every address the 2017 table of each Domeo 210 variant documents, by space,
# plus the input registers only the 2014 table documents.
_DOCUMENTED_210_INPUTS = {*range(6, 11), *range(12, 18), 19, 20, *range(21, 28)}
DOCUMENTED_210: dict[str, set[int]] = {
    "input": _DOCUMENTED_210_INPUTS,
    "discrete": {5, 6, 7, *range(10, 15)},
    "coil": {1, 2, 3, 4, 6, 7, 8, 9, 12, 13, 14},
    "holding": {0, 1, 2, 8, 9, 10, 11, *range(15, 18), *range(22, 29), *range(31, 34)},
}
DOCUMENTED_210_DHU: dict[str, set[int]] = {
    "input": _DOCUMENTED_210_INPUTS,
    "discrete": {5, 6, 7, *range(10, 15)},
    "coil": {2, 3, 4, 6, 7, 8, 9, 12, 13, 14},
    "holding": {0, 1, 2, 8, 9, 10, 11, 15, *range(18, 29), 31},
}

# Every address the S&P table documents, by space.
DOCUMENTED: dict[str, set[int]] = {
    "input": {*range(0, 6), *range(10, 15), 16, 17, *range(21, 32)},
    "discrete": set(range(0, 17)),
    "coil": set(range(0, 9)),
    "holding": {*range(0, 3), *range(4, 34), *range(38, 42), *range(44, 54)},
}


def load_image(unit: Any, image: dict[str, dict[int, Any]] = FACTORY_225_FL) -> None:
    """Seed a ``MockModbusUnit`` with a copy of a register image."""
    for space, values in deepcopy(image).items():
        getattr(unit, space).update(values)
