import unittest
from unittest.mock import patch

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
    recent_item_fill,
    rgb_to_hex,
)


def _require_wx():
    try:
        import wx
    except ImportError:
        raise unittest.SkipTest("wxPython is not installed")
    return wx


def _wx_app(wxmod):
    try:
        return wxmod.App(False)
    except SystemExit as exc:
        raise unittest.SkipTest(
            "wxPython needs a display; this runner has none"
        ) from exc


class ConfirmationParentPlanTests(unittest.TestCase):
    def test_plan_forbids_nested_panel_button_parent(self) -> None:
        plan = confirmation_dialog_parent_plan()
        self.assertEqual(plan["window"], "dialog")
        self.assertIn("ok_button", plan["controls"])
        self.assertIn("cancel_button", plan["controls"])
        self.assertIn("details", plan["controls"])
        self.assertNotIn("panel", plan["controls"])


class PrimaryActionLabelTests(unittest.TestCase):
    def test_launch_buttons_use_launch_prefix(self) -> None:
        labels = primary_action_labels()
        self.assertEqual(labels["official_release"], "Launch Official Release")
        self.assertEqual(labels["selected_commit"], "Launch Selected Commit")
        self.assertEqual(labels["restore_official_release"], "Restore Official Release")
        self.assertEqual(labels["refresh"], "Refresh")
        self.assertIn("Launch", labels["selected_commit"])

    def test_recent_list_has_explicit_load_action(self) -> None:
        labels = recent_action_labels()
        self.assertEqual(labels["load_target"], "Load Target")
        self.assertEqual(labels["edit_alias"], "Edit Alias")
        self.assertEqual(labels["remove"], "Remove")
        self.assertEqual(LOAD_SELECTED_COMMIT_LABEL, "Load Target")


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
        wx = _require_wx()
        from labgym_launcher.gui import ConfirmationDialog

        app = _wx_app(wx)
        try:
            frame = wx.Frame(None)
            dialog = ConfirmationDialog(
                frame,
                "Action: Official Release\nResolved: 3.0.1\nlabgym: 3.0.0 -> 3.0.1",
            )
            try:
                window, parents = dialog.widget_parents()
                dialog._dialog.Layout()
                self.assertTrue(dialog.details_ctrl.GetValue().startswith("Action: Official Release"))
                ok_button = dialog._dialog.FindWindowById(wx.ID_OK)
                self.assertEqual(ok_button.GetLabel(), "Install")
                self.assertIn("before installing", dialog.intro_ctrl.GetLabel())
                self.assertNotIn("LabGym will not be launched", dialog.intro_ctrl.GetLabel())
                for name, parent in parents.items():
                    self.assertIsNotNone(parent, msg="%s has no parent" % name)
                    self.assertEqual(
                        parent.GetClassName(),
                        "wxDialog",
                        msg="%s parent class is %s" % (name, parent.GetClassName()),
                    )
                    self.assertTrue(
                        parent.IsSameAs(window),
                        msg="%s parent is not the dialog" % name,
                    )
            finally:
                dialog.Destroy()
                frame.Destroy()
        finally:
            app.Destroy()

    def test_restore_confirmation_uses_restore_button_and_copy(self) -> None:
        wx = _require_wx()
        from labgym_launcher.gui import ConfirmationDialog
        from labgym_launcher.theme import DARK_PALETTE

        app = _wx_app(wx)
        try:
            frame = wx.Frame(None)
            dialog = ConfirmationDialog(
                frame,
                "Action: Restore Official Release\nLabGym will launch: no",
                action="rollback",
                palette=DARK_PALETTE,
            )
            try:
                ok_button = dialog._dialog.FindWindowById(wx.ID_OK)
                self.assertEqual(ok_button.GetLabel(), "Restore")
                intro = dialog.intro_ctrl.GetLabel().replace("\n", " ")
                self.assertIn("before restoring", intro)
                self.assertNotIn("before installing", intro)
                self.assertIn("LabGym will not be launched", intro)
                dialog_bg = dialog._dialog.GetBackgroundColour()
                self.assertEqual(
                    (dialog_bg.Red(), dialog_bg.Green(), dialog_bg.Blue()),
                    DARK_PALETTE.window_bg,
                )
            finally:
                dialog.Destroy()
                frame.Destroy()
        finally:
            app.Destroy()


class LauncherFrameWxTests(unittest.TestCase):
    def test_primary_buttons_compact_session_and_readable_recent_list(self) -> None:
        wx = _require_wx()
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from labgym_launcher.app_icon import get_frame_icon_path, packaged_icon_paths
        from labgym_launcher.backend import LauncherBackend
        from labgym_launcher.gui import LauncherFrame
        from labgym_launcher.recent import RecentDemo
        from fakes import DEMO_SHA, FakeRunner

        temp = TemporaryDirectory()
        app = _wx_app(wx)
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
                self.assertEqual(frame.home_btn.GetLabel(), "Launch Official Release")
                self.assertEqual(frame.demo_btn.GetLabel(), "Launch Selected Commit")
                self.assertIn("Launch", frame.demo_btn.GetLabel())
                self.assertEqual(frame.rollback_btn.GetLabel(), "Restore Official Release")
                self.assertEqual(frame.refresh_btn.GetLabel(), "Refresh")
                self.assertEqual(frame.session_box.GetLabel(), "Current State")
                self.assertEqual(frame.target_box.GetLabel(), "Launch Target")
                self.assertEqual(frame.recent_box.GetLabel(), "Remembered Commits")
                self.assertEqual(frame.purpose_ctrl.GetLabel().replace("\n", " "), (
                    "Launch the Official Release or a Selected Commit. "
                    "One session of each kind may run at the same time."
                ))
                self.assertIs(frame.home_btn.GetParent(), frame.target_box)
                self.assertIs(frame.demo_btn.GetParent(), frame.target_box)
                self.assertIs(frame.rollback_btn.GetParent(), frame.window_panel)
                self.assertIs(frame.refresh_btn.GetParent(), frame.window_panel)
                self.assertEqual(frame.window_panel.GetName(), WINDOW_PANEL_NAME)
                self.assertEqual(frame.details_btn.GetLabel(), "Details")
                self.assertEqual(frame.load_recent_btn.GetLabel(), "Load Target")
                self.assertEqual(frame.edit_recent_btn.GetLabel(), "Edit Alias")
                self.assertEqual(frame.remove_recent_btn.GetLabel(), "Remove")
                self.assertFalse(frame.demo_btn.IsEnabled())
                self.assertFalse(frame.load_recent_btn.IsEnabled())
                self.assertFalse(frame.edit_recent_btn.IsEnabled())
                self.assertFalse(frame.remove_recent_btn.IsEnabled())
                icon_path = get_frame_icon_path()
                self.assertTrue(icon_path)
                self.assertTrue(Path(icon_path).is_file())
                loaded_icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ANY)
                if not loaded_icon.IsOk():
                    png_path = packaged_icon_paths()["png"]
                    self.assertTrue(png_path.is_file())
                    loaded_icon = wx.Icon(str(png_path), wx.BITMAP_TYPE_ANY)
                self.assertTrue(
                    loaded_icon.IsOk(),
                    "wx failed to load frame icon from %s" % icon_path,
                )
                self.assertFalse(hasattr(frame, "status_ctrl"))
                self.assertIn("desired GitHub commit hash", frame.target_hint.GetLabel())
                self.assertNotIn("unique commit hash", frame.target_hint.GetLabel())
                session = frame.session_ctrl.GetValue()
                self.assertEqual(len(session.splitlines()), 4)
                self.assertIn("Installed:", session)
                self.assertIn("Official Release session:", session)
                self.assertIn("Selected Commit session:", session)
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

    def test_layout_shows_remembered_rows_at_min_and_default(self) -> None:
        wx = _require_wx()
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from labgym_launcher.backend import LauncherBackend
        from labgym_launcher.gui import (
            FRAME_MIN_SIZE,
            FRAME_START_SIZE,
            LauncherFrame,
            RECENT_LIST_MIN_HEIGHT,
        )
        from labgym_launcher.recent import RecentDemo
        from fakes import DEMO_SHA, FakeRunner

        temp = TemporaryDirectory()
        app = _wx_app(wx)
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
                    RecentDemo("bob/LabGym", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", subject="No alias here"),
                ]
                frame.refresh_recent_list()
                frame._frame.Show()
                app.Yield(True)
                default_list = frame.recent_list.GetSize().GetHeight()
                self.assertGreaterEqual(default_list, RECENT_LIST_MIN_HEIGHT)
                aliased = frame.recent_list.GetItemRect(0)
                compact = frame.recent_list.GetItemRect(1)
                self.assertGreaterEqual(default_list, aliased.GetHeight() + compact.GetHeight())

                frame._frame.SetSize(FRAME_MIN_SIZE)
                frame._frame.Layout()
                app.Yield(True)
                min_list = frame.recent_list.GetSize().GetHeight()
                aliased = frame.recent_list.GetItemRect(0)
                self.assertGreaterEqual(
                    min_list,
                    aliased.GetHeight(),
                    "minimum window must show one full aliased remembered row; "
                    "GTK chrome may leave less list height than macOS",
                )
                self.assertEqual(
                    (frame._frame.GetSize().GetWidth(), frame._frame.GetSize().GetHeight()),
                    FRAME_MIN_SIZE,
                )
                self.assertEqual(
                    (frame._frame.GetMinSize().GetWidth(), frame._frame.GetMinSize().GetHeight()),
                    FRAME_MIN_SIZE,
                )
                self.assertEqual(
                    (FRAME_START_SIZE[0], FRAME_START_SIZE[1]),
                    (860, 720),
                )
            finally:
                frame._frame.Destroy()
        finally:
            app.Destroy()
            temp.cleanup()

    def test_forced_dark_palette_is_applied_to_recent_list(self) -> None:
        wx = _require_wx()
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from labgym_launcher.backend import LauncherBackend
        from labgym_launcher.gui import LauncherFrame
        from labgym_launcher.recent import RecentDemo
        from fakes import DEMO_SHA, FakeRunner

        temp = TemporaryDirectory()
        app = _wx_app(wx)
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
                list_bg = frame.recent_list.GetBackgroundColour()
                self.assertEqual(
                    (list_bg.Red(), list_bg.Green(), list_bg.Blue()),
                    DARK_PALETTE.recent_item_bg,
                )
                self.assertEqual(
                    recent_item_fill(DARK_PALETTE, 0, True),
                    DARK_PALETTE.selected_row_bg,
                )
                self.assertIs(frame.home_btn.GetParent(), frame.target_box)
                self.assertIs(frame.demo_btn.GetParent(), frame.target_box)
                self.assertIs(frame.rollback_btn.GetParent(), frame.window_panel)
                self.assertIs(frame.refresh_btn.GetParent(), frame.window_panel)
            finally:
                frame._frame.Destroy()
        finally:
            app.Destroy()
            temp.cleanup()


    def test_recent_list_shows_alias_before_provenance(self) -> None:
        wx = _require_wx()
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from labgym_launcher.backend import LauncherBackend
        from labgym_launcher.gui import LauncherFrame
        from labgym_launcher.recent import RecentDemo, load_recent, save_recent
        from fakes import DEMO_SHA, FakeRunner

        temp = TemporaryDirectory()
        app = _wx_app(wx)
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
        wx = _require_wx()
        from labgym_launcher.gui import DemoEditDialog
        from fakes import DEMO_SHA

        app = _wx_app(wx)
        try:
            frame = wx.Frame(None)
            dialog = DemoEditDialog(
                frame,
                "alice/LabGym",
                DEMO_SHA,
                "Courtship demo",
            )
            try:
                self.assertEqual(dialog._dialog.GetTitle(), "Edit Alias")
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
        wx = _require_wx()
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
        app = _wx_app(wx)
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


class EnablementWxTests(unittest.TestCase):
    def _frame(self, wxmod):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from labgym_launcher.backend import LauncherBackend
        from labgym_launcher.gui import LauncherFrame
        from fakes import FakeRunner

        temp = TemporaryDirectory()
        backend = LauncherBackend(
            data_dir=Path(temp.name),
            runner=FakeRunner(),
            python="python",
            fetch_pypi_version=lambda: "3.0.1",
        )
        frame = LauncherFrame(backend=backend)
        return temp, frame

    def test_launch_selected_commit_disabled_for_blank_and_whitespace(self) -> None:
        wx = _require_wx()
        app = _wx_app(wx)
        temp, frame = self._frame(wx)
        try:
            self.assertFalse(frame.demo_btn.IsEnabled())
            frame.commit_ctrl.SetValue("   ")
            frame._update_action_enablement()
            self.assertFalse(frame.demo_btn.IsEnabled())
            frame.commit_ctrl.SetValue("abc1def")
            frame._update_action_enablement()
            self.assertTrue(frame.demo_btn.IsEnabled())
            frame.commit_ctrl.SetValue("master")
            frame._update_action_enablement()
            self.assertTrue(frame.demo_btn.IsEnabled())
            frame.commit_ctrl.SetValue("")
            frame._update_action_enablement()
            self.assertFalse(frame.demo_btn.IsEnabled())
        finally:
            frame._frame.Destroy()
            app.Destroy()
            temp.cleanup()

    def test_remembered_actions_disabled_without_selection(self) -> None:
        wx = _require_wx()
        from labgym_launcher.recent import RecentDemo
        from fakes import DEMO_SHA

        app = _wx_app(wx)
        temp, frame = self._frame(wx)
        try:
            self.assertFalse(frame.load_recent_btn.IsEnabled())
            self.assertFalse(frame.edit_recent_btn.IsEnabled())
            self.assertFalse(frame.remove_recent_btn.IsEnabled())
            frame.recent = [RecentDemo("alice/LabGym", DEMO_SHA, subject="Add UI")]
            frame.refresh_recent_list()
            self.assertEqual(frame.recent_list.GetSelection(), 0)
            self.assertTrue(frame.load_recent_btn.IsEnabled())
            self.assertTrue(frame.edit_recent_btn.IsEnabled())
            self.assertTrue(frame.remove_recent_btn.IsEnabled())
            frame.recent_list.SetSelection(wx.NOT_FOUND)
            frame._update_action_enablement()
            self.assertFalse(frame.load_recent_btn.IsEnabled())
            self.assertFalse(frame.edit_recent_btn.IsEnabled())
            self.assertFalse(frame.remove_recent_btn.IsEnabled())
        finally:
            frame._frame.Destroy()
            app.Destroy()
            temp.cleanup()

    def test_gated_buttons_stay_disabled_after_working_false(self) -> None:
        wx = _require_wx()
        app = _wx_app(wx)
        temp, frame = self._frame(wx)
        try:
            self.assertFalse(frame.demo_btn.IsEnabled())
            self.assertFalse(frame.load_recent_btn.IsEnabled())
            frame._set_working(True, "Working... checking the requested target.")
            self.assertFalse(frame.demo_btn.IsEnabled())
            self.assertFalse(frame.home_btn.IsEnabled())
            frame._set_working(False)
            self.assertTrue(frame.home_btn.IsEnabled())
            self.assertFalse(frame.demo_btn.IsEnabled())
            self.assertFalse(frame.load_recent_btn.IsEnabled())
            self.assertFalse(frame.edit_recent_btn.IsEnabled())
            self.assertFalse(frame.remove_recent_btn.IsEnabled())
        finally:
            frame._frame.Destroy()
            app.Destroy()
            temp.cleanup()


class RemoveConfirmWxTests(unittest.TestCase):
    def test_remove_dialog_copy_and_cancel_vs_confirm(self) -> None:
        wx = _require_wx()
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from labgym_launcher.backend import LauncherBackend
        from labgym_launcher.gui import LauncherFrame
        from labgym_launcher.gui_flow import REMOVE_REMEMBERED_TITLE
        from labgym_launcher.recent import RecentDemo, load_recent
        from fakes import DEMO_SHA, FakeRunner

        temp = TemporaryDirectory()
        app = _wx_app(wx)
        try:
            backend = LauncherBackend(
                data_dir=Path(temp.name),
                runner=FakeRunner(),
                python="python",
                fetch_pypi_version=lambda: "3.0.1",
            )
            frame = LauncherFrame(backend=backend)
            try:
                item = RecentDemo(
                    "alice/LabGym",
                    DEMO_SHA,
                    subject="Add UI",
                    alias="Courtship demo",
                )
                frame.recent = [item]
                frame.refresh_recent_list()
                dialog = frame._make_remove_remembered_dialog(item)
                try:
                    self.assertEqual(dialog.GetTitle(), REMOVE_REMEMBERED_TITLE)
                    message = dialog.GetMessage()
                    self.assertIn("Remove this remembered commit from the list?", message)
                    self.assertIn('Remembered entry: "Courtship demo"', message)
                    self.assertIn(
                        "This does not uninstall LabGym or change the current environment.",
                        message,
                    )
                    if hasattr(dialog, "GetYesLabel"):
                        self.assertEqual(dialog.GetYesLabel().replace("&", ""), "Remove")
                    if hasattr(dialog, "GetNoLabel"):
                        self.assertEqual(dialog.GetNoLabel().replace("&", ""), "Cancel")
                finally:
                    dialog.Destroy()

                with patch.object(
                    frame, "_confirm_remove_remembered", return_value=False
                ):
                    frame.on_remove_recent(None)
                self.assertEqual(len(frame.recent), 1)
                self.assertTrue(frame.remove_recent_btn.IsEnabled())

                with patch.object(
                    frame, "_confirm_remove_remembered", return_value=True
                ):
                    frame.on_remove_recent(None)
                self.assertEqual(frame.recent, [])
                self.assertFalse(frame.remove_recent_btn.IsEnabled())
                self.assertEqual(load_recent(backend.data_dir), [])
            finally:
                frame._frame.Destroy()
        finally:
            app.Destroy()
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
