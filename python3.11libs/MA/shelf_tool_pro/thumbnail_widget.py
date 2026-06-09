"""缩略图控件"""

import os
import re
import logging

from PySide6 import QtWidgets, QtGui, QtCore

from MA.common import ShelfToolsCacheManager, ShelfToolsSettingsManager
from MA.common.constants import SHELFTOOLS_NOTES_DIR
from MA.shelf_tool_pro.shelf_loader import execute_tool, drop_at_cursor, make_unique_id
from MA.shelf_tool_pro.styles import TEXT_SECONDARY, CONTEXT_MENU_STYLE
from MA.shelf_tool_pro.web_renderer import WebRenderer, WebRendererPool
from MA.shelf_tool_pro.markdown_text_edit import MarkdownTextEdit

logger = logging.getLogger("MA")

# ── 收藏图标（SVG，模块级只加载一次） ──────────────────────
_FAVORITE_ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "MA favorite.svg")
_FAVORITE_PIXMAP = QtGui.QPixmap(_FAVORITE_ICON_PATH) if os.path.isfile(_FAVORITE_ICON_PATH) else None

class ThumbnailWidget(QtWidgets.QWidget):
    """单个工具的缩略图控件，支持点击执行、拖拽放置、右键菜单。"""

    # ── 常量 ──────────────────────────────────
    _HORIZONTAL_GAP = 10    # 面板与缩略图水平间距
    _BOTTOM_MARGIN = 100    # 面板与屏幕底部间距（留出任务栏空间）
    _NOTES_PANEL_WIDTH = 450
    _NOTES_PANEL_HEIGHT = 600
    _NOTES_HIDE_DELAY = 100  # 鼠标离开备注面板后的延迟隐藏时间（ms）
    _DEFAULT_NOTES_SHOW_DELAY = 800  # 备注悬停延迟默认值（ms），可由设置面板覆盖

    def __init__(self, unique_id, display_name, size, parent=None, icon_path="", bg_color="", border_color=""):
        super().__init__(parent)
        self._unique_id = unique_id
        self._display_name = display_name
        self._drag_start = None
        self._size = 0
        self._notes_timer_id = None
        # 备注悬停延迟（ms）：由面板从 ShelfToolsSettingsManager 注入
        self._notes_show_delay = self._DEFAULT_NOTES_SHOW_DELAY
        self._icon_path = icon_path
        self._bg_color = bg_color
        self._border_color = border_color
        self._rendered_pixmap = None
        self._movie = None        # QMovie 实例（GIF 动画）
        self._movie_path = ""     # 当前 GIF 文件路径（用于对比更改）

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        # 图片容器（QWidget 容器用于叠加星标）
        self.image_container = QtWidgets.QWidget()
        self.image_container.setFixedSize(size + 2, size + 2)
        self.image_container.setStyleSheet("background-color: transparent;")
        
        self.image_label = QtWidgets.QLabel(self.image_container)
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: transparent;")
        self.image_label.setGeometry(0, 0, size + 2, size + 2)
        
        # 收藏图标（叠加在缩略图右上角，手动定位）
        self.favorite_star = QtWidgets.QLabel(self.image_container)
        star_size = max(16, size // 5)
        self.favorite_star.setFixedSize(star_size, star_size)
        self.favorite_star.move(size + 2 - star_size - 2, 2)
        self.favorite_star.setAlignment(QtCore.Qt.AlignCenter)
        self._update_favorite_icon(star_size)
        # 添加阴影效果，增加立体感
        shadow = QtWidgets.QGraphicsDropShadowEffect(self.favorite_star)
        shadow.setBlurRadius(20)
        shadow.setOffset(-4, 4)
        shadow.setColor(QtGui.QColor(0, 0, 0, 180))
        self.favorite_star.setGraphicsEffect(shadow)
        self.favorite_star.hide()  # 默认隐藏
        self.favorite_star.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.favorite_star.raise_()  # 确保在最上层
        
        layout.addWidget(self.image_container)

        # 名称标签（带背景色）
        self.name_label = QtWidgets.QLabel(display_name)
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self._update_name_label_style()
        layout.addWidget(self.name_label)

        self.setToolTip(display_name)
        self.setCursor(QtCore.Qt.OpenHandCursor)
        self.updateSize(size)

        # 初始化收藏状态
        self._update_favorite_star()

    def _update_favorite_star(self):
        """更新收藏星标显示状态。"""
        if ShelfToolsSettingsManager.is_favorite(self._unique_id):
            self.favorite_star.show()
        else:
            self.favorite_star.hide()

    def _update_favorite_icon(self, star_size):
        """更新收藏图标（SVG 缩放到指定尺寸）。"""
        if _FAVORITE_PIXMAP and not _FAVORITE_PIXMAP.isNull():
            scaled = _FAVORITE_PIXMAP.scaled(
                star_size, star_size,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            self.favorite_star.setPixmap(scaled)
            self.favorite_star.setStyleSheet("background-color: transparent;")
        else:
            # SVG 加载失败，回退到文字
            self.favorite_star.setText("★")
            self.favorite_star.setStyleSheet(
                f"color: #fbbf24; font-size: {star_size}px; font-weight: bold; background-color: transparent;")

    def _update_name_label_style(self):
        """更新名称标签样式（带背景色）。"""
        # 内置工具：固定白底黑字，覆盖默认的 shelf 颜色样式
        if self._is_builtin:
            self.name_label.setStyleSheet(
                "color: #000000; "
                "background-color: #ffffff; "
                "border: 1px solid #ffffff; "
                "border-radius: 4px; "
                "padding: 2px 8px; "
            )
        elif self._bg_color and self._border_color:
            # 半透明背景 + 边框
            self.name_label.setStyleSheet(
                f"color: {TEXT_SECONDARY}; "
                f"background-color: {self._bg_color}; "
                f"border: 2px solid {self._border_color}; "
                f"border-radius: 4px; "
                f"padding: 2px 8px; "
            )
        else:
            self.name_label.setStyleSheet(f"color: {TEXT_SECONDARY}; background-color: transparent;")

    def _on_toggle_favorite(self):
        """切换收藏状态并刷新面板。"""
        is_fav = ShelfToolsSettingsManager.toggle_favorite(self._unique_id)
        self._update_favorite_star()
        
        # 通知面板刷新（用于筛选状态更新）
        p = self.parent()
        while p is not None:
            if hasattr(p, '_on_favorite_changed'):
                p._on_favorite_changed()
                break
            p = p.parent()

    @staticmethod
    def _make_rounded_pixmap(size, radius, color):
        """创建指定圆角的纯色占位图。"""
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtGui.QColor(color))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(0, 0, size, size, radius, radius)
        painter.end()
        return pixmap

    def _get_available_geometry(self):
        """获取当前屏幕的可用区域（排除任务栏）。"""
        screen = QtGui.QGuiApplication.screenAt(self.mapToGlobal(QtCore.QPoint(0, 0)))
        if screen is None:
            screen = QtGui.QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def _clamp_to_screen(self, pos, width, height):
        """将面板位置约束在屏幕可用区域内，避免被任务栏或屏幕边缘裁剪。"""
        available = self._get_available_geometry()

        # 水平方向：优先右侧，超出则左侧；若左侧也超出则贴右边框
        if pos.x() + width > available.right():
            pos = self.mapToGlobal(QtCore.QPoint(-width - self._HORIZONTAL_GAP, 0))
        if pos.x() < available.left():
            pos.setX(available.left())
        if pos.x() + width > available.right():
            pos.setX(available.right() - width)

        # 垂直方向：底部超出则上移（留 _BOTTOM_MARGIN 间距），顶部超出则下移
        if pos.y() + height > available.bottom():
            pos.setY(available.bottom() - height - self._BOTTOM_MARGIN)
        if pos.y() < available.y():
            pos.setY(available.y())

        return pos

    def _position_dialog(self, dialog):
        """定位对话框：显示在缩略图右侧，超出屏幕时自动约束。"""
        dialog.adjustSize()
        QtWidgets.QApplication.processEvents()
        w = max(dialog.sizeHint().width(), dialog.minimumWidth())
        h = max(dialog.sizeHint().height(), dialog.minimumHeight())
        pos = self.mapToGlobal(QtCore.QPoint(self.width() + self._HORIZONTAL_GAP, 0))
        pos = self._clamp_to_screen(pos, w, h)
        dialog.move(pos)
        dialog.raise_()
        dialog.activateWindow()

    def updateSize(self, size):
        """更新控件大小。"""
        if size == self._size:
            return
        self._size = size
        name_h = max(16, size // 6)
        radius = max(3, size // 8)
        self.setFixedSize(size, size + 4 + name_h + 8)
        # +2 缓冲防止右边缘圆角被裁剪
        self.image_container.setFixedSize(size + 2, size + 2)
        self.name_label.setFixedHeight(name_h)
        font = self.name_label.font()
        font.setPointSize(max(7, size // 14))
        self.name_label.setFont(font)

        # 更新星标大小和位置
        star_size = max(16, size // 5)
        self.favorite_star.setFixedSize(star_size, star_size)
        self.favorite_star.move(size + 2 - star_size - 2, 2)
        self._update_favorite_icon(star_size)

        self._render_thumbnail(size)
        self._update_favorite_star()

    def previewSize(self, size):
        """Cheap live resize while dragging; final render happens on release."""
        name_h = max(16, size // 6)
        self.setFixedSize(size, size + 4 + name_h + 8)
        self.image_container.setFixedSize(size + 2, size + 2)
        self.image_label.setGeometry(0, 0, size + 2, size + 2)
        # 更新星标位置、大小和图标
        star_size = max(16, size // 5)
        self.favorite_star.setFixedSize(star_size, star_size)
        self.favorite_star.move(size + 2 - star_size - 2, 2)
        self._update_favorite_icon(star_size)
        self.name_label.setFixedHeight(name_h)
        font = self.name_label.font()
        font.setPointSize(max(7, size // 14))
        self.name_label.setFont(font)

        pixmap = self._rendered_pixmap
        if pixmap is None or pixmap.isNull():
            pixmap = self.image_label.pixmap()
        if pixmap is None or pixmap.isNull():
            return
        self.image_label.setPixmap(pixmap.scaled(
            size, size,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.FastTransformation,
        ))

    def _set_thumbnail_pixmap(self, pixmap):
        self._rendered_pixmap = QtGui.QPixmap(pixmap)
        self.image_label.setPixmap(pixmap)

    def _stop_gif(self):
        """停止并清理 QMovie，显式释放文件句柄。"""
        if self._movie:
            self._movie.stop()
            try:
                self._movie.frameChanged.disconnect(self._on_movie_frame)
            except (TypeError, RuntimeError):
                pass
            # 显式清空文件名释放文件句柄（Windows 文件锁定问题）
            self._movie.setFileName("")
            self._movie.deleteLater()
            self._movie = None
            self._movie_path = ""

    def _paint_rounded_image(self, painter, src_pixmap, size, radius):
        """在 painter 上绘制圆角图片：有透明通道则跳过背景色，否则铺背景。"""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)

        scaled = src_pixmap.scaled(
            size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

        # 有透明通道 → 跳过背景色，透明部分透出到面板
        has_alpha = src_pixmap.hasAlphaChannel()
        if not has_alpha:
            painter.setBrush(QtGui.QColor("#2d2d2d"))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(0, 0, size, size, radius, radius)

        # 圆角 clip 画图像
        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, size, size, radius, radius)
        painter.setClipPath(path)

        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)

    def _on_movie_frame(self, _frame):
        """QMovie 帧更新：用当前帧绘制圆角缩略图。"""
        if not self._movie:
            return
        frame_pixmap = self._movie.currentPixmap()
        if frame_pixmap.isNull():
            return
        size = self._size
        if size <= 0:
            return
        radius = max(3, size // 8)

        canvas = QtGui.QPixmap(size, size)
        canvas.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(canvas)
        self._paint_rounded_image(painter, frame_pixmap, size, radius)
        painter.end()

        self._set_thumbnail_pixmap(canvas)

    @property
    def _is_builtin(self) -> bool:
        """判断当前工具是否为内置工具。委托给 shelf_loader.is_builtin_tool。"""
        from MA.shelf_tool_pro.shelf_loader import is_builtin_tool
        return is_builtin_tool(self._unique_id)

    def _get_note(self) -> str:
        """获取当前工具的备注内容。内置工具从 BuiltinToolsCacheManager 读取。"""
        if self._is_builtin:
            from MA.common.settings import BuiltinToolsCacheManager
            return BuiltinToolsCacheManager.get_tool_note(self._unique_id) or ""
        else:
            from MA.common.settings import ShelfToolsCacheManager
            return ShelfToolsCacheManager.get_note(self._unique_id) or ""

    def _render_thumbnail(self, size):
        """渲染缩略图：优先读缓存 GIF/PNG/JPG，其次 Houdini 内部图标，否则灰色占位图。"""
        radius = max(3, size // 8)

        # 内置工具从 BuiltinToolsCacheManager 获取图标，用户工具从 ShelfToolsCacheManager 获取
        if self._is_builtin:
            from MA.common.settings import BuiltinToolsCacheManager
            cached_icon = BuiltinToolsCacheManager.get_tool_icon(self._unique_id)
        else:
            from MA.common.settings import ShelfToolsCacheManager
            cached_icon = ShelfToolsCacheManager.get_tool_icon(self._unique_id)
        
        cached_icon = cached_icon or self._icon_path

        if cached_icon and os.path.isfile(cached_icon):
            # ── GIF：启用 QMovie ──
            ext = os.path.splitext(cached_icon)[1].lower()
            if ext == ".gif":
                if self._movie_path != cached_icon:
                    self._stop_gif()
                    self._movie = QtGui.QMovie(cached_icon)
                    self._movie_path = cached_icon
                    self._movie.frameChanged.connect(self._on_movie_frame)
                    # 默认不播放，hover 才播
                    self._movie.stop()
                # 跳转到第一帧并用当前 size 重绘
                self._movie.jumpToFrame(0)
                self._on_movie_frame(0)
                return

            # ── 静态图 ──
            src = QtGui.QPixmap(cached_icon)
            if not src.isNull():
                canvas = QtGui.QPixmap(size, size)
                canvas.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(canvas)
                self._paint_rounded_image(painter, src, size, radius)
                painter.end()
                self._set_thumbnail_pixmap(canvas)
                # 上一步如果是 GIF 则停掉
                self._stop_gif()
                return

        # ── Houdini 内部图标名（如 "MISC_generic" 或 "hicon:/SVGIcons.index?COMMON_scattered.svg"）──
        if cached_icon:
            icon_pixmap = self._load_houdini_icon(cached_icon, size)
            if icon_pixmap is not None:
                canvas = QtGui.QPixmap(size, size)
                canvas.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(canvas)
                self._paint_rounded_image(painter, icon_pixmap, size, radius)
                painter.end()
                self._set_thumbnail_pixmap(canvas)
                self._stop_gif()
                return

        # 灰色占位图
        self._stop_gif()
        self._set_thumbnail_pixmap(self._make_rounded_pixmap(size, radius, "#2d2d2d"))

    def _load_houdini_icon(self, icon_ref, size):
        """从 Houdini 内部图标名加载 QPixmap（高 DPI 优化）。

        使用 hou.qt.Icon() API，通过 4x 超采样 + 平滑缩放解决放大后模糊问题。
        """
        try:
            import hou
        except ImportError:
            return None

        # 解析 icon_ref → 候选图标名列表
        candidates = []
        if icon_ref.startswith("hicon:"):
            if "?" in icon_ref:
                raw_name = icon_ref.split("?", 1)[1]
                candidates.append(raw_name)
                if raw_name.endswith(".svg"):
                    candidates.append(raw_name[:-4])
            else:
                candidates.append(icon_ref[len("hicon:"):])
        else:
            candidates.append(icon_ref)

        for name in candidates:
            try:
                qt_icon = hou.qt.Icon(name)
                if qt_icon is None or qt_icon.isNull():
                    continue
                # 4x 超采样 + 平滑缩放，解决大尺寸下模糊问题
                super_size = size * 4
                pixmap = qt_icon.pixmap(QtCore.QSize(super_size, super_size))
                if pixmap.isNull():
                    continue
                pixmap = pixmap.scaled(
                    size, size,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
                return pixmap
            except Exception:
                continue

        return None

    # ── 鼠标事件 ──────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_start = event.pos()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & QtCore.Qt.LeftButton) or self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() < 10:
            return
        drag = QtGui.QDrag(self)
        mime = QtCore.QMimeData()
        mime.setText(f"ma_tool:{self._unique_id}")
        drag.setMimeData(mime)
        drag.setPixmap(
            self.image_label.pixmap().scaled(64, 64, QtCore.Qt.KeepAspectRatio,
                                             QtCore.Qt.SmoothTransformation)
        )
        drag.exec(QtCore.Qt.CopyAction)
        drop_at_cursor(self._unique_id)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self._drag_start is not None:
            if (event.pos() - self._drag_start).manhattanLength() < 10:
                try:
                    execute_tool(self._unique_id)
                except SystemExit:
                    pass
        elif event.button() == QtCore.Qt.MiddleButton:
            self._open_notes_window()
        self._drag_start = None

    # ─ 右键菜单 ──────────────────────────────────
    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)
        
        # 收藏菜单项（根据当前状态显示"收藏"或"取消收藏"）
        is_fav = ShelfToolsSettingsManager.is_favorite(self._unique_id)
        fav_action = menu.addAction("取消收藏" if is_fav else "收藏")
        fav_action.triggered.connect(self._on_toggle_favorite)
        
        # 内置工具只显示收藏，不显示设置/标签/备注/删除
        if not self._is_builtin:
            menu.addSeparator()
            settings_action = menu.addAction("设置\u2026")
            settings_action.triggered.connect(self._on_settings)
            tags_action = menu.addAction("标签\u2026")
            notes_action = menu.addAction("备注")
            menu.addSeparator()
            delete_action = menu.addAction("删除")
            delete_action.triggered.connect(self._on_delete_tool)
            tags_action.triggered.connect(self._on_edit_tags)
            notes_action.triggered.connect(self._on_edit_notes)
        
        menu.exec(event.globalPos())

    def _on_edit_tags(self):
        """打开标签设置对话框。"""
        # 获取当前标签
        current_tags = ShelfToolsCacheManager.get_tags(self._unique_id)
        
        # 创建标签设置对话框
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"设置标签 — {self.name_label.text()}")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet("QDialog { background-color: #1D1D20; color: white; }")
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标签输入区域
        tags_group = QtWidgets.QGroupBox("标签")
        tags_group.setStyleSheet(
            "QGroupBox { color: #cccccc; font-size: 12px; border: 1px solid #3d3d3d; "
            "border-radius: 6px; margin-top: 12px; padding: 16px 12px 12px 12px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }"
        )
        group_layout = QtWidgets.QVBoxLayout(tags_group)
        group_layout.setSpacing(8)
        
        # 标签输入框
        tags_input = QtWidgets.QLineEdit()
        tags_input.setPlaceholderText("输入标签，用逗号分隔（如：建模,角色,rigging）")
        tags_input.setStyleSheet(
            "QLineEdit { background-color: #2d2d2d; color: white; border: 1px solid #3d3d3d; "
            "border-radius: 4px; padding: 6px; }"
            "QLineEdit:focus { border-color: #0d6399; }"
        )
        if current_tags:
            tags_input.setText(",".join(current_tags))
        
        group_layout.addWidget(tags_input)
        
        # 标签提示
        hint_lbl = QtWidgets.QLabel("支持中英文标签，多个标签用逗号分隔")
        hint_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        group_layout.addWidget(hint_lbl)
        
        layout.addWidget(tags_group)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("取消")
        cancel_btn.setStyleSheet(
            "QPushButton { background-color: #2d2d2d; color: white; border: 1px solid #3d3d3d; "
            "border-radius: 4px; padding: 8px 16px; }"
            "QPushButton:hover { background-color: #3d3d3d; }"
        )
        cancel_btn.clicked.connect(dialog.reject)
        
        ok_btn = QtWidgets.QPushButton("确定")
        ok_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; border: none; "
            "border-radius: 4px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        ok_btn.clicked.connect(dialog.accept)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
        
        # 定位：与备注面板一致，显示在缩略图右侧
        self._position_dialog(dialog)
        
        # 显示对话框
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            # 解析标签（支持中英文逗号分隔）
            tags_text = tags_input.text().strip()
            new_tags = []
            if tags_text:
                new_tags = [t.strip() for t in re.split(r'[,，]', tags_text) if t.strip()]
            
            # 保存标签
            ShelfToolsCacheManager.set_tags(self._unique_id, new_tags)
            
            # 通知面板刷新（用于标签筛选更新）
            p = self.parent()
            while p is not None:
                if hasattr(p, '_on_tags_changed'):
                    p._on_tags_changed()
                    break
                p = p.parent()

    def _on_settings(self):
        """打开工具设置对话框（首选项 + 内容标签页）。"""
        from MA.shelf_tool_pro.shelf_loader import _TOOL_REGISTRY, _TOOL_SCRIPTS
        if self._unique_id not in _TOOL_REGISTRY:
            return
        shelf_stem, tool_name, label, _, shelf_path = _TOOL_REGISTRY[self._unique_id]

        # 从缓存加载自定义图标（.shelf 的 icon 属性只存 Houdini 内部名）
        icon_path = ShelfToolsCacheManager.get_tool_icon(self._unique_id) or ""

        # 获取工具脚本内容
        script_content = _TOOL_SCRIPTS.get(self._unique_id, "")

        # 停止 GIF 释放文件锁（防止替换时 Windows 文件锁定）
        self._stop_gif()
        # 强制处理 deleteLater 事件，确保 QMovie 句柄立即释放
        QtWidgets.QApplication.processEvents()

        from MA.shelf_tool_pro.save_tool_dialog import ToolSettingsDialog
        dialog = ToolSettingsDialog(
            mode="edit",
            tool_name=tool_name,
            label=label,
            shelf_file_path=shelf_path,
            icon_path=icon_path,
            script_content=script_content,
            parent=self,
        )
        # 定位：与备注面板一致，显示在缩略图右侧
        self._position_dialog(dialog)

        if dialog.exec() != QtWidgets.QDialog.Accepted:
            # 用户取消，重新加载GIF恢复播放
            self._render_thumbnail(self._size)
            return
        result = dialog.get_result()
        if result is None:
            return

        # 缓存图标路径（始终执行，与 .shelf 文件无关）
        new_icon = result.get("icon_path", "")
        ShelfToolsCacheManager.set_tool_icon(self._unique_id, new_icon)

        # 检查名称或标签是否改变
        new_tool_name = result["tool_name"]
        new_label = result["label"]
        name_changed = new_tool_name != tool_name
        label_changed = new_label != label

        if name_changed or label_changed:
            from MA.shelf_tool_pro.shelf_saver import rename_tool_in_shelf, update_tool_in_shelf
            
            if name_changed:
                # 重命名工具（同时更新 label）
                updated = rename_tool_in_shelf(
                    shelf_file=shelf_path,
                    old_name=tool_name,
                    new_name=new_tool_name,
                    new_label=new_label,
                )
            else:
                # 仅更新 label
                updated = update_tool_in_shelf(
                    shelf_file=shelf_path,
                    tool_name=tool_name,
                    new_label=new_label,
                )
            
            if not updated:
                QtWidgets.QMessageBox.warning(self, "错误",
                    "更新工具失败。")
                return
            
            # 如果名称改变了，需要迁移缓存数据
            if name_changed:
                self._migrate_cache_data(self._unique_id, make_unique_id(os.path.dirname(shelf_path), shelf_stem, new_tool_name))

        # 更新脚本代码（如果有变更）
        new_code = result.get("code")
        if new_code is not None and new_code != script_content:
            from MA.shelf_tool_pro.shelf_saver import update_tool_script_in_shelf
            # 如果名称改变了，用新名称；否则用原名称
            target_name = new_tool_name if name_changed else tool_name
            if not update_tool_script_in_shelf(shelf_path, target_name, new_code):
                QtWidgets.QMessageBox.warning(self, "错误",
                    "更新工具脚本失败。")
                return

        # 刷新面板
        from MA.shelf_tool_pro.shelf_loader import refresh_tools
        refresh_tools()
        # 通知父级面板刷新（通过 parent chain 找到面板）
        p = self.parent()
        while p is not None:
            if hasattr(p, '_refresh_tools'):
                p._refresh_tools()
                break
            p = p.parent()

    def _migrate_cache_data(self, old_unique_id: str, new_unique_id: str):
        """迁移缓存数据（图标、标签、收藏、备注）到新的 unique_id。"""
        # 迁移图标缓存
        old_icon = ShelfToolsCacheManager.get_tool_icon(old_unique_id)
        if old_icon:
            ShelfToolsCacheManager.set_tool_icon(new_unique_id, old_icon)
            ShelfToolsCacheManager.remove_tool_icon(old_unique_id)
        
        # 迁移标签缓存
        old_tags = ShelfToolsCacheManager.get_tags(old_unique_id)
        if old_tags:
            ShelfToolsCacheManager.set_tags(new_unique_id, old_tags)
        
        # 迁移收藏状态
        if ShelfToolsSettingsManager.is_favorite(old_unique_id):
            favs = list(ShelfToolsSettingsManager.get_favorites())
            if old_unique_id in favs:
                favs.remove(old_unique_id)
            if new_unique_id not in favs:
                favs.insert(0, new_unique_id)
            ShelfToolsSettingsManager.set_favorites(favs)
        
        # 迁移备注文件
        old_note_path = os.path.join(SHELFTOOLS_NOTES_DIR, f"{old_unique_id}.md")
        new_note_path = os.path.join(SHELFTOOLS_NOTES_DIR, f"{new_unique_id}.md")
        if os.path.exists(old_note_path):
            try:
                os.rename(old_note_path, new_note_path)
            except OSError:
                pass

    def _on_edit_notes(self):
        """弹出分屏对话框：左侧编辑，右侧实时预览。"""
        current_note = self._get_note()
        
        # 创建自定义对话框以控制窗口大小
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"Edit Notes — {self.name_label.text()}")
        dialog.resize(900, 700)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # 分屏布局：左侧编辑，右侧预览
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # 左侧：Markdown-aware 编辑器（局部变量，避免实例引用泄漏）
        text_edit = MarkdownTextEdit()
        text_edit.setPlainText(current_note)
        text_edit.setStyleSheet(
            "QTextEdit { "
            "  background-color: #1F1F24; "
            "  color: #ffffff; "
            "  border: 1px solid #3d3d3d; "
            "  border-radius: 4px; "
            "  padding: 8px; "
            "  font-family: Consolas, monospace; "
            "  font-size: 13px; "
            "}"
        )
        splitter.addWidget(text_edit)
        
        # 右侧：实时预览（局部变量）
        preview_renderer = WebRenderer()
        preview_browser = preview_renderer.get_widget()
        preview_browser.setStyleSheet(
            "QWebEngineView { "
            "  background-color: #1F1F24; "
            "  border: 1px solid #3d3d3d; "
            "  border-radius: 4px; "
            "}"
        )
        # 初始预览
        preview_renderer.render(current_note)
        splitter.addWidget(preview_browser)
        
        # 对话框关闭时销毁 WebRenderer 释放 QtWebEngineProcess
        dialog.finished.connect(preview_renderer.get_widget().deleteLater)
        
        # 设置分割比例 50:50
        splitter.setSizes([450, 450])
        
        layout.addWidget(splitter)
        
        # 防抖定时器：300ms 延迟更新预览（局部变量）
        preview_timer = QtCore.QTimer()
        preview_timer.setSingleShot(True)
        
        def _on_text_changed():
            preview_timer.start(300)  # 300ms debounce
        
        def _update_preview():
            markdown_text = text_edit.toPlainText()
            preview_renderer.render(markdown_text)
        
        preview_timer.timeout.connect(_update_preview)
        text_edit.textChanged.connect(_on_text_changed)
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("Cancel")
        ok_btn = QtWidgets.QPushButton("OK")
        cancel_btn.setMinimumWidth(80)
        ok_btn.setMinimumWidth(80)
        cancel_btn.setStyleSheet(
            "QPushButton { "
            "  background-color: #2d2d2d; "
            "  color: white; "
            "  border: 1px solid #3d3d3d; "
            "  border-radius: 4px; "
            "  padding: 8px 16px; "
            "}"
            "QPushButton:hover { background-color: #3d3d3d; }"
        )
        ok_btn.setStyleSheet(
            "QPushButton { "
            "  background-color: #4CAF50; "
            "  color: white; "
            "  border: none; "
            "  border-radius: 4px; "
            "  padding: 8px 16px; "
            "  font-weight: bold; "
            "}"
            "QPushButton:hover { background-color: #45a049; }"
        )
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
        
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        
        # 定位：约束在屏幕可用区域
        pos = self.mapToGlobal(QtCore.QPoint(self.width() + self._HORIZONTAL_GAP, 0))
        pos = self._clamp_to_screen(pos, dialog.width(), dialog.height())
        dialog.move(pos)
        
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            new_note = text_edit.toPlainText()
            ShelfToolsCacheManager.set_note(self._unique_id, new_note)

    def _on_delete_tool(self):
        """删除当前工具：确认 → 从 .shelf 移除 → 清理 → 刷新面板。"""
        from MA.shelf_tool_pro.shelf_loader import _TOOL_REGISTRY, refresh_tools
        from MA.shelf_tool_pro.shelf_saver import remove_tool_from_shelf
        from MA.common.constants import SHELFTOOLS_NOTES_DIR

        # 确认对话框
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("删除工具")
        msg_box.setText(
            f"确定要删除 '{self.name_label.text()}' 吗？\n\n"
            "此操作将从 .shelf 文件中移除该工具及相关数据。"
        )
        cancel_btn = msg_box.addButton("取消", QtWidgets.QMessageBox.RejectRole)
        ok_btn = msg_box.addButton("确定", QtWidgets.QMessageBox.AcceptRole)
        msg_box.setDefaultButton(cancel_btn)

        # 设置按钮样式
        from MA.shelf_tool_pro import styles
        ok_btn.setStyleSheet(
            f"QPushButton {{ background-color: {styles.ACCENT_BLUE}; color: {styles.TEXT_PRIMARY}; "
            f"border: none; padding: 6px 10px; border-radius: 10px; font-weight: bold; min-width: 40px; }}"
            f"QPushButton:hover {{ background-color: #0a4d7a; }}"
            f"QPushButton:pressed {{ background-color: #083a5f; }}"
        )
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background-color: {styles.BG_INPUT}; color: {styles.TEXT_PRIMARY}; "
            f"border: 1px solid {styles.BORDER_COLOR}; padding: 6px 10px; border-radius: 10px; min-width: 40px; }}"
            f"QPushButton:hover {{ background-color: {styles.BG_HOVER}; }}"
            f"QPushButton:pressed {{ background-color: #252525; }}"
        )

        msg_box.exec()
        if msg_box.clickedButton() != ok_btn:
            return

        # 从注册表获取工具信息
        if self._unique_id not in _TOOL_REGISTRY:
            logger.warning("Tool '%s' not found in registry", self._unique_id)
            QtWidgets.QMessageBox.warning(self, "错误", "未在注册表中找到该工具。")
            return

        _, tool_name, _, _, shelf_path = _TOOL_REGISTRY[self._unique_id]

        # 1. 从 .shelf 文件移除
        if not remove_tool_from_shelf(tool_name, shelf_path):
            QtWidgets.QMessageBox.warning(self, "错误",
                f"从工具架移除工具失败\n{shelf_path}")
            return

        # 2. 删除备注文件
        note_path = os.path.join(SHELFTOOLS_NOTES_DIR, f"{self._unique_id}.md")
        if os.path.exists(note_path):
            try:
                os.remove(note_path)
            except OSError as e:
                logger.warning("Failed to remove notes %s: %s", note_path, e)

        # 3. 停止 GIF 释放文件锁，再清除图标缓存并删除文件
        self._stop_gif()
        ShelfToolsCacheManager.remove_tool_icon(self._unique_id)

        # 4. 找到父 panel（在 detach 前保存引用，否则 parent() 返回 None）
        panel = self.parent()
        while panel is not None and not hasattr(panel, '_refresh_tools'):
            panel = panel.parent()

        # 5. 删除自身控件
        self.setParent(None)
        self.deleteLater()

        # 6. 刷新面板
        refresh_tools()
        if panel is not None:
            panel._refresh_tools()

    def _open_notes_window(self):
        """以悬浮窗口方式打开备注（只读，渲染 markdown，带标题栏）。"""
        # 无备注则无事发生
        current_note = self._get_note()
        if not current_note.strip():
            return

        # 创建独立窗口（带标题栏）
        notes_window = QtWidgets.QDialog(self)
        notes_window.setWindowTitle(f"Notes - {self.name_label.text()}")
        notes_window.setWindowFlags(
            QtCore.Qt.WindowType.Dialog
            | QtCore.Qt.WindowType.WindowCloseButtonHint
            | QtCore.Qt.WindowType.WindowMaximizeButtonHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        notes_window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        notes_window.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, False)
        notes_window.resize(450, 600)
        notes_window.setStyleSheet("background-color: #1F1F24;")

        # 垂直布局
        layout = QtWidgets.QVBoxLayout(notes_window)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # 备注显示区（只读）
        notes_renderer = WebRenderer()
        notes_window._notes_renderer = notes_renderer  # 绑定到窗口防止 GC
        notes_display = notes_renderer.get_widget()
        notes_display.setStyleSheet(
            "QWebEngineView { "
            "  background-color: #1F1F24; "
            "  border: none; "
            "}"
        )
        layout.addWidget(notes_display)
        # Render after positioning so the window is only shown with ready content.
        
        # 窗口关闭时彻底销毁 WebRenderer 释放 QtWebEngineProcess
        view = notes_display
        page = view.page()
        def _cleanup_notes_window():
            notes_window._ready_to_show = False
            page.deleteLater()
            view.deleteLater()

        notes_window.finished.connect(_cleanup_notes_window)
        
        # 定位：约束在屏幕可用区域
        pos = self.mapToGlobal(QtCore.QPoint(self.width() + self._HORIZONTAL_GAP, 0))
        pos = self._clamp_to_screen(pos, notes_window.width(), notes_window.height())
        notes_window.move(pos)
        notes_window._ready_to_show = True

        def _show_after_render(_=None):
            if not getattr(notes_window, "_ready_to_show", False):
                return
            notes_window.show()
            notes_window.raise_()
            notes_window.activateWindow()

        notes_renderer.render(current_note, _show_after_render, fade=True)

    def enterEvent(self, event):
        """鼠标进入：启动延迟定时器（可由设置面板调整） + GIF 播放。"""
        super().enterEvent(event)
        # 启动备注定时器（延迟由设置面板控制，默认 800ms）
        self._notes_timer_id = self.startTimer(self._notes_show_delay)
        # 播放 GIF
        if self._movie:
            self._movie.start()

    def set_notes_show_delay(self, value: int):
        """更新备注悬停延迟（ms）。由设置面板在用户调整时调用。

        正在等待的定时器不会被重置——只影响下一次 enterEvent。
        """
        self._notes_show_delay = max(100, min(2000, int(value)))

    def leaveEvent(self, event):
        """鼠标离开：停止定时器 + GIF + 检查是否移向备注面板。"""
        super().leaveEvent(event)
        if self._notes_timer_id is not None:
            self.killTimer(self._notes_timer_id)
            self._notes_timer_id = None
        # 停止 GIF
        if self._movie:
            self._movie.stop()
        
        # 检查鼠标是否移向备注面板
        if WebRendererPool.has_renderer():
            notes_panel = WebRendererPool.get_renderer().get_widget()
            if notes_panel.isVisible():
                # 延迟隐藏，给鼠标移动到备注面板的时间
                QtCore.QTimer.singleShot(150, self._delayed_hide_notes)
            else:
                WebRendererPool.hide_notes()

    def timerEvent(self, event):
        """定时器触发：备注面板显示。"""
        if self._notes_timer_id is not None and event.timerId() == self._notes_timer_id:
            self._notes_timer_id = None
            logger.debug("timerEvent: notes timer triggered for %s", self._unique_id)
            self._show_notes_panel()
        super().timerEvent(event)

    def _show_notes_panel(self):
        """显示备注面板：下方→右侧→左侧→上方，始终不遮挡缩略图。"""
        note_text = self._get_note()
        if not note_text or not note_text.strip():
            return

        self._install_notes_event_filters()

        panel_width = WebRendererPool._NOTES_PANEL_WIDTH
        panel_height = WebRendererPool._NOTES_PANEL_HEIGHT
        gap = 10
        available = self._get_available_geometry()

        # 缩略图在屏幕上的边界
        tl = self.mapToGlobal(QtCore.QPoint(0, 0))
        widget_rect = QtCore.QRect(tl, self.size())

        pos = None

        # 1. 下方（固定间距，不随缩略图大小变化）
        below_y = widget_rect.bottom() + gap
        if below_y + panel_height <= available.bottom():
            pos = QtCore.QPoint(widget_rect.x(), below_y)

        # 2. 上方
        if pos is None:
            above_y = widget_rect.top() - panel_height - gap
            if above_y >= available.top():
                pos = QtCore.QPoint(widget_rect.x(), above_y)

        # 3. 右侧（垂直对齐顶部）
        if pos is None:
            right_x = widget_rect.right() + gap
            if right_x + panel_width <= available.right():
                pos = QtCore.QPoint(right_x, widget_rect.top())

        # 4. 左侧（垂直对齐顶部）
        if pos is None:
            left_x = widget_rect.left() - panel_width - gap
            if left_x >= available.left():
                pos = QtCore.QPoint(left_x, widget_rect.top())

        # 5. 保底
        if pos is None:
            pos = QtCore.QPoint(widget_rect.x(), below_y)
            pos = self._clamp_to_screen(pos, panel_width, panel_height)

        WebRendererPool.show_notes(note_text, pos)

    def _install_notes_event_filters(self):
        """确保当前缩略图已注册为备注面板的事件过滤器。"""
        if getattr(self, '_notes_filter_installed', False):
            return
        renderer = WebRendererPool.get_renderer()
        renderer.get_widget().installEventFilter(self)
        self._notes_filter_installed = True

    def _hide_notes_panel(self):
        """隐藏备注面板。"""
        WebRendererPool.hide_notes()

    def _delayed_hide_notes(self):
        """延迟隐藏备注面板（检查鼠标是否在备注面板上）。"""
        if not WebRendererPool._mouse_in_notes:
            WebRendererPool.hide_notes()

    def eventFilter(self, obj, event):
        """事件过滤器：检测鼠标进入/离开备注面板。"""
        if WebRendererPool.is_notes_panel(obj):
            if event.type() == QtCore.QEvent.Type.Enter:
                WebRendererPool._mouse_in_notes = True
            elif event.type() == QtCore.QEvent.Type.Leave:
                WebRendererPool._mouse_in_notes = False
                QtCore.QTimer.singleShot(self._NOTES_HIDE_DELAY, self._hide_notes_panel)
        return super().eventFilter(obj, event)
