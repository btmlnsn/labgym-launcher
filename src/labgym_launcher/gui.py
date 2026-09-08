import sys
import threading
from typing import Callable, List, Optional

from labgym_launcher.app_icon import (
    APP_NAME,
    set_frame_icon,
    setup_application_icons,
)
from labgym_launcher.backend import LauncherBackend
from labgym_launcher.confirm import format_status
from labgym_launcher.constants import (
    CANONICAL_SOURCE,
    LAUNCH_OFFICIAL_RELEASE_LABEL,
    RESTORE_OFFICIAL_LABEL,
    SELECTED_COMMIT_BUTTON_LABEL,
)
from labgym_launcher.gui_flow import (
    ALREADY_ACTIVE,
    GUI_EMPTY_COMMIT_ERROR,
    REMOVE_REMEMBERED_TITLE,
    SESSION_BLOCKED,
    already_active_success_message,
    applied_success_message,
    apply_if_approved,
    confirmation_display,
    format_session_summary,
    gui_error_text,
    record_demo_if_needed,
    remembered_actions_enabled,
    remove_remembered_confirm_text,
    select_official_release,
    select_rollback,
    select_selected_commit,
    selected_commit_action_enabled,
)
from labgym_launcher.recent import (
    RecentDemo,
    load_recent,
    remove_recent,
    save_recent,
    set_recent_alias,
)
from labgym_launcher.sessions import session_class_for_action
from labgym_launcher.theme import (
    LauncherPalette,
    palette_for_dark_appearance,
    read_native_appearance_is_dark,
    recent_item_fill,
    recent_item_text,
    recent_selection_palette,
    rgb_to_hex,
)


def _import_wx():
    try:
        import wx
        import wx.html  # noqa: F401 - SimpleHtmlListBox for recent commits
    except ImportError as exc:
        raise ImportError(
            "wxPython is required for the LabGym Launcher GUI. "
            "Install it with: pip install 'labgym-launcher[gui]'"
        ) from exc
    return wx


wx = None  # populated in main() / frame construction


def _wx():
    global wx
    if wx is None:
        wx = _import_wx()
    return wx


def confirmation_dialog_parent_plan():
    """Sizer-managed confirmation widgets must share the dialog as parent.

    ``CreateButtonSizer`` parents OK/Cancel to the dialog. Putting those
    buttons in a nested panel sizer triggers a wx assertion.
    """
    return {
        "window": "dialog",
        "controls": ("label", "details", "ok_button", "cancel_button"),
    }


def primary_action_labels():
    return {
        "official_release": LAUNCH_OFFICIAL_RELEASE_LABEL,
        "selected_commit": SELECTED_COMMIT_BUTTON_LABEL,
        "restore_official_release": RESTORE_OFFICIAL_LABEL,
        "refresh": REFRESH_LABEL,
    }


def recent_action_labels():
    return {
        "load_target": LOAD_TARGET_LABEL,
        "edit_alias": EDIT_ALIAS_LABEL,
        "remove": "Remove",
    }


# Startup size is chosen so the compact launcher layout is readable without
# requiring the user to resize. The window may grow; it should not open smaller.
# Min height keeps at least one aliased remembered row (and preferably two
# compact rows) visible after the header, Current State, and Launch Target.
FRAME_START_SIZE = (860, 720)
FRAME_MIN_SIZE = (780, 680)
SESSION_SUMMARY_HEIGHT = 72
RECENT_LIST_MIN_HEIGHT = 120
SECONDARY_WIDGET_NAME = "launcher-secondary"
WINDOW_PANEL_NAME = "launcher-window"
CURRENT_STATE_LABEL = "Current State"
LAUNCH_TARGET_LABEL = "Launch Target"
REMEMBERED_COMMITS_LABEL = "Remembered Commits"
LOAD_TARGET_LABEL = "Load Target"
EDIT_ALIAS_LABEL = "Edit Alias"
REFRESH_LABEL = "Refresh"
LOAD_SELECTED_COMMIT_LABEL = LOAD_TARGET_LABEL
PURPOSE_TEXT = (
    "Launch the Official Release or a Selected Commit. "
    "One session of each kind may run at the same time."
)
TARGET_HINT_TEXT = (
    "username/repo-name and a desired GitHub commit hash. "
    "Default source: umyelab/LabGym."
)


def native_appearance_is_dark(wxmod=None) -> bool:
    wxmod = wxmod or _wx()
    return read_native_appearance_is_dark(
        wxmod.SystemSettings,
        wxmod.SYS_COLOUR_WINDOW,
    )


def resolve_launcher_palette(palette: Optional[LauncherPalette] = None) -> LauncherPalette:
    if palette is not None:
        return palette
    return palette_for_dark_appearance(native_appearance_is_dark())


def apply_theme(widget, palette: LauncherPalette) -> None:
    wxmod = _wx()
    class_name = widget.GetClassName()
    primary = wxmod.Colour(*palette.primary_text)
    secondary = wxmod.Colour(*palette.secondary_text)
    window_bg = wxmod.Colour(*palette.window_bg)
    panel_bg = wxmod.Colour(*palette.panel_bg)
    panel_border = wxmod.Colour(*palette.panel_border)
    if class_name in ("wxFrame", "wxDialog"):
        widget.SetBackgroundColour(window_bg)
        widget.SetForegroundColour(primary)
    elif class_name == "wxHtmlListBox":
        widget.SetBackgroundColour(wxmod.Colour(*palette.recent_item_bg))
        widget.SetForegroundColour(primary)
    elif class_name == "wxPanel":
        if widget.GetName() == WINDOW_PANEL_NAME:
            widget.SetBackgroundColour(window_bg)
        else:
            widget.SetBackgroundColour(panel_bg)
        widget.SetForegroundColour(primary)
    elif class_name == "wxStaticBox":
        widget.SetBackgroundColour(panel_bg)
        widget.SetForegroundColour(primary)
    elif class_name == "wxStaticText":
        parent = widget.GetParent()
        parent_name = parent.GetName() if parent else ""
        if parent_name == WINDOW_PANEL_NAME:
            widget.SetBackgroundColour(window_bg)
        else:
            widget.SetBackgroundColour(panel_bg)
        if widget.GetName() == SECONDARY_WIDGET_NAME:
            widget.SetForegroundColour(secondary)
        else:
            widget.SetForegroundColour(primary)
    elif class_name == "wxTextCtrl":
        widget.SetBackgroundColour(panel_bg)
        widget.SetForegroundColour(primary)
    elif class_name == "wxButton":
        # Native buttons belong on the parent surface. Filling them with
        # panel_bg paints a leftover rectangle behind the action row.
        pass
    else:
        widget.SetBackgroundColour(panel_bg)
        widget.SetForegroundColour(primary)
    if hasattr(widget, "SetBorderColour"):
        widget.SetBorderColour(panel_border)
    for child in widget.GetChildren():
        apply_theme(child, palette)
    widget.Refresh()


_RecentCommitList = None


def _recent_commit_list_type():
    global _RecentCommitList
    if _RecentCommitList is not None:
        return _RecentCommitList
    wxmod = _wx()

    class RecentCommitList(wxmod.html.HtmlListBox):
        def __init__(self, parent, palette: LauncherPalette) -> None:
            super().__init__(parent, style=wxmod.BORDER_SIMPLE)
            self._labels = []
            self._palette = palette
            self.SetMargins(8, 6)
            self.apply_palette(palette)
            self.Bind(wxmod.EVT_LISTBOX, self._on_selection)

        def apply_palette(self, palette: LauncherPalette) -> None:
            self._palette = palette
            self.SetBackgroundColour(wxmod.Colour(*palette.recent_item_bg))
            self.SetForegroundColour(wxmod.Colour(*palette.primary_text))
            self.SetSelectionBackground(wxmod.Colour(*palette.selected_row_bg))
            self.Refresh()

        def _on_selection(self, event) -> None:
            self.Refresh()
            event.Skip()

        def Set(self, labels) -> None:
            self._labels = list(labels)
            self.SetItemCount(len(self._labels))
            self.Refresh()

        def GetCount(self) -> int:
            return len(self._labels)

        def GetString(self, index: int) -> str:
            return self._labels[index]

        def OnDrawBackground(self, dc, rect, n) -> None:
            fill = recent_item_fill(self._palette, n, self.IsSelected(n))
            dc.SetBrush(wxmod.Brush(wxmod.Colour(*fill)))
            dc.SetPen(wxmod.TRANSPARENT_PEN)
            dc.DrawRectangle(rect)
            if self.IsSelected(n):
                dc.SetPen(wxmod.Pen(wxmod.Colour(*self._palette.selected_row_accent), 1))
                dc.SetBrush(wxmod.TRANSPARENT_BRUSH)
                dc.DrawRectangle(rect)

        def OnGetItem(self, n: int) -> str:
            if n < 0 or n >= len(self._labels):
                return ""
            color = recent_item_text(self._palette, self.IsSelected(n))
            return '<font color="%s">%s</font>' % (rgb_to_hex(color), self._labels[n])

    _RecentCommitList = RecentCommitList
    return _RecentCommitList


def _ok_cancel_sizer(wxmod, dialog, ok_label: Optional[str] = None):
    buttons = dialog.CreateButtonSizer(wxmod.OK | wxmod.CANCEL)
    if ok_label:
        ok_button = dialog.FindWindowById(wxmod.ID_OK)
        if ok_button is not None:
            ok_button.SetLabel(ok_label)
    return buttons


class ConfirmationDialog:
    def __init__(self, parent, text: str) -> None:
        wxmod = _wx()
        self._dialog = wxmod.Dialog(
            parent,
            title="LabGym Launcher confirmation",
            style=wxmod.DEFAULT_DIALOG_STYLE | wxmod.RESIZE_BORDER,
        )
        root = wxmod.BoxSizer(wxmod.VERTICAL)
        label = wxmod.StaticText(
            self._dialog,
            label=(
                "Review the resolved commit and dependency changes before installing. "
                "Nothing is installed until you confirm."
            ),
        )
        root.Add(label, 0, wxmod.ALL | wxmod.EXPAND, 10)
        box = wxmod.TextCtrl(
            self._dialog,
            value=text,
            style=wxmod.TE_MULTILINE | wxmod.TE_READONLY | wxmod.BORDER_SIMPLE | wxmod.HSCROLL,
        )
        box.SetMinSize((780, 420))
        self.details_ctrl = box
        root.Add(box, 1, wxmod.LEFT | wxmod.RIGHT | wxmod.BOTTOM | wxmod.EXPAND, 10)
        root.Add(
            _ok_cancel_sizer(wxmod, self._dialog, ok_label="Install"),
            0,
            wxmod.ALL | wxmod.ALIGN_RIGHT,
            10,
        )
        self._dialog.SetSizerAndFit(root)
        apply_theme(self._dialog, resolve_launcher_palette())
        if parent:
            self._dialog.CentreOnParent()
        else:
            self._dialog.Centre()

    def ShowModal(self) -> int:
        return self._dialog.ShowModal()

    def Destroy(self) -> None:
        self._dialog.Destroy()

    def widget_parents(self):
        wxmod = _wx()
        dialog = self._dialog
        parents = {
            "details": self.details_ctrl.GetParent(),
            "ok_button": dialog.FindWindowById(wxmod.ID_OK).GetParent()
            if dialog.FindWindowById(wxmod.ID_OK)
            else None,
            "cancel_button": dialog.FindWindowById(wxmod.ID_CANCEL).GetParent()
            if dialog.FindWindowById(wxmod.ID_CANCEL)
            else None,
        }
        return dialog, parents


class DemoEditDialog:
    def __init__(
        self,
        parent,
        source_repo: str,
        commit: str,
        alias: str = "",
    ) -> None:
        wxmod = _wx()
        self._dialog = wxmod.Dialog(
            parent,
            title="Edit Alias",
            style=wxmod.DEFAULT_DIALOG_STYLE | wxmod.RESIZE_BORDER,
        )
        root = wxmod.BoxSizer(wxmod.VERTICAL)
        form = wxmod.FlexGridSizer(3, 2, 8, 8)
        form.AddGrowableCol(1, 1)
        form.Add(
            wxmod.StaticText(self._dialog, label="Source repo"),
            0,
            wxmod.ALIGN_CENTER_VERTICAL,
        )
        self.source_ctrl = wxmod.TextCtrl(
            self._dialog,
            value=source_repo,
            style=wxmod.TE_READONLY,
        )
        form.Add(self.source_ctrl, 1, wxmod.EXPAND)
        form.Add(
            wxmod.StaticText(self._dialog, label="Commit hash"),
            0,
            wxmod.ALIGN_CENTER_VERTICAL,
        )
        self.commit_ctrl = wxmod.TextCtrl(
            self._dialog,
            value=commit,
            style=wxmod.TE_READONLY,
        )
        form.Add(self.commit_ctrl, 1, wxmod.EXPAND)
        form.Add(
            wxmod.StaticText(self._dialog, label="Alias"),
            0,
            wxmod.ALIGN_CENTER_VERTICAL,
        )
        self.alias_ctrl = wxmod.TextCtrl(self._dialog, value=alias)
        form.Add(self.alias_ctrl, 1, wxmod.EXPAND)
        root.Add(form, 0, wxmod.ALL | wxmod.EXPAND, 10)
        hint = wxmod.StaticText(
            self._dialog,
            label=(
                "Optional label for this remembered entry. "
                "It does not change the source repo or commit that will be launched. "
                "Clear the field to remove the alias."
            ),
        )
        hint.SetName(SECONDARY_WIDGET_NAME)
        hint.Wrap(520)
        self.alias_hint = hint
        root.Add(hint, 0, wxmod.LEFT | wxmod.RIGHT | wxmod.BOTTOM | wxmod.EXPAND, 10)
        root.Add(_ok_cancel_sizer(wxmod, self._dialog), 0, wxmod.ALL | wxmod.ALIGN_RIGHT, 10)
        self._dialog.SetSizerAndFit(root)
        apply_theme(self._dialog, resolve_launcher_palette())
        if parent:
            self._dialog.CentreOnParent()
        else:
            self._dialog.Centre()

    def ShowModal(self) -> int:
        return self._dialog.ShowModal()

    def Destroy(self) -> None:
        self._dialog.Destroy()

    def values(self):
        return self.alias_ctrl.GetValue()

    def alias_value(self) -> str:
        return self.alias_ctrl.GetValue()


class StatusDetailsDialog:
    def __init__(self, parent, text: str) -> None:
        wxmod = _wx()
        self._dialog = wxmod.Dialog(
            parent,
            title="Launcher details",
            style=wxmod.DEFAULT_DIALOG_STYLE | wxmod.RESIZE_BORDER,
        )
        root = wxmod.BoxSizer(wxmod.VERTICAL)
        box = wxmod.TextCtrl(
            self._dialog,
            value=text,
            style=wxmod.TE_MULTILINE | wxmod.TE_READONLY | wxmod.BORDER_SIMPLE | wxmod.HSCROLL,
        )
        box.SetMinSize((640, 420))
        self.details_ctrl = box
        root.Add(box, 1, wxmod.ALL | wxmod.EXPAND, 10)
        root.Add(
            self._dialog.CreateButtonSizer(wxmod.OK),
            0,
            wxmod.LEFT | wxmod.RIGHT | wxmod.BOTTOM | wxmod.ALIGN_RIGHT,
            10,
        )
        self._dialog.SetSizerAndFit(root)
        apply_theme(self._dialog, resolve_launcher_palette())
        if parent:
            self._dialog.CentreOnParent()
        else:
            self._dialog.Centre()

    def ShowModal(self) -> int:
        return self._dialog.ShowModal()

    def Destroy(self) -> None:
        self._dialog.Destroy()


class LauncherFrame:
    def __init__(
        self,
        backend: Optional[LauncherBackend] = None,
        palette: Optional[LauncherPalette] = None,
    ) -> None:
        wxmod = _wx()
        self.backend = backend or LauncherBackend()
        self.palette = resolve_launcher_palette(palette)
        self.recent: List[RecentDemo] = load_recent(self.backend.data_dir)
        self._working = False
        self._status_details = ""
        self._frame = wxmod.Frame(None, title=APP_NAME)
        self._frame.SetSize(FRAME_START_SIZE)
        self._frame.SetMinSize(FRAME_MIN_SIZE)
        self._frame.Centre()
        set_frame_icon(self._frame)
        panel = wxmod.Panel(self._frame, name=WINDOW_PANEL_NAME)
        self.window_panel = panel
        outer = wxmod.BoxSizer(wxmod.VERTICAL)

        self.purpose_ctrl = wxmod.StaticText(panel, label=PURPOSE_TEXT)
        self.purpose_ctrl.SetName(SECONDARY_WIDGET_NAME)
        outer.Add(self.purpose_ctrl, 0, wxmod.LEFT | wxmod.RIGHT | wxmod.TOP | wxmod.EXPAND, 10)

        self.session_box = wxmod.StaticBox(panel, label=CURRENT_STATE_LABEL)
        session = wxmod.StaticBoxSizer(self.session_box, wxmod.VERTICAL)
        self.session_panel = wxmod.Panel(self.session_box)
        session_inner = wxmod.BoxSizer(wxmod.VERTICAL)
        session_style = wxmod.TE_MULTILINE | wxmod.TE_READONLY | wxmod.BORDER_NONE
        if hasattr(wxmod, "TE_NO_VSCROLL"):
            session_style |= wxmod.TE_NO_VSCROLL
        self.session_ctrl = wxmod.TextCtrl(self.session_panel, style=session_style)
        self.session_ctrl.SetMinSize((-1, SESSION_SUMMARY_HEIGHT))
        session_inner.Add(self.session_ctrl, 1, wxmod.EXPAND)
        self.session_panel.SetSizer(session_inner)
        session.Add(self.session_panel, 1, wxmod.ALL | wxmod.EXPAND, 6)
        session_buttons = wxmod.BoxSizer(wxmod.HORIZONTAL)
        self.details_btn = wxmod.Button(self.session_box, label="Details")
        session_buttons.Add(self.details_btn, 0)
        session.Add(session_buttons, 0, wxmod.LEFT | wxmod.RIGHT | wxmod.BOTTOM | wxmod.ALIGN_RIGHT, 6)
        outer.Add(session, 0, wxmod.LEFT | wxmod.RIGHT | wxmod.TOP | wxmod.EXPAND, 10)

        self.target_box = wxmod.StaticBox(panel, label=LAUNCH_TARGET_LABEL)
        top = wxmod.StaticBoxSizer(self.target_box, wxmod.VERTICAL)
        self.home_btn = wxmod.Button(self.target_box, label=LAUNCH_OFFICIAL_RELEASE_LABEL)
        top.Add(self.home_btn, 0, wxmod.ALL, 8)
        grid = wxmod.FlexGridSizer(2, 2, 8, 8)
        grid.AddGrowableCol(1, 1)
        grid.Add(
            wxmod.StaticText(self.target_box, label="Source repo"),
            0,
            wxmod.ALIGN_CENTER_VERTICAL,
        )
        self.source_ctrl = wxmod.TextCtrl(self.target_box, value=CANONICAL_SOURCE)
        grid.Add(self.source_ctrl, 1, wxmod.EXPAND)
        grid.Add(
            wxmod.StaticText(self.target_box, label="Commit hash"),
            0,
            wxmod.ALIGN_CENTER_VERTICAL,
        )
        self.commit_ctrl = wxmod.TextCtrl(self.target_box)
        grid.Add(self.commit_ctrl, 1, wxmod.EXPAND)
        top.Add(grid, 0, wxmod.LEFT | wxmod.RIGHT | wxmod.EXPAND, 8)
        hint = wxmod.StaticText(self.target_box, label=TARGET_HINT_TEXT)
        hint.SetName(SECONDARY_WIDGET_NAME)
        self.target_hint = hint
        top.Add(hint, 0, wxmod.LEFT | wxmod.RIGHT | wxmod.TOP, 8)
        demo_row = wxmod.BoxSizer(wxmod.HORIZONTAL)
        self.demo_btn = wxmod.Button(self.target_box, label=SELECTED_COMMIT_BUTTON_LABEL)
        demo_row.Add(self.demo_btn, 0)
        top.Add(demo_row, 0, wxmod.ALL | wxmod.ALIGN_RIGHT, 8)
        outer.Add(top, 0, wxmod.LEFT | wxmod.RIGHT | wxmod.TOP | wxmod.EXPAND, 10)

        self.recent_box = wxmod.StaticBox(panel, label=REMEMBERED_COMMITS_LABEL)
        recent_box = wxmod.StaticBoxSizer(self.recent_box, wxmod.VERTICAL)
        self.recent_list = _recent_commit_list_type()(self.recent_box, self.palette)
        self.recent_list.SetMinSize((-1, RECENT_LIST_MIN_HEIGHT))
        recent_box.Add(self.recent_list, 1, wxmod.ALL | wxmod.EXPAND, 8)
        recent_buttons = wxmod.BoxSizer(wxmod.HORIZONTAL)
        self.load_recent_btn = wxmod.Button(self.recent_box, label=LOAD_TARGET_LABEL)
        self.edit_recent_btn = wxmod.Button(self.recent_box, label=EDIT_ALIAS_LABEL)
        self.remove_recent_btn = wxmod.Button(self.recent_box, label="Remove")
        recent_buttons.Add(self.load_recent_btn, 0, wxmod.RIGHT, 8)
        recent_buttons.Add(self.edit_recent_btn, 0, wxmod.RIGHT, 8)
        recent_buttons.Add(self.remove_recent_btn, 0)
        recent_box.Add(recent_buttons, 0, wxmod.ALL | wxmod.ALIGN_RIGHT, 8)
        outer.Add(recent_box, 1, wxmod.LEFT | wxmod.RIGHT | wxmod.TOP | wxmod.EXPAND, 10)

        maintenance = wxmod.BoxSizer(wxmod.HORIZONTAL)
        self.rollback_btn = wxmod.Button(panel, label=RESTORE_OFFICIAL_LABEL)
        self.refresh_btn = wxmod.Button(panel, label=REFRESH_LABEL)
        maintenance.Add(self.rollback_btn, 0, wxmod.RIGHT, 8)
        maintenance.Add(self.refresh_btn, 0)
        outer.Add(maintenance, 0, wxmod.LEFT | wxmod.RIGHT | wxmod.TOP, 10)

        self.activity_ctrl = wxmod.StaticText(panel, label="")
        self.activity_ctrl.SetName(SECONDARY_WIDGET_NAME)
        outer.Add(self.activity_ctrl, 0, wxmod.ALL | wxmod.EXPAND, 10)

        panel.SetSizer(outer)
        frame_sizer = wxmod.BoxSizer(wxmod.VERTICAL)
        frame_sizer.Add(panel, 1, wxmod.EXPAND)
        self._frame.SetSizer(frame_sizer)
        apply_theme(self._frame, self.palette)
        self.recent_list.apply_palette(self.palette)
        self._paint_session_summary()
        self._wrap_flexible_text()

        self._frame.Bind(wxmod.EVT_BUTTON, self.on_home, self.home_btn)
        self._frame.Bind(wxmod.EVT_BUTTON, self.on_demo, self.demo_btn)
        self._frame.Bind(wxmod.EVT_BUTTON, self.on_rollback, self.rollback_btn)
        self._frame.Bind(wxmod.EVT_BUTTON, self.on_refresh, self.refresh_btn)
        self._frame.Bind(wxmod.EVT_BUTTON, self.on_details, self.details_btn)
        self._frame.Bind(wxmod.EVT_BUTTON, self.on_load_recent, self.load_recent_btn)
        self._frame.Bind(wxmod.EVT_BUTTON, self.on_edit_recent, self.edit_recent_btn)
        self._frame.Bind(wxmod.EVT_BUTTON, self.on_remove_recent, self.remove_recent_btn)
        self._frame.Bind(wxmod.EVT_LISTBOX_DCLICK, self.on_load_recent, self.recent_list)
        self._frame.Bind(wxmod.EVT_LISTBOX, self.on_recent_selection, self.recent_list)
        self._frame.Bind(wxmod.EVT_TEXT, self.on_commit_text, self.commit_ctrl)
        self._frame.Bind(wxmod.EVT_SIZE, self.on_frame_size)

        self.refresh_recent_list()
        self.refresh_status()
        self._update_action_enablement()
        self._wrap_flexible_text()

    def Show(self) -> bool:
        return self._frame.Show()

    def refresh_status(self) -> None:
        try:
            status = self.backend.status()
            self.session_ctrl.SetValue(format_session_summary(status))
            self._status_details = format_status(status)
        except Exception as exc:
            self.session_ctrl.SetValue("Current State: unavailable")
            self._status_details = gui_error_text(exc)
        self.activity_ctrl.SetLabel("")
        self._paint_session_summary()

    def _paint_session_summary(self) -> None:
        wxmod = _wx()
        fill = wxmod.Colour(*self.palette.panel_bg)
        text = wxmod.Colour(*self.palette.primary_text)
        for widget in (self.session_box, self.session_panel, self.session_ctrl):
            widget.SetBackgroundColour(fill)
            widget.SetForegroundColour(text)
        self.session_panel.Refresh()
        self.session_ctrl.Refresh()

    def status_details_text(self) -> str:
        return self._status_details

    def _wrap_flexible_text(self) -> None:
        width = self.window_panel.GetClientSize().GetWidth() - 40
        if width < 200:
            width = FRAME_MIN_SIZE[0] - 60
        self.purpose_ctrl.SetLabel(PURPOSE_TEXT)
        self.purpose_ctrl.Wrap(width)
        self.target_hint.SetLabel(TARGET_HINT_TEXT)
        self.target_hint.Wrap(width)
        self.window_panel.Layout()

    def on_frame_size(self, event) -> None:
        self._wrap_flexible_text()
        event.Skip()

    def refresh_recent_list(self) -> None:
        labels = [item.html_label() for item in self.recent]
        self.recent_list.Set(labels)
        if labels:
            self.recent_list.SetSelection(0)
        self._update_action_enablement()

    def _recent_selection_index(self) -> int:
        wxmod = _wx()
        index = self.recent_list.GetSelection()
        if index == wxmod.NOT_FOUND:
            return -1
        return index

    def _update_action_enablement(self) -> None:
        if self._working:
            return
        self.demo_btn.Enable(
            selected_commit_action_enabled(self.commit_ctrl.GetValue(), False)
        )
        recent_enabled = remembered_actions_enabled(
            self._recent_selection_index(),
            len(self.recent),
            False,
        )
        self.load_recent_btn.Enable(recent_enabled)
        self.edit_recent_btn.Enable(recent_enabled)
        self.remove_recent_btn.Enable(recent_enabled)

    def _set_working(self, working: bool, message: Optional[str] = None) -> None:
        self._working = working
        ungated = (
            self.source_ctrl,
            self.commit_ctrl,
            self.home_btn,
            self.rollback_btn,
            self.refresh_btn,
            self.recent_list,
            self.details_btn,
        )
        gated = (
            self.demo_btn,
            self.load_recent_btn,
            self.edit_recent_btn,
            self.remove_recent_btn,
        )
        if working:
            for control in ungated + gated:
                control.Enable(False)
            if message:
                self.activity_ctrl.SetLabel(message)
            return
        for control in ungated:
            control.Enable(True)
        self._update_action_enablement()
        self.activity_ctrl.SetLabel("")

    def _show_error(self, message: str) -> None:
        wxmod = _wx()
        wxmod.MessageBox(message, "LabGym Launcher", wxmod.OK | wxmod.ICON_ERROR, self._frame)
        self.refresh_status()

    def _show_info(self, message: str) -> None:
        wxmod = _wx()
        wxmod.MessageBox(message, "LabGym Launcher", wxmod.OK | wxmod.ICON_INFORMATION, self._frame)
        self.refresh_status()

    def _run_background(self, work: Callable[[], object], then: Callable[[object], None]) -> None:
        wxmod = _wx()

        def worker() -> None:
            try:
                result = work()
            except Exception as exc:
                wxmod.CallAfter(self._on_background_error, exc)
                return
            wxmod.CallAfter(then, result)

        threading.Thread(target=worker, daemon=False).start()

    def _on_background_error(self, exc: BaseException) -> None:
        self._set_working(False)
        self._show_error(gui_error_text(exc))

    def _begin_select(self, selector: Callable, launch: bool) -> None:
        if self._working:
            return
        self._set_working(True, "Working... checking the requested target.")

        def work():
            selection = selector()
            launch_result = None
            if selection.outcome == ALREADY_ACTIVE and launch:
                launch_result = self.backend.launch(
                    wait=False,
                    session_class=session_class_for_action(selection.target),
                )
            return selection, launch_result

        self._run_background(
            work,
            lambda packed: self._after_select(packed[0], launch, packed[1]),
        )

    def _after_select(self, selection, launch: bool, launch_result=None) -> None:
        if selection.outcome == SESSION_BLOCKED:
            self._set_working(False)
            self.refresh_status()
            self._show_info(selection.message)
            return
        if selection.outcome == ALREADY_ACTIVE:
            self._set_working(False)
            self.refresh_status()
            if launch and launch_result is not None and launch_result.blocked:
                self._show_info(launch_result.message)
            elif launch:
                self._show_info(already_active_success_message(selection.target, True))
            else:
                self._show_info(already_active_success_message(selection.target, False))
            return
        self._after_prepare(selection.confirmation, launch)

    def _after_prepare(self, confirmation, launch: bool) -> None:
        wxmod = _wx()
        dialog = ConfirmationDialog(self._frame, confirmation_display(confirmation))
        try:
            result = dialog.ShowModal()
            approved = result == wxmod.ID_OK
        finally:
            dialog.Destroy()
        if not approved:
            self._set_working(False)
            self.refresh_status()
            return
        self._set_working(True, "Working... installing approved dependencies.")
        self._run_background(
            lambda: apply_if_approved(self.backend, confirmation, True, launch),
            lambda outcome: self._after_apply(confirmation, launch, outcome),
        )

    def _after_apply(self, confirmation, launch: bool, outcome: str) -> None:
        self._set_working(False)
        if outcome == "cancelled":
            self.refresh_status()
            return
        if outcome == "blocked":
            self.refresh_status()
            result = self.backend.last_launch_result
            message = (
                result.message
                if result is not None and result.message
                else "A LabGym session of this type is already running."
            )
            self._show_info(message)
            return
        if confirmation.action == "demo":
            self.recent = record_demo_if_needed(self.recent, confirmation)
            save_recent(self.backend.data_dir, self.recent)
            self.refresh_recent_list()
        self.refresh_status()
        if launch:
            self._show_info(applied_success_message(confirmation.action, True))
        else:
            self._show_info(applied_success_message(confirmation.action, False))

    def _selected_recent(self) -> Optional[RecentDemo]:
        wxmod = _wx()
        index = self.recent_list.GetSelection()
        if index == wxmod.NOT_FOUND or index < 0 or index >= len(self.recent):
            return None
        return self.recent[index]

    def on_home(self, event) -> None:
        self._begin_select(lambda: select_official_release(self.backend), launch=True)

    def on_demo(self, event) -> None:
        source = self.source_ctrl.GetValue().strip() or None
        commit = self.commit_ctrl.GetValue().strip()
        if not selected_commit_action_enabled(commit, self._working):
            self._show_error(GUI_EMPTY_COMMIT_ERROR)
            return

        def select():
            return select_selected_commit(self.backend, commit, source_repo=source)

        self._begin_select(select, launch=True)

    def on_rollback(self, event) -> None:
        self._begin_select(lambda: select_rollback(self.backend), launch=False)

    def on_refresh(self, event) -> None:
        self.refresh_status()

    def on_details(self, event) -> None:
        dialog = StatusDetailsDialog(self._frame, self._status_details)
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()

    def on_commit_text(self, event) -> None:
        self._update_action_enablement()
        event.Skip()

    def on_recent_selection(self, event) -> None:
        self._update_action_enablement()
        event.Skip()

    def on_load_recent(self, event) -> None:
        item = self._selected_recent()
        if not item:
            return
        self.source_ctrl.SetValue(item.source_repo)
        self.commit_ctrl.SetValue(item.commit)
        self._update_action_enablement()

    def on_use_recent(self, event) -> None:
        self.on_load_recent(event)

    def on_edit_recent(self, event) -> None:
        wxmod = _wx()
        index = self.recent_list.GetSelection()
        item = self._selected_recent()
        if item is None:
            return
        dialog = DemoEditDialog(
            self._frame,
            item.source_repo,
            item.commit,
            item.alias or "",
        )
        try:
            result = dialog.ShowModal()
            if result != wxmod.ID_OK:
                return
            alias = dialog.alias_value()
        finally:
            dialog.Destroy()
        self.recent = set_recent_alias(self.recent, index, alias)
        save_recent(self.backend.data_dir, self.recent)
        self.refresh_recent_list()

    def _make_remove_remembered_dialog(self, item: RecentDemo):
        wxmod = _wx()
        dialog = wxmod.MessageDialog(
            self._frame,
            remove_remembered_confirm_text(item.source_repo, item.commit, item.alias),
            REMOVE_REMEMBERED_TITLE,
            wxmod.YES_NO | wxmod.NO_DEFAULT | wxmod.ICON_QUESTION,
        )
        if hasattr(dialog, "SetYesNoLabels"):
            dialog.SetYesNoLabels("Remove", "Cancel")
        return dialog

    def _confirm_remove_remembered(self, item: RecentDemo) -> bool:
        wxmod = _wx()
        dialog = self._make_remove_remembered_dialog(item)
        try:
            return dialog.ShowModal() == wxmod.ID_YES
        finally:
            dialog.Destroy()

    def on_remove_recent(self, event) -> None:
        wxmod = _wx()
        index = self.recent_list.GetSelection()
        if index == wxmod.NOT_FOUND or index < 0 or index >= len(self.recent):
            return
        item = self.recent[index]
        if not self._confirm_remove_remembered(item):
            return
        self.recent = remove_recent(self.recent, index)
        save_recent(self.backend.data_dir, self.recent)
        self.refresh_recent_list()


class LauncherApp:
    def __init__(self) -> None:
        wxmod = _wx()
        self._app = wxmod.App(False)
        self._app.SetAppName(APP_NAME)
        setup_application_icons()

    def OnInit(self) -> bool:
        frame = LauncherFrame()
        frame.Show()
        return True

    def MainLoop(self) -> int:
        return int(self._app.MainLoop() or 0)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        _import_wx()
    except ImportError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1
    app = _wx().App(False)
    app.SetAppName(APP_NAME)
    setup_application_icons()
    frame = LauncherFrame()
    frame.Show()
    return int(app.MainLoop() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
