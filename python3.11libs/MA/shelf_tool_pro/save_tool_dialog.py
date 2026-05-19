"""统一工具设置对话框 ToolSettingsDialog。

两种模式：
- create: 拖入节点时创建新工具（含 shelf 文件选择）
- edit:  右键编辑已有工具（name 只读，无 shelf 文件选择）

纯 PySide6 实现，无 hou 依赖。
"""

import os
import glob
import re
import logging

from PySide6 import QtWidgets, QtGui, QtCore

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
    """返回 MAtoolbar 目录路径。"""
    return os.path.join(_MA_TOOLS_DIR, "MAtoolbar")


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

_INPUT_CONTAINER_STYLE = (
    f"background-color: {BG_INPUT};"
    f"border: 1px solid {BORDER_COLOR}; border-radius: 4px;"
)

_SUFFIX_STYLE = "color: #666666; background: transparent; padding: 0 4px; font-size: 12px;"

_DROPDOWN_BTN_STYLE = (
    f"background: transparent; border: none;"
    f"color: {ACCENT_BLUE}; font-size: 14px; padding: 0 8px;"
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

_THUMB_BG = "#2d2d2d"


def _make_thumb_pixmap(file_path: str, size: int = 100) -> QtGui.QPixmap:
    """从文件加载图片并缩放到指定尺寸，失败时返回灰色占位图。"""
    pixmap = QtGui.QPixmap(file_path)
    if pixmap.isNull():
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtGui.QColor(_THUMB_BG))
    return pixmap.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)


class ToolSettingsDialog(QtWidgets.QDialog):
    """统一工具设置对话框。

    两种模式：
    - mode="create": 拖入节点创建新工具，显示 shelf 文件选择
    - mode="edit":   右键编辑已有工具，name 只读，无 shelf 文件选择

    Args:
        mode: "create" 或 "edit"
        node_paths: 创建模式下的节点路径列表
        tool_name: 编辑模式下的当前 name（create 模式可传空字符串）
        label: 编辑模式下的当前 label（create 模式可传空字符串）
        shelf_file_path: 编辑模式下的 .shelf 文件路径
        icon_path: 编辑模式下的当前图标路径
        parent: 父级 QWidget
    """

    def __init__(
        self,
        mode: str = "create",
        node_paths: list[str] | None = None,
        tool_name: str = "",
        label: str = "",
        shelf_file_path: str = "",
        icon_path: str = "",
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)
        self._mode = mode
        self._node_paths = list(node_paths) if node_paths else []
        self._result: dict | None = None
        self._icon_path = icon_path
        self._shelf_file_path = shelf_file_path
        self._tool_name = tool_name  # edit 模式用原始名（不 strip，保留空格）
        self._preview_movie = None   # 预览 GIF 动画
        self._shelf_file_items: list[tuple[str, str]] = []  # (显示名, 完整路径)

        title = "编辑工具" if mode == "edit" else "保存工具"
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.setStyleSheet(
            f"ToolSettingsDialog {{"
            f"  background-color: {BG_PRIMARY};"
            f"  color: {TEXT_PRIMARY};"
            f"}}"
        )

        self._build_ui(tool_name, label)
        if mode == "create":
            self._load_shelf_files()
        self._connect_signals()
        self._validate_inputs()

    # ── UI 构建 ──────────────────────────────────

    def _build_ui(self, tool_name: str, label: str) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._build_name_label_section(layout, tool_name, label)
        self._build_thumb_section(layout)
        if self._mode == "create":
            self._add_separator(layout)
            self._build_shelf_section(layout)
        layout.addStretch()
        self._build_button_row(layout)

    def _build_name_label_section(self, layout: QtWidgets.QVBoxLayout,
                                   tool_name: str, label: str) -> None:
        """Name + Label 输入区域。"""
        # ── Name ──
        name_layout = QtWidgets.QVBoxLayout()
        name_layout.setSpacing(4)

        name_lbl = QtWidgets.QLabel("名称 *")
        name_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

        self._name_input = QtWidgets.QLineEdit()
        self._name_input.setText(tool_name)
        if self._mode == "edit":
            self._name_input.setReadOnly(True)
            self._name_input.setStyleSheet(_INPUT_READONLY_STYLE)
            self._name_input.setToolTip("创建后不可修改")
        else:
            self._name_input.setPlaceholderText("例如 my_custom_tool")
            self._name_input.setStyleSheet(_INPUT_STYLE)

        self._name_hint = QtWidgets.QLabel("")
        self._name_hint.setStyleSheet("color: #ef4444; font-size: 11px;")
        self._name_hint.setWordWrap(True)

        name_layout.addWidget(name_lbl)
        name_layout.addWidget(self._name_input)
        name_layout.addWidget(self._name_hint)

        # ── Label ──
        label_layout = QtWidgets.QVBoxLayout()
        label_layout.setSpacing(4)

        label_lbl = QtWidgets.QLabel("显示名称")
        label_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

        self._label_input = QtWidgets.QLineEdit()
        self._label_input.setText(label)
        self._label_input.setPlaceholderText("显示名称（支持中文）")
        self._label_input.setStyleSheet(_INPUT_STYLE)

        label_layout.addWidget(label_lbl)
        label_layout.addWidget(self._label_input)

        layout.addLayout(name_layout)
        layout.addLayout(label_layout)

    def _build_thumb_section(self, layout: QtWidgets.QVBoxLayout) -> None:
        """缩略图选择区域：点击预览图浏览文件。"""
        thumb_group = QtWidgets.QGroupBox("缩略图")
        thumb_group.setStyleSheet(_GROUPBOX_STYLE)
        group_layout = QtWidgets.QVBoxLayout(thumb_group)
        group_layout.setSpacing(10)

        # 可点击预览图
        self._thumb_preview = QtWidgets.QLabel()
        self._thumb_preview.setFixedSize(100, 100)
        self._thumb_preview.setAlignment(QtCore.Qt.AlignCenter)
        self._thumb_preview.setStyleSheet(f"background-color: {_THUMB_BG}; border-radius: 6px;")
        self._thumb_preview.setCursor(QtCore.Qt.PointingHandCursor)
        self._thumb_preview.setToolTip("点击选择图标")
        self._thumb_preview.installEventFilter(self)
        self._update_thumb_preview()

        preview_row = QtWidgets.QHBoxLayout()
        preview_row.addWidget(self._thumb_preview)
        preview_row.addStretch()
        group_layout.addLayout(preview_row)

        layout.addWidget(thumb_group)

    def _add_separator(self, layout: QtWidgets.QVBoxLayout) -> None:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {BORDER_COLOR}; max-height: 1px;")
        layout.addWidget(sep)

    def _build_shelf_section(self, layout: QtWidgets.QVBoxLayout) -> None:
        """Shelf 文件选择区域（仅 create 模式）：文件名输入 + .shelf 后缀 + 下拉菜单。"""
        shelf_group = QtWidgets.QGroupBox("工具架文件")
        shelf_group.setStyleSheet(_GROUPBOX_STYLE)
        group_layout = QtWidgets.QVBoxLayout(shelf_group)
        group_layout.setSpacing(10)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)

        lbl = QtWidgets.QLabel("保存至：")
        lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        row.addWidget(lbl)

        # 自定义输入框容器：文件名 + ".shelf" 后缀 + 蓝色倒三角按钮
        container = QtWidgets.QWidget()
        container.setStyleSheet(_INPUT_CONTAINER_STYLE)
        h = QtWidgets.QHBoxLayout(container)
        h.setContentsMargins(8, 0, 0, 0)
        h.setSpacing(0)

        self._shelf_name_edit = QtWidgets.QLineEdit()
        self._shelf_name_edit.setPlaceholderText("选择已有文件或输入名称")
        self._shelf_name_edit.setStyleSheet(
            "background: transparent; border: none; color: #ffffff;"
        )

        suffix_lbl = QtWidgets.QLabel(".shelf")
        suffix_lbl.setStyleSheet(_SUFFIX_STYLE)

        self._shelf_btn = QtWidgets.QPushButton("▾")
        self._shelf_btn.setFixedWidth(28)
        self._shelf_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._shelf_btn.setStyleSheet(_DROPDOWN_BTN_STYLE)
        self._shelf_btn.clicked.connect(self._show_shelf_menu)

        h.addWidget(self._shelf_name_edit)
        h.addWidget(suffix_lbl)
        h.addWidget(self._shelf_btn)

        row.addWidget(container)
        row.addStretch()
        group_layout.addLayout(row)
        layout.addWidget(shelf_group)

    def _build_button_row(self, layout: QtWidgets.QVBoxLayout) -> None:
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        self._save_btn = QtWidgets.QPushButton("保存")
        self._save_btn.setMinimumWidth(90)
        self._save_btn.setEnabled(self._mode == "edit")  # edit mode starts valid
        self._save_btn.setStyleSheet(_SAVE_BUTTON_STYLE)
        self._save_btn.clicked.connect(self._on_save)

        cancel_btn = QtWidgets.QPushButton("取消")
        cancel_btn.setMinimumWidth(90)
        cancel_btn.setStyleSheet(_CANCEL_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    # ── Shelf 文件扫描 ───────────────────────────

    def _load_shelf_files(self) -> None:
        """扫描 toolbar/*.shelf 填充文件列表，默认选中第一个。"""
        self._shelf_file_items = []
        self._shelf_name_edit.clear()
        tdir = _toolbar_dir()
        if not os.path.isdir(tdir):
            logger.warning("toolbar 目录不存在: %s", tdir)
            return
        items = sorted(glob.glob(os.path.join(tdir, "*.shelf")))
        for fp in items:
            stem = os.path.splitext(os.path.basename(fp))[0]
            self._shelf_file_items.append((stem, fp))
        if self._shelf_file_items:
            self._shelf_name_edit.setText(self._shelf_file_items[0][0])

    # ── 信号连接 ──────────────────────────────────

    # ── 事件过滤器（缩略图预览点击） ───────────────

    def eventFilter(self, obj, event):
        if obj is self._thumb_preview and event.type() == QtCore.QEvent.Type.MouseButtonPress:
            if event.button() == QtCore.Qt.LeftButton:
                self._on_browse_icon()
                return True
            if event.button() == QtCore.Qt.RightButton:
                self._show_thumb_context_menu(event.globalPosition().toPoint())
                return True
        return super().eventFilter(obj, event)

    def _show_thumb_context_menu(self, pos: QtCore.QPoint) -> None:
        """缩略图预览的右键菜单：清除图标。"""
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY};"
            f"  border: 1px solid {BORDER_COLOR}; border-radius: 4px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 20px; border-radius: 3px; }}"
            f"QMenu::item:selected {{ background-color: {BG_HOVER}; }}"
        )
        clear_action = menu.addAction("清除图标")
        clear_action.triggered.connect(self._on_clear_icon)
        menu.exec(pos)

    def _on_clear_icon(self) -> None:
        """清除自定义图标，恢复默认。"""
        self._icon_path = ""
        self._update_thumb_preview()

    # ── 对话框关闭时清理 GIF ──────────────────────

    def reject(self):
        self._stop_preview_movie()
        super().reject()

    def accept(self):
        self._stop_preview_movie()
        super().accept()

    def _stop_preview_movie(self):
        if self._preview_movie:
            self._preview_movie.stop()
            try:
                self._preview_movie.frameChanged.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._preview_movie.deleteLater()
            self._preview_movie = None

    def _show_shelf_menu(self) -> None:
        """点击倒三角弹出可用 .shelf 文件列表。"""
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY};"
            f"  border: 1px solid {BORDER_COLOR}; border-radius: 4px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 20px; border-radius: 3px; }}"
            f"QMenu::item:selected {{ background-color: {BG_HOVER}; }}"
        )
        for stem, _ in self._shelf_file_items:
            action = menu.addAction(stem)
            action.triggered.connect(lambda checked=False, n=stem: self._shelf_name_edit.setText(n))
        btn_pos = self._shelf_btn.mapToGlobal(QtCore.QPoint(0, self._shelf_btn.height()))
        menu.exec(btn_pos)

    def _connect_signals(self) -> None:
        self._name_input.textChanged.connect(self._validate_inputs)
        if self._mode == "create":
            self._shelf_name_edit.textChanged.connect(
                lambda: self._validate_inputs()
            )

    # ── 输入验证 ───────────────────────────────

    def _validate_inputs(self) -> None:
        name = self._name_input.text().strip()
        hint = ""
        valid = True

        if self._mode == "create":
            if not name:
                hint = "请输入工具名称"
                valid = False
            elif not _TOOL_NAME_REGEX.match(name):
                hint = "只允许字母、数字和下划线"
                valid = False

        self._name_hint.setText(hint)
        if self._mode == "create":
            self._name_input.setStyleSheet(
                _INPUT_INVALID_STYLE if (name and not valid) else _INPUT_STYLE
            )

        # Shelf file validation（create mode only）
        if valid and self._mode == "create":
            valid = bool(self._shelf_name_edit.text().strip())

        self._save_btn.setEnabled(valid)

    # ── Slot: 浏览图标 ───────────────────────────

    def _on_browse_icon(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择图标",
            "",
            "图片 (*.png *.jpg *.jpeg *.svg *.gif)",
        )
        if not file_path:
            return
        self._icon_path = file_path
        self._update_thumb_preview()

    def _update_thumb_preview(self) -> None:
        """更新缩略图预览区域：GIF 持续播放，静态图固定显示。"""
        # 清理旧动画
        self._stop_preview_movie()

        if not self._icon_path or not os.path.exists(self._icon_path):
            pixmap = QtGui.QPixmap(100, 100)
            pixmap.fill(QtGui.QColor(_THUMB_BG))
            self._thumb_preview.setPixmap(pixmap)
            return

        ext = os.path.splitext(self._icon_path)[1].lower()
        if ext == ".gif":
            # GIF：持续播放直到对话框关闭，保持宽高比
            self._preview_movie = QtGui.QMovie(self._icon_path)
            movie_size = QtGui.QImageReader(self._icon_path).size()
            if movie_size.isValid():
                scaled = movie_size.scaled(100, 100, QtCore.Qt.KeepAspectRatio)
                self._preview_movie.setScaledSize(scaled)
            else:
                self._preview_movie.setScaledSize(QtCore.QSize(100, 100))
            self._thumb_preview.setMovie(self._preview_movie)
            self._preview_movie.start()
        else:
            pixmap = _make_thumb_pixmap(self._icon_path, 100)
            self._thumb_preview.setPixmap(pixmap)

    # ── Slot: 保存 ────────────────────────────────

    def _on_save(self) -> None:
        tool_name = self._tool_name if self._mode == "edit" else self._name_input.text().strip()
        label = self._label_input.text().strip() or tool_name

        if self._mode == "create":
            name = self._shelf_name_edit.text().strip()
            # 匹配已有项则用完整路径，否则拼 toolbar/ 路径
            shelf_file = next(
                (path for stem, path in self._shelf_file_items if stem == name),
                os.path.join(_toolbar_dir(), name + ".shelf"),
            )
        else:
            shelf_file = self._shelf_file_path

        self._result = {
            "tool_name": tool_name,
            "label": label,
            "icon_path": self._icon_path,
            "shelf_file": shelf_file,
            "node_paths": list(self._node_paths),
        }
        self.accept()

    # ── 公共接口 ──────────────────────────────────

    def get_result(self) -> dict | None:
        """返回用户输入的信息字典，取消则返回 None。

        Returns:
            dict: {
                "tool_name": str,
                "label": str,
                "icon_path": str,
                "shelf_file": str,     # 目标 .shelf 文件路径
                "node_paths": list[str],
            }
            None 如果用户取消对话框。
        """
        if self.result() == QtWidgets.QDialog.DialogCode.Accepted:
            return self._result
        return None


# ── 兼容别名 ──────────────────────────────────
SaveToolDialog = ToolSettingsDialog
