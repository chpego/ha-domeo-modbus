"""Base entity for the S&P DOMEO EVO integration."""

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import override

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from modbus_connection import (
    IllegalFunctionError,
    ModbusError,
    ServerDeviceFailureError,
)

from .const import DOMAIN
from .coordinator import DomeoEvoCoordinator, DomeoEvoRuntimeData


@dataclass(frozen=True, kw_only=True)
class DomeoEvoEntityDescription(EntityDescription):
    """Which component of the unit an entity reads."""

    component: str  # attribute name on DomeoEvo, e.g. 'readings'


class DomeoEvoEntity(CoordinatorEntity[DomeoEvoCoordinator]):
    """An entity backed by one component of the unit.

    Components are polled independently, so an entity is unavailable when its
    own component failed to read, not when any of them did.
    """

    _attr_has_entity_name = True
    entity_description: DomeoEvoEntityDescription

    def __init__(
        self,
        runtime_data: DomeoEvoRuntimeData,
        entity_description: DomeoEvoEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(runtime_data.coordinator_for(entity_description.component))
        self.entity_description = entity_description
        # The unit reports no serial number.
        self._attr_unique_id = (
            f"{self.coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self._attr_device_info = runtime_data.readings.device_info

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        return (
            super().available
            and self.entity_description.component in self.coordinator.data.updated
        )

    async def _async_write(self, write: Awaitable[None]) -> None:
        """Send a write to the unit, then refresh what it changed."""
        try:
            await write
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_value",
                translation_placeholders={"error": str(err)},
            ) from err
        except IllegalFunctionError as err:
            # What a unit with jumper JP1 open answers to every write.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_refused",
                translation_placeholders={"error": str(err)},
            ) from err
        except ServerDeviceFailureError as err:
            # What a Domeo 210 DHU answered to a humidity regulation airflow
            # its table allows (chpego/ha-domeo-modbus#15).
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_not_carried_out",
                translation_placeholders={"error": str(err)},
            ) from err
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
