"""缩略图控件。"""

import os
import shutil
import logging

from PySide6 import QtWidgets, QtGui, QtCore

from MA.common import ShelfToolsSettingsManager, ShelfToolsCacheManager
from MA.shelf_tool_pro.shelf_loader import execute_tool, drop_at_cursor
from MA.shelf_tool_pro.styles import TEXT_SECONDARY, CONTEXT_MENU_STYLE

logger = logging.getLogger("MA")


class ThumbnailWidget(QtWidgets.QWidget):
    """单个工具的缩略图控件，支持点击执行、拖拽放置、右键菜单。"""

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
        self._notes_panel = None

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

        self._init_notes_panel()

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
        """弹出多行文本输入对话框，编辑备注。"""
        current_note = ShelfToolsCacheManager.get_note(self._unique_id) or ""
        new_note, ok = QtWidgets.QInputDialog.getMultiLineText(
            self, "Edit Notes", "Enter notes (markdown supported):", text=current_note)
        if ok:
            ShelfToolsCacheManager.set_note(self._unique_id, new_note)

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
        """鼠标离开：停止定时器，停止 GIF 动画，隐藏备注面板。"""
        super().leaveEvent(event)
        if self._gif_timer_id is not None:
            self.killTimer(self._gif_timer_id)
            self._gif_timer_id = None
        self._stop_gif_animation()
        if self._notes_timer_id is not None:
            self.killTimer(self._notes_timer_id)
            self._notes_timer_id = None
        self._hide_notes_panel()

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
        if not self._notes_panel:
            logger.warning("_show_notes_panel: _notes_panel is None")
            return
        note_text = ShelfToolsCacheManager.get_note(self._unique_id)
        logger.debug("_show_notes_panel: unique_id=%s, note_text=%r", self._unique_id, note_text)
        if not note_text or not note_text.strip():
            logger.debug("_show_notes_panel: no note text, skipping")
            return
        self._notes_panel.setMarkdown(note_text)
        self._notes_panel.adjustSize()
        # 限制最大宽度为缩略图宽度
        max_width = max(self.width(), 200)
        self._notes_panel.setMaximumWidth(max_width)
        self._notes_panel.adjustSize()
        # 定位在缩略图上方
        pos = self.mapToGlobal(QtCore.QPoint(0, -self._notes_panel.height()))
        self._notes_panel.move(pos)
        logger.debug("_show_notes_panel: showing at %s, size=%s", pos, self._notes_panel.size())
        self._notes_panel.show()
        self._notes_panel.raise_()
        self._notes_panel.activateWindow()  # 确保面板在最前

    def _hide_notes_panel(self):
        """隐藏备注面板。"""
        if self._notes_panel:
            self._notes_panel.hide()
