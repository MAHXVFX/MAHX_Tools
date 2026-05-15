import os

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap, QImage, QCursor

FAVORITE_STAR_STYLE = (
    "background-color: #e0cb56; color: #000000; font-size: 14px; font-weight: bold; "
    "border-radius: 7px; border: none; padding: 0px;"
)


class HDRThumbnailWidget(QtWidgets.QWidget):
    doubleClicked = Signal(str)
    favoriteToggled = Signal(str)

    def __init__(self, hdr_path, thumbnail_path, size=180, image_size=170, parent=None, lazy_load=False, is_favorite=False):
        super().__init__(parent)
        self.hdr_path = os.path.normpath(hdr_path)
        self.thumbnail_path = os.path.normpath(thumbnail_path)
        self._is_favorite = is_favorite
        self._original_pixmap = None
        self._placeholder_pixmap = None
        self._loaded = False
        self._image_size = image_size
        self.setFixedSize(size, size + 20)
        self.setCursor(QCursor(QtCore.Qt.PointingHandCursor))
        self._hovered = False

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setFixedSize(image_size, image_size)
        self.image_label.setStyleSheet("background-color: #2b2b2b; border-radius: 5px;")
        self.image_label.installEventFilter(self)
        if not lazy_load:
            self._load_thumbnail(image_size)
        else:
            placeholder = self._create_placeholder(image_size)
            scaled_placeholder = placeholder.scaled(image_size, image_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_placeholder)
            self._loaded = False
        main_layout.addWidget(self.image_label)

        self._star_label = QtWidgets.QLabel("\u2605", self.image_label)
        self._star_label.setStyleSheet(FAVORITE_STAR_STYLE)
        self._star_label.setFixedSize(20, 20)
        self._star_label.setAlignment(QtCore.Qt.AlignCenter)
        self._star_label.setVisible(self._is_favorite)
        self._position_star()

        self.name_label = QtWidgets.QLabel(os.path.basename(self.hdr_path))
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.name_label.setStyleSheet("color: #cccccc; font-size: 10px;")
        self.name_label.setFixedHeight(20)
        self.name_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.name_label.installEventFilter(self)
        main_layout.addWidget(self.name_label)

    def _position_star(self):
        w = self._star_label.width()
        self._star_label.move(self.image_label.width() - w - 2, 2)

    def setFavorite(self, is_favorite):
        self._is_favorite = is_favorite
        self._star_label.setVisible(is_favorite)

    def _load_thumbnail(self, image_size=170):
        if self._loaded:
            return
        if not self.image_label:
            return

        thumbnail_path = os.path.normpath(self.thumbnail_path)
        if os.path.exists(thumbnail_path):
            pixmap = QPixmap(thumbnail_path)
            if not pixmap.isNull():
                self._original_pixmap = pixmap
                scaled_pixmap = self._original_pixmap.scaled(image_size, image_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.image_label.setPixmap(scaled_pixmap)
                self._loaded = True
                return

        placeholder = self._create_placeholder(image_size)
        self._original_pixmap = placeholder
        scaled_pixmap = placeholder.scaled(image_size, image_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)
        self._loaded = True

    def ensure_loaded(self, image_size=170):
        if not self._loaded and self.image_label:
            self._load_thumbnail(image_size)

    def unload(self):
        if self._loaded and self.image_label:
            self._loaded = False
            self._original_pixmap = None
            placeholder = self._create_placeholder(self.image_label.width())
            self.image_label.setPixmap(placeholder)

    def _create_placeholder(self, image_size=170):
        img = QImage(image_size, image_size, QImage.Format_RGB32)
        img.fill(QtCore.Qt.GlobalColor.darkGray)
        return QPixmap.fromImage(img)

    def updateSize(self, size, image_size, cache=None):
        self.setFixedSize(size, size + 20)
        self.image_label.setFixedSize(image_size, image_size)
        self._image_size = image_size
        self._reload_scaled_pixmap(image_size)
        self._position_star()

    def _reload_scaled_pixmap(self, image_size):
        if self._original_pixmap:
            scaled_pixmap = self._original_pixmap.scaled(image_size, image_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)

    def enterEvent(self, event):
        self._hovered = True
        self.setStyleSheet("background-color: #3a3a3a; border-radius: 8px;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.setStyleSheet("background-color: transparent;")
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit(self.hdr_path)
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, global_pos):
        menu = QtWidgets.QMenu(self)
        action_text = "\u53d6\u6d88\u6536\u85cf" if self._is_favorite else "\u6536\u85cf"
        favorite_action = menu.addAction(action_text)
        selected_action = menu.exec(global_pos)
        if selected_action == favorite_action:
            self.favoriteToggled.emit(self.hdr_path)

    def contextMenuEvent(self, event):
        self._show_context_menu(event.globalPos())
        super().contextMenuEvent(event)

    def eventFilter(self, obj, event):
        if obj in (getattr(self, 'image_label', None), getattr(self, 'name_label', None)) and event.type() == QtCore.QEvent.ContextMenu:
            self._show_context_menu(event.globalPos())
            return True
        return super().eventFilter(obj, event)
