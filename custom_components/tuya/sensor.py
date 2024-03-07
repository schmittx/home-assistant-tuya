# Custom Component
"""Support for Tuya sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager
from tuya_iot.device import TuyaDeviceStatusRange

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import HomeAssistantTuyaData
from .base import EnumTypeData, IntegerTypeData, TuyaEntity
from .const import (
    DEVICE_CLASS_UNITS,
    DOMAIN,
    TUYA_DISCOVERY_NEW,
    DPCode,
    DPType,
    UnitOfMeasurement,
)


@dataclass(frozen=True)
class TuyaSensorEntityDescription(SensorEntityDescription):
    """Describes Tuya sensor entity."""


SENSORS: dict[str, tuple[TuyaSensorEntityDescription, ...]] = {
    # Star Projector
    "dj": (
        TuyaSensorEntityDescription(
            key=DPCode.WORK_MODE,
            name="Mode",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya sensor dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_map: dict[str, Any]) -> None:
        """Discover and add a discovered Tuya sensor."""
        entities: list[TuyaSensorEntity] = []

        for device in device_map.values():
            if descriptions := SENSORS.get(device.category):
                for description in descriptions:
                    if description.key in device.status:
                        entities.append(
                            TuyaSensorEntity(
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


class TuyaSensorEntity(TuyaEntity, SensorEntity):
    """Tuya Sensor Entity."""

    entity_description: TuyaSensorEntityDescription

    _status_range: TuyaDeviceStatusRange | None = None
    _type: DPType | None = None
    _type_data: IntegerTypeData | EnumTypeData | None = None
    _uom: UnitOfMeasurement | None = None

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaSensorEntityDescription,
    ) -> None:
        """Init Tuya sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        if int_type := self.find_dpcode(description.key, dptype=DPType.INTEGER):
            self._type_data = int_type
            self._type = DPType.INTEGER
            if description.native_unit_of_measurement is None:
                self._attr_native_unit_of_measurement = int_type.unit
        elif enum_type := self.find_dpcode(
            description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            self._type_data = enum_type
            self._type = DPType.ENUM
        else:
            self._type = self.get_dptype(DPCode(description.key))

        # Logic to ensure the set device class and API received Unit Of Measurement
        # match Home Assistants requirements.
        if (
            self.device_class is not None
            and not self.device_class.startswith(DOMAIN)
            and description.native_unit_of_measurement is None
        ):
            # We cannot have a device class, if the UOM isn't set or the
            # device class cannot be found in the validation mapping.
            if (
                self.native_unit_of_measurement is None
                or self.device_class not in DEVICE_CLASS_UNITS
            ):
                self._attr_device_class = None
                return

            uoms = DEVICE_CLASS_UNITS[self.device_class]
            self._uom = uoms.get(self.native_unit_of_measurement) or uoms.get(
                self.native_unit_of_measurement.lower()
            )

            # Unknown unit of measurement, device class should not be used.
            if self._uom is None:
                self._attr_device_class = None
                return

            # If we still have a device class, we should not use an icon
            if self.device_class:
                self._attr_icon = None

            # Found unit of measurement, use the standardized Unit
            # Use the target conversion unit (if set)
            self._attr_native_unit_of_measurement = (
                self._uom.conversion_unit or self._uom.unit
            )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        # Only continue if data type is known
        if self._type not in (
            DPType.INTEGER,
            DPType.STRING,
            DPType.ENUM,
            DPType.JSON,
            DPType.RAW,
        ):
            return None

        # Raw value
        value = self.device.status.get(self.entity_description.key)
        if value is None:
            return None

        # Valid string or enum value
        return value
