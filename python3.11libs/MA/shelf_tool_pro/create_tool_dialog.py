"""创建工具对话框 - 从 Python 代码创建 shelf 工具。

两步流程：
1. 输入 Python 代码（带语法高亮）
2. 设置工具属性（名称、显示名称、shelf 文件、缩略图）
"""

import os
import glob
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
    GROUPBOX_STYLE,
    INPUT_STYLE,
    INPUT_INVALID_STYLE,
    DROPDOWN_BTN_STYLE,
    INPUT_CONTAINER_STYLE,
    SUFFIX_STYLE,
    SAVE_BUTTON_STYLE,
    CANCEL_BUTTON_STYLE,
    THUMB_BG,
)
from MA.shelf_tool_pro.python_code_editor import PythonCodeEdit

logger = logging.getLogger("MA")

# ── 项目路径辅助 ──────────────────────────────

from MA.common.constants import _MA_TOOLS_DIR


def _toolbar_dir() -> str:
    """返回 MAtoolbar 目录路径。"""
    return os.path.join(_MA_TOOLS_DIR, "MAtoolbar")


from MA.shelf_tool_pro.shelf_saver import validate_tool_name

# ── 样式常量（使用 styles.py 中的统一定义） ──────

_THUMB_BG = THUMB_BG


def _make_thumb_pixmap(file_path: str, size: int = 100) -> QtGui.QPixmap:
    """从文件加载图片并缩放到指定尺寸，失败时返回灰色占位图。"""
    pixmap = QtGui.QPixmap(file_path)
    if pixmap.isNull():
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtGui.QColor(_THUMB_BG))
    return pixmap.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)


class CreateToolDialog(QtWidgets.QDialog):
    """创建工具对话框。

    用户输入 Python 代码后，点击"下一步"进入工具属性设置。
    最终返回代码和工具属性信息。

    Args:
        parent: 父级 QWidget
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._result: dict | None = None
        self._icon_path = ""
        self._preview_movie = None
        self._shelf_file_items: list[tuple[str, str]] = []  # (显示名, 完整路径)

        self.setWindowTitle("创建工具")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(
            f"CreateToolDialog {{"
            f"  background-color: {BG_PRIMARY};"
            f"  color: {TEXT_PRIMARY};"
            f"}}"
        )

        self._build_ui()
        self._load_shelf_files()
        self._connect_signals()
        self._validate_inputs()

    # ── UI 构建 ──────────────────────────────────

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 代码编辑区域
        code_group = QtWidgets.QGroupBox("Python 代码")
        code_group.setStyleSheet(GROUPBOX_STYLE)
        code_layout = QtWidgets.QVBoxLayout(code_group)
        code_layout.setSpacing(8)

        self._code_edit = PythonCodeEdit()
        self._code_edit.setPlaceholderText("# 在此输入 Python 代码\nimport hou\n\n# 创建节点\nnode = hou.node('/obj').createNode('geo', 'my_geo')")
        self._code_edit.setMinimumHeight(200)
        code_layout.addWidget(self._code_edit)

        # 代码提示
        hint_lbl = QtWidgets.QLabel("输入要执行的 Python 代码，支持 Houdini Python API")
        hint_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        code_layout.addWidget(hint_lbl)

        layout.addWidget(code_group, 1)  # 代码区域占据剩余空间

        # 工具属性区域
        props_group = QtWidgets.QGroupBox("工具属性")
        props_group.setStyleSheet(GROUPBOX_STYLE)
        props_layout = QtWidgets.QVBoxLayout(props_group)
        props_layout.setSpacing(8)

        # 名称输入
        name_layout = QtWidgets.QVBoxLayout()
        name_layout.setSpacing(4)

        name_lbl = QtWidgets.QLabel("名称 *")
        name_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        name_layout.addWidget(name_lbl)

        self._name_input = QtWidgets.QLineEdit()
        self._name_input.setPlaceholderText("例如 my_custom_tool")
        self._name_input.setStyleSheet(INPUT_STYLE)
        name_layout.addWidget(self._name_input)

        self._name_hint = QtWidgets.QLabel("")
        self._name_hint.setStyleSheet("color: #ef4444; font-size: 11px;")
        self._name_hint.setWordWrap(True)
        name_layout.addWidget(self._name_hint)

        props_layout.addLayout(name_layout)

        # 显示名称输入
        label_layout = QtWidgets.QVBoxLayout()
        label_layout.setSpacing(4)

        label_lbl = QtWidgets.QLabel("显示名称")
        label_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        label_layout.addWidget(label_lbl)

        self._label_input = QtWidgets.QLineEdit()
        self._label_input.setPlaceholderText("显示名称（支持中文）")
        self._label_input.setStyleSheet(INPUT_STYLE)
        label_layout.addWidget(self._label_input)

        props_layout.addLayout(label_layout)

        # Shelf 文件选择
        shelf_layout = QtWidgets.QHBoxLayout()
        shelf_layout.setSpacing(8)

        shelf_lbl = QtWidgets.QLabel("保存至：")
        shelf_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        shelf_layout.addWidget(shelf_lbl)

        container = QtWidgets.QWidget()
        container.setStyleSheet(INPUT_CONTAINER_STYLE)
        h = QtWidgets.QHBoxLayout(container)
        h.setContentsMargins(8, 0, 0, 0)
        h.setSpacing(0)

        self._shelf_name_edit = QtWidgets.QLineEdit()
        self._shelf_name_edit.setPlaceholderText("选择已有文件或输入名称")
        self._shelf_name_edit.setStyleSheet(
            "background: transparent; border: none; color: #ffffff;"
        )

        suffix_lbl = QtWidgets.QLabel(".shelf")
        suffix_lbl.setStyleSheet(SUFFIX_STYLE)

        self._shelf_btn = QtWidgets.QPushButton("▾")
        self._shelf_btn.setFixedWidth(28)
        self._shelf_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._shelf_btn.setStyleSheet(DROPDOWN_BTN_STYLE)
        self._shelf_btn.clicked.connect(self._show_shelf_menu)

        h.addWidget(self._shelf_name_edit)
        h.addWidget(suffix_lbl)
        h.addWidget(self._shelf_btn)

        shelf_layout.addWidget(container)
        shelf_layout.addStretch()
        props_layout.addLayout(shelf_layout)

        # 缩略图选择
        thumb_layout = QtWidgets.QVBoxLayout()
        thumb_layout.setSpacing(4)

        thumb_lbl = QtWidgets.QLabel("缩略图")
        thumb_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        thumb_layout.addWidget(thumb_lbl)

        # 可点击预览图
        self._thumb_preview = QtWidgets.QLabel()
        self._thumb_preview.setFixedSize(100, 100)
        self._thumb_preview.setAlignment(QtCore.Qt.AlignCenter)
        self._thumb_preview.setStyleSheet(f"background-color: {_THUMB_BG}; border-radius: 6px;")
        self._thumb_preview.setCursor(QtCore.Qt.PointingHandCursor)
        self._thumb_preview.setToolTip("点击选择图标（可选）")
        self._thumb_preview.installEventFilter(self)
        self._update_thumb_preview()

        preview_row = QtWidgets.QHBoxLayout()
        preview_row.addWidget(self._thumb_preview)
        preview_row.addStretch()
        thumb_layout.addLayout(preview_row)

        props_layout.addLayout(thumb_layout)

        layout.addWidget(props_group)

        # 按钮区域
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        self._create_btn = QtWidgets.QPushButton("创建")
        self._create_btn.setMinimumWidth(90)
        self._create_btn.setEnabled(False)
        self._create_btn.setStyleSheet(SAVE_BUTTON_STYLE)
        self._create_btn.clicked.connect(self._on_create)

        cancel_btn = QtWidgets.QPushButton("取消")
        cancel_btn.setMinimumWidth(90)
        cancel_btn.setStyleSheet(CANCEL_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self._create_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _load_shelf_files(self):
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

    def _show_shelf_menu(self):
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

    def _connect_signals(self):
        """连接信号。"""
        self._name_input.textChanged.connect(self._validate_inputs)
        self._shelf_name_edit.textChanged.connect(self._validate_inputs)
        self._code_edit.textChanged.connect(self._validate_inputs)

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
            # 显式清空文件名释放文件句柄（Windows 文件锁定问题）
            self._preview_movie.setFileName("")
            self._preview_movie.deleteLater()
            self._preview_movie = None

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

    def _validate_inputs(self):
        """验证输入。"""
        name = self._name_input.text().strip()
        hint = ""
        valid = True

        # 检查代码是否为空
        code = self._code_edit.toPlainText().strip()
        if not code:
            valid = False

        # 检查名称
        if not name:
            hint = "请输入工具名称"
            valid = False
        else:
            error = validate_tool_name(name)
            if error:
                hint = error
                valid = False
            else:
                # 检查是否重名（同时检查已加载的注册表和 .shelf 文件）
                from MA.shelf_tool_pro.shelf_loader import _TOOL_REGISTRY
                from MA.shelf_tool_pro.shelf_saver import check_name_conflict
                shelf_name = self._shelf_name_edit.text().strip()
                shelf_file = next(
                    (path for stem, path in self._shelf_file_items if stem == shelf_name),
                    os.path.join(_toolbar_dir(), shelf_name + ".shelf"),
                )
                
                # 检查已加载的注册表
                for uid, info in _TOOL_REGISTRY.items():
                    _, tool_name, _, _, reg_shelf_path = info
                    if tool_name == name and reg_shelf_path == shelf_file:
                        hint = f"同名工具已存在于 {os.path.basename(shelf_file)}"
                        valid = False
                        break
                
                # 检查 .shelf 文件（防止未加载的工具）
                if valid and check_name_conflict(name, shelf_file):
                    hint = f"同名工具已存在于 {os.path.basename(shelf_file)}"
                    valid = False

        self._name_hint.setText(hint)
        self._name_input.setStyleSheet(
            INPUT_INVALID_STYLE if (name and hint) else INPUT_STYLE
        )

        # 检查 shelf 文件
        if valid:
            valid = bool(self._shelf_name_edit.text().strip())

        self._create_btn.setEnabled(valid)

    def _on_create(self):
        """点击创建按钮。"""
        # 先停止预览动画，释放 GIF 文件锁
        self._stop_preview_movie()

        code = self._code_edit.toPlainText().strip()
        tool_name = self._name_input.text().strip()
        label = self._label_input.text().strip() or tool_name

        shelf_name = self._shelf_name_edit.text().strip()
        shelf_file = next(
            (path for stem, path in self._shelf_file_items if stem == shelf_name),
            os.path.join(_toolbar_dir(), shelf_name + ".shelf"),
        )

        self._result = {
            "code": code,
            "tool_name": tool_name,
            "label": label,
            "shelf_file": shelf_file,
            "icon_path": self._icon_path,
        }
        self.accept()

    def get_result(self) -> dict | None:
        """返回创建结果。

        Returns:
            dict: {
                "code": str,           # Python 代码
                "tool_name": str,      # 工具名称
                "label": str,          # 显示名称
                "shelf_file": str,     # .shelf 文件路径
                "icon_path": str,      # 缩略图路径（可选）
            }
            None 如果用户取消对话框。
        """
        if self.result() == QtWidgets.QDialog.DialogCode.Accepted:
            return self._result
        return None
