"""创建工具对话框 - 从 Python 代码创建 shelf 工具。

两步流程：
1. 输入 Python 代码（带语法高亮）
2. 设置工具属性（名称、显示名称、shelf 文件）
"""

import os
import glob
import logging

from PySide6 import QtWidgets, QtCore

from MA.shelf_tool_pro.styles import (
    ACCENT_BLUE,
    BG_PRIMARY,
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


from MA.shelf_tool_pro.shelf_saver import _VALID_TOOL_NAME_RE as _TOOL_NAME_REGEX

# ── 样式常量 ──────────────────────────────────

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

_INPUT_STYLE = (
    f"QLineEdit {{"
    f"  background-color: {BG_INPUT};"
    f"  color: {TEXT_PRIMARY};"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  border-radius: 4px;"
    f"  padding: 6px;"
    f"}}"
    f"QLineEdit:focus {{ border-color: {ACCENT_BLUE}; }}"
)

_INPUT_INVALID_STYLE = (
    f"QLineEdit {{"
    f"  background-color: {BG_INPUT};"
    f"  color: {TEXT_PRIMARY};"
    f"  border: 1px solid #ef4444;"
    f"  border-radius: 4px;"
    f"  padding: 6px;"
    f"}}"
)

_DROPDOWN_BTN_STYLE = (
    f"background: transparent; border: none;"
    f"color: {ACCENT_BLUE}; font-size: 14px; padding: 0 8px;"
)

_INPUT_CONTAINER_STYLE = (
    f"background-color: {BG_INPUT};"
    f"border: 1px solid {BORDER_COLOR}; border-radius: 4px;"
)

_SUFFIX_STYLE = "color: #666666; background: transparent; padding: 0 4px; font-size: 12px;"

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
        code_group.setStyleSheet(_GROUPBOX_STYLE)
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
        props_group.setStyleSheet(_GROUPBOX_STYLE)
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
        self._name_input.setStyleSheet(_INPUT_STYLE)
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
        self._label_input.setStyleSheet(_INPUT_STYLE)
        label_layout.addWidget(self._label_input)

        props_layout.addLayout(label_layout)

        # Shelf 文件选择
        shelf_layout = QtWidgets.QHBoxLayout()
        shelf_layout.setSpacing(8)

        shelf_lbl = QtWidgets.QLabel("保存至：")
        shelf_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
        shelf_layout.addWidget(shelf_lbl)

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

        shelf_layout.addWidget(container)
        shelf_layout.addStretch()
        props_layout.addLayout(shelf_layout)

        layout.addWidget(props_group)

        # 按钮区域
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        self._create_btn = QtWidgets.QPushButton("创建")
        self._create_btn.setMinimumWidth(90)
        self._create_btn.setEnabled(False)
        self._create_btn.setStyleSheet(_SAVE_BUTTON_STYLE)
        self._create_btn.clicked.connect(self._on_create)

        cancel_btn = QtWidgets.QPushButton("取消")
        cancel_btn.setMinimumWidth(90)
        cancel_btn.setStyleSheet(_CANCEL_BUTTON_STYLE)
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
        elif not _TOOL_NAME_REGEX.match(name):
            hint = "只允许字母、数字、下划线和空格"
            valid = False
        else:
            # 检查是否重名
            from MA.shelf_tool_pro.shelf_loader import _TOOL_REGISTRY
            shelf_name = self._shelf_name_edit.text().strip()
            shelf_file = next(
                (path for stem, path in self._shelf_file_items if stem == shelf_name),
                os.path.join(_toolbar_dir(), shelf_name + ".shelf"),
            )
            for uid, info in _TOOL_REGISTRY.items():
                _, tool_name, _, _, reg_shelf_path = info
                if tool_name == name and reg_shelf_path == shelf_file:
                    hint = f"同名工具已存在于 {os.path.basename(shelf_file)}"
                    valid = False
                    break

        self._name_hint.setText(hint)
        self._name_input.setStyleSheet(
            _INPUT_INVALID_STYLE if (name and hint) else _INPUT_STYLE
        )

        # 检查 shelf 文件
        if valid:
            valid = bool(self._shelf_name_edit.text().strip())

        self._create_btn.setEnabled(valid)

    def _on_create(self):
        """点击创建按钮。"""
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
            }
            None 如果用户取消对话框。
        """
        if self.result() == QtWidgets.QDialog.DialogCode.Accepted:
            return self._result
        return None
