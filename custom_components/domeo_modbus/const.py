"""Constants for the S&P DOMEO EVO integration."""

from datetime import timedelta
from typing import Literal

DOMAIN = "domeo_modbus"
MANUFACTURER = "S&P"

CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"
CONF_UNIT_ID = "unit_id"
CONF_VARIANT = "variant"

# The model option of the previous range, next to the DOMEO EVO sizes.
MODEL_DOMEO_210 = "210"

PARITY_EVEN = "even"
# The serial parity choices, as ModbusSerialParams spells them.
PARITIES: dict[str, Literal["E", "O", "N"]] = {"even": "E", "odd": "O", "none": "N"}

TYPE_SERIAL = "serial"
TYPE_TCP = "tcp"

DEFAULT_PORT = 502

READINGS_INTERVAL = timedelta(seconds=30)
SETTINGS_INTERVAL = timedelta(minutes=5)

# A gateway that keeps its socket open while the unit behind it is silent
# needs a fresh link after this many polls in a row time out.
TIMEOUTS_BEFORE_RECONNECT = 3
