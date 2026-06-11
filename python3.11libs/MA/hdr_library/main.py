from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

from MA.hdr_library import HDRLibraryPanel
from MA.common import SettingsManager
from MA.common.styles import DIALOG_BG_STYLE

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
        # 保存窗口几何信息
        if self._geometry_dirty:
            settings = SettingsManager.load()
            size = self.size()
            pos = self.pos()
            settings['window_width'] = size.width()
            settings['window_height'] = size.height()
            settings['window_x'] = pos.x()
            settings['window_y'] = pos.y()
            SettingsManager.save(settings)

        # 委托给面板的统一保存逻辑
        if self.panel_widget:
            self.panel_widget._save_on_close()

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
        windll.shell32.SetCurrentProcessExplicitAppUserModelID('MA.HDRLibrary.1')
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
    _panel_window.setWindowTitle("MA HDR")
    _panel_window.setMinimumSize(500, 360)
    _panel_window.setWindowFlags(
        Qt.Window | Qt.WindowMinimizeButtonHint |
        Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint
    )
    _panel_window.setStyleSheet(DIALOG_BG_STYLE)
    _apply_window_flags(_panel_window)

    from MA.common.constants import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
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
