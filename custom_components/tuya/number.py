# Custom Component
"""Support for Tuya number."""
from __future__ import annotations

from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import IntegerTypeData, TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode, DPType


NUMBERS: dict[str, tuple[NumberEntityDescription, ...]] = {
    # Star Projector
    "dj": (
        NumberEntityDescription(
            key=DPCode.MOTOR_SPEED,
            name="Speed",
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya number dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_map: dict[str, Any]) -> None:
        """Discover and add a discovered Tuya number."""
        entities: list[TuyaNumberEntity] = []

        for device in device_map.values():
            if descriptions := NUMBERS.get(device.category):
                for description in descriptions:
                    if description.key in device.status:
                        entities.append(
                            TuyaNumberEntity(
                                device=device,
                                device_manager=hass_data.device_manager,
                                description=description,
                            )
                        )

        async_add_entities(entities)

    async_discover_device(hass_data.device_manager.device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaNumberEntity(TuyaEntity, NumberEntity):
    """Tuya Number Entity."""

    _number: IntegerTypeData | None = None

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: NumberEntityDescription,
    ) -> None:
        """Init TuyaNumberEntity."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        if int_type := self.find_dpcode(
            description.key, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._number = int_type
            self._attr_native_max_value = int(self._number.max / 10)
            self._attr_native_min_value = int(self._number.min / 10)
            self._attr_native_step = int(self._number.step)

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        # Unknown or unsupported data type
        if self._number is None:
            return None

        # Raw value
        if (value := self.device.status.get(self.entity_description.key)) is None:
            return None

        return round(value / 10)

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        if self._number is None:
            raise RuntimeError("Cannot set value, device doesn't provide type data")

        self._send_command(
            [
                {
                    "code": self.entity_description.key,
                    "value": round(value * 10),
                }
            ]
        )
