import unittest

from labgym_launcher.gui import (
    FRAME_MIN_SIZE,
    FRAME_START_SIZE,
    LOAD_SELECTED_COMMIT_LABEL,
    WINDOW_PANEL_NAME,
    confirmation_dialog_parent_plan,
    primary_action_labels,
    recent_action_labels,
    recent_selection_palette,
)
from labgym_launcher.theme import (
    DARK_PALETTE,
    LIGHT_PALETTE,
    contrast_ratio,
    rgb_to_hex,
)


class ConfirmationParentPlanTests(unittest.TestCase):
    def test_plan_forbids_nested_panel_button_parent(self) -> None:
        plan = confirmation_dialog_parent_plan()
        self.assertEqual(plan["window"], "dialog")
        self.assertIn("ok_button", plan["controls"])
        self.assertIn("cancel_button", plan["controls"])
        self.assertIn("details", plan["controls"])
        self.assertNotIn("panel", plan["controls"])


class PrimaryActionLabelTests(unittest.TestCase):
    def test_selected_commit_button_omits_launch(self) -> None:
        labels = primary_action_labels()
        self.assertEqual(labels["official_release"], "Official Release")
        self.assertEqual(labels["selected_commit"], "Selected Commit")
        self.assertNotIn("Launch", labels["selected_commit"])

    def test_recent_list_has_explicit_load_action(self) -> None:
        labels = recent_action_labels()
        self.assertEqual(labels["load_selected_commit"], "Load Selected Commit")
        self.assertEqual(LOAD_SELECTED_COMMIT_LABEL, "Load Selected Commit")


class SelectionPaletteTests(unittest.TestCase):
    def test_selected_row_colors_are_readable_in_both_modes(self) -> None:
        for mode, expected in (("light", LIGHT_PALETTE), ("dark", DARK_PALETTE)):
            palette = recent_selection_palette(mode)
            self.assertEqual(palette["background"], expected.selected_row_bg)
            self.assertEqual(palette["foreground"], expected.selected_row_text)
            self.assertEqual(palette["text"], expected.primary_text)
            self.assertGreaterEqual(
                contrast_ratio(palette["foreground"], palette["background"]),
                4.5,
            )
            self.assertGreaterEqual(
                contrast_ratio(palette["text"], palette["item"]),
                4.5,
            )


class ConfirmationDialogWxTests(unittest.TestCase):
    def test_confirmation_widgets_are_parented_to_the_dialog(self) -> None:
        try:
            import wx
        except ImportError:
            self.skipTest("wxPython is not installed")
        from labgym_launcher.gui import ConfirmationDialog

        app = wx.App(False)
        try:
            frame = wx.Frame(None)
            dialog = ConfirmationDialog(
                frame,
                "LabGym Launcher confirmation\nResolved: 3.0.1\nlabgym: 3.0.0 -> 3.0.1",
            )
            try:
                window, parents = dialog.widget_parents()
                dialog._dialog.Layout()
                self.assertTrue(dialog.details_ctrl.GetValue().startswith("LabGym Launcher confirmation"))
                for name, parent in parents.items():
                    self.assertIs(parent, window, msg="%s parent is not the dialog" % name)
            finally:
                dialog.Destroy()
                frame.Destroy()
        finally:
            app.Destroy()


class LauncherFrameWxTests(unittest.TestCase):
    def test_primary_buttons_compact_session_and_readable_recent_list(self) -> None:
        try:
            import wx
        except ImportError:
            self.skipTest("wxPython is not installed")
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from labgym_launcher.backend import LauncherBackend
        from labgym_launcher.gui import LauncherFrame
        from labgym_launcher.recent import RecentDemo
        from fakes import DEMO_SHA, FakeRunner

        temp = TemporaryDirectory()
        app = wx.App(False)
        try:
            backend = LauncherBackend(
                data_dir=Path(temp.name),
                runner=FakeRunner(),
                python="python",
                fetch_pypi_version=lambda: "3.0.1",
            )
            frame = LauncherFrame(backend=backend)
            try:
                size = frame._frame.GetSize()
                self.assertEqual((size.GetWidth(), size.GetHeight()), FRAME_START_SIZE)
                min_size = frame._frame.GetMinSize()
                self.assertEqual((min_size.GetWidth(), min_size.GetHeight()), FRAME_MIN_SIZE)
                self.assertEqual(frame.home_btn.GetLabel(), "Official Release")
                self.assertEqual(frame.demo_btn.GetLabel(), "Selected Commit")
                self.assertNotIn("Launch", frame.demo_btn.GetLabel())
                self.assertIs(frame.home_btn.GetParent(), frame.window_panel)
                self.assertIs(frame.demo_btn.GetParent(), frame.window_panel)
                self.assertIs(frame.rollback_btn.GetParent(), frame.window_panel)
                self.assertIs(frame.refresh_btn.GetParent(), frame.window_panel)
                self.assertEqual(frame.window_panel.GetName(), WINDOW_PANEL_NAME)
                self.assertEqual(frame.details_btn.GetLabel(), "Details")
                self.assertEqual(frame.load_recent_btn.GetLabel(), "Load Selected Commit")
                self.assertFalse(hasattr(frame, "status_ctrl"))
                self.assertIn("desired GitHub commit hash", frame.target_hint.GetLabel())
                self.assertNotIn("unique commit hash", frame.target_hint.GetLabel())
                session = frame.session_ctrl.GetValue()
                self.assertLessEqual(len(session.splitlines()), 2)
                self.assertNotIn("Active checkout:", session)
                self.assertNotIn("Data dir:", session)
                self.assertNotIn("LabGym Launcher status", session)
                details = frame.status_details_text()
                self.assertIn("LabGym Launcher status", details)

                long_subject = (
                    "Fix the selected-commit history UI so it is readable again "
                    "without packing metadata into each row"
                )
                frame.recent = [
                    RecentDemo(
                        "alice/LabGym",
                        DEMO_SHA,
                        branch_name="demo-branch",
                        subject=long_subject,
                    )
                ]
                frame.refresh_recent_list()
                self.assertEqual(frame.recent_list.GetCount(), 1)
                html = frame.recent_list.GetString(0)
                self.assertIn("<br>", html)
                self.assertEqual(html.count("<br>"), 1)
                self.assertIn("alice/LabGym", html)
                self.assertIn(DEMO_SHA[:7], html)
                self.assertIn(long_subject, html)
                self.assertNotIn("...", html)
                self.assertNotIn("detached commit", html)
                self.assertNotIn("Branch:", html)
                selected_bg = frame.recent_list.GetSelectionBackground()
                self.assertEqual(
                    (selected_bg.Red(), selected_bg.Green(), selected_bg.Blue()),
                    frame.palette.selected_row_bg,
                )
                selected_html = frame.recent_list.OnGetItem(0)
                self.assertIn(rgb_to_hex(frame.palette.selected_row_text), selected_html)
                self.assertIn(long_subject, selected_html)

                frame.source_ctrl.SetValue("other/LabGym")
                frame.commit_ctrl.SetValue("deadbeef")
                frame.on_load_recent(None)
                self.assertEqual(frame.source_ctrl.GetValue(), "alice/LabGym")
                self.assertEqual(frame.commit_ctrl.GetValue(), DEMO_SHA)

                frame.source_ctrl.SetValue("")
                frame.commit_ctrl.SetValue("")
                frame.on_use_recent(None)
                self.assertEqual(frame.source_ctrl.GetValue(), "alice/LabGym")
                self.assertEqual(frame.commit_ctrl.GetValue(), DEMO_SHA)

                frame._frame.Layout()
                frame.session_panel.Layout()
                panel_size = frame.session_panel.GetClientSize()
                ctrl_size = frame.session_ctrl.GetSize()
                self.assertGreater(panel_size.GetWidth(), 600)
                self.assertLessEqual(abs(ctrl_size.GetWidth() - panel_size.GetWidth()), 2)
                session_bg = frame.session_ctrl.GetBackgroundColour()
                panel_bg = frame.session_panel.GetBackgroundColour()
                expected = frame.palette.panel_bg
                self.assertEqual(
                    (session_bg.Red(), session_bg.Green(), session_bg.Blue()),
                    expected,
                )
                self.assertEqual(
                    (panel_bg.Red(), panel_bg.Green(), panel_bg.Blue()),
                    expected,
                )
                self.assertNotEqual(expected, (0, 0, 0))
            finally:
                frame._frame.Destroy()
        finally:
            app.Destroy()
            temp.cleanup()

    def test_forced_dark_palette_is_applied_to_recent_list(self) -> None:
        try:
            import wx
        except ImportError:
            self.skipTest("wxPython is not installed")
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from labgym_launcher.backend import LauncherBackend
        from labgym_launcher.gui import LauncherFrame
        from labgym_launcher.recent import RecentDemo
        from fakes import DEMO_SHA, FakeRunner

        temp = TemporaryDirectory()
        app = wx.App(False)
        try:
            backend = LauncherBackend(
                data_dir=Path(temp.name),
                runner=FakeRunner(),
                python="python",
                fetch_pypi_version=lambda: "3.0.1",
            )
            frame = LauncherFrame(backend=backend, palette=DARK_PALETTE)
            try:
                self.assertEqual(frame.palette.mode, "dark")
                frame.recent = [
                    RecentDemo("alice/LabGym", DEMO_SHA, subject="Add selected-commit UI")
                ]
                frame.refresh_recent_list()
                selected_bg = frame.recent_list.GetSelectionBackground()
                self.assertEqual(
                    (selected_bg.Red(), selected_bg.Green(), selected_bg.Blue()),
                    DARK_PALETTE.selected_row_bg,
                )
                selected_html = frame.recent_list.OnGetItem(0)
                self.assertIn(rgb_to_hex(DARK_PALETTE.selected_row_text), selected_html)
                panel_bg = frame.session_ctrl.GetBackgroundColour()
                self.assertEqual(
                    (panel_bg.Red(), panel_bg.Green(), panel_bg.Blue()),
                    DARK_PALETTE.panel_bg,
                )
                window_bg = frame.window_panel.GetBackgroundColour()
                self.assertEqual(
                    (window_bg.Red(), window_bg.Green(), window_bg.Blue()),
                    DARK_PALETTE.window_bg,
                )
                for button in (
                    frame.home_btn,
                    frame.demo_btn,
                    frame.rollback_btn,
                    frame.refresh_btn,
                ):
                    self.assertIs(button.GetParent(), frame.window_panel)
                    button_bg = button.GetBackgroundColour()
                    self.assertNotEqual(
                        (button_bg.Red(), button_bg.Green(), button_bg.Blue()),
                        DARK_PALETTE.panel_bg,
                    )
            finally:
                frame._frame.Destroy()
        finally:
            app.Destroy()
            temp.cleanup()


    def test_recent_list_shows_alias_before_provenance(self) -> None:
        try:
            import wx
        except ImportError:
            self.skipTest("wxPython is not installed")
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from labgym_launcher.backend import LauncherBackend
        from labgym_launcher.gui import LauncherFrame
        from labgym_launcher.recent import RecentDemo, load_recent, save_recent
        from fakes import DEMO_SHA, FakeRunner

        temp = TemporaryDirectory()
        app = wx.App(False)
        try:
            backend = LauncherBackend(
                data_dir=Path(temp.name),
                runner=FakeRunner(),
                python="python",
                fetch_pypi_version=lambda: "3.0.1",
            )
            frame = LauncherFrame(backend=backend)
            try:
                frame.recent = [
                    RecentDemo(
                        "alice/LabGym",
                        DEMO_SHA,
                        subject="Add selected-commit UI",
                        alias="Courtship demo",
                    ),
                    RecentDemo("bob/LabGym", "bbbbbbb", subject="No alias here"),
                ]
                frame.refresh_recent_list()
                self.assertEqual(frame.recent_list.GetCount(), 2)
                aliased = frame.recent_list.GetString(0)
                self.assertIn("<b>Courtship demo</b>", aliased)
                self.assertIn("alice/LabGym", aliased)
                self.assertIn(DEMO_SHA[:7], aliased)
                self.assertIn("Add selected-commit UI", aliased)
                self.assertEqual(aliased.count("<br>"), 2)
                plain = frame.recent_list.GetString(1)
                self.assertIn("bob/LabGym", plain)
                self.assertNotIn("Courtship demo", plain)
                self.assertEqual(plain.count("<br>"), 1)

                frame.on_load_recent(None)
                self.assertEqual(frame.source_ctrl.GetValue(), "alice/LabGym")
                self.assertEqual(frame.commit_ctrl.GetValue(), DEMO_SHA)

                save_recent(backend.data_dir, frame.recent)
                reloaded = load_recent(backend.data_dir)
                self.assertEqual(reloaded[0].alias, "Courtship demo")
                self.assertIsNone(reloaded[1].alias)
            finally:
                frame._frame.Destroy()
        finally:
            app.Destroy()
            temp.cleanup()


class AliasDialogWxTests(unittest.TestCase):
    def test_dialog_shows_readonly_provenance_and_editable_alias(self) -> None:
        try:
            import wx
        except ImportError:
            self.skipTest("wxPython is not installed")
        from labgym_launcher.gui import DemoEditDialog
        from fakes import DEMO_SHA

        app = wx.App(False)
        try:
            frame = wx.Frame(None)
            dialog = DemoEditDialog(
                frame,
                "alice/LabGym",
                DEMO_SHA,
                "Courtship demo",
            )
            try:
                self.assertEqual(dialog._dialog.GetTitle(), "Edit alias")
                self.assertEqual(dialog.source_ctrl.GetValue(), "alice/LabGym")
                self.assertEqual(dialog.commit_ctrl.GetValue(), DEMO_SHA)
                self.assertFalse(dialog.source_ctrl.IsEditable())
                self.assertFalse(dialog.commit_ctrl.IsEditable())
                self.assertTrue(dialog.alias_ctrl.IsEditable())
                self.assertEqual(dialog.alias_value(), "Courtship demo")
                dialog.alias_ctrl.SetValue("Courtship v2")
                self.assertEqual(dialog.values(), "Courtship v2")
                self.assertIn("does not change", dialog.alias_hint.GetLabel())
            finally:
                dialog.Destroy()
                frame.Destroy()
        finally:
            app.Destroy()

    def test_edit_action_updates_and_clears_alias_without_changing_identity(self) -> None:
        try:
            import wx
        except ImportError:
            self.skipTest("wxPython is not installed")
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        from labgym_launcher import gui as gui_mod
        from labgym_launcher.backend import LauncherBackend
        from labgym_launcher.gui import LauncherFrame
        from labgym_launcher.recent import RecentDemo, load_recent
        from fakes import DEMO_SHA, FakeRunner

        class _ScriptedDialog(gui_mod.DemoEditDialog):
            next_alias = "Courtship demo"

            def ShowModal(self) -> int:
                self.alias_ctrl.SetValue(self.next_alias)
                return wx.ID_OK

        temp = TemporaryDirectory()
        app = wx.App(False)
        try:
            backend = LauncherBackend(
                data_dir=Path(temp.name),
                runner=FakeRunner(),
                python="python",
                fetch_pypi_version=lambda: "3.0.1",
            )
            frame = LauncherFrame(backend=backend)
            try:
                frame.recent = [
                    RecentDemo("alice/LabGym", DEMO_SHA, subject="Add selected-commit UI")
                ]
                frame.refresh_recent_list()

                with patch.object(gui_mod, "DemoEditDialog", _ScriptedDialog):
                    frame.on_edit_recent(None)
                self.assertEqual(frame.recent[0].alias, "Courtship demo")
                self.assertEqual(frame.recent[0].source_repo, "alice/LabGym")
                self.assertEqual(frame.recent[0].commit, DEMO_SHA)
                html = frame.recent_list.GetString(0)
                self.assertIn("<b>Courtship demo</b>", html)
                self.assertIn("alice/LabGym", html)
                self.assertIn(DEMO_SHA[:7], html)

                _ScriptedDialog.next_alias = ""
                with patch.object(gui_mod, "DemoEditDialog", _ScriptedDialog):
                    frame.on_edit_recent(None)
                self.assertIsNone(frame.recent[0].alias)
                html = frame.recent_list.GetString(0)
                self.assertNotIn("Courtship demo", html)
                self.assertIn("alice/LabGym", html)
                self.assertEqual(html.count("<br>"), 1)

                saved = load_recent(backend.data_dir)
                self.assertEqual(len(saved), 1)
                self.assertIsNone(saved[0].alias)
                self.assertEqual(saved[0].commit, DEMO_SHA)
            finally:
                frame._frame.Destroy()
        finally:
            app.Destroy()
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
