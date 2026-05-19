"""缩略图控件"""

import os
import logging

from PySide6 import QtWidgets, QtGui, QtCore

from MA.common import ShelfToolsCacheManager
from MA.shelf_tool_pro.shelf_loader import execute_tool, drop_at_cursor
from MA.shelf_tool_pro.styles import TEXT_SECONDARY, CONTEXT_MENU_STYLE
from MA.shelf_tool_pro.web_renderer import WebRenderer, WebRendererPool
from MA.shelf_tool_pro.markdown_text_edit import MarkdownTextEdit

logger = logging.getLogger("MA")

class ThumbnailWidget(QtWidgets.QWidget):
    """单个工具的缩略图控件，支持点击执行、拖拽放置、右键菜单。"""

    # ── 常量 ──────────────────────────────────
    _HORIZONTAL_GAP = 10    # 面板与缩略图水平间距
    _BOTTOM_MARGIN = 20     # 面板与屏幕底部间距
    _NOTES_PANEL_WIDTH = 450
    _NOTES_PANEL_HEIGHT = 600
    _NOTES_HIDE_DELAY = 100  # 鼠标离开备注面板后的延迟隐藏时间（ms）

    def __init__(self, unique_id, display_name, size, parent=None, icon_path=""):
        super().__init__(parent)
        self._unique_id = unique_id
        self._display_name = display_name
        self._drag_start = None
        self._size = 0
        self._notes_timer_id = None
        self._icon_path = icon_path
        self._movie = None        # QMovie 实例（GIF 动画）
        self._movie_path = ""     # 当前 GIF 文件路径（用于对比更改）

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.image_label)

        self.name_label = QtWidgets.QLabel(display_name)
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.name_label.setStyleSheet(f"color: {TEXT_SECONDARY}; background-color: transparent;")
        layout.addWidget(self.name_label)

        self.setToolTip(display_name)
        self.setCursor(QtCore.Qt.OpenHandCursor)
        self.updateSize(size)

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

    def updateSize(self, size):
        """更新控件大小。"""
        if size == self._size:
            return
        self._size = size
        name_h = max(14, size // 6)
        radius = max(3, size // 8)
        self.setFixedSize(size, size + 4 + name_h + 8)
        # +2 缓冲防止右边缘圆角被裁剪
        self.image_label.setFixedSize(size + 2, size + 2)
        self.name_label.setFixedHeight(name_h)
        font = self.name_label.font()
        font.setPointSize(max(7, size // 16))
        self.name_label.setFont(font)

        self._render_thumbnail(size)

    def _stop_gif(self):
        """停止并清理 QMovie。"""
        if self._movie:
            self._movie.stop()
            try:
                self._movie.frameChanged.disconnect(self._on_movie_frame)
            except (TypeError, RuntimeError):
                pass
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

        self.image_label.setPixmap(canvas)

    def _render_thumbnail(self, size):
        """渲染缩略图：优先读缓存 GIF/PNG/JPG，其次 .shelf 图标路径，否则灰色占位图。"""
        radius = max(3, size // 8)

        # 从缓存取图标路径
        from MA.common.settings import ShelfToolsCacheManager
        cached_icon = ShelfToolsCacheManager.get_tool_icon(self._unique_id) or self._icon_path

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
                self.image_label.setPixmap(canvas)
                # 上一步如果是 GIF 则停掉
                self._stop_gif()
                return

        # 灰色占位图
        self._stop_gif()
        self.image_label.setPixmap(self._make_rounded_pixmap(size, radius, "#2d2d2d"))

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
        settings_action = menu.addAction("设置\u2026")
        notes_action = menu.addAction("备注")
        menu.addSeparator()
        delete_action = menu.addAction("删除")
        settings_action.triggered.connect(self._on_settings)
        notes_action.triggered.connect(self._on_edit_notes)
        delete_action.triggered.connect(self._on_delete_tool)
        menu.exec(event.globalPos())

    def _on_settings(self):
        """打开工具设置对话框。"""
        from MA.shelf_tool_pro.shelf_loader import _TOOL_REGISTRY
        if self._unique_id not in _TOOL_REGISTRY:
            return
        _, tool_name, label, _, shelf_path = _TOOL_REGISTRY[self._unique_id]

        # 从缓存加载自定义图标（.shelf 的 icon 属性只存 Houdini 内部名）
        from MA.common.settings import ShelfToolsCacheManager
        icon_path = ShelfToolsCacheManager.get_tool_icon(self._unique_id) or ""

        from MA.shelf_tool_pro.save_tool_dialog import ToolSettingsDialog
        dialog = ToolSettingsDialog(
            mode="edit",
            node_paths=[],
            tool_name=tool_name,
            label=label,
            shelf_file_path=shelf_path,
            icon_path=icon_path,
            parent=self,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        result = dialog.get_result()
        if result is None:
            return

        # 更新 .shelf 文件中的 label（icon 只支持 Houdini 内部图标名，不写入）
        from MA.shelf_tool_pro.shelf_saver import update_tool_in_shelf
        updated = update_tool_in_shelf(
            shelf_file=result["shelf_file"],
            tool_name=result["tool_name"],
            new_label=result["label"],
        )
        if not updated:
            QtWidgets.QMessageBox.warning(self, "错误",
                "更新工具失败。")
            return

        # 缓存图标路径
        from MA.common.settings import ShelfToolsCacheManager
        new_icon = result.get("icon_path", "")
        ShelfToolsCacheManager.set_tool_icon(self._unique_id, new_icon)

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

    def _on_edit_notes(self):
        """弹出分屏对话框：左侧编辑，右侧实时预览。"""
        current_note = ShelfToolsCacheManager.get_note(self._unique_id) or ""
        
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
        from MA.common import ShelfToolsCacheManager
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

        # 3. 清除图标缓存
        from MA.common.settings import ShelfToolsCacheManager
        ShelfToolsCacheManager.remove_tool_icon(self._unique_id)

        # 5. 找到父 panel（在 detach 前保存引用）
        panel = self.parent()
        while panel is not None and not hasattr(panel, '_refresh_tools'):
            panel = panel.parent()

        # 6. 删除自身控件
        self.setParent(None)
        self.deleteLater()

        # 7. 刷新面板
        refresh_tools()
        if panel is not None:
            panel._refresh_tools()

    def _open_notes_window(self):
        """以悬浮窗口方式打开备注（只读，渲染 markdown，带标题栏）。"""
        # 无备注则无事发生
        current_note = ShelfToolsCacheManager.get_note(self._unique_id) or ""
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
        """鼠标进入：启动 500ms 延迟定时器 + GIF 播放。"""
        super().enterEvent(event)
        # 启动备注定时器
        self._notes_timer_id = self.startTimer(500)
        # 播放 GIF
        if self._movie:
            self._movie.start()

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
        note_text = ShelfToolsCacheManager.get_note(self._unique_id)
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
