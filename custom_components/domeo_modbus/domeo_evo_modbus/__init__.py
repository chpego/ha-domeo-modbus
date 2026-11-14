"""Read and control S&P DOMEO EVO ventilation units over Modbus."""

from typing import Final, Literal

from modbus_connection.model import UpdateReport

from .controls import Controls
from .device import ALL, READINGS, SETTINGS, DomeoEvo, NotADomeoEvoError, Source
from .domeo210 import (
    FLOW_LIMITS_210,
    BypassState,
    DefrostType,
    Domeo210,
    Domeo210Version,
    HeaterState,
    HumiditySettings210,
    NotADomeo210Error,
)
from .enums import (
    AirSensType,
    AutoMode,
    ClpContact,
    ControlPanel,
    EquipmentVersion,
    LimitSwitchState,
    Model,
    OperatingMode,
    PreheaterState,
    PreheatMode,
    Variant,
)
from .limits import FLOW_LIMITS, FlowLimits
from .readings import PROBES, AirSensProbes, Identity, Readings
from .settings import HumiditySettings, Settings
from .status import Status

# The unit's factory line settings: 19200 baud, 8 data bits, even parity,
# 1 stop bit (holding 40002 and 40003).
DEFAULT_BAUDRATE: Final = 19200
DEFAULT_PARITY: Final[Literal["E"]] = "E"
DEFAULT_STOPBITS: Final[Literal[1]] = 1
DEFAULT_UNIT_ID: Final = 1

# Either range of unit.
type AnyDomeo = DomeoEvo | Domeo210

__all__ = [
    "ALL",
    "DEFAULT_BAUDRATE",
    "DEFAULT_PARITY",
    "DEFAULT_STOPBITS",
    "DEFAULT_UNIT_ID",
    "FLOW_LIMITS",
    "FLOW_LIMITS_210",
    "PROBES",
    "READINGS",
    "SETTINGS",
    "AirSensProbes",
    "AirSensType",
    "AnyDomeo",
    "AutoMode",
    "BypassState",
    "ClpContact",
    "ControlPanel",
    "Controls",
    "DefrostType",
    "Domeo210",
    "Domeo210Version",
    "DomeoEvo",
    "EquipmentVersion",
    "FlowLimits",
    "HeaterState",
    "HumiditySettings",
    "HumiditySettings210",
    "Identity",
    "LimitSwitchState",
    "Model",
    "NotADomeo210Error",
    "NotADomeoEvoError",
    "OperatingMode",
    "PreheatMode",
    "PreheaterState",
    "Readings",
    "Settings",
    "Source",
    "Status",
    "UpdateReport",
    "Variant",
]
