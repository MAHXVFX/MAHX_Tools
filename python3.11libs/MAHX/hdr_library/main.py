import os
import logging

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

from .library_panel import HDRLibraryPanel
from MAHX.common import SettingsManager, CacheManager
from MAHX.common.styles import DIALOG_BG_STYLE

logger = logging.getLogger("MAHX")

_panel_window = None


class SavedSizeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._geometry_dirty = False
        self._track_geometry_changes = False
        self.panel_widget = None

    def capture_initial_state(self):
        self._geometry_dirty = False
        self._track_geometry_changes = True

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._track_geometry_changes:
            self._geometry_dirty = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._track_geometry_changes:
            self._geometry_dirty = True

    def closeEvent(self, event):
        # ── 设置（小数据） ──
        settings = SettingsManager.load()
        if self._geometry_dirty:
            size = self.size()
            pos = self.pos()
            settings['window_width'] = size.width()
            settings['window_height'] = size.height()
            settings['window_x'] = pos.x()
            settings['window_y'] = pos.y()

        if self.panel_widget:
            panel = self.panel_widget
            if panel._settings_dirty:
                settings['thumbnail_size'] = panel._thumb_mgr.thumbnail_size
                settings['current_filter'] = panel.folder_combo.currentText()
                settings['recent_hdrs'] = panel._filter_mgr.recent_hdrs
                settings['favorite_hdrs'] = panel._filter_mgr.favorite_hdrs
                settings['hdr_directory'] = panel.hdr_directory
                settings['cache_directory'] = panel.cache_directory
                settings['print_path'] = panel.print_path_checkbox.isChecked()
        SettingsManager.save(settings)

        # ── 缓存（大数据） ──
        if self.panel_widget and self.panel_widget._filter_mgr.thumbnails:
            panel = self.panel_widget
            cache = CacheManager.load()
            cache['subfolders'] = panel._filter_mgr.subfolders
            cache['thumbnails'] = panel._filter_mgr.group_thumbnails_by_folder(panel.cache_directory)
            if os.path.exists(panel.hdr_directory):
                cache['hdr_dir_mtime'] = os.path.getmtime(panel.hdr_directory)
                subfolders_mtime = {}
                for folder in panel._filter_mgr.subfolders:
                    folder_path = os.path.join(panel.hdr_directory, folder)
                    if os.path.exists(folder_path):
                        subfolders_mtime[folder] = os.path.getmtime(folder_path)
                cache['subfolders_mtime'] = subfolders_mtime
            CacheManager.save(cache)

        super().closeEvent(event)


def _apply_window_flags(window):
    try:
        from ctypes import windll
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        hwnd = int(window.winId())
        SetWindowLong = windll.user32.SetWindowLongW
        GetWindowLong = windll.user32.GetWindowLongW
        style = GetWindowLong(hwnd, GWL_EXSTYLE)
        style |= WS_EX_APPWINDOW
        SetWindowLong(hwnd, GWL_EXSTYLE, style)
        windll.shell32.SetCurrentProcessExplicitAppUserModelID('MAHX.HDRLibrary.1')
    except Exception:
        pass


def Panel():
    global _panel_window
    if _panel_window is not None:
        try:
            if _panel_window.isVisible():
                _panel_window.raise_()
                _panel_window.activateWindow()
                return
        except (RuntimeError, AttributeError):
            _panel_window = None

    panel_widget = HDRLibraryPanel()

    import hou
    parent_window = hou.qt.mainWindow()

    _panel_window = SavedSizeDialog(parent_window)
    _panel_window.panel_widget = panel_widget
    _panel_window.setWindowTitle("HDR Asset Library - MAHX Tools")
    _panel_window.setMinimumSize(500, 360)
    _panel_window.setWindowFlags(
        Qt.Window | Qt.WindowMinimizeButtonHint |
        Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint
    )
    _panel_window.setStyleSheet(DIALOG_BG_STYLE)
    _apply_window_flags(_panel_window)

    from MAHX.common.constants import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
    settings = SettingsManager.load()
    w = settings.get('window_width', DEFAULT_WINDOW_WIDTH)
    h = settings.get('window_height', DEFAULT_WINDOW_HEIGHT)
    _panel_window.resize(w, h)
    if settings.get('window_x') is not None and settings.get('window_y') is not None:
        _panel_window.move(settings['window_x'], settings['window_y'])

    _panel_window.setAttribute(Qt.WA_DeleteOnClose)
    dialog_layout = QtWidgets.QVBoxLayout()
    dialog_layout.setContentsMargins(0, 0, 0, 0)
    _panel_window.setLayout(dialog_layout)
    dialog_layout.addWidget(panel_widget)
    panel_widget._load_settings()
    _panel_window.show()
    QtCore.QTimer.singleShot(100, _panel_window.capture_initial_state)
