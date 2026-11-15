"""Tests for the Domeo 210, the unit of the previous range."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_MODEL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusUnit, WriteEvent
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from custom_components.domeo_modbus.const import CONF_VARIANT, DOMAIN
from custom_components.domeo_modbus.coordinator import modbus_control_issue_id

from . import MOCK_210_DATA, MOCK_210_TITLE, MOCK_ENTRY_ID, MOCK_TCP_INPUT
from .register_images import (
    FACTORY_225_FL,
    PREVIOUS_DOMEO_210_DHU,
    PREVIOUS_DOMEO_210_FL,
)

COIL = 0x05
FC06 = 0x06


def _image(**changes: dict[int, Any]) -> dict[str, dict[int, Any]]:
    """The Domeo 210 image, with some registers changed."""
    image = deepcopy(PREVIOUS_DOMEO_210_FL)
    for space, values in changes.items():
        image[space].update(values)
    return image


@pytest.fixture
def register_image(request: pytest.FixtureRequest) -> dict[str, dict[int, Any]]:
    """The registers of a Domeo 210, unless a test says otherwise."""
    return getattr(request, "param", PREVIOUS_DOMEO_210_FL)


@pytest.fixture
def entry_data(request: pytest.FixtureRequest) -> dict[str, Any]:
    """The data of a Domeo 210 entry, unless a test says otherwise."""
    return getattr(request, "param", MOCK_210_DATA)


@pytest.fixture
def mock_config_entry(entry_data: dict[str, Any]) -> MockConfigEntry:
    """A config entry for the mock Domeo 210."""
    return MockConfigEntry(
        domain=DOMAIN, entry_id=MOCK_ENTRY_ID, data=entry_data, title=MOCK_210_TITLE
    )


@pytest.fixture
def writes(mock_unit: MockModbusUnit) -> list[WriteEvent]:
    """The writes the mock unit receives."""
    events: list[WriteEvent] = []
    mock_unit.on_write(events.append)
    return events


async def _start(hass: HomeAssistant) -> str:
    """Open the user flow on the network link."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "tcp"}
    )
    return result["flow_id"]


@pytest.mark.usefixtures("mock_temporary_unit")
@pytest.mark.parametrize(
    ("register_image", "variant", "title"),
    [
        pytest.param(PREVIOUS_DOMEO_210_FL, "fl", "Domeo 210 FL", id="fl"),
        pytest.param(PREVIOUS_DOMEO_210_DHU, "dhu", "Domeo 210 DHU", id="dhu"),
    ],
    indirect=["register_image"],
)
@pytest.mark.usefixtures("mock_temporary_unit")
async def test_user_flow_adds_a_domeo_210(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, variant: str, title: str
) -> None:
    """Test a Domeo 210 of either variant is added."""
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**MOCK_TCP_INPUT, CONF_MODEL: "210", CONF_VARIANT: variant}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == {**MOCK_210_DATA, CONF_VARIANT: variant}


@pytest.mark.usefixtures("mock_temporary_unit")
async def test_user_flow_refuses_a_serenite_domeo_210(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the Domeo 210 cannot be added as a Serenite."""
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**MOCK_TCP_INPUT, CONF_MODEL: "210", CONF_VARIANT: "serenite"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "variant_not_available"}


@pytest.mark.parametrize("register_image", [FACTORY_225_FL], indirect=True)
@pytest.mark.usefixtures("mock_temporary_unit")
async def test_user_flow_refuses_a_domeo_evo_as_a_domeo_210(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a DOMEO EVO chosen as a Domeo 210 is refused."""
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**MOCK_TCP_INPUT, CONF_MODEL: "210"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_a_domeo_210"}


@pytest.mark.parametrize(
    "platforms",
    [
        pytest.param([platform], id=platform.value)
        for platform in (
            Platform.BINARY_SENSOR,
            Platform.BUTTON,
            Platform.NUMBER,
            Platform.SENSOR,
            Platform.SWITCH,
        )
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the entities a Domeo 210 gets, and their states."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize("platforms", [[Platform.SELECT]])
async def test_no_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Domeo 210 has nothing to choose from a list."""
    assert not er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )


@pytest.mark.parametrize(
    ("domain", "service", "entity_id", "data", "write"),
    [
        pytest.param(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            "switch.domeo_210_holiday_mode",
            {},
            WriteEvent("coil", 7, [True], COIL),
            id="holiday_mode_is_coil_7",
        ),
        pytest.param(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            "switch.domeo_210_automatic_bypass",
            {},
            WriteEvent("coil", 8, [False], COIL),
            id="auto_bypass_is_coil_8",
        ),
        pytest.param(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            "switch.domeo_210_manual_bypass",
            {},
            WriteEvent("coil", 9, [True], COIL),
            id="manual_bypass_is_coil_9",
        ),
        pytest.param(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            "button.domeo_210_start_boost",
            {},
            WriteEvent("holding", 15, [1], FC06),
            id="start_boost_is_holding_15",
        ),
        pytest.param(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            "button.domeo_210_reset_filter_alarm",
            {},
            WriteEvent("coil", 12, [True], COIL),
            id="reset_filter_alarm_is_coil_12",
        ),
        pytest.param(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            "number.domeo_210_high_airflow",
            {ATTR_VALUE: 210},
            WriteEvent("holding", 10, [210], FC06),
            id="boost_airflow_is_holding_10",
        ),
        pytest.param(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            "number.domeo_210_supply_extract_unbalance",
            {ATTR_VALUE: -5},
            WriteEvent("holding", 8, [0xFFFB], FC06),
            id="unbalance_is_signed",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_command(
    hass: HomeAssistant,
    writes: list[WriteEvent],
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, Any],
    write: WriteEvent,
) -> None:
    """Test each command sends exactly the expected Modbus write."""
    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )
    assert writes == [write]


@pytest.mark.usefixtures("init_integration")
async def test_airflow_range_of_the_210(hass: HomeAssistant) -> None:
    """Test the Domeo 210 refuses an airflow outside its range."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.domeo_210_high_airflow", ATTR_VALUE: 211},
            blocking=True,
        )


@pytest.mark.parametrize("register_image", [_image(coil={6: True})], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_europe_version(hass: HomeAssistant) -> None:
    """Test the Europe version gets standby instead of holiday mode, and no boost."""
    assert hass.states.get("switch.domeo_210_standby") is not None
    assert hass.states.get("switch.domeo_210_holiday_mode") is None
    assert hass.states.get("button.domeo_210_start_boost") is None
    assert hass.states.get("button.domeo_210_reset_filter_alarm") is not None


@pytest.mark.parametrize(
    "register_image",
    [_image(coil={2: True, 3: True}, input={26: 1, 27: 5})],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_heating_batteries_when_installed(hass: HomeAssistant) -> None:
    """Test the battery states appear only on a unit that has them."""
    pre = hass.states.get("sensor.domeo_210_pre_heating_battery")
    post = hass.states.get("sensor.domeo_210_post_heating_battery")
    assert pre is not None
    assert pre.state == "on"
    assert post is not None
    assert post.state == "thermal_protection"


async def test_extras_refused_leave_no_fan_speed(
    hass: HomeAssistant,
    mock_unit: MockModbusUnit,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: Any,
) -> None:
    """Test a unit that refuses the 2014 registers still sets up, without fan speeds."""
    mock_unit.fail_read(19, IllegalDataAddressError(), register_type="input")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.domeo_210_airflow") is not None
    assert hass.states.get("sensor.domeo_210_extract_fan_speed") is None


@pytest.mark.usefixtures("init_integration")
async def test_no_jp1_repair(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Domeo 210, which does not report JP1, never raises the repair."""
    issue_id = modbus_control_issue_id(init_integration)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a Domeo 210 include its raw register map."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )


@pytest.mark.parametrize(
    ("register_image", "entry_data"),
    [(PREVIOUS_DOMEO_210_DHU, {**MOCK_210_DATA, CONF_VARIANT: "dhu"})],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_dhu_humidity_regulation(
    hass: HomeAssistant, writes: list[WriteEvent]
) -> None:
    """Test the DHU gets its humidity regulation, and the table's gaps hold."""
    level = hass.states.get("number.domeo_210_humidity_upper_threshold")
    assert level is not None
    assert level.state == "90"
    assert hass.states.get("number.domeo_210_humidity_maximum_airflow") is not None

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.domeo_210_humidity_upper_threshold", ATTR_VALUE: 80},
        blocking=True,
    )
    assert writes == [WriteEvent("holding", 21, [80], FC06)]

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.domeo_210_humidity_lower_threshold",
                ATTR_VALUE: 85,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_fl_has_no_humidity_regulation(hass: HomeAssistant) -> None:
    """Test the FL gets no humidity regulation settings."""
    assert hass.states.get("number.domeo_210_humidity_upper_threshold") is None
