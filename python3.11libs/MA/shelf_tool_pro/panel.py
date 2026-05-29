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
    BG_PRIMARY, BG_SECONDARY, BG_INPUT, TEXT_PRIMARY, TEXT_SECONDARY, BORDER_COLOR,
    SETTINGS_BUTTON_STYLE, THUMB_SLIDER_STYLE,
)
from MA.shelf_tool_pro.shelf_loader import _TOOL_NAMES, _TOOL_REGISTRY
from MA.shelf_tool_pro.thumbnail_widget import ThumbnailWidget

_logger = logging.getLogger("MA")

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
    """获取统一的 shelf 颜色映射（确保所有地方使用相同的映射）。"""
    shelf_names = set()
    for uid, info in _TOOL_REGISTRY.items():
        shelf_names.add(info[0])  # shelf_stem
    
    color_map = {}
    for i, name in enumerate(sorted(shelf_names)):
        color_map[name] = _SHELF_COLORS[i % len(_SHELF_COLORS)]
    
    return color_map


def save_thumb_size(value):
    """保存缩略图大小到缓存。"""
    ShelfToolsSettingsManager.update("thumb_size", value)


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

        main_layout.addLayout(self._create_toolbar(init_size))
        main_layout.addWidget(self._create_settings_panel())

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setStyleSheet(f"color: {BORDER_COLOR}; background-color: {BORDER_COLOR}; max-height: 1px;")
        main_layout.addWidget(sep)

        main_layout.addWidget(self._create_scroll_area(init_size), 1)

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
            from MA.shelf_tool_pro.shelf_saver import check_name_conflict, save_node_to_shelf

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

            # Save to .shelf file (icon not written — only supports Houdini internal names)
            success = save_node_to_shelf(
                node_paths=result["node_paths"],
                tool_name=tool_name,
                label=result["label"],
                shelf_file_path=shelf_file,
            )
            if not success:
                QtWidgets.QMessageBox.warning(self, "错误",
                    "保存工具到工具架文件失败。")
                return

            # Cache icon path (键用 unique_id = shelf_stem + tool_name)
            from MA.common.settings import ShelfToolsCacheManager
            shelf_stem = os.path.splitext(os.path.basename(shelf_file))[0]
            unique_id = f"{shelf_stem}_{tool_name}"
            ShelfToolsCacheManager.set_tool_icon(unique_id, result.get("icon_path", ""))

            # Load the .shelf file into Houdini
            if hou is not None:
                try:
                    hou.shelves.loadFile(result["shelf_file"])
                except Exception as exc:
                    _logger.warning("hou.shelves.loadFile failed: %s", exc)

            # Refresh panel
            self._refresh_tools()

            # 直接打印到控制台，代替弹窗
            print(f"工具 '{result['label']}' 已保存到")
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

        # 获取统一的 shelf 颜色映射
        shelf_color_map = _get_shelf_color_map()

        for idx, unique_id in enumerate(tool_names):
            if unique_id in tool_registry:
                shelf_stem, _, label, icon, _ = tool_registry[unique_id]
                display_name = label
            else:
                display_name = unique_id.split("_", 1)[-1]
                icon = ""
                shelf_stem = unique_id.split("_", 1)[0] if "_" in unique_id else "default"

            # 获取该 shelf 对应的颜色（背景色, 边框色）
            bg_color, border_color = shelf_color_map.get(shelf_stem, _SHELF_COLORS[0])

            tw = ThumbnailWidget(unique_id, display_name, size, icon_path=icon, 
                                 bg_color=bg_color, border_color=border_color)
            self._thumb_widgets.append(tw)
            layout.addWidget(tw, idx // cols, idx % cols)

    # ── 面板刷新 ──────────────────────────────────

    def _refresh_tools(self):
        """Refresh the tool list in the scroll area after saving a new tool."""
        from MA.shelf_tool_pro.shelf_loader import refresh_tools

        refresh_tools()  # re-scan .shelf files, update globals

        # Re-import to bind locally updated _TOOL_NAMES / _TOOL_REGISTRY
        from MA.shelf_tool_pro.shelf_loader import _TOOL_NAMES, _TOOL_REGISTRY

        # 获取当前筛选状态
        current_filter = self.filter_combo.itemData(self.filter_combo.currentIndex())

        # 根据筛选条件获取工具列表
        if current_filter == "all":
            filtered_names = list(_TOOL_NAMES)
        elif current_filter == "favorites":
            filtered_names = [uid for uid in ShelfToolsSettingsManager.get_favorites() if uid in _TOOL_REGISTRY]
        else:
            shelf_name = current_filter
            filtered_names = [uid for uid in _TOOL_NAMES if uid in _TOOL_REGISTRY and _TOOL_REGISTRY[uid][0] == shelf_name]

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

    def _create_toolbar(self, init_size):
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)

        self.settings_btn = QtWidgets.QPushButton("设置")
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet(SETTINGS_BUTTON_STYLE)
        self.settings_btn.clicked.connect(self._toggle_settings)
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

        # 筛选下拉菜单
        filter_lbl = QtWidgets.QLabel("筛选")
        filter_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 13px; font-weight: bold; background-color: transparent;")
        layout.addWidget(filter_lbl)
        layout.addSpacing(4)

        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.setMinimumWidth(120)
        self.filter_combo.setStyleSheet(
            f"QComboBox {{ background-color: {BG_INPUT}; color: white; border: 1px solid {BORDER_COLOR}; "
            f"border-radius: 4px; padding: 3px 8px; font-size: 11px; }} "
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
            f"border-radius: 4px; padding: 3px 8px; font-size: 11px; }} "
            f"QComboBox::drop-down {{ border: none; }} "
            f"QComboBox QAbstractItemView {{ background-color: {BG_INPUT}; color: white; "
            f"selection-background-color: #0d6399; }}")
        self.tag_filter_combo.setCursor(QtCore.Qt.PointingHandCursor)
        self._populate_tag_filter_combo()
        self.tag_filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.tag_filter_combo)

        layout.addStretch()
        return layout

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
        return self.settings_widget

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
        from MA.shelf_tool_pro.create_tool_dialog import CreateToolDialog
        
        dialog = CreateToolDialog(parent=self)
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
            shelf_stem = os.path.splitext(os.path.basename(result["shelf_file"]))[0]
            unique_id = f"{shelf_stem}_{result['tool_name']}"
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

        if self.thumb_slider.isSliderDown():
            if not self._preview_update_timer.isActive():
                self._preview_update_timer.start()
            return

        self._apply_pending_thumb_size()

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
        
        Args:
            restore_filter: 是否恢复上次关闭时的筛选状态。
        """
        # 保存当前筛选状态（防止 clear() 丢失选择）
        current_filter = None
        if self.filter_combo.count() > 0:
            current_filter = self.filter_combo.itemData(self.filter_combo.currentIndex())

        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()

        # ItemData values: 'all' or shelf_stem string
        self.filter_combo.addItem("全部", userData="all")

        # 获取统一的 shelf 颜色映射
        shelf_color_map = _get_shelf_color_map()

        for name in sorted(shelf_color_map.keys()):
            self.filter_combo.addItem(name, userData=name)
            # 设置背景色和文字颜色
            bg_color, border_color = shelf_color_map[name]
            index = self.filter_combo.count() - 1
            self.filter_combo.setItemData(index, QtGui.QColor(bg_color), QtCore.Qt.BackgroundRole)
            self.filter_combo.setItemData(index, QtGui.QColor(TEXT_PRIMARY), QtCore.Qt.ForegroundRole)

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
        """填充标签筛选下拉菜单：全部标签、★ 收藏、各唯一标签。"""
        # 保存当前筛选状态（防止 clear() 丢失选择）
        current_tag = None
        if self.tag_filter_combo.count() > 0:
            current_tag = self.tag_filter_combo.itemData(self.tag_filter_combo.currentIndex())

        self.tag_filter_combo.blockSignals(True)
        self.tag_filter_combo.clear()

        # 添加"全部"和"收藏"选项
        self.tag_filter_combo.addItem("全部标签", userData="all")
        self.tag_filter_combo.addItem("★ 收藏", userData="favorites")

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

    def _get_filtered_tool_names(self):
        """根据当前筛选项返回工具名列表。"""
        data = self.filter_combo.itemData(self.filter_combo.currentIndex())
        tag_data = self.tag_filter_combo.itemData(self.tag_filter_combo.currentIndex())

        # 首先按 shelf 筛选
        if data == "all":
            filtered_names = list(_TOOL_NAMES)
        else:
            # shelf 名称过滤
            shelf_name = data
            filtered_names = [uid for uid in _TOOL_NAMES if uid in _TOOL_REGISTRY and _TOOL_REGISTRY[uid][0] == shelf_name]

        # 然后按标签/收藏筛选
        if tag_data == "favorites":
            # 收藏筛选
            favorites = ShelfToolsSettingsManager.get_favorites()
            filtered_names = [uid for uid in filtered_names if uid in favorites]
        elif tag_data != "all":
            # 标签筛选
            filtered_names = [
                uid for uid in filtered_names
                if tag_data in ShelfToolsCacheManager.get_tags(uid)
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
