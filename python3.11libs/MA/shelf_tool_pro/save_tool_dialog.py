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
    BG_SECONDARY,
    BG_INPUT,
    BG_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    BORDER_COLOR,
)
from MA.shelf_tool_pro.python_code_editor import PythonCodeEdit

logger = logging.getLogger("MA")

# ── 项目路径辅助 ──────────────────────────────

from MA.common.constants import _MA_TOOLS_DIR


def _toolbar_dir() -> str:
    """返回 MAtoolbar 目录路径。"""
    return os.path.join(_MA_TOOLS_DIR, "MAtoolbar")


from MA.shelf_tool_pro.shelf_saver import validate_tool_name
from MA.shelf_tool_pro.shelf_loader import _TOOL_REGISTRY

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
    - mode="edit":   右键编辑已有工具，name 只读，含首选项和内容两个标签页

    Args:
        mode: "create" 或 "edit"
        node_paths: 创建模式下的节点路径列表
        tool_name: 编辑模式下的当前 name（create 模式可传空字符串）
        label: 编辑模式下的当前 label（create 模式可传空字符串）
        shelf_file_path: 编辑模式下的 .shelf 文件路径
        icon_path: 编辑模式下的当前图标路径
        script_content: 编辑模式下的工具脚本内容（create 模式可传空字符串）
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
        script_content: str = "",
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
        self._script_content = script_content  # 工具脚本内容
        
        # 保存原始值用于变更检测（编辑模式）
        self._original_tool_name = tool_name
        self._original_label = label
        self._original_icon_path = icon_path
        self._original_script_content = script_content

        title = "编辑工具" if mode == "edit" else "保存工具"
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)
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

        # 统一使用 QTabWidget 双标签页
        self._tab_widget = QtWidgets.QTabWidget()
        self._tab_widget.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {BORDER_COLOR}; border-radius: 4px; background-color: {BG_SECONDARY}; }}"
            f"QTabBar::tab {{ background-color: {BG_PRIMARY}; color: {TEXT_SECONDARY}; "
            f"padding: 8px 20px; border: 1px solid {BORDER_COLOR}; border-bottom: none; "
            f"border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }}"
            f"QTabBar::tab:selected {{ background-color: {BG_SECONDARY}; color: {TEXT_PRIMARY}; "
            f"border-top: 2px solid {ACCENT_BLUE}; }}"
            f"QTabBar::tab:hover {{ background-color: {BG_HOVER}; color: {TEXT_PRIMARY}; }}"
        )

        # 标签页 1：首选项
        prefs_tab = QtWidgets.QWidget()
        prefs_layout = QtWidgets.QVBoxLayout(prefs_tab)
        prefs_layout.setSpacing(12)
        prefs_layout.setContentsMargins(16, 16, 16, 16)
        self._build_name_label_section(prefs_layout, tool_name, label)
        self._build_thumb_section(prefs_layout)
        if self._mode == "create":
            self._build_shelf_section(prefs_layout)
        prefs_layout.addStretch()
        self._tab_widget.addTab(prefs_tab, "首选项")

        # 标签页 2：内容
        content_tab = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_tab)
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(16, 16, 16, 16)

        self._code_edit = PythonCodeEdit()
        self._code_edit.setPlainText(self._script_content)
        self._code_edit.setMinimumHeight(200)
        content_layout.addWidget(self._code_edit)

        hint_text = "输入要执行的 Python 代码，支持 Houdini Python API" if self._mode == "create" else "工具的 Python 脚本代码（保存后更新 .shelf 文件）"
        hint_lbl = QtWidgets.QLabel(hint_text)
        hint_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        content_layout.addWidget(hint_lbl)

        self._tab_widget.addTab(content_tab, "内容")

        layout.addWidget(self._tab_widget, 1)
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

        btn_text = "创建" if self._mode == "create" else "保存"
        self._save_btn = QtWidgets.QPushButton(btn_text)
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
        self._validate_inputs()

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
            # 显式清空文件名释放文件句柄（Windows 文件锁定问题）
            self._preview_movie.setFileName("")
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
        self._label_input.textChanged.connect(self._validate_inputs)
        if self._mode == "create":
            self._shelf_name_edit.textChanged.connect(
                lambda: self._validate_inputs()
            )
        # 代码编辑器变更触发验证（两种模式都有）
        if self._code_edit is not None:
            self._code_edit.textChanged.connect(self._validate_inputs)

    # ── 输入验证 ───────────────────────────────

    def _validate_inputs(self) -> None:
        name = self._name_input.text().strip()
        hint = ""
        valid = True

        if not name:
            hint = "请输入工具名称"
            valid = False
        else:
            error = validate_tool_name(name)
            if error:
                hint = error
                valid = False
            else:
                # 检查同 shelf 中是否已存在同名工具
                # 确定目标 shelf 文件
                if self._mode == "create":
                    shelf_name = self._shelf_name_edit.text().strip()
                    shelf_file = next(
                        (path for stem, path in self._shelf_file_items if stem == shelf_name),
                        os.path.join(_toolbar_dir(), shelf_name + ".shelf"),
                    )
                else:
                    shelf_file = self._shelf_file_path
                
                # 检查是否重名（编辑模式下排除自身）
                for uid, info in _TOOL_REGISTRY.items():
                    shelf_stem, tool_name, _, _, reg_shelf_path = info
                    if tool_name == name and reg_shelf_path == shelf_file:
                        # 编辑模式下，如果名称没变则允许
                        if self._mode == "edit" and self._tool_name == name:
                            continue
                        hint = f"同名工具已存在于 {os.path.basename(shelf_file)}"
                        valid = False
                        break

        self._name_hint.setText(hint)
        self._name_input.setStyleSheet(
            _INPUT_INVALID_STYLE if (name and not valid) else _INPUT_STYLE
        )

        # Shelf file validation（create mode only）
        if valid and self._mode == "create":
            valid = bool(self._shelf_name_edit.text().strip())
        
        # 代码非空检查（两种模式都检查）
        if valid and self._code_edit is not None:
            if not self._code_edit.toPlainText().strip():
                valid = False
        
        # 编辑模式下，检查是否有变更
        if valid and self._mode == "edit":
            has_changes = self._has_changes()
            valid = has_changes

        self._save_btn.setEnabled(valid)
    
    def _has_changes(self) -> bool:
        """检查编辑模式下是否有变更。"""
        if self._mode != "edit":
            return True
        
        # 检查名称是否变化
        current_name = self._name_input.text().strip()
        if current_name != self._original_tool_name:
            return True
        
        # 检查显示名称是否变化
        current_label = self._label_input.text().strip()
        if current_label != self._original_label:
            return True
        
        # 检查图标是否变化
        if self._icon_path != self._original_icon_path:
            return True
        
        # 检查脚本代码是否变化
        if self._code_edit is not None:
            current_script = self._code_edit.toPlainText()
            if current_script != self._original_script_content:
                return True
        
        return False

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
        self._validate_inputs()

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
        # 先停止预览动画，释放 GIF 文件锁（Windows 下 QMovie 会锁定文件）
        self._stop_preview_movie()

        tool_name = self._name_input.text().strip()
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
            "code": self._code_edit.toPlainText() if self._code_edit is not None else "",
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
                "code": str,           # 工具脚本代码
            }
            None 如果用户取消对话框。
        """
        if self.result() == QtWidgets.QDialog.DialogCode.Accepted:
            return self._result
        return None


# ── 兼容别名 ──────────────────────────────────
SaveToolDialog = ToolSettingsDialog
