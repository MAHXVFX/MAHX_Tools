"""自定义保存对话框 SaveToolDialog。

纯 PySide6 实现，无 hou 依赖，收集用户输入的 tool 元数据。
"""

import os
import glob
import re
import logging

from PySide6 import QtWidgets

from MA.shelf_tool_pro.styles import (
    ACCENT_BLUE,
    BG_PRIMARY,
    BG_INPUT,
    BG_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BORDER_COLOR,
)

logger = logging.getLogger("MA")

# ── 项目路径辅助 ──────────────────────────────

from MA.common.constants import _MA_TOOLS_DIR


def _toolbar_dir() -> str:
    """返回 toolbar 目录路径。"""
    return os.path.join(_MA_TOOLS_DIR, "toolbar")


from MA.shelf_tool_pro.shelf_saver import _VALID_TOOL_NAME_RE as _TOOL_NAME_REGEX

# ── 样式常量 ──────────────────────────────────

def _lineedit_style(border_color: str, text_color: str = TEXT_PRIMARY,
                     focus_color: str | None = None) -> str:
    focus = f"QLineEdit:focus {{ border-color: {focus_color}; }}" if focus_color else ""
    return (
        f"QLineEdit {{"
        f"  background-color: {BG_INPUT};"
        f"  color: {text_color};"
        f"  border: 1px solid {border_color};"
        f"  border-radius: 4px;"
        f"  padding: 6px;"
        f"}}{focus}"
    )


_INPUT_STYLE = _lineedit_style(BORDER_COLOR, focus_color=ACCENT_BLUE)
_INPUT_INVALID_STYLE = _lineedit_style("#ef4444")
_INPUT_READONLY_STYLE = _lineedit_style(BORDER_COLOR, TEXT_SECONDARY)

_BROWSE_BUTTON_STYLE = (
    f"QPushButton {{"
    f"  background-color: {BG_INPUT};"
    f"  color: {TEXT_PRIMARY};"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  border-radius: 4px;"
    f"  padding: 6px 12px;"
    f"}}"
    f"QPushButton:hover {{ background-color: {BG_HOVER}; }}"
)

_RADIO_STYLE = (
    f"QRadioButton {{"
    f"  color: {TEXT_PRIMARY};"
    f"  font-size: 12px;"
    f"  spacing: 6px;"
    f"}}"
    f"QRadioButton::indicator {{"
    f"  width: 14px; height: 14px;"
    f"  border-radius: 7px;"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  background-color: {BG_INPUT};"
    f"}}"
    f"QRadioButton::indicator:checked {{"
    f"  background-color: {ACCENT_BLUE};"
    f"  border-color: {ACCENT_BLUE};"
    f"}}"
)

_COMBO_STYLE = (
    f"QComboBox {{"
    f"  background-color: {BG_INPUT};"
    f"  color: {TEXT_PRIMARY};"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  border-radius: 4px;"
    f"  padding: 6px;"
    f"}}"
    f"QComboBox:hover {{ border-color: {BG_HOVER}; }}"
    f"QComboBox::drop-down {{ border: none; width: 20px; }}"
    f"QComboBox QAbstractItemView {{"
    f"  background-color: {BG_INPUT};"
    f"  color: {TEXT_PRIMARY};"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  selection-background-color: {BG_HOVER};"
    f"}}"
)

_SAVE_BUTTON_STYLE = (
    f"QPushButton {{"
    f"  background-color: {ACCENT_BLUE};"
    f"  color: white;"
    f"  border-radius: 6px;"
    f"  padding: 8px 20px;"
    f"}}"
    f"QPushButton:hover {{ background-color: #0e77b8; }}"
    f"QPushButton:disabled {{"
    f"  background-color: #3a3a3a;"
    f"  color: #666666;"
    f"}}"
)

_CANCEL_BUTTON_STYLE = (
    f"QPushButton {{"
    f"  background-color: {BG_INPUT};"
    f"  color: {TEXT_SECONDARY};"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  border-radius: 6px;"
    f"  padding: 8px 20px;"
    f"}}"
    f"QPushButton:hover {{"
    f"  background-color: {BG_HOVER};"
    f"  color: {TEXT_PRIMARY};"
    f"}}"
)

_GROUPBOX_STYLE = (
    f"QGroupBox {{"
    f"  color: {TEXT_SECONDARY};"
    f"  font-size: 12px;"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  border-radius: 6px;"
    f"  margin-top: 12px;"
    f"  padding: 16px 12px 12px 12px;"
    f"}}"
    f"QGroupBox::title {{"
    f"  subcontrol-origin: margin;"
    f"  left: 12px;"
    f"  padding: 0 4px;"
    f"}}"
)


class SaveToolDialog(QtWidgets.QDialog):
    """自定义保存 Shelf Tool 对话框。

    收集用户输入的 tool name、label、icon、shelf 文件路径等信息，
    不包含任何 .shelf 写入逻辑。

    Args:
        node_paths: 要保存的节点路径列表（只读引用）。
        parent: 父级 QWidget。
    """

    def __init__(self, node_paths: list[str], parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._node_paths = list(node_paths)
        self._result: dict | None = None
        self._icon_path: str = ""

        self.setWindowTitle("Save Shelf Tool")
        self.setMinimumWidth(500)
        self.setStyleSheet(
            f"SaveToolDialog {{"
            f"  background-color: {BG_PRIMARY};"
            f"  color: {TEXT_PRIMARY};"
            f"}}"
        )

        self._build_ui()
        self._load_shelf_files()
        self._connect_signals()
        self._validate_name()

    # ── UI 构建 ──────────────────────────────────

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._build_name_section(layout)
        self._build_icon_section(layout)
        self._add_separator(layout)
        self._build_shelf_section(layout)
        layout.addStretch()
        self._build_button_row(layout)

    def _build_name_section(self, layout: QtWidgets.QVBoxLayout) -> None:
        name_layout = QtWidgets.QVBoxLayout()
        name_layout.setSpacing(4)

        lbl = QtWidgets.QLabel("Tool Name *")
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

        self._name_input = QtWidgets.QLineEdit()
        self._name_input.setPlaceholderText("e.g. my_custom_tool")
        self._name_input.setStyleSheet(_INPUT_STYLE)

        self._name_hint = QtWidgets.QLabel("")
        self._name_hint.setStyleSheet("color: #ef4444; font-size: 11px;")
        self._name_hint.setWordWrap(True)

        name_layout.addWidget(lbl)
        name_layout.addWidget(self._name_input)
        name_layout.addWidget(self._name_hint)
        layout.addLayout(name_layout)

    def _build_icon_section(self, layout: QtWidgets.QVBoxLayout) -> None:
        icon_layout = QtWidgets.QHBoxLayout()
        icon_layout.setSpacing(8)

        lbl = QtWidgets.QLabel("Icon")
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        lbl.setFixedWidth(30)

        self._icon_input = QtWidgets.QLineEdit()
        self._icon_input.setReadOnly(True)
        self._icon_input.setPlaceholderText("No icon selected")
        self._icon_input.setStyleSheet(_INPUT_READONLY_STYLE)

        browse_btn = QtWidgets.QPushButton("Browse\u2026")
        browse_btn.setFixedWidth(80)
        browse_btn.setStyleSheet(_BROWSE_BUTTON_STYLE)
        browse_btn.clicked.connect(self._on_browse_icon)

        icon_layout.addWidget(lbl)
        icon_layout.addWidget(self._icon_input)
        icon_layout.addWidget(browse_btn)
        layout.addLayout(icon_layout)

    def _add_separator(self, layout: QtWidgets.QVBoxLayout) -> None:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {BORDER_COLOR}; max-height: 1px;")
        layout.addWidget(sep)

    def _build_shelf_section(self, layout: QtWidgets.QVBoxLayout) -> None:
        shelf_group = QtWidgets.QGroupBox("Shelf File")
        shelf_group.setStyleSheet(_GROUPBOX_STYLE)
        group_layout = QtWidgets.QVBoxLayout(shelf_group)
        group_layout.setSpacing(10)

        # Append to existing
        self._append_radio = QtWidgets.QRadioButton("Append to:")
        self._append_radio.setChecked(True)
        self._append_radio.setStyleSheet(_RADIO_STYLE)

        self._shelf_combo = QtWidgets.QComboBox()
        self._shelf_combo.setMinimumWidth(200)
        self._shelf_combo.setStyleSheet(_COMBO_STYLE)

        append_row = QtWidgets.QHBoxLayout()
        append_row.setSpacing(8)
        append_row.addWidget(self._append_radio)
        append_row.addWidget(self._shelf_combo)
        append_row.addStretch()
        group_layout.addLayout(append_row)

        # New file
        self._new_radio = QtWidgets.QRadioButton("New file:")
        self._new_radio.setStyleSheet(_RADIO_STYLE)

        self._new_file_input = QtWidgets.QLineEdit()
        self._new_file_input.setPlaceholderText("Select location for new .shelf file\u2026")
        self._new_file_input.setReadOnly(True)
        self._new_file_input.setEnabled(False)
        self._new_file_input.setStyleSheet(_INPUT_READONLY_STYLE)

        new_browse_btn = QtWidgets.QPushButton("Browse\u2026")
        new_browse_btn.setFixedWidth(80)
        new_browse_btn.setStyleSheet(_BROWSE_BUTTON_STYLE)
        new_browse_btn.clicked.connect(self._on_browse_new_shelf)

        new_row = QtWidgets.QHBoxLayout()
        new_row.setSpacing(8)
        new_row.addWidget(self._new_radio)
        new_row.addWidget(self._new_file_input)
        new_row.addWidget(new_browse_btn)
        group_layout.addLayout(new_row)

        layout.addWidget(shelf_group)

    def _build_button_row(self, layout: QtWidgets.QVBoxLayout) -> None:
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setMinimumWidth(90)
        cancel_btn.setStyleSheet(_CANCEL_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)

        self._save_btn = QtWidgets.QPushButton("Save")
        self._save_btn.setMinimumWidth(90)
        self._save_btn.setEnabled(False)
        self._save_btn.setStyleSheet(_SAVE_BUTTON_STYLE)
        self._save_btn.clicked.connect(self._on_save)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self._save_btn)
        layout.addLayout(btn_layout)

    # ── Shelf 文件扫描 ───────────────────────────

    def _load_shelf_files(self) -> None:
        """扫描 toolbar/*.shelf 填充下拉框。"""
        self._shelf_combo.clear()
        tdir = _toolbar_dir()
        if not os.path.isdir(tdir):
            logger.warning("toolbar 目录不存在: %s", tdir)
            return
        for fp in sorted(glob.glob(os.path.join(tdir, "*.shelf"))):
            self._shelf_combo.addItem(os.path.basename(fp), fp)

    # ── 信号连接 ──────────────────────────────────

    def _connect_signals(self) -> None:
        self._name_input.textChanged.connect(self._validate_name)
        self._append_radio.toggled.connect(
            lambda checked: checked and self._on_shelf_mode_changed()
        )
        self._shelf_combo.currentIndexChanged.connect(
            lambda: self._update_save_button()
        )

    # ── Slot: 名字验证 ───────────────────────────

    def _validate_name(self) -> None:
        name = self._name_input.text().strip()
        hint = ""
        valid = True

        if not name:
            hint = "Tool name is required"
            valid = False
        elif not _TOOL_NAME_REGEX.match(name):
            hint = "Only letters, numbers, and underscores allowed"
            valid = False

        self._name_hint.setText(hint)
        self._name_input.setStyleSheet(
            _INPUT_INVALID_STYLE if (name and not valid) else _INPUT_STYLE
        )
        self._name_input.setProperty("_valid", valid)
        self._update_save_button()

    # ── Slot: 保存按钮状态 ──────────────────────

    def _update_save_button(self) -> None:
        name = self._name_input.text().strip()
        can_save = bool(_TOOL_NAME_REGEX.match(name))

        if can_save:
            if self._append_radio.isChecked():
                can_save = self._shelf_combo.count() > 0
            else:
                can_save = bool(self._new_file_input.text().strip())

        self._save_btn.setEnabled(can_save)

    # ── Slot: Shelf 模式切换 ─────────────────────

    def _on_shelf_mode_changed(self) -> None:
        is_append = self._append_radio.isChecked()
        self._shelf_combo.setEnabled(is_append)
        self._new_file_input.setEnabled(not is_append)
        self._update_save_button()

    # ── Slot: 浏览图标 ───────────────────────────

    def _on_browse_icon(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Icon",
            "",
            "Images (*.png *.jpg *.svg *.jpeg)",
        )
        if file_path:
            self._icon_path = file_path
            self._icon_input.setText(os.path.basename(file_path))

    # ── Slot: 浏览新建 Shelf 文件 ────────────────

    def _on_browse_new_shelf(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Create Shelf File",
            "",
            "Shelf Files (*.shelf)",
        )
        if file_path:
            if not file_path.lower().endswith(".shelf"):
                file_path += ".shelf"
            self._new_file_input.setText(file_path)
            self._update_save_button()

    # ── Slot: 保存 ────────────────────────────────

    def _on_save(self) -> None:
        tool_name = self._name_input.text().strip()

        if self._append_radio.isChecked():
            shelf_file: str = self._shelf_combo.currentData()
            is_new_file = False
        else:
            shelf_file = self._new_file_input.text().strip()
            is_new_file = True

        self._result = {
            "tool_name": tool_name,
            "label": tool_name,
            "icon_path": self._icon_path,
            "shelf_file": shelf_file,
            "is_new_file": is_new_file,
            "node_paths": list(self._node_paths),
        }
        self.accept()

    # ── 公共接口 ──────────────────────────────────

    def get_result(self) -> dict | None:
        """返回用户输入的信息字典，取消则返回 None。

        Returns:
            dict: {
                "tool_name": str,
                "label": str,          # == tool_name (保留兼容)
                "icon_path": str,
                "shelf_file": str,     # 目标 .shelf 文件路径
                "is_new_file": bool,   # True=新建文件, False=追加到已有
                "node_paths": list[str],
            }
            None 如果用户取消对话框。
        """
        if self.result() == QtWidgets.QDialog.DialogCode.Accepted:
            return self._result
        return None
