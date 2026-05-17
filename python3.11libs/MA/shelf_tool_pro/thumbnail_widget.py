"""缩略图控件"""

import os
import shutil
import logging

from PySide6 import QtWidgets, QtGui, QtCore

from MA.common import ShelfToolsSettingsManager, ShelfToolsCacheManager
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

    def __init__(self, unique_id, display_name, size, parent=None, custom_name=None, custom_image_info=None):
        super().__init__(parent)
        self._unique_id = unique_id
        self._display_name = display_name
        self._drag_start = None
        self._size = 0
        self._movie = None
        self._gif_timer_id = None
        self._notes_timer_id = None
        self._custom_image_path = None
        self._is_gif = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.image_label)

        name_to_display = custom_name if custom_name else display_name
        self.name_label = QtWidgets.QLabel(name_to_display)
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.name_label.setStyleSheet(f"color: {TEXT_SECONDARY}; background-color: transparent;")
        layout.addWidget(self.name_label)

        self.setToolTip(display_name)
        self.setCursor(QtCore.Qt.OpenHandCursor)
        self.updateSize(size)

        if custom_image_info:
            self._custom_image_path = custom_image_info.get("path")
            self._is_gif = custom_image_info.get("is_gif", False)
            self._load_custom_image()

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

        if self._custom_image_path:
            self._load_custom_image()
        else:
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
        rename_action = menu.addAction("Rename")
        set_image_action = menu.addAction("Set Image")
        notes_action = menu.addAction("Notes")
        rename_action.triggered.connect(self._on_rename)
        set_image_action.triggered.connect(self._on_set_image)
        notes_action.triggered.connect(self._on_edit_notes)
        menu.exec(event.globalPos())

    def _on_rename(self):
        """弹出改名对话框。"""
        current_name = self.name_label.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "Rename", "Enter new name:", text=current_name)
        if ok and new_name.strip():
            self.name_label.setText(new_name.strip())
            ShelfToolsCacheManager.set_custom_name(self._unique_id, new_name.strip())

    def _on_set_image(self):
        """弹出文件选择对话框，设置自定义缩略图。"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Thumbnail Image", "", "Images (*.jpg *.jpeg *.png *.gif)")
        if not file_path:
            return

        thumb_dir = ShelfToolsSettingsManager.get_thumbnail_directory()
        os.makedirs(thumb_dir, exist_ok=True)

        ext = os.path.splitext(file_path)[1].lower()
        dest_filename = f"{self._unique_id}_custom{ext}"
        dest_path = os.path.join(thumb_dir, dest_filename)

        shutil.copy2(file_path, dest_path)

        is_gif = ext == ".gif"
        ShelfToolsCacheManager.set_custom_image(self._unique_id, dest_path, is_gif)

        self._custom_image_path = dest_path
        self._is_gif = is_gif
        self._load_custom_image()

    def _on_edit_notes(self):
        """弹出分屏对话框：左侧编辑，右侧实时预览。"""
        current_note = ShelfToolsCacheManager.get_note(self._unique_id) or ""
        
        # 创建自定义对话框以控制窗口大小
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Edit Notes")
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
        # 渲染 markdown
        notes_renderer.render(current_note)
        
        # 窗口关闭时彻底销毁 WebRenderer 释放 QtWebEngineProcess
        view = notes_display
        page = view.page()
        notes_window.finished.connect(lambda: (page.deleteLater(), view.deleteLater()))
        
        # 定位：约束在屏幕可用区域
        pos = self.mapToGlobal(QtCore.QPoint(self.width() + self._HORIZONTAL_GAP, 0))
        pos = self._clamp_to_screen(pos, notes_window.width(), notes_window.height())
        notes_window.move(pos)
        notes_window.show()
        notes_window.raise_()
        notes_window.activateWindow()

    def _load_custom_image(self):
        """加载自定义图片到 image_label。GIF 默认显示第一帧。"""
        if not self._custom_image_path or not os.path.exists(self._custom_image_path):
            return

        self._stop_gif_animation()
        # 清理旧 QMovie 对象
        if self._movie:
            self._movie.deleteLater()
            self._movie = None

        if self._is_gif:
            self._movie = QtGui.QMovie(self._custom_image_path)
            self._movie.setCacheMode(QtGui.QMovie.CacheAll)
            self._movie.jumpToFrame(0)
            self._movie.frameChanged.connect(self._on_gif_frame_changed)
            self._on_gif_frame_changed()
        else:
            src_pixmap = QtGui.QPixmap(self._custom_image_path)
            self._render_to_label(src_pixmap)

    def _on_gif_frame_changed(self):
        """GIF 帧变化时更新显示。"""
        if not self._movie:
            return
        pixmap = self._movie.currentPixmap()
        if not pixmap.isNull():
            self._render_to_label(pixmap)

    def _render_to_label(self, src_pixmap):
        """将源图片缩放、居中、圆角化后显示在 image_label 上。"""
        size = self._size
        if size <= 0:
            return
        radius = max(3, size // 8)

        # 缩放到适应 size x size 区域，保持比例
        scaled = src_pixmap.scaled(
            size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

        # 创建精确大小的透明画布，居中绘制
        canvas = QtGui.QPixmap(size, size)
        canvas.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(canvas)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()

        # 应用圆角遮罩（带灰色背景）
        rounded = self._apply_rounded_mask_with_bg(canvas, radius, size)
        self.image_label.setPixmap(rounded)

    @staticmethod
    def _apply_rounded_mask_with_bg(pixmap, radius, final_size):
        """对图片应用圆角遮罩，并添加灰色背景以显示长方形图片的圆角。"""
        result = QtGui.QPixmap(final_size, final_size)
        result.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(result)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)

        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, final_size, final_size, radius, radius)

        # 1. 绘制灰色背景
        painter.fillPath(path, QtGui.QColor("#2d2d2d"))
        # 2. 裁剪并绘制图片
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return result

    def enterEvent(self, event):
        """鼠标进入：启动 500ms 延迟定时器（GIF 动画 + 备注面板）。"""
        super().enterEvent(event)
        logger.debug("enterEvent: unique_id=%s, is_gif=%s, has_notes=%s", 
                     self._unique_id, self._is_gif, 
                     ShelfToolsCacheManager.get_note(self._unique_id))
        if self._is_gif and self._movie:
            self._gif_timer_id = self.startTimer(500)
        # 始终启动 notes timer（无论是否有 GIF）
        self._notes_timer_id = self.startTimer(500)

    def leaveEvent(self, event):
        """鼠标离开：停止定时器，停止 GIF 动画，检查是否移向备注面板。"""
        super().leaveEvent(event)
        if self._gif_timer_id is not None:
            self.killTimer(self._gif_timer_id)
            self._gif_timer_id = None
        self._stop_gif_animation()
        if self._notes_timer_id is not None:
            self.killTimer(self._notes_timer_id)
            self._notes_timer_id = None
        
        # 检查鼠标是否移向备注面板
        if WebRendererPool.has_renderer():
            notes_panel = WebRendererPool.get_renderer().get_widget()
            if notes_panel.isVisible():
                # 延迟隐藏，给鼠标移动到备注面板的时间
                QtCore.QTimer.singleShot(150, self._delayed_hide_notes)
            else:
                WebRendererPool.hide_notes()

    def timerEvent(self, event):
        """定时器触发：GIF 动画 / 备注面板显示。"""
        # 处理 GIF timer
        if self._gif_timer_id is not None and event.timerId() == self._gif_timer_id:
            self._gif_timer_id = None
            self._start_gif_animation()
        # 处理 notes timer
        if self._notes_timer_id is not None and event.timerId() == self._notes_timer_id:
            self._notes_timer_id = None
            logger.debug("timerEvent: notes timer triggered for %s", self._unique_id)
            self._show_notes_panel()
        super().timerEvent(event)

    def _start_gif_animation(self):
        """开始播放 GIF 动画。"""
        if self._movie and self._is_gif:
            if self._movie.state() == QtGui.QMovie.NotRunning:
                self._movie.start()
            elif self._movie.paused():
                self._movie.setPaused(False)

    def _stop_gif_animation(self):
        """停止 GIF 动画，恢复显示第一帧。"""
        if self._movie:
            self._movie.stop()
            self._movie.jumpToFrame(0)
            self._on_gif_frame_changed()

    def _show_notes_panel(self):
        """显示备注面板（如有备注内容）。"""
        note_text = ShelfToolsCacheManager.get_note(self._unique_id)
        if not note_text or not note_text.strip():
            return

        # 安装事件过滤器到所有已存在的渲染器面板上
        self._install_notes_event_filters()

        # 智能定位
        panel_width = WebRendererPool._NOTES_PANEL_WIDTH
        panel_height = WebRendererPool._NOTES_PANEL_HEIGHT
        pos_above = self.mapToGlobal(QtCore.QPoint(0, -panel_height))
        available = self._get_available_geometry()

        if pos_above.y() < available.y():
            pos = self.mapToGlobal(QtCore.QPoint(0, self.height()))
        else:
            pos = pos_above

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