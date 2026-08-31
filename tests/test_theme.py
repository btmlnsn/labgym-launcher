import unittest

from labgym_launcher.theme import (
    DARK_PALETTE,
    LIGHT_PALETTE,
    appearance_is_dark_from_rgb,
    contrast_ratio,
    hex_to_rgb,
    palette_for_dark_appearance,
    palette_for_mode,
    read_native_appearance_is_dark,
    recent_item_fill,
    recent_item_text,
    recent_selection_palette,
    relative_luminance,
)


class _Colour:
    def __init__(self, rgb) -> None:
        self._rgb = rgb

    def Red(self):
        return self._rgb[0]

    def Green(self):
        return self._rgb[1]

    def Blue(self):
        return self._rgb[2]


class _Appearance:
    def __init__(self, dark: bool) -> None:
        self._dark = dark

    def IsDark(self):
        return self._dark


class _Settings:
    def __init__(self, dark=None, window_rgb=None) -> None:
        self._dark = dark
        self._window_rgb = window_rgb or (255, 255, 255)

    def GetAppearance(self):
        if self._dark is None:
            raise AttributeError("GetAppearance unused")
        return _Appearance(self._dark)

    def GetColour(self, _key):
        return _Colour(self._window_rgb)


class _SettingsWithoutAppearance:
    def __init__(self, window_rgb) -> None:
        self._window_rgb = window_rgb

    def GetColour(self, _key):
        return _Colour(self._window_rgb)


class ThemeSelectionTests(unittest.TestCase):
    def test_light_and_dark_palettes_match_specified_hex(self) -> None:
        self.assertEqual(LIGHT_PALETTE.mode, "light")
        self.assertEqual(LIGHT_PALETTE.window_bg, hex_to_rgb("#F5F7FA"))
        self.assertEqual(LIGHT_PALETTE.selected_row_bg, hex_to_rgb("#DCEBFF"))
        self.assertEqual(LIGHT_PALETTE.selected_row_text, hex_to_rgb("#102A43"))
        self.assertEqual(DARK_PALETTE.mode, "dark")
        self.assertEqual(DARK_PALETTE.window_bg, hex_to_rgb("#1F232A"))
        self.assertEqual(DARK_PALETTE.selected_row_bg, hex_to_rgb("#244A73"))
        self.assertEqual(DARK_PALETTE.selected_row_text, hex_to_rgb("#F8FAFC"))

    def test_palette_for_mode_and_appearance(self) -> None:
        self.assertIs(palette_for_mode("light"), LIGHT_PALETTE)
        self.assertIs(palette_for_mode("dark"), DARK_PALETTE)
        self.assertIs(palette_for_dark_appearance(False), LIGHT_PALETTE)
        self.assertIs(palette_for_dark_appearance(True), DARK_PALETTE)

    def test_appearance_from_window_luminance(self) -> None:
        self.assertFalse(appearance_is_dark_from_rgb(hex_to_rgb("#F5F7FA")))
        self.assertTrue(appearance_is_dark_from_rgb(hex_to_rgb("#1F232A")))

    def test_native_appearance_prefers_is_dark(self) -> None:
        self.assertTrue(read_native_appearance_is_dark(_Settings(dark=True), 0))
        self.assertFalse(read_native_appearance_is_dark(_Settings(dark=False), 0))

    def test_native_appearance_falls_back_to_window_colour(self) -> None:
        self.assertTrue(
            read_native_appearance_is_dark(
                _SettingsWithoutAppearance(hex_to_rgb("#1F232A")),
                0,
            )
        )
        self.assertFalse(
            read_native_appearance_is_dark(
                _SettingsWithoutAppearance(hex_to_rgb("#F5F7FA")),
                0,
            )
        )

    def test_gui_detection_uses_wx_appearance_when_provided(self) -> None:
        from labgym_launcher.gui import native_appearance_is_dark, resolve_launcher_palette

        class _Wx:
            SYS_COLOUR_WINDOW = 0
            SystemSettings = _Settings(dark=True)

        self.assertTrue(native_appearance_is_dark(_Wx))
        self.assertIs(resolve_launcher_palette(LIGHT_PALETTE), LIGHT_PALETTE)
        self.assertIs(resolve_launcher_palette(DARK_PALETTE), DARK_PALETTE)


class SelectedRowPaletteTests(unittest.TestCase):
    def test_selected_rows_have_strong_contrast_in_both_modes(self) -> None:
        for mode in ("light", "dark"):
            palette = palette_for_mode(mode)
            selection = recent_selection_palette(mode)
            self.assertEqual(selection["background"], palette.selected_row_bg)
            self.assertEqual(selection["foreground"], palette.selected_row_text)
            self.assertGreaterEqual(
                contrast_ratio(palette.selected_row_text, palette.selected_row_bg),
                4.5,
            )
            self.assertGreaterEqual(
                contrast_ratio(palette.primary_text, palette.recent_item_bg),
                4.5,
            )
            self.assertEqual(recent_item_text(palette, True), palette.selected_row_text)
            self.assertEqual(recent_item_text(palette, False), palette.primary_text)
            self.assertEqual(recent_item_fill(palette, 0, False), palette.recent_item_bg)
            self.assertEqual(recent_item_fill(palette, 1, False), palette.recent_alt_bg)
            self.assertEqual(recent_item_fill(palette, 0, True), palette.selected_row_bg)

    def test_light_selection_does_not_use_white_text(self) -> None:
        self.assertLess(relative_luminance(LIGHT_PALETTE.selected_row_text), 0.5)
        self.assertGreater(relative_luminance(LIGHT_PALETTE.selected_row_bg), 0.5)

    def test_dark_selection_does_not_use_pale_highlight(self) -> None:
        self.assertLess(relative_luminance(DARK_PALETTE.selected_row_bg), 0.5)
        self.assertGreater(relative_luminance(DARK_PALETTE.selected_row_text), 0.5)


if __name__ == "__main__":
    unittest.main()
