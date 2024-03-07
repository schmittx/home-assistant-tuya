# Custom Component
"""Support for the Tuya lights."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode
from .util import remap_value, tuya_to_hsv, hsv_to_tuya


@dataclass(frozen=True)
class TuyaLightEntityDescription(LightEntityDescription):
    """Describe an Tuya light entity."""

    color_mode: ColorMode | None = None


LIGHTS: dict[str, tuple[TuyaLightEntityDescription, ...]] = {
    # Star Projector
    "dj": (
        TuyaLightEntityDescription(
            key=DPCode.LASER_SWITCH,
            color_mode=ColorMode.BRIGHTNESS,
            name="Laser",
        ),
        TuyaLightEntityDescription(
            key=DPCode.RGB_SWITCH,
            color_mode=ColorMode.HS,
            name="Color",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya light entity dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_map: dict[str, Any]) -> None:
        """Discover and add a discovered Tuya light."""
        entities: list[TuyaLightEntity] = []

        for device in device_map.values():
            if descriptions := LIGHTS.get(device.category):
                for description in descriptions:
                    if description.key in device.status:
                        entities.append(
                            TuyaLightEntity(
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


class TuyaLightEntity(TuyaEntity, LightEntity):
    """Tuya light entity."""

    entity_description: TuyaLightEntityDescription

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaLightEntityDescription,
    ) -> None:
        """Init TuyaLightEntity."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._attr_color_mode = description.color_mode

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.device.status.get(self.entity_description.key, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on or control the light."""
        commands = [
            {
                "code": DPCode.SWITCH_LED,
                "value": True,
            },
            {
                "code": self.entity_description.key,
                "value": True,
            },
        ]

        if all(
            [
                self.color_mode == ColorMode.HS,
                any(
                    [
                        ATTR_BRIGHTNESS in kwargs,
                        ATTR_HS_COLOR in kwargs,
                    ]
                ),
            ]
        ):
            hue, sat = kwargs.get(ATTR_HS_COLOR, self.hs_color)
            val = kwargs.get(ATTR_BRIGHTNESS, self.brightness)
            value = hsv_to_tuya(
                hue=int(hue),
                sat=int(sat),
                val=round(remap_value(value=val, to_max=100)),
            )
            commands += [
                {
                    "code": DPCode.COLOUR_DATA,
                    "value": value,
                }
            ]

        if all(
            [
                self.color_mode == ColorMode.BRIGHTNESS,
                ATTR_BRIGHTNESS in kwargs,
            ]
        ):
            commands += [
                {
                    "code": DPCode.BRIGHT_VALUE,
                    "value": round(remap_value(value=kwargs[ATTR_BRIGHTNESS], to_max=1000)),
                }
            ]

        self._send_command(commands)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._send_command([{"code": self.entity_description.key, "value": False}])

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if self.color_mode == ColorMode.HS:
            hue, sat, val = tuya_to_hsv(self.device.status[DPCode.COLOUR_DATA])
            return round(remap_value(value=val, from_max=100))
        return round(
            remap_value(
                value=self.device.status[DPCode.BRIGHT_VALUE],
                from_max=1000,
                from_min=10,
            )
        )

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs_color of the light."""
        if self.color_mode == ColorMode.HS:
            hue, sat, val = tuya_to_hsv(self.device.status[DPCode.COLOUR_DATA])
            return (hue, sat)
        return None

    @property
    def supported_color_modes(self) -> set[str]:
        """Flag supported color modes."""
        return set([self.color_mode])
