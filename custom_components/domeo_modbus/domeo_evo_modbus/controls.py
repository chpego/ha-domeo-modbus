"""The unit's switches and commands, from its coils (FC01 / FC05).

The S&P table numbers coils from 1, so table coil ``n`` is address ``n - 1``.

Coil 9 ("reset the AIRSENS IDs") is deliberately not modelled. It forgets the
paired probes and needs the unit to be restarted, which is not something to
expose next to everyday commands.
"""

from __future__ import annotations

from modbus_connection.model import Component, coil

from .enums import AutoMode, ClpContact, EquipmentVersion


class Controls(Component):
    """Holiday mode, bypass, defrost and the filter alarm reset."""

    coil_ranges = ((0, 7),)

    _equipment_version = coil(0)  # coil 1, read-only here
    _auto_mode = coil(1, writable=True)  # coil 2
    _clp_contact = coil(2, writable=True)  # coil 3
    # The table gives 0 = On and 1 = Off for holiday mode, but reports from
    # two real units point the other way: 1 = On, like every other coil
    # (chpego/ha-domeo-modbus#6).
    _holiday_mode = coil(3, writable=True)  # coil 4
    _auto_bypass = coil(4, writable=True)  # coil 5
    _manual_bypass = coil(5, writable=True)  # coil 6
    _defrost_cancelled = coil(6, writable=True)  # coil 7: 0 = allow, 1 = cancel
    _filter_reset = coil(7, writable=True)  # coil 8

    @property
    def equipment_version(self) -> EquipmentVersion | None:
        """The factory equipment configuration (version A or B)."""
        raw = self._equipment_version
        return None if raw is None else EquipmentVersion(int(raw))

    @property
    def auto_mode(self) -> AutoMode | None:
        """How the unit regulates in automatic mode."""
        raw = self._auto_mode
        return None if raw is None else AutoMode(int(raw))

    @property
    def clp_contact(self) -> ClpContact | None:
        """The wiring of the external CLP contact."""
        raw = self._clp_contact
        return None if raw is None else ClpContact(int(raw))

    @property
    def holiday_mode(self) -> bool | None:
        """Whether holiday mode (halved airflow) is on."""
        return self._holiday_mode

    @property
    def auto_bypass(self) -> bool | None:
        """Whether the bypass opens automatically."""
        return self._auto_bypass

    @property
    def manual_bypass(self) -> bool | None:
        """Whether the bypass is forced open."""
        return self._manual_bypass

    @property
    def defrost_allowed(self) -> bool | None:
        """Whether the unit may defrost."""
        raw = self._defrost_cancelled
        return None if raw is None else not raw

    async def async_set_auto_mode(self, mode: AutoMode) -> None:
        """Choose how the unit regulates in automatic mode."""
        await self.write("_auto_mode", bool(AutoMode(mode)))

    async def async_set_clp_contact(self, contact: ClpContact) -> None:
        """Declare how the external CLP contact is wired."""
        await self.write("_clp_contact", bool(ClpContact(contact)))

    async def async_set_holiday_mode(self, on: bool) -> None:
        """Turn holiday mode on or off."""
        await self.write("_holiday_mode", bool(on))

    async def async_set_auto_bypass(self, on: bool) -> None:
        """Let the bypass open automatically, or not."""
        await self.write("_auto_bypass", bool(on))

    async def async_set_manual_bypass(self, on: bool) -> None:
        """Force the bypass open, or release it."""
        await self.write("_manual_bypass", bool(on))

    async def async_set_defrost_allowed(self, allowed: bool) -> None:
        """Allow the unit to defrost, or cancel defrosting."""
        await self.write("_defrost_cancelled", not allowed)

    async def async_reset_filter_alarm(self) -> None:
        """Acknowledge the filter alarm and restart its countdown."""
        await self.write("_filter_reset", True)
