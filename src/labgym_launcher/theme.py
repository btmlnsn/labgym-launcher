"""Strict light/dark palettes for the launcher GUI.

Color values are the only concern of this module. Layout and list content live
elsewhere. Theme selection can be tested without importing wx.
"""

from dataclasses import dataclass
from typing import Tuple

RGB = Tuple[int, int, int]


def hex_to_rgb(value: str) -> RGB:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) != 6:
        raise ValueError("invalid hex color: %s" % value)
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def rgb_to_hex(rgb: RGB) -> str:
    return "#%02X%02X%02X" % rgb


def relative_luminance(rgb: RGB) -> float:
    def channel(value: int) -> float:
        scaled = value / 255.0
        if scaled <= 0.03928:
            return scaled / 12.92
        return ((scaled + 0.055) / 1.055) ** 2.4

    red, green, blue = rgb
    return (
        0.2126 * channel(red)
        + 0.7152 * channel(green)
        + 0.0722 * channel(blue)
    )


def contrast_ratio(foreground: RGB, background: RGB) -> float:
    lighter = max(relative_luminance(foreground), relative_luminance(background))
    darker = min(relative_luminance(foreground), relative_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def appearance_is_dark_from_rgb(window_rgb: RGB) -> bool:
    return relative_luminance(window_rgb) < 0.5


def read_native_appearance_is_dark(system_settings, window_colour_key) -> bool:
    """Detect dark mode from a wx-like SystemSettings object.

    Prefers GetAppearance().IsDark() / IsUsingDarkBackground() when present,
    then falls back to the luminance of SYS_COLOUR_WINDOW.
    """
    get_appearance = getattr(system_settings, "GetAppearance", None)
    if callable(get_appearance):
        appearance = get_appearance()
        for name in ("IsDark", "IsUsingDarkBackground"):
            method = getattr(appearance, name, None)
            if callable(method):
                return bool(method())
    colour = system_settings.GetColour(window_colour_key)
    return appearance_is_dark_from_rgb(
        (colour.Red(), colour.Green(), colour.Blue())
    )


@dataclass(frozen=True)
class LauncherPalette:
    mode: str
    window_bg: RGB
    panel_bg: RGB
    panel_border: RGB
    primary_text: RGB
    secondary_text: RGB
    recent_item_bg: RGB
    recent_alt_bg: RGB
    selected_row_bg: RGB
    selected_row_text: RGB
    selected_row_accent: RGB

    def hex(self, name: str) -> str:
        return rgb_to_hex(getattr(self, name))


def _palette(mode: str, colors: dict) -> LauncherPalette:
    return LauncherPalette(
        mode=mode,
        **{key: hex_to_rgb(value) for key, value in colors.items()},
    )


LIGHT_PALETTE = _palette(
    "light",
    {
        "window_bg": "#F5F7FA",
        "panel_bg": "#FFFFFF",
        "panel_border": "#D9E2EC",
        "primary_text": "#102A43",
        "secondary_text": "#52606D",
        "recent_item_bg": "#FFFFFF",
        "recent_alt_bg": "#F8FAFC",
        "selected_row_bg": "#DCEBFF",
        "selected_row_text": "#102A43",
        "selected_row_accent": "#7AA7E8",
    },
)

DARK_PALETTE = _palette(
    "dark",
    {
        "window_bg": "#1F232A",
        "panel_bg": "#262B33",
        "panel_border": "#3A404A",
        "primary_text": "#E5E7EB",
        "secondary_text": "#A7B0BE",
        "recent_item_bg": "#262B33",
        "recent_alt_bg": "#2B313A",
        "selected_row_bg": "#244A73",
        "selected_row_text": "#F8FAFC",
        "selected_row_accent": "#5B8FD9",
    },
)


def palette_for_mode(mode: str) -> LauncherPalette:
    if mode == "dark":
        return DARK_PALETTE
    if mode == "light":
        return LIGHT_PALETTE
    raise ValueError("unknown theme mode: %s" % mode)


def palette_for_dark_appearance(is_dark: bool) -> LauncherPalette:
    return DARK_PALETTE if is_dark else LIGHT_PALETTE


def recent_selection_palette(mode: str = "light") -> dict:
    palette = palette_for_mode(mode)
    return {
        "background": palette.selected_row_bg,
        "foreground": palette.selected_row_text,
        "text": palette.primary_text,
        "accent": palette.selected_row_accent,
        "item": palette.recent_item_bg,
        "alt": palette.recent_alt_bg,
    }


def recent_item_fill(palette: LauncherPalette, index: int, selected: bool) -> RGB:
    if selected:
        return palette.selected_row_bg
    if index % 2:
        return palette.recent_alt_bg
    return palette.recent_item_bg


def recent_item_text(palette: LauncherPalette, selected: bool) -> RGB:
    if selected:
        return palette.selected_row_text
    return palette.primary_text
