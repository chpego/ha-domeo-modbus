"""Config flow for the S&P DOMEO EVO integration (and the Domeo 210)."""

from collections.abc import Mapping
import logging
from typing import Any, override

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MODEL, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
    TextSelector,
)
from modbus_connection import ModbusError, ModbusTimeoutError
import probatio

from .const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_UNIT_ID,
    CONF_VARIANT,
    DEFAULT_PORT,
    DOMAIN,
    MODEL_DOMEO_210,
    PARITIES,
    PARITY_EVEN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .domeo_evo_modbus import (
    DEFAULT_BAUDRATE,
    DEFAULT_UNIT_ID,
    AnyDomeo,
    Model,
    NotADomeo210Error,
    NotADomeoEvoError,
    Variant,
)
from .helpers import create_device, create_modbus_params

_LOGGER = logging.getLogger(__name__)

STEP_RECONFIGURE_SERIAL = "reconfigure_serial"
STEP_RECONFIGURE_TCP = "reconfigure_tcp"

BAUDRATES = ["4800", "9600", "19200", "38400"]
PARITY_OPTIONS = list(PARITIES)

UNIT_ID_SELECTOR = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)),
    probatio.Coerce(int),
)

DEVICE_FIELDS = {
    probatio.Required(CONF_MODEL, default=Model.DOMEO_EVO_225.value): SelectSelector(
        SelectSelectorConfig(
            options=[*(model.value for model in Model), MODEL_DOMEO_210],
            translation_key=CONF_MODEL,
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
    probatio.Required(CONF_VARIANT, default=Variant.FL.value): SelectSelector(
        SelectSelectorConfig(
            options=[variant.value for variant in Variant],
            translation_key=CONF_VARIANT,
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
}

STEP_TCP_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
        **DEVICE_FIELDS,
    }
)

STEP_SERIAL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default=str(DEFAULT_BAUDRATE)): probatio.All(
            SelectSelector(
                SelectSelectorConfig(
                    options=BAUDRATES, mode=SelectSelectorMode.DROPDOWN
                )
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_PARITY, default=PARITY_EVEN): SelectSelector(
            SelectSelectorConfig(
                options=PARITY_OPTIONS,
                translation_key=CONF_PARITY,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
        **DEVICE_FIELDS,
    }
)

# The link settings that identify one unit, by connection type.
IDENTITY_KEYS = {
    TYPE_TCP: (CONF_TYPE, CONF_HOST, CONF_PORT, CONF_UNIT_ID),
    TYPE_SERIAL: (CONF_TYPE, CONF_DEVICE, CONF_UNIT_ID),
}


class _VariantNotAvailableError(Exception):
    """The chosen model has no such variant."""


class _UnitSilentError(Exception):
    """The link is up, but the unit behind it does not answer."""


def _is_210(data: Mapping[str, Any]) -> bool:
    """Whether config entry data describes a Domeo 210."""
    return bool(data[CONF_MODEL] == MODEL_DOMEO_210)


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> AnyDomeo:
    """Read the unit behind these link settings, or raise."""
    params = create_modbus_params(data)
    if _is_210(data) and data[CONF_VARIANT] == Variant.SERENITE:
        raise _VariantNotAvailableError
    async with async_get_temporary_unit(hass, params, data[CONF_UNIT_ID]) as unit:
        device = create_device(unit, data)
        try:
            await device.async_validate()
        except ModbusTimeoutError as err:
            if unit.connected:
                raise _UnitSilentError from err
            raise
    return device


# What the form shows for each known way a probe fails, first match wins.
_PROBE_ERRORS: tuple[tuple[type[Exception], str], ...] = (
    (_VariantNotAvailableError, "variant_not_available"),
    (_UnitSilentError, "unit_silent"),
    (NotADomeoEvoError, "not_a_domeo_evo"),
    (NotADomeo210Error, "not_a_domeo_210"),
    (ModbusError, "cannot_connect"),
    (HomeAssistantError, "cannot_connect"),
)


def _same_unit(data: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    """Whether two sets of link settings reach the same unit."""
    keys = IDENTITY_KEYS[data[CONF_TYPE]]
    return all(data.get(key) == other.get(key) for key in keys)


class DomeoEvoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the S&P DOMEO EVO."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the unit is reached."""
        return self.async_show_menu(
            step_id="user", menu_options=[TYPE_TCP, TYPE_SERIAL]
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a unit behind a Modbus TCP gateway."""
        return await self._async_step_link(TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a unit on a serial port."""
        return await self._async_step_link(
            TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_link(
        self,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the unit behind them."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            # The unit has no serial number to use as a unique ID.
            self._async_abort_entries_match(
                {key: data[key] for key in IDENTITY_KEYS[connection_type]}
            )
            device, errors, placeholders = await self._async_validate(data)
            if device is not None:
                return self.async_create_entry(title=device.name, data=data)

        return self.async_show_form(
            step_id=connection_type,
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the unit is reached from now on."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[STEP_RECONFIGURE_TCP, STEP_RECONFIGURE_SERIAL],
        )

    async def async_step_reconfigure_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reach the unit through a Modbus TCP gateway from now on."""
        return await self._async_step_reconfigure_link(
            STEP_RECONFIGURE_TCP, TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input
        )

    async def async_step_reconfigure_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reach the unit on a serial port from now on."""
        return await self._async_step_reconfigure_link(
            STEP_RECONFIGURE_SERIAL, TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_reconfigure_link(
        self,
        step_id: str,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for new link settings, then probe the unit behind them."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            if any(
                _same_unit(data, other.data)
                for other in self._async_current_entries()
                if other.entry_id != entry.entry_id
            ):
                return self.async_abort(reason="already_configured")
            # Another range has other entities: the old ones would linger.
            if _is_210(data) != _is_210(entry.data):
                return self.async_show_form(
                    step_id=step_id,
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": "range_changed"},
                )

            # One port cannot run two line settings at once, so a running
            # entry gives up its link before the new settings are probed.
            relinking = False
            if entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
                current = create_modbus_params(entry.data)
                new = create_modbus_params(data)
                if new.endpoint == current.endpoint and new != current:
                    relinking = await self.hass.config_entries.async_unload(
                        entry.entry_id
                    )

            device, errors, placeholders = await self._async_validate(data)
            if device is not None:
                return self.async_update_reload_and_abort(entry, data=data)
            if relinking:
                await self.hass.config_entries.async_setup(entry.entry_id)

        suggested = user_input or (
            entry.data
            if entry.data[CONF_TYPE] == connection_type
            else {
                CONF_UNIT_ID: entry.data[CONF_UNIT_ID],
                CONF_MODEL: entry.data[CONF_MODEL],
                CONF_VARIANT: entry.data[CONF_VARIANT],
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[AnyDomeo | None, dict[str, str], dict[str, str]]:
        """Probe the unit, returning it or the errors to show instead."""
        try:
            device = await _async_probe(self.hass, data)
        except (
            _VariantNotAvailableError,
            _UnitSilentError,
            NotADomeoEvoError,
            NotADomeo210Error,
            ModbusError,
            HomeAssistantError,
        ) as err:
            error = next(key for kind, key in _PROBE_ERRORS if isinstance(err, kind))
            return None, {"base": error}, {}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return None, {"base": "unknown"}, {}
        return device, {}, {}
