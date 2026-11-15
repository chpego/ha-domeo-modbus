"""Helpers for the S&P DOMEO EVO integration."""

from collections.abc import Mapping
from typing import Any

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MODEL, CONF_PORT, CONF_TYPE
from modbus_connection import ModbusSerialParams, ModbusTcpParams, ModbusUnit

from .const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_VARIANT,
    MODEL_DOMEO_210,
    PARITIES,
    TYPE_SERIAL,
)
from .domeo_evo_modbus import (
    DEFAULT_STOPBITS,
    AnyDomeo,
    Domeo210,
    DomeoEvo,
    Model,
    Variant,
)


def create_device(unit: ModbusUnit, data: Mapping[str, Any]) -> AnyDomeo:
    """The device object for the model in config entry data."""
    if data[CONF_MODEL] == MODEL_DOMEO_210:
        return Domeo210(unit, Variant(data[CONF_VARIANT]))
    return DomeoEvo(unit, Model(data[CONF_MODEL]), Variant(data[CONF_VARIANT]))


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=data[CONF_BAUDRATE],
            parity=PARITIES[data[CONF_PARITY]],
            stopbits=DEFAULT_STOPBITS,
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
