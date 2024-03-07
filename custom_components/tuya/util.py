# Custom Component
"""Utility methods for the Tuya integration."""
from __future__ import annotations

DEFAULT_COLOUR_DATA = "000003e803e8"


def remap_value(
    value: float | int,
    from_min: float | int = 0,
    from_max: float | int = 255,
    to_min: float | int = 0,
    to_max: float | int = 255,
    reverse: bool = False,
) -> float:
    """Remap a value from its current range, to a new range."""
    if reverse:
        value = from_max - value + from_min
    return ((value - from_min) / (from_max - from_min)) * (to_max - to_min) + to_min


def colour_data_str_to_list(value: str,
) -> list:
    """Remap a value from its current range, to a new range."""
    return [value[i:i+4] for i in range(0, len(value), 4)]


def tuya_to_hsv(value: str) -> tuple:
    """Remap a value from its current range, to a new range."""
    hsv = colour_data_str_to_list((value or DEFAULT_COLOUR_DATA)) or colour_data_str_to_list(DEFAULT_COLOUR_DATA)
    return (
        int(hsv[0], 16),
        round(int(hsv[1], 16)/10),
        round(int(hsv[2], 16)/10),
    )


def digit_to_char(digit):
    if digit < 10:
        return chr(ord('0') + digit)
    return chr(ord('a') + digit - 10)


def num_to_str(num, base=16):
    if num < 0:
        return '-' + num_to_str(-num, base)
    else:
        (d, m) = divmod(num, base)
        if d:
            return num_to_str(d,base) + digit_to_char(m)
        return digit_to_char(m)


def pad(value):
    return value.rjust(4, "0")


def hsv_to_tuya(hue: int, sat: int, val: int) -> str:
    """Remap a value from its current range, to a new range."""
    return f"{pad(num_to_str(hue)) + pad(num_to_str(sat*10)) + pad(num_to_str(val*10))}"