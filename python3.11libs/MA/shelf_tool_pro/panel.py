"""MAShelfToolPro 主面板。"""

import os
import logging

from PySide6 import QtWidgets, QtGui, QtCore

try:
    import hou
except ImportError:
    hou = None

from MA.common import ShelfToolsSettingsManager, ShelfToolsCacheManager
from MA.common.animation_helper import elastic_resize
from MA.shelf_tool_pro.styles import (
    BG_PRIMARY, BG_SECONDARY, BG_INPUT, BG_HOVER, TEXT_PRIMARY, TEXT_SECONDARY, BORDER_COLOR,
    ACCENT_BLUE, ACCENT_PURPLE,
    SETTINGS_BUTTON_STYLE, THUMB_SLIDER_STYLE,
    SAVE_BUTTON_STYLE, CANCEL_BUTTON_STYLE, SUFFIX_STYLE,
)
from MA.shelf_tool_pro.shelf_loader import _TOOL_NAMES, _TOOL_REGISTRY, make_unique_id
from MA.shelf_tool_pro.thumbnail_widget import ThumbnailWidget, _FAVORITE_PIXMAP

_logger = logging.getLogger("MA")

# ── 自定义字体加载 ──────────────────────────────────
_FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "AlimamaFangYuanTiVF-Thin.ttf")
_CUSTOM_FONT_ID = QtGui.QFontDatabase.addApplicationFont(_FONT_PATH)
_CUSTOM_FONT_FAMILY = QtGui.QFontDatabase.applicationFontFamilies(_CUSTOM_FONT_ID)[0] if _CUSTOM_FONT_ID >= 0 else None

# 收藏图标（从 thumbnail_widget 导入，创建 QIcon 只创建一次）
_FAVORITE_ICON = QtGui.QIcon(_FAVORITE_PIXMAP) if _FAVORITE_PIXMAP and not _FAVORITE_PIXMAP.isNull() else None

_DEFAULT_SIZE = 130

# 彩虹背景色（用于区分不同 shelf 文件的工具）
# 每个颜色包含：(背景色, 边框色)
_SHELF_COLORS = [
    ("#7A1520", "#E84040"),  # 红
    ("#8A3000", "#FF6B2B"),  # 橙
    ("#9A7000", "#FFD540"),  # 黄
    ("#1A6B45", "#40D98B"),  # 绿
    ("#103F7A", "#3B8DEE"),  # 蓝
    ("#402058", "#9B6BB0"),  # 紫
]


def load_thumb_size():
    """从缓存加载缩略图大小。"""
    data = ShelfToolsSettingsManager.load()
    return max(70, min(250, data.get("thumb_size", _DEFAULT_SIZE)))


def _get_shelf_color_map():
    """获取统一的 shelf 颜色映射（确保所有地方使用相同的映射）。

    使用复合键 ``{prefix}_{shelfStem}`` 区分来自不同目录的同名 shelf 文件。
    内置工具统一使用白色；用户 shelf 使用彩虹色。
    builtin 判定委托给 shelf_loader.is_builtin_tool。
    """
    from MA.shelf_tool_pro.shelf_loader import is_builtin_tool

    builtin_keys = set()
    user_keys = set()
    for uid, info in _TOOL_REGISTRY.items():
        shelf_stem = info[0]
        prefix = uid.split("_", 1)[0]
        key = f"{prefix}_{shelf_stem}"
        if is_builtin_tool(uid):
            builtin_keys.add(key)
        else:
            user_keys.add(key)

    color_map = {}
    for key in builtin_keys:
        color_map[key] = ("#ffffff", "#ffffff")
    for i, key in enumerate(sorted(user_keys)):
        color_map[key] = _SHELF_COLORS[i % len(_SHELF_COLORS)]

    return color_map


def _get_prefix_label(prefix):
    """将 unique_id 前缀映射为可读的来源标识（用于同名工具消歧）。"""
    if prefix == "deflt":
        return "默认"
    if prefix == "built":
        return "内置"
    # 额外路径：尝试从设置中获取对应的目录名
    try:
        from MA.common.settings import ShelfToolsSettingsManager
        for p in ShelfToolsSettingsManager.get_extra_shelf_paths():
            from MA.shelf_tool_pro.shelf_loader import path_prefix
            if path_prefix(p) == prefix:
                return os.path.basename(os.path.normpath(p))
    except Exception:
        pass
    return prefix


def save_thumb_size(value):
    """保存缩略图大小到缓存。"""
    ShelfToolsSettingsManager.update("thumb_size", value)


class _ToolbarWidget(QtWidgets.QWidget):
    """工具栏容器：面板宽度 ≥ _BREAKPOINT_WIDTH 时保持不压缩，< 时才收缩。"""
    _BREAKPOINT_WIDTH = 895

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(self._BREAKPOINT_WIDTH)
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(0)
        return hint


class MAShelfToolProPanel(QtWidgets.QWidget):
    """MA ShelfTools Pro 主面板。"""

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self._save_dialog_open = False
        self._pending_thumb_size = None
        self._preview_update_timer = QtCore.QTimer(self)
        self._preview_update_timer.setSingleShot(True)
        self._preview_update_timer.setInterval(16)
        self._preview_update_timer.timeout.connect(self._preview_pending_thumb_size)
        self.setMinimumWidth(350)
        self.setStyleSheet(f"background-color: {BG_PRIMARY};")

        init_size = load_thumb_size()

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._create_toolbar(init_size))
        main_layout.addWidget(self._create_settings_panel())

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setStyleSheet(f"color: {BORDER_COLOR}; background-color: {BORDER_COLOR}; max-height: 1px;")
        main_layout.addWidget(sep)

        main_layout.addWidget(self._create_scroll_area(init_size), 1)

        # Bug fix: 首次显示时 _build_thumb_widgets 在 viewport 尚未确定宽度
        # 时执行，导致 cols 计算错误、缩略图被固定为错误列数（典型 3 列）。
        # QTimer.singleShot(0, ...) 延迟到事件循环下一帧 reflow——此时
        # viewport 宽度已定，_relayout_grid 重新计算 cols 并重排所有 widget。
        # 后续用户拖动面板由 resizeEvent -> _relayout_grid 处理。
        QtCore.QTimer.singleShot(0, self._relayout_grid)

    # ── 拖放事件 ──────────────────────────────────

    def dragEnterEvent(self, event):
        """Accept Houdini node drags, reject own tool drags."""
        mime = event.mimeData()

        # Reject own panel drag-out (MIME: "ma_tool:...")
        if mime.hasText() and mime.text().strip().startswith("ma_tool:"):
            event.ignore()
            return

        # Check for Houdini node MIME type (GUI-only)
        accepted = False
        if hou is not None and hasattr(hou, 'qt') and hasattr(hou.qt, 'mimeType') and \
           hasattr(hou.qt.mimeType, 'nodePath'):
            if mime.hasFormat(hou.qt.mimeType.nodePath):
                accepted = True

        # Fallback: check text/plain for node path pattern
        if not accepted and mime.hasText():
            text = mime.text().strip()
            # Node paths start with "/"
            first_line = text.split("\n")[0].split("\t")[0]
            if first_line.startswith("/") and hou is not None:
                if hou.node(first_line) is not None:
                    accepted = True

        if accepted:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle Houdini node drop: show dialog, save tool, refresh panel."""
        if self._save_dialog_open:
            event.ignore()  # prevent re-entrant
            return

        mime = event.mimeData()
        node_paths = []

        # Extract node paths from MIME data
        if hou is not None and hasattr(hou, 'qt') and hasattr(hou.qt, 'mimeType') and \
           hasattr(hou.qt.mimeType, 'nodePath') and \
           mime.hasFormat(hou.qt.mimeType.nodePath):
            try:
                raw = bytes(mime.data(hou.qt.mimeType.nodePath)).decode('utf-8', errors='replace')
                node_paths = [p.strip() for p in raw.split("\t") if p.strip()]
            except Exception:
                pass
        # Fallback to text/plain
        if not node_paths and mime.hasText():
            text = mime.text().strip()
            node_paths = [p.strip() for p in text.split("\t") if p.strip().startswith("/")]

        if not node_paths:
            return

        # Validate paths exist
        valid_paths = []
        if hou is not None:
            for p in node_paths:
                if hou.node(p) is not None:
                    valid_paths.append(p)
        else:
            valid_paths = node_paths

        if not valid_paths:
            return

        event.acceptProposedAction()

        self._save_dialog_open = True
        try:
            from MA.shelf_tool_pro.save_tool_dialog import ToolSettingsDialog
            dialog = ToolSettingsDialog(
                mode="create",
                node_paths=valid_paths,
                parent=self,
            )
            if dialog.exec() != QtWidgets.QDialog.Accepted:
                return  # cancelled

            result = dialog.get_result()
            if result is None:
                return

            # Check name conflict before saving
            from MA.shelf_tool_pro.shelf_saver import check_name_conflict, save_code_to_shelf

            shelf_file = result["shelf_file"]
            tool_name = result["tool_name"]

            if check_name_conflict(tool_name, shelf_file):
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "工具名称冲突",
                    f"工具 '{tool_name}' 已存在于\n{shelf_file}\n\n是否覆盖？",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No,
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return

            # Save code to .shelf file
            success = save_code_to_shelf(
                code=result["code"],
                tool_name=tool_name,
                label=result["label"],
                shelf_file_path=shelf_file,
            )
            if not success:
                QtWidgets.QMessageBox.warning(self, "错误",
                    "保存工具失败。")
                return

            # Cache icon path (键用 unique_id = prefix + shelf_stem + tool_name)
            from MA.common.settings import ShelfToolsCacheManager
            shelf_dir = os.path.dirname(shelf_file)
            shelf_stem = os.path.splitext(os.path.basename(shelf_file))[0]
            unique_id = make_unique_id(shelf_dir, shelf_stem, tool_name)
            ShelfToolsCacheManager.set_tool_icon(unique_id, result.get("icon_path", ""))

            # Load the .shelf file into Houdini
            if hou is not None:
                try:
                    hou.shelves.loadFile(result["shelf_file"])
                except Exception as exc:
                    _logger.warning("hou.shelves.loadFile failed: %s", exc)

            # Refresh panel
            self._refresh_tools()

            print(f"工具 '{result['label']}' 已创建")
            print(result['shelf_file'])
        finally:
            self._save_dialog_open = False

    # ── 工具缩略图助手 ────────────────────────────

    @staticmethod
    def _calc_grid_cols(container_width: int, thumb_size: int, spacing: int = 12) -> int:
        """根据容器宽度和缩略图尺寸计算列数。"""
        cell = thumb_size + spacing
        return max(1, (container_width - spacing) // cell)

    def _build_thumb_widgets(self, layout, tool_names, size, tool_registry=None):
        """向 GridLayout 填充 ThumbnailWidget 实例（自动换行）。

        Args:
            tool_registry: 优先使用的注册表（解决刷新后引用过时问题），
                           None 则回退到模块级 _TOOL_REGISTRY。
        """
        if tool_registry is None:
            tool_registry = _TOOL_REGISTRY
        if not tool_names:
            info = QtWidgets.QLabel("未找到工具")
            info.setAlignment(QtCore.Qt.AlignCenter)
            info.setStyleSheet(
                "color: #888888; font-size: 14px; padding: 20px; background: transparent;")
            layout.addWidget(info, 0, 0)
            return

        # 确定可用宽度
        if self.scroll_area is not None:
            avail = self.scroll_area.viewport().width()
        else:
            avail = self.width() - 12

        cols = self._calc_grid_cols(avail, size)
        self._thumb_widgets = []

        # 获取统一的 shelf 颜色映射（复合键：{prefix}_{shelfStem}）
        shelf_color_map = _get_shelf_color_map()

        # 预计算：检测同名工具（相同 label + 相同 shelf_stem，来自不同目录）
        _label_stem_prefixes = {}  # (label, shelf_stem) -> set of prefixes
        for _uid in tool_names:
            if _uid in tool_registry:
                _stem, _, _label, _, _ = tool_registry[_uid]
                _pfx = _uid.split("_", 1)[0]
                _label_stem_prefixes.setdefault((_label, _stem), set()).add(_pfx)

        for idx, unique_id in enumerate(tool_names):
            prefix = unique_id.split("_", 1)[0]

            if unique_id in tool_registry:
                shelf_stem, _, label, icon, _ = tool_registry[unique_id]
                display_name = label
            else:
                # fallback: 格式 {prefix}_{shelfStem}_{toolName}，跳过第一个 _ 前的前缀
                parts = unique_id.split("_", 1)
                rest = parts[-1] if len(parts) > 1 else unique_id
                display_name = rest
                icon = ""
                shelf_stem = rest.split("_", 1)[0] if "_" in rest else "default"

            # 同名工具消歧：仅非默认路径追加来源标识（默认目录保持原名）
            if prefix != "deflt" and len(_label_stem_prefixes.get((label, shelf_stem), set())) > 1:
                display_name = f"{display_name} ({_get_prefix_label(prefix)})"

            # 获取该 shelf 对应的颜色（复合键查找）
            color_key = f"{prefix}_{shelf_stem}"
            bg_color, border_color = shelf_color_map.get(color_key, _SHELF_COLORS[0])

            tw = ThumbnailWidget(unique_id, display_name, size, icon_path=icon, 
                                 bg_color=bg_color, border_color=border_color)
            # 从设置注入当前备注悬停延迟（覆盖默认值 800ms）
            tw.set_notes_show_delay(ShelfToolsSettingsManager.get_notes_show_delay())
            self._thumb_widgets.append(tw)
            layout.addWidget(tw, idx // cols, idx % cols)

    # ── 面板刷新 ──────────────────────────────────

    def _refresh_tools(self):
        """Refresh the tool list in the scroll area after saving a new tool."""
        global _TOOL_NAMES, _TOOL_REGISTRY
        from MA.shelf_tool_pro.shelf_loader import refresh_tools

        refresh_tools()  # re-scan .shelf files, update globals

        # Re-import to bind locally updated _TOOL_NAMES / _TOOL_REGISTRY
        from MA.shelf_tool_pro.shelf_loader import _TOOL_NAMES, _TOOL_REGISTRY

        # 更新 shelf 筛选下拉菜单（新增的 shelf 文件需要显示）
        self._populate_filter_combo()

        # 复用统一的筛选逻辑（包含 shelf、标签、搜索三层筛选）
        filtered_names = self._get_filtered_tool_names()

        size = self.thumb_slider.value()

        old_container = self.tools_container
        new_container = QtWidgets.QWidget()
        new_container.setStyleSheet(f"background-color: {BG_SECONDARY};")
        new_layout = QtWidgets.QGridLayout(new_container)
        new_layout.setContentsMargins(6, 6, 6, 6)
        new_layout.setSpacing(12)
        new_layout.setAlignment(QtCore.Qt.AlignTop)

        self._build_thumb_widgets(new_layout, filtered_names, size, _TOOL_REGISTRY)

        # Swap in new container
        self.tools_container = new_container
        self.scroll_area.setWidget(new_container)
        try:
            old_container.deleteLater()
        except RuntimeError:
            pass  # Qt already deleted the old widget during setWidget()

    def _on_refresh(self):
        """刷新按钮点击：重新扫描工具并刷新面板。"""
        self._refresh_tools()
        if hou is not None:
            hou.ui.setStatusMessage("工具已刷新", hou.severityType.ImportantMessage)

    def _create_toolbar(self, init_size):
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)

        self.settings_btn = QtWidgets.QPushButton("设置")
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet(SETTINGS_BUTTON_STYLE)
        self.settings_btn.clicked.connect(self._toggle_settings)
        # 应用自定义字体
        if _CUSTOM_FONT_FAMILY:
            self.settings_btn.setFont(QtGui.QFont(_CUSTOM_FONT_FAMILY))
        layout.addWidget(self.settings_btn)

        layout.addSpacing(10)

        lbl_thumb_size = QtWidgets.QLabel("缩略图大小")
        lbl_thumb_size.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 13px; font-weight: bold; background-color: transparent;")
        layout.addWidget(lbl_thumb_size)

        self.thumb_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.thumb_slider.setObjectName("thumbSizeSlider")
        self.thumb_slider.setMinimum(70)
        self.thumb_slider.setMaximum(250)
        self.thumb_slider.setMaximumWidth(200)
        self.thumb_slider.setValue(init_size)
        self.thumb_slider.setStyleSheet(THUMB_SLIDER_STYLE)
        self.thumb_slider.setCursor(QtCore.Qt.PointingHandCursor)
        self.thumb_slider.valueChanged.connect(self._on_size_changed)
        self.thumb_slider.sliderReleased.connect(self._commit_thumb_size)

        # 滚轮调整后去抖提交（sliderReleased 不响应滚轮）
        self._size_commit_timer = QtCore.QTimer(self)
        self._size_commit_timer.setSingleShot(True)
        self._size_commit_timer.setInterval(300)
        self._size_commit_timer.timeout.connect(self._commit_thumb_size)

        layout.addSpacing(10)
        layout.addWidget(self.thumb_slider)

        self.size_label = QtWidgets.QLineEdit(str(init_size))
        self.size_label.setFixedWidth(40)
        self.size_label.setAlignment(QtCore.Qt.AlignCenter)
        self.size_label.setStyleSheet(
            f"background-color: {BG_INPUT}; color: white; border: 1px solid {BORDER_COLOR}; "
            f"border-radius: 4px; padding: 2px 4px; font-size: 11px;")
        self.size_label.returnPressed.connect(self._on_size_edit)
        layout.addSpacing(6)
        layout.addWidget(self.size_label)

        layout.addSpacing(10)

        # ── 搜索框 ──────────────────────────────────
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("搜索...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(150)
        self.search_input.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 4px; "
            f"padding: 4px 8px; font-size: 11px; }}"
            f"QLineEdit:focus {{ border-color: {ACCENT_BLUE}; }}"
        )
        layout.addWidget(self.search_input)
        layout.addSpacing(10)

        # 筛选下拉菜单
        filter_lbl = QtWidgets.QLabel("shelf")
        filter_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 13px; font-weight: bold; background-color: transparent;")
        layout.addWidget(filter_lbl)
        layout.addSpacing(4)

        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.setMinimumWidth(120)
        self.filter_combo.setStyleSheet(
            f"QComboBox {{ background-color: {BG_INPUT}; color: white; border: 1px solid {BORDER_COLOR}; "
            f"border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold; }} "
            f"QComboBox::drop-down {{ border: none; }} "
            f"QComboBox QAbstractItemView {{ background-color: {BG_INPUT}; color: white; "
            f"selection-background-color: #0d6399; outline: none; }} "
            f"QComboBox QAbstractItemView::item {{ padding: 4px 8px 4px 24px; }}")
        self.filter_combo.setCursor(QtCore.Qt.PointingHandCursor)
        
        # 设置自定义委托以支持背景色（只在文字前方显示小色块）
        class ColorDelegate(QtWidgets.QStyledItemDelegate):
            def paint(self, painter, option, index):
                bg_color = index.data(QtCore.Qt.BackgroundRole)
                
                # 绘制默认背景（选中状态等）
                super().paint(painter, option, index)
                
                # 如果有自定义颜色，在文字前方绘制小色块
                if bg_color and bg_color.isValid():
                    painter.save()
                    painter.setRenderHint(QtGui.QPainter.Antialiasing)
                    painter.setBrush(bg_color)
                    painter.setPen(QtCore.Qt.NoPen)
                    
                    # 绘制圆角矩形色块
                    block_width = 12
                    block_height = 12
                    x = option.rect.left() + 4
                    y = option.rect.top() + (option.rect.height() - block_height) // 2
                    painter.drawRoundedRect(x, y, block_width, block_height, 3, 3)
                    
                    painter.restore()
        
        self._filter_delegate = ColorDelegate()
        self.filter_combo.setItemDelegate(self._filter_delegate)
        self._populate_filter_combo(restore_filter=True)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.filter_combo)

        # 标签筛选下拉菜单
        layout.addSpacing(10)
        tag_lbl = QtWidgets.QLabel("标签")
        tag_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 13px; font-weight: bold; background-color: transparent;")
        layout.addWidget(tag_lbl)
        layout.addSpacing(4)

        self.tag_filter_combo = QtWidgets.QComboBox()
        self.tag_filter_combo.setMinimumWidth(100)
        self.tag_filter_combo.setStyleSheet(
            f"QComboBox {{ background-color: {BG_INPUT}; color: white; border: 1px solid {BORDER_COLOR}; "
            f"border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold; }} "
            f"QComboBox::drop-down {{ border: none; }} "
            f"QComboBox QAbstractItemView {{ background-color: {BG_INPUT}; color: white; "
            f"selection-background-color: #0d6399; }}")
        self.tag_filter_combo.setCursor(QtCore.Qt.PointingHandCursor)
        self._populate_tag_filter_combo()
        self.tag_filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.tag_filter_combo)

        # ── 刷新按钮 ──────────────────────────────────
        layout.addSpacing(10)
        refresh_icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "MA refresh.svg")
        self.refresh_btn = QtWidgets.QPushButton()
        self.refresh_btn.setObjectName("refreshButton")
        self.refresh_btn.setToolTip("刷新工具列表")
        self.refresh_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.refresh_btn.setFixedSize(30, 30)
        self.refresh_btn.setIcon(QtGui.QIcon(refresh_icon_path))
        self.refresh_btn.setIconSize(QtCore.QSize(22, 22))
        self.refresh_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; border: none; border-radius: 4px; padding: 4px; }}"
            f"QPushButton:hover {{ background-color: {BG_HOVER}; }}"
        )
        self.refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(self.refresh_btn)

        # 搜索去抖定时器
        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(500)
        self._search_timer.timeout.connect(self._apply_filter)
        self.search_input.textChanged.connect(lambda: self._search_timer.start())

        # 用 _ToolbarWidget 包裹，控制 toolbar 压缩阈值
        toolbar_widget = _ToolbarWidget()
        toolbar_widget.setLayout(layout)
        toolbar_widget.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        return toolbar_widget

    def _create_settings_panel(self):
        self.settings_widget = QtWidgets.QWidget()
        self.settings_widget.setVisible(False)
        settings_layout = QtWidgets.QVBoxLayout(self.settings_widget)
        settings_layout.setContentsMargins(8, 4, 8, 4)
        settings_layout.setSpacing(8)

        dir_row = QtWidgets.QHBoxLayout()
        dir_row.addWidget(QtWidgets.QLabel("缩略图路径："))
        self.thumb_path_edit = QtWidgets.QLineEdit()
        self.thumb_path_edit.setText(ShelfToolsSettingsManager.get_thumbnail_directory())
        self.thumb_path_edit.setStyleSheet(
            f"background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_COLOR}; "
            f"border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        dir_row.addWidget(self.thumb_path_edit)

        self.browse_btn = QtWidgets.QPushButton("浏览")
        self.browse_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.browse_btn.setStyleSheet(
            f"background-color: {BORDER_COLOR}; color: white; border: none; "
            f"border-radius: 10px; padding: 6px 16px; font-size: 11px;")
        self.browse_btn.clicked.connect(self._browse_thumbnail_directory)
        dir_row.addWidget(self.browse_btn)

        settings_layout.addLayout(dir_row)

        # ── Shelf 路径管理 + 备注悬停延迟（同行双方框） ────────
        _GROUP_STYLE = (
            f"QGroupBox {{ color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 6px; "
            f"margin-top: 10px; padding: 14px 8px 8px 8px; background-color: transparent; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; "
            f"left: 10px; padding: 0 6px; background-color: {BG_SECONDARY}; }}"
        )

        groups_row = QtWidgets.QHBoxLayout()
        groups_row.setSpacing(12)

        # 左侧：Shelf 路径管理（自适应宽度）
        shelf_group = QtWidgets.QGroupBox("Shelf 路径管理")
        shelf_group.setStyleSheet(_GROUP_STYLE)
        shelf_group.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        shelf_row = QtWidgets.QHBoxLayout(shelf_group)
        shelf_row.setContentsMargins(8, 4, 8, 4)

        self.add_shelf_path_btn = QtWidgets.QPushButton("Shelf 路径管理")
        self.add_shelf_path_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.add_shelf_path_btn.setStyleSheet(
            f"QPushButton {{ background-color: {BORDER_COLOR}; color: white; border: none; "
            f"border-radius: 10px; padding: 5px 14px; font-size: 11px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {BG_HOVER}; }}"
            f"QPushButton:pressed {{ background-color: {ACCENT_BLUE}; }}"
        )
        self.add_shelf_path_btn.clicked.connect(self._on_add_shelf_path)
        shelf_row.addWidget(self.add_shelf_path_btn)

        groups_row.addWidget(shelf_group)

        # 右侧：备注悬停延迟（自适应宽度）
        delay_group = QtWidgets.QGroupBox("备注悬停延迟")
        delay_group.setStyleSheet(_GROUP_STYLE)
        delay_group.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        delay_row = QtWidgets.QHBoxLayout(delay_group)
        delay_row.setContentsMargins(8, 4, 8, 4)

        # 数值显示：自定义 widget（数字 + 紫色下划线，下划线宽度随数字变化）
        self.notes_delay_field = _UnderlinedNumber(
            ShelfToolsSettingsManager.get_notes_show_delay()
        )
        self.notes_delay_field.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 11px; font-weight: bold; "
            f"background-color: transparent;"
        )
        delay_row.addWidget(self.notes_delay_field)

        # 单位 "ms" 紧贴数值右侧（灰色 SUFFIX_STYLE）
        self.notes_delay_unit = QtWidgets.QLabel("ms")
        self.notes_delay_unit.setStyleSheet(SUFFIX_STYLE)
        delay_row.addWidget(self.notes_delay_unit)
        delay_row.addSpacing(6)

        # 修改按钮：点击弹窗输入新值
        self.modify_delay_btn = QtWidgets.QPushButton("修改")
        self.modify_delay_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.modify_delay_btn.setStyleSheet(
            f"QPushButton {{ background-color: {BORDER_COLOR}; color: white; border: none; "
            f"border-radius: 10px; padding: 5px 14px; font-size: 11px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {BG_HOVER}; }}"
            f"QPushButton:pressed {{ background-color: {ACCENT_BLUE}; }}"
        )
        self.modify_delay_btn.clicked.connect(self._on_modify_delay)
        delay_row.addWidget(self.modify_delay_btn)

        groups_row.addWidget(delay_group)
        groups_row.addStretch(1)
        settings_layout.addLayout(groups_row)
        return self.settings_widget

    def _on_modify_delay(self):
        """打开修改延迟弹窗：确认后持久化、刷新面板、状态提示。"""
        current = ShelfToolsSettingsManager.get_notes_show_delay()
        dialog = _NotesDelayDialog(current, parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        new_value = dialog.get_value()
        if new_value == current:
            return  # 无变化，跳过

        # 1. 持久化
        ShelfToolsSettingsManager.set_notes_show_delay(new_value)

        # 2. 更新数值显示（下划线会自动随数字宽度重算）
        self.notes_delay_field.setValue(new_value)

        # 3. 触发面板刷新（与刷新按钮一致：重建缩略图，新 widget 读取最新值）
        self._refresh_tools()

        # 4. 状态提示（与刷新按钮风格一致）
        if hou is not None:
            hou.ui.setStatusMessage(
                f"延迟已更新：{new_value} ms",
                hou.severityType.ImportantMessage
            )

    def _on_add_shelf_path(self):
        """打开 shelf 路径管理弹窗，关闭后如有变更则刷新面板。"""
        dialog = _ShelfPathsDialog(parent=self)
        dialog.exec()
        if dialog.paths_changed:
            self._refresh_tools()
            if hou is not None:
                hou.ui.setStatusMessage(
                    "shelf 路径已更新",
                    hou.severityType.ImportantMessage
                )

    def _create_scroll_area(self, init_size):
        """创建带滚动区域的工具区，参考 HDR 面板架构。"""
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet(f"background-color: {BG_SECONDARY}; border: none;")

        self.tools_container = QtWidgets.QWidget()
        self.tools_container.setStyleSheet(f"background-color: {BG_SECONDARY};")
        tools_layout = QtWidgets.QGridLayout(self.tools_container)
        tools_layout.setContentsMargins(6, 6, 6, 6)
        tools_layout.setSpacing(12)
        tools_layout.setAlignment(QtCore.Qt.AlignTop)

        self._build_thumb_widgets(tools_layout, self._get_filtered_tool_names(), init_size)

        self.scroll_area.setWidget(self.tools_container)
        return self.scroll_area

    # ── 重排网格（面板缩放 / 滑块调大小时） ─────

    def _relayout_grid(self) -> None:
        """保持现有 widgets，按当前宽度重新计算列数并重排。"""
        if not hasattr(self, '_thumb_widgets') or not self._thumb_widgets:
            return
        layout = self.tools_container.layout()
        if layout is None:
            return
        avail = self.scroll_area.viewport().width()
        size = self.thumb_slider.value()
        cols = self._calc_grid_cols(avail, size)
        for idx, tw in enumerate(self._thumb_widgets):
            row, col = idx // cols, idx % cols
            layout.addWidget(tw, row, col)

    def resizeEvent(self, event):
        """面板缩放时自动重排网格。"""
        super().resizeEvent(event)
        self._relayout_grid()

    # ── 右键菜单 ──────────────────────────────────

    def contextMenuEvent(self, event):
        """面板空白区域右键菜单。"""
        from MA.shelf_tool_pro.styles import CONTEXT_MENU_STYLE
        
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)
        
        create_action = menu.addAction("创建工具\u2026")
        create_action.triggered.connect(self._on_create_tool)
        
        menu.exec(event.globalPos())

    def _on_create_tool(self):
        """打开创建工具对话框。"""
        from MA.shelf_tool_pro.save_tool_dialog import ToolSettingsDialog
        
        dialog = ToolSettingsDialog(mode="create", parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        
        result = dialog.get_result()
        if result is None:
            return
        
        # 保存代码到 .shelf 文件
        from MA.shelf_tool_pro.shelf_saver import save_code_to_shelf
        success = save_code_to_shelf(
            code=result["code"],
            tool_name=result["tool_name"],
            label=result["label"],
            shelf_file_path=result["shelf_file"],
        )
        
        if not success:
            QtWidgets.QMessageBox.warning(self, "错误", "保存工具失败。")
            return
        
        # 保存缩略图缓存
        icon_path = result.get("icon_path", "")
        if icon_path:
            shelf_dir = os.path.dirname(result["shelf_file"])
            shelf_stem = os.path.splitext(os.path.basename(result["shelf_file"]))[0]
            unique_id = make_unique_id(shelf_dir, shelf_stem, result['tool_name'])
            ShelfToolsCacheManager.set_tool_icon(unique_id, icon_path)
        
        # 加载 .shelf 文件到 Houdini
        if hou is not None:
            try:
                hou.shelves.loadFile(result["shelf_file"])
            except Exception as exc:
                _logger.warning("hou.shelves.loadFile failed: %s", exc)
        
        # 刷新面板
        self._refresh_tools()
        
        # 提示成功
        print(f"工具 '{result['label']}' 已创建")
        print(result['shelf_file'])

    def _toggle_settings(self):
        is_visible = self.settings_widget.isVisible()
        elastic_resize(self.settings_widget, not is_visible)

    def _browse_thumbnail_directory(self):
        current_dir = self.thumb_path_edit.text()
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "选择缩略图目录", current_dir)
        if dir_path:
            self.thumb_path_edit.setText(dir_path)
            ShelfToolsSettingsManager.set_thumbnail_directory(dir_path)

    def _on_size_changed(self, value):
        self.size_label.setText(str(value))
        self._pending_thumb_size = value

        # 拖动或滚轮：都走 previewSize 快速预览路径
        if not self._preview_update_timer.isActive():
            self._preview_update_timer.start()

        if self.thumb_slider.isSliderDown():
            # 拖动中：停止提交定时器（由 sliderReleased 触发提交）
            self._size_commit_timer.stop()
        else:
            # 滚轮/键盘：去抖提交最终渲染+保存
            self._size_commit_timer.start()

    def _preview_pending_thumb_size(self):
        value = self._pending_thumb_size
        if value is None:
            return
        if hasattr(self, '_thumb_widgets'):
            for tw in self._thumb_widgets:
                try:
                    tw.previewSize(value)
                except RuntimeError:
                    pass
        self._relayout_grid()

    def _apply_pending_thumb_size(self):
        value = self._pending_thumb_size
        if value is None:
            value = self.thumb_slider.value()
        self._pending_thumb_size = None
        self._apply_thumb_size(value)

    def _apply_thumb_size(self, value):
        if hasattr(self, '_thumb_widgets'):
            for tw in self._thumb_widgets:
                try:
                    tw.updateSize(value)
                except RuntimeError:
                    pass  # widget 已被删除（例如最后 tool 被删后 shelf 文件已清空）
        self._relayout_grid()

    def _commit_thumb_size(self):
        self._size_commit_timer.stop()
        if self._preview_update_timer.isActive():
            self._preview_update_timer.stop()
        if self._pending_thumb_size is not None:
            self._apply_pending_thumb_size()
        save_thumb_size(self.thumb_slider.value())

    def _on_size_edit(self):
        try:
            v = int(self.size_label.text().strip())
            v = max(70, min(250, v))
            self.thumb_slider.setValue(v)
            self._commit_thumb_size()
        except ValueError:
            self.size_label.setText(str(self.thumb_slider.value()))

    # ── 筛选功能 ──────────────────────────────────

    def _populate_filter_combo(self, restore_filter=False):
        """填充筛选下拉菜单：全部、各 shelf 名称。
        
        使用复合键 ``{prefix}_{shelfStem}`` 区分来自不同目录的同名 shelf。
        显示标签仅展示 shelf 名称，同名时追加来源标识。
        
        Args:
            restore_filter: 是否恢复上次关闭时的筛选状态。
        """
        # 保存当前筛选状态（防止 clear() 丢失选择）
        current_filter = None
        if self.filter_combo.count() > 0:
            current_filter = self.filter_combo.itemData(self.filter_combo.currentIndex())

        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()

        # ItemData values: 'all' or composite key "{prefix}_{shelfStem}"
        self.filter_combo.addItem("全部", userData="all")

        # 获取统一的 shelf 颜色映射（复合键）
        shelf_color_map = _get_shelf_color_map()

        # 分组：shelf_stem -> list of composite keys
        _stem_keys = {}
        for ck in shelf_color_map:
            parts = ck.split("_", 1)
            if len(parts) == 2:
                _stem_keys.setdefault(parts[1], []).append(ck)

        for stem in sorted(_stem_keys.keys()):
            keys = _stem_keys[stem]
            if len(keys) == 1:
                # 唯一来源，无需消歧
                self.filter_combo.addItem(stem, userData=keys[0])
            else:
                # 同名 shelf 来自多个目录，追加来源标识（默认目录保持原名）
                for ck in sorted(keys):
                    prefix = ck.split("_", 1)[0]
                    if prefix == "deflt":
                        self.filter_combo.addItem(stem, userData=ck)
                    else:
                        self.filter_combo.addItem(
                            f"{stem} ({_get_prefix_label(prefix)})", userData=ck)

            # 设置颜色（取该 stem 下第一个 key 的颜色）
            bg_color, border_color = shelf_color_map[keys[0]]
            index = self.filter_combo.count() - 1
            # 多来源时为每个条目分别着色，单来源只着一次
            if len(keys) == 1:
                self.filter_combo.setItemData(index, QtGui.QColor(bg_color), QtCore.Qt.BackgroundRole)
                self.filter_combo.setItemData(index, QtGui.QColor(TEXT_PRIMARY), QtCore.Qt.ForegroundRole)
            else:
                # 回溯 len(keys) 个条目分别着色
                for i, ck in enumerate(sorted(keys)):
                    ci = index - len(keys) + 1 + i
                    bg, _ = shelf_color_map[ck]
                    self.filter_combo.setItemData(ci, QtGui.QColor(bg), QtCore.Qt.BackgroundRole)
                    self.filter_combo.setItemData(ci, QtGui.QColor(TEXT_PRIMARY), QtCore.Qt.ForegroundRole)

        # 确定要恢复的筛选项
        if restore_filter:
            saved_filter = ShelfToolsSettingsManager.get_filter()
            index = self.filter_combo.findData(saved_filter)
            if index >= 0:
                self.filter_combo.setCurrentIndex(index)
            else:
                self.filter_combo.setCurrentIndex(0)
        elif current_filter is not None:
            # 非首次加载时，恢复调用前的选择
            index = self.filter_combo.findData(current_filter)
            if index >= 0:
                self.filter_combo.setCurrentIndex(index)

        self.filter_combo.blockSignals(False)

        # 信号被 block，手动应用筛选
        self._apply_filter()

    def _populate_tag_filter_combo(self):
        """填充标签筛选下拉菜单：全部标签、收藏、各唯一标签。"""
        # 保存当前筛选状态（防止 clear() 丢失选择）
        current_tag = None
        if self.tag_filter_combo.count() > 0:
            current_tag = self.tag_filter_combo.itemData(self.tag_filter_combo.currentIndex())

        self.tag_filter_combo.blockSignals(True)
        self.tag_filter_combo.clear()

        # 添加"全部"和"收藏"选项
        self.tag_filter_combo.addItem("全部标签", userData="all")
        # 收藏选项带 SVG 图标
        if _FAVORITE_ICON:
            self.tag_filter_combo.addItem(_FAVORITE_ICON, "收藏", userData="favorites")
        else:
            self.tag_filter_combo.addItem("收藏", userData="favorites")

        # 从缓存获取所有唯一标签
        all_tags = ShelfToolsCacheManager.get_all_tags()

        for tag in all_tags:
            self.tag_filter_combo.addItem(tag, userData=tag)

        # 恢复之前的选择
        if current_tag is not None:
            index = self.tag_filter_combo.findData(current_tag)
            if index >= 0:
                self.tag_filter_combo.setCurrentIndex(index)

        self.tag_filter_combo.blockSignals(False)

    def _on_filter_changed(self, index):
        """筛选项变化时触发。"""
        self._apply_filter()

    def _parse_search_query(self, text: str) -> tuple[str, str]:
        """解析搜索文本，返回 (mode, query)。

        mode: "label" | "tag" | "name" | "shelf"
        query: 搜索内容
        """
        text = text.strip()
        if not text:
            return ("label", "")

        for prefix in ("tag:", "name:", "shelf:"):
            if text.lower().startswith(prefix):
                query = text[len(prefix):].strip()
                mode = prefix[:-1]
                return (mode, query)

        return ("label", text)

    def _get_filtered_tool_names(self):
        """根据当前筛选项返回工具名列表。"""
        data = self.filter_combo.itemData(self.filter_combo.currentIndex())
        tag_data = self.tag_filter_combo.itemData(self.tag_filter_combo.currentIndex())

        # 首先按 shelf 筛选
        if data == "all":
            filtered_names = list(_TOOL_NAMES)
        else:
            # 复合键过滤：data = "{prefix}_{shelfStem}"
            parts = data.split("_", 1)
            if len(parts) == 2:
                filter_prefix, filter_stem = parts
                filtered_names = [
                    uid for uid in _TOOL_NAMES
                    if uid in _TOOL_REGISTRY
                    and _TOOL_REGISTRY[uid][0] == filter_stem
                    and uid.split("_", 1)[0] == filter_prefix
                ]
            else:
                # 兼容旧格式（仅 shelf_stem）
                filtered_names = [
                    uid for uid in _TOOL_NAMES
                    if uid in _TOOL_REGISTRY and _TOOL_REGISTRY[uid][0] == data
                ]

        # 然后按标签/收藏筛选
        if tag_data == "favorites":
            # 收藏筛选
            favorites = ShelfToolsSettingsManager.get_favorites()
            filtered_names = [uid for uid in filtered_names if uid in favorites]
        elif tag_data != "all":
            # 标签筛选（用户工具从 ShelfToolsCacheManager，内置工具从 BuiltinToolsCacheManager）
            from MA.common.settings import BuiltinToolsCacheManager
            filtered_names = [
                uid for uid in filtered_names
                if tag_data in ShelfToolsCacheManager.get_tags(uid)
                or tag_data in BuiltinToolsCacheManager.get_tool_tags(uid)
            ]

        # Layer 3: 搜索文本筛选（叠加/交集）
        search_text = self.search_input.text().strip()
        if search_text:
            mode, query = self._parse_search_query(search_text)
            if query:
                query_lower = query.lower()
                if mode == "tag":
                    from MA.common.settings import BuiltinToolsCacheManager
                    filtered_names = [
                        uid for uid in filtered_names
                        if any(query_lower in tag.lower() for tag in ShelfToolsCacheManager.get_tags(uid))
                        or any(query_lower in tag.lower() for tag in BuiltinToolsCacheManager.get_tool_tags(uid))
                    ]
                elif mode == "name":
                    filtered_names = [
                        uid for uid in filtered_names
                        if query_lower in _TOOL_REGISTRY[uid][1].lower()
                    ]
                elif mode == "shelf":
                    filtered_names = [
                        uid for uid in filtered_names
                        if query_lower in _TOOL_REGISTRY[uid][0].lower()
                    ]
                else:  # label（默认）
                    filtered_names = [
                        uid for uid in filtered_names
                        if query_lower in _TOOL_REGISTRY[uid][2].lower()
                    ]

        return filtered_names

    def _apply_filter(self):
        """应用当前筛选条件，重新构建缩略图网格。"""
        if not hasattr(self, 'tools_container'):
            return  # 面板尚未初始化完成，跳过
        filtered_names = self._get_filtered_tool_names()
        size = self.thumb_slider.value()

        old_container = self.tools_container
        new_container = QtWidgets.QWidget()
        new_container.setStyleSheet(f"background-color: {BG_SECONDARY};")
        new_layout = QtWidgets.QGridLayout(new_container)
        new_layout.setContentsMargins(6, 6, 6, 6)
        new_layout.setSpacing(12)
        new_layout.setAlignment(QtCore.Qt.AlignTop)

        self._build_thumb_widgets(new_layout, filtered_names, size, _TOOL_REGISTRY)

        self.tools_container = new_container
        self.scroll_area.setWidget(new_container)
        try:
            old_container.deleteLater()
        except RuntimeError:
            pass

    def _on_favorite_changed(self):
        """收藏状态变化时的回调（由 ThumbnailWidget 调用）。"""
        # 如果当前是收藏筛选，刷新显示
        tag_data = self.tag_filter_combo.itemData(self.tag_filter_combo.currentIndex())
        if tag_data == "favorites":
            self._apply_filter()
        # 更新下拉菜单中的 shelf 列表（以防新增/删除工具）
        self._populate_filter_combo()

    def _on_tags_changed(self):
        """标签变化时的回调（由 ThumbnailWidget 调用）。"""
        # 更新标签筛选下拉菜单
        self._populate_tag_filter_combo()
        # 如果当前是标签筛选，刷新显示
        tag_data = self.tag_filter_combo.itemData(self.tag_filter_combo.currentIndex())
        if tag_data != "all":
            self._apply_filter()

    def closeEvent(self, event):
        """面板关闭时保存当前筛选状态。"""
        current_filter = self.filter_combo.itemData(self.filter_combo.currentIndex())
        ShelfToolsSettingsManager.set_filter(current_filter)
        super().closeEvent(event)


class _NotesDelayDialog(QtWidgets.QDialog):
    """备注悬停延迟调整对话框。模态输入：输入框 + 确认/取消。

    设计要点：
    - 内容居中布局，左右留白对等
    - 固定大小，不允许用户拖拽边框调整
    - 右上角 × 可点击关闭
    """

    def __init__(self, current_value: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("修改备注悬停延迟")
        self.setModal(True)
        # 显式声明 WindowCloseButtonHint：Qt.WindowType.Dialog 本身不包含
        # 关闭按钮 hint，部分平台/版本下不显式声明就不会渲染右上角 ×
        self.setWindowFlags(
            QtCore.Qt.WindowType.Dialog
            | QtCore.Qt.WindowType.WindowCloseButtonHint
        )
        # 双保险：setFixedSize 已锁死大小，但显式禁用 sizeGrip 避免后续若
        # setFixedSize 被误删时，右下角又出现可拖拽的三角柄
        self.setSizeGripEnabled(False)
        self.setStyleSheet(f"QDialog {{ background-color: {BG_PRIMARY}; }}")

        layout = QtWidgets.QVBoxLayout(self)
        # 水平内边距 24 → 12（收窄一半），垂直 22 → 18，整体更紧凑
        layout.setContentsMargins(12, 18, 12, 18)
        layout.setSpacing(14)

        # 标题（居中）
        # 注：label 样式中的 background-color: transparent 是防御性设置——
        # QLabel 默认 autoFillBackground=False，但部分主题/调色板下会继承
        # 父级 QFrame 背景；显式声明避免出现与 BG_PRIMARY 不同的色块
        title = QtWidgets.QLabel("修改备注悬停延迟")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 15px; font-weight: bold; "
            f"background-color: transparent;"
        )
        layout.addWidget(title)

        # 建议范围（居中，灰色提示，仅作 UX 引导）
        recommend = QtWidgets.QLabel(
            f"建议范围 "
            f"{ShelfToolsSettingsManager._RECOMMENDED_MIN_NOTES_SHOW_DELAY} - "
            f"{ShelfToolsSettingsManager._RECOMMENDED_MAX_NOTES_SHOW_DELAY} ms"
        )
        recommend.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        recommend.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; "
            f"background-color: transparent;"
        )
        layout.addWidget(recommend)

        # 输入框行（居中：两侧 stretch）
        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(6)
        input_row.addStretch(1)

        self.spin = QtWidgets.QSpinBox()
        self.spin.setRange(
            ShelfToolsSettingsManager._MIN_NOTES_SHOW_DELAY,
            ShelfToolsSettingsManager._MAX_NOTES_SHOW_DELAY,
        )
        self.spin.setValue(current_value)
        # 取消上下三角形按钮：只允许手动输入
        self.spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        # min-width 不是死代码：被后续 setFixedSize 覆盖，但会被 adjustSize()
        # 在计算 sizeHint 时看到——影响弹窗最终宽度。删掉则 spin 缩到默认
        # 30px，整个弹窗宽度跟着塌陷
        self.spin.setMinimumWidth(90)
        self.spin.setStyleSheet(
            f"QSpinBox {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 4px; "
            f"padding: 8px 12px; font-size: 14px; font-weight: bold; }}"
            f"QSpinBox:focus {{ border-color: {ACCENT_BLUE}; }}"
        )
        input_row.addWidget(self.spin)

        ms_label = QtWidgets.QLabel("ms")
        ms_label.setStyleSheet(SUFFIX_STYLE)
        input_row.addWidget(ms_label)
        input_row.addStretch(1)

        layout.addLayout(input_row)

        # 按钮行（居中：两侧 stretch）
        button_row = QtWidgets.QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addStretch(1)

        def _btn(text: str, style: str, slot, default: bool = False) -> QtWidgets.QPushButton:
            """创建样式化按钮：统一光标/最小高度/样式表/信号连接。

            注：setMinimumHeight(32) 不是死代码——被后续 setFixedSize 覆盖，
            但会被 adjustSize() 的 sizeHint 计算看到，影响弹窗最终高度。
            32px 是触屏目标标准高度，删掉则按钮缩到默认 24px，弹窗塌陷。
            """
            b = QtWidgets.QPushButton(text)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setDefault(default)
            b.setMinimumHeight(32)
            b.setStyleSheet(style)
            b.clicked.connect(slot)
            return b

        button_row.addWidget(_btn("确认", SAVE_BUTTON_STYLE, self.accept, default=True))
        button_row.addWidget(_btn("取消", CANCEL_BUTTON_STYLE, self.reject))
        button_row.addStretch(1)

        layout.addLayout(button_row)

        # 锁死弹窗尺寸：adjustSize 计算内容理想尺寸，setFixedSize 设为该尺寸
        # 等价于 setMinimumSize == setMaximumSize，setSizePolicy/Fixed 只能约束
        # layout 中的行为，无法阻止用户拖拽边框——setFixedSize 才是真正锁死
        self.adjustSize()
        self.setFixedSize(self.size())

    def get_value(self) -> int:
        """返回用户在弹窗中输入的新值。"""
        return self.spin.value()


class _UnderlinedNumber(QtWidgets.QWidget):
    """只读数字 + 下方紫色下划线 widget。

    下划线宽度始终匹配数字文本宽度（数字位数变化时下划线自动伸缩）。
    替代 QLineEdit+border-bottom 方案，避免下划线横跨固定宽度。
    """

    def __init__(self, value: int, parent=None):
        super().__init__(parent)
        self._value = str(int(value))
        # Maximum + Fixed：宽由 sizeHint 决定（=文字宽度），不会被迫拉伸
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Maximum,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

    def setValue(self, value: int):
        """设置新数字。触发 sizeHint 重算和重绘，下划线自动适配。"""
        self._value = str(int(value))
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self._value)
        return QtCore.QSize(text_w, fm.height() + 4)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        # 数字文字（占据除下划线外的全部区域，居中）
        painter.setPen(QtGui.QColor(TEXT_PRIMARY))
        painter.setFont(self.font())
        text_rect = QtCore.QRect(0, 0, self.width(), self.height() - 4)
        painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignCenter, self._value)
        # 紫色下划线：底部 2px，宽度 = widget 宽 = 文字宽
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(ACCENT_PURPLE))
        painter.drawRect(0, self.height() - 2, self.width(), 2)


class _ShelfPathsDialog(QtWidgets.QDialog):
    """shelf 路径管理弹窗。

    展示当前所有 shelf 扫描路径（默认 MAtoolbar + 用户手动添加的额外路径），
    支持添加新文件夹路径和删除已添加的路径。
    关闭弹窗后通过 paths_changed 属性通知主面板是否需要刷新。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.paths_changed = False
        self.setWindowTitle("Shelf 路径管理")
        self.setModal(True)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Dialog
            | QtCore.Qt.WindowType.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(False)
        self.setStyleSheet(f"QDialog {{ background-color: {BG_PRIMARY}; }}")
        self.setMinimumWidth(520)

        # 加载锁图标（用于内置/默认路径标识）
        lock_icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "MA lock.svg")
        self._lock_icon = QtGui.QIcon(lock_icon_path) if os.path.isfile(lock_icon_path) else QtGui.QIcon()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(12)

        # 标题
        title = QtWidgets.QLabel("Shelf 路径管理")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 15px; font-weight: bold; "
            f"background-color: transparent;"
        )
        layout.addWidget(title)

        # 说明文字
        hint = QtWidgets.QLabel("以下路径中的 .shelf 文件将被加载到面板中")
        hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; "
            f"background-color: transparent;"
        )
        layout.addWidget(hint)

        # ── 路径列表区域 ────────────────────────
        self._list_widget = QtWidgets.QListWidget()
        self._list_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._list_widget.setStyleSheet(
            f"QListWidget {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 4px; "
            f"padding: 4px; font-size: 12px; }}"
            f"QListWidget::item {{ padding: 6px 8px; border-radius: 3px; }}"
            f"QListWidget::item:selected {{ background-color: {ACCENT_BLUE}; }}"
            f"QListWidget::item:hover:!selected {{ background-color: {BG_HOVER}; }}"
        )
        self._populate_list()
        layout.addWidget(self._list_widget, 1)

        # ── 按钮行 ────────────────────────────────
        button_row = QtWidgets.QHBoxLayout()
        button_row.setSpacing(8)

        # 添加路径按钮
        self.add_btn = QtWidgets.QPushButton("添加路径")
        self.add_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.add_btn.setMinimumHeight(32)
        self.add_btn.setStyleSheet(SAVE_BUTTON_STYLE)
        self.add_btn.clicked.connect(self._on_add_path)
        button_row.addWidget(self.add_btn)

        # 删除路径按钮
        self.remove_btn = QtWidgets.QPushButton("删除选中")
        self.remove_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.remove_btn.setMinimumHeight(32)
        self.remove_btn.clicked.connect(self._on_remove_path)
        button_row.addWidget(self.remove_btn)

        button_row.addStretch(1)

        # 关闭按钮
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setMinimumHeight(32)
        close_btn.setStyleSheet(
            f"QPushButton {{ background-color: {BG_INPUT}; color: {TEXT_SECONDARY}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 6px; "
            f"padding: 8px 20px; }}"
            f"QPushButton:hover {{ background-color: {BG_HOVER}; color: {TEXT_PRIMARY}; }}"
        )
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)

        layout.addLayout(button_row)

        # 更新删除按钮可用状态
        self._list_widget.currentRowChanged.connect(self._update_remove_btn)
        self._update_remove_btn(self._list_widget.currentRow())

    def _get_default_path(self) -> str:
        """获取默认的 MAtoolbar 路径。"""
        from MA.shelf_tool_pro.shelf_loader import project_root
        return os.path.normpath(os.path.join(project_root(), "MAtoolbar"))

    def _get_builtin_path(self) -> str:
        """获取内置工具 builtin_tools 路径。"""
        from MA.shelf_tool_pro.shelf_loader import project_root
        return os.path.normpath(os.path.join(project_root(), "builtin_tools"))

    def _populate_list(self):
        """填充路径列表：内置路径 + 默认路径（均不可删除）+ 额外路径。"""
        self._list_widget.clear()

        builtin_path = self._get_builtin_path()
        default_path = self._get_default_path()

        # 受保护项的样式：灰色文字
        protected_fg = QtGui.QColor(TEXT_SECONDARY)

        # 内置工具路径（不可删除）
        builtin_item = QtWidgets.QListWidgetItem(f"[内置] {builtin_path}")
        builtin_item.setData(QtCore.Qt.ItemDataRole.UserRole, {"path": builtin_path, "is_default": True})
        builtin_item.setToolTip("内置工具路径，不可删除")
        builtin_item.setForeground(protected_fg)
        if not self._lock_icon.isNull():
            builtin_item.setIcon(self._lock_icon)
        self._list_widget.addItem(builtin_item)

        # 默认路径（不可删除）
        default_item = QtWidgets.QListWidgetItem(f"[默认] {default_path}")
        default_item.setData(QtCore.Qt.ItemDataRole.UserRole, {"path": default_path, "is_default": True})
        default_item.setToolTip("默认路径，不可删除")
        default_item.setForeground(protected_fg)
        if not self._lock_icon.isNull():
            default_item.setIcon(self._lock_icon)
        self._list_widget.addItem(default_item)

        # 额外路径（可删除）
        user_fg = QtGui.QColor(TEXT_PRIMARY)
        extra_paths = ShelfToolsSettingsManager.get_extra_shelf_paths()
        for p in extra_paths:
            item = QtWidgets.QListWidgetItem(p)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, {"path": p, "is_default": False})
            item.setToolTip(p)
            item.setForeground(user_fg)
            self._list_widget.addItem(item)

        # 默认选中第一项
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    # 删除按钮样式：可删除（常规亮度）vs 不可删除（更暗）
    _REMOVE_BTN_ENABLED = CANCEL_BUTTON_STYLE
    _REMOVE_BTN_DISABLED = (
        f"QPushButton {{ background-color: #1a1a1a; color: #3a3a3a; "
        f"border: 1px solid #252525; border-radius: 6px; "
        f"padding: 8px 20px; }}"
        f"QPushButton:hover {{ background-color: #1a1a1a; color: #3a3a3a; }}"
    )

    def _update_remove_btn(self, row: int):
        """根据选中行更新删除按钮状态与样式：受保护路径暗色不可用，用户路径亮色可删除。"""
        if row < 0 or row >= self._list_widget.count():
            self.remove_btn.setEnabled(False)
            self.remove_btn.setStyleSheet(self._REMOVE_BTN_DISABLED)
            return
        item = self._list_widget.item(row)
        data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        is_default = data.get("is_default", False) if data else False
        self.remove_btn.setEnabled(not is_default)
        self.remove_btn.setStyleSheet(
            self._REMOVE_BTN_DISABLED if is_default else self._REMOVE_BTN_ENABLED
        )

    def _on_add_path(self):
        """打开文件夹选择对话框，添加新的 shelf 路径。"""
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "选择 shelf 文件夹", ""
        )
        if not dir_path:
            return

        norm = os.path.normpath(dir_path)

        # 检查是否与内置路径重复
        if norm == self._get_builtin_path():
            QtWidgets.QMessageBox.information(
                self, "提示", "该路径已是内置工具路径，无需重复添加。"
            )
            return

        # 检查是否与默认路径重复
        if norm == self._get_default_path():
            QtWidgets.QMessageBox.information(
                self, "提示", "该路径已是默认路径，无需重复添加。"
            )
            return

        # 检查是否与已有额外路径重复
        added = ShelfToolsSettingsManager.add_extra_shelf_path(dir_path)
        if not added:
            QtWidgets.QMessageBox.information(
                self, "提示", "该路径已存在。"
            )
            return

        # 添加到列表
        item = QtWidgets.QListWidgetItem(norm)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, {"path": norm, "is_default": False})
        item.setToolTip(norm)
        item.setForeground(QtGui.QColor(TEXT_PRIMARY))
        self._list_widget.addItem(item)
        self._list_widget.setCurrentRow(self._list_widget.count() - 1)

        self.paths_changed = True

    def _on_remove_path(self):
        """删除当前选中的额外路径。"""
        row = self._list_widget.currentRow()
        if row < 0:
            return
        item = self._list_widget.item(row)
        data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if data.get("is_default", False):
            return  # 默认路径不可删除

        path = data["path"]
        ShelfToolsSettingsManager.remove_extra_shelf_path(path)
        self._list_widget.takeItem(row)
        self.paths_changed = True
