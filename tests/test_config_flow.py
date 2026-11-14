"""Tests for the S&P DOMEO EVO config flow."""

from typing import Any
from unittest.mock import AsyncMock, PropertyMock, patch

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from modbus_connection import ModbusConnectionError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.domeo_modbus.const import CONF_BAUDRATE, CONF_VARIANT, DOMAIN

from . import (
    MOCK_SERIAL_DATA,
    MOCK_SERIAL_INPUT,
    MOCK_TCP_DATA,
    MOCK_TCP_INPUT,
    MOCK_TITLE,
)
from .register_images import PREVIOUS_DOMEO_210_FL

pytestmark = pytest.mark.usefixtures("mock_temporary_unit")


async def _start(hass: HomeAssistant, step: str) -> str:
    """Open the user flow and pick a connection type."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step
    return result["flow_id"]


@pytest.mark.parametrize(
    ("step", "user_input", "data"),
    [
        pytest.param("tcp", MOCK_TCP_INPUT, MOCK_TCP_DATA, id="tcp"),
        pytest.param("serial", MOCK_SERIAL_INPUT, MOCK_SERIAL_DATA, id="serial"),
    ],
)
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    step: str,
    user_input: dict[str, Any],
    data: dict[str, Any],
) -> None:
    """Test adding a unit over each kind of link."""
    flow_id = await _start(hass, step)
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_TITLE
    assert result["data"] == data
    assert result["result"].unique_id is None
    assert len(mock_setup_entry.mock_calls) == 1


async def test_title_names_model_and_variant(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the entry is named after the unit the user chose."""
    flow_id = await _start(hass, "tcp")
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**MOCK_TCP_INPUT, CONF_MODEL: "450", CONF_VARIANT: "serenite"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "DOMEO EVO 450 SERENITE"


@pytest.mark.parametrize(
    ("break_unit", "error"),
    [
        pytest.param(
            lambda connection, unit: unit.fail_requests(ModbusConnectionError()),
            "cannot_connect",
            id="unreachable",
        ),
        pytest.param(
            lambda connection, unit: unit.input.update({2: 9}),
            "not_a_domeo_evo",
            id="other_device",
        ),
        pytest.param(
            lambda connection, unit: unit.input.update(PREVIOUS_DOMEO_210_FL["input"]),
            "not_a_domeo_evo",
            id="previous_domeo_range",
        ),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_connection: MockModbusConnection,
    mock_unit: MockModbusUnit,
    break_unit: Any,
    error: str,
) -> None:
    """Test an unreadable unit shows an error, and the user can retry."""
    original = dict(mock_unit.input)
    break_unit(mock_connection, mock_unit)
    flow_id = await _start(hass, "tcp")

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_unit.fail_requests(None)
    mock_unit.input.update(original)
    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unit_silent(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_connection: MockModbusConnection,
    mock_unit: MockModbusUnit,
) -> None:
    """Test a gateway that answers while the unit behind it does not."""
    await mock_connection.connect()
    mock_unit.fail_requests(ModbusTimeoutError())
    flow_id = await _start(hass, "tcp")

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unit_silent"}

    mock_unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_timeout_without_a_link(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unit: MockModbusUnit,
) -> None:
    """Test a timeout before any link is up reads as unreachable."""
    mock_unit.fail_requests(ModbusTimeoutError())
    flow_id = await _start(hass, "tcp")
    with patch.object(
        MockModbusUnit, "connected", new_callable=PropertyMock, return_value=False
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(HomeAssistantError, "cannot_connect", id="link_in_use"),
        pytest.param(RuntimeError, "unknown", id="unexpected"),
    ],
)
async def test_user_flow_probe_raises(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test errors raised around the probe itself."""
    flow_id = await _start(hass, "tcp")
    with patch(
        "custom_components.domeo_modbus.domeo_evo_modbus.DomeoEvo.async_validate",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("step", "entry_data", "user_input"),
    [
        pytest.param("tcp", MOCK_TCP_DATA, MOCK_TCP_INPUT, id="tcp"),
        pytest.param("serial", MOCK_SERIAL_DATA, MOCK_SERIAL_INPUT, id="serial"),
        pytest.param(
            "tcp",
            MOCK_TCP_DATA,
            {**MOCK_TCP_INPUT, CONF_MODEL: "315"},
            id="tcp_other_model",
        ),
        pytest.param(
            "serial",
            MOCK_SERIAL_DATA,
            {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: "9600"},
            id="serial_other_baudrate",
        ),
    ],
    indirect=["entry_data"],
)
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    step: str,
    user_input: dict[str, Any],
) -> None:
    """Test the same unit on the same link cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start(hass, step)
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_another_unit_on_the_same_gateway(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a second unit at another address on one gateway is a new entry."""
    mock_config_entry.add_to_hass(hass)
    mock_connection.for_unit(2).input.update(mock_connection.for_unit(1).input)
    flow_id = await _start(hass, "tcp")
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**MOCK_TCP_INPUT, "unit_id": 2}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def _start_reconfigure(
    hass: HomeAssistant, entry: MockConfigEntry, step: str
) -> str:
    """Open the reconfigure flow and pick a connection type."""
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["type"] is FlowResultType.FORM
    return result["flow_id"]


@pytest.mark.parametrize(
    ("step", "user_input", "data"),
    [
        pytest.param(
            "reconfigure_tcp",
            {**MOCK_TCP_INPUT, CONF_HOST: "192.168.1.201"},
            {**MOCK_TCP_DATA, CONF_HOST: "192.168.1.201"},
            id="new_host",
        ),
        pytest.param(
            "reconfigure_serial", MOCK_SERIAL_INPUT, MOCK_SERIAL_DATA, id="to_serial"
        ),
    ],
)
async def test_reconfigure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    step: str,
    user_input: dict[str, Any],
    data: dict[str, Any],
) -> None:
    """Test pointing an entry at a new link."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_reconfigure(hass, mock_config_entry, step)
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == data


async def test_reconfigure_error_then_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test a failed probe keeps the form open."""
    mock_config_entry.add_to_hass(hass)
    mock_unit.fail_requests(ModbusConnectionError())
    flow_id = await _start_reconfigure(hass, mock_config_entry, "reconfigure_tcp")
    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_onto_another_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry cannot be pointed at a unit another entry already has."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN, data={**MOCK_TCP_DATA, CONF_HOST: "192.168.1.201"}
    )
    other.add_to_hass(hass)
    flow_id = await _start_reconfigure(hass, mock_config_entry, "reconfigure_tcp")
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**MOCK_TCP_INPUT, CONF_HOST: "192.168.1.201"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("entry_data", [MOCK_SERIAL_DATA], indirect=True)
async def test_reconfigure_line_settings_of_a_loaded_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
) -> None:
    """Test the entry gives up its port to probe new line settings on it."""
    assert init_integration.state is ConfigEntryState.LOADED
    new_input = {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: "9600"}
    flow_id = await _start_reconfigure(hass, init_integration, "reconfigure_serial")

    mock_unit.input[2] = 9
    result = await hass.config_entries.flow.async_configure(flow_id, new_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_a_domeo_evo"}
    # The probe failed, so the entry runs again on its old settings.
    assert init_integration.state is ConfigEntryState.LOADED

    mock_unit.input[2] = 1
    with patch(
        "custom_components.domeo_modbus.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, new_input)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data[CONF_BAUDRATE] == 9600


@pytest.mark.parametrize(
    ("entry_data", "model"),
    [
        pytest.param(MOCK_TCP_DATA, "210", id="evo_to_210"),
        pytest.param({**MOCK_TCP_DATA, CONF_MODEL: "210"}, "225", id="210_to_evo"),
    ],
    indirect=["entry_data"],
)
async def test_reconfigure_refuses_another_range(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entry_data: dict[str, Any],
    model: str,
) -> None:
    """Test an entry cannot switch between the DOMEO EVO and the Domeo 210."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_reconfigure(hass, mock_config_entry, "reconfigure_tcp")
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**MOCK_TCP_INPUT, CONF_MODEL: model}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "range_changed"}
    assert mock_config_entry.data == entry_data
