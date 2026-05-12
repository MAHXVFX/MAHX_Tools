import os

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

from .library_panel import HDRLibraryPanel
from MAHX.common import SettingsManager


_panel_window = None


def _on_panel_closed():
    global _panel_window
    if _panel_window:
        size = _panel_window.size()
        settings = SettingsManager.load()
        settings['window_width'] = size.width()
        settings['window_height'] = size.height()
        SettingsManager.save(settings)
    _panel_window = None


def Panel():
    global _panel_window
    if _panel_window is not None and _panel_window.isVisible():
        _panel_window.raise_()
        _panel_window.activateWindow()
        return

    class SavedSizeDialog(QtWidgets.QDialog):
        def capture_initial_state(self):
            self._geometry_dirty = False
            self._track_geometry_changes = True

        def moveEvent(self, event):
            super().moveEvent(event)
            if getattr(self, '_track_geometry_changes', False):
                self._geometry_dirty = True

        def resizeEvent(self, event):
            super().resizeEvent(event)
            if getattr(self, '_track_geometry_changes', False):
                self._geometry_dirty = True

        def closeEvent(self, event):
            size = self.size()
            pos = self.pos()
            settings = SettingsManager.load()
            if getattr(self, '_geometry_dirty', False):
                settings['window_width'] = size.width()
                settings['window_height'] = size.height()
                settings['window_x'] = pos.x()
                settings['window_y'] = pos.y()
            if hasattr(self, 'panel_widget'):
                if self.panel_widget._settings_dirty:
                    settings['thumbnail_size'] = self.panel_widget._thumbnail_size
                    settings['current_filter'] = self.panel_widget.folder_combo.currentText()
                    settings['recent_hdrs'] = self.panel_widget._recent_hdrs
                    settings['favorite_hdrs'] = self.panel_widget._favorite_hdrs
                    settings['hdr_directory'] = self.panel_widget.hdr_directory
                    settings['cache_directory'] = self.panel_widget.cache_directory
                    settings['print_path'] = self.panel_widget.print_path_checkbox.isChecked()

                if self.panel_widget._thumbnail_cache_dirty and self.panel_widget.thumbnails:
                    settings['subfolders'] = self.panel_widget._subfolders
                    settings['thumbnails'] = self.panel_widget._group_thumbnails_by_folder()
                    if os.path.exists(self.panel_widget.hdr_directory):
                        settings['hdr_dir_mtime'] = os.path.getmtime(self.panel_widget.hdr_directory)
                        subfolders_mtime = {}
                        for folder in self.panel_widget._subfolders:
                            folder_path = os.path.join(self.panel_widget.hdr_directory, folder)
                            if os.path.exists(folder_path):
                                subfolders_mtime[folder] = os.path.getmtime(folder_path)
                        settings['subfolders_mtime'] = subfolders_mtime
            SettingsManager.save(settings)
            super().closeEvent(event)

    panel_widget = HDRLibraryPanel()

    import hou
    parent_window = hou.qt.mainWindow()

    _panel_window = SavedSizeDialog(parent_window)
    _panel_window.panel_widget = panel_widget
    _panel_window.setWindowTitle("HDR Asset Library - MAHX Tools")
    _panel_window.setMinimumSize(500, 360)
    _panel_window.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
    _panel_window.setStyleSheet("QDialog { background-color: #18181b; }")

    try:
        from ctypes import windll
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        hwnd = int(_panel_window.winId())
        SetWindowLong = windll.user32.SetWindowLongW
        GetWindowLong = windll.user32.GetWindowLongW
        style = GetWindowLong(hwnd, GWL_EXSTYLE)
        style |= WS_EX_APPWINDOW
        SetWindowLong(hwnd, GWL_EXSTYLE, style)
        windll.shell32.SetCurrentProcessExplicitAppUserModelID('MAHX.HDRLibrary.1')
    except:
        pass

    settings = SettingsManager.load()
    if settings.get('window_width') and settings.get('window_height'):
        _panel_window.resize(settings['window_width'], settings['window_height'])
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
