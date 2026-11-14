"""Tests for the S&P DOMEO EVO integration."""

from copy import deepcopy
from typing import Any

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MODEL, CONF_PORT, CONF_TYPE

from custom_components.domeo_modbus.const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_UNIT_ID,
    CONF_VARIANT,
    TYPE_SERIAL,
    TYPE_TCP,
)
from custom_components.domeo_modbus.domeo_evo_modbus import AirSensType

from .register_images import FACTORY_225_FL

MOCK_ENTRY_ID = "01JDOMEOEVO225FL0000000000"
MOCK_TITLE = "DOMEO EVO 225 FL"

MOCK_TCP_INPUT = {
    CONF_HOST: "192.168.1.200",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
    CONF_MODEL: "225",
    CONF_VARIANT: "fl",
}
MOCK_TCP_DATA = {CONF_TYPE: TYPE_TCP, **MOCK_TCP_INPUT}

MOCK_SERIAL_INPUT = {
    CONF_DEVICE: "/dev/ttyUSB0",
    CONF_BAUDRATE: "19200",
    CONF_PARITY: "even",
    CONF_UNIT_ID: 1,
    CONF_MODEL: "225",
    CONF_VARIANT: "fl",
}
MOCK_SERIAL_DATA = {CONF_TYPE: TYPE_SERIAL, **MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}


def serenite_image() -> dict[str, dict[int, Any]]:
    """A SERENITE unit with CO2, humidity and VOC probes in slots 1, 3 and 5."""
    image = deepcopy(FACTORY_225_FL)
    image["discrete"][11] = False  # probe 1 connected
    image["discrete"][13] = False  # probe 3 connected
    image["discrete"][15] = False  # probe 5 connected
    image["discrete"][16] = False  # preheat battery connected
    image["input"][4] = 61  # integrated humidity sensor
    image["input"].update(
        {
            22: int(AirSensType.CO2),
            24: int(AirSensType.HUMIDITY),
            26: int(AirSensType.VOC),
            27: 645,
            29: 58,
            31: 420,
        }
    )
    # Probe 3 measures humidity, so its thresholds are in %RH.
    image["holding"][22] = [60, 1000, 1000, 65, 1000, 1000]
    image["holding"][28] = [90, 2000, 2000, 85, 2000, 2000]
    return image


MOCK_SERENITE_DATA = {**MOCK_TCP_DATA, CONF_VARIANT: "serenite"}

MOCK_210_TITLE = "Domeo 210"
MOCK_210_DATA = {**MOCK_TCP_DATA, CONF_MODEL: "210"}
