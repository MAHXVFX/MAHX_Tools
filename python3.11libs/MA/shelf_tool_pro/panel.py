"""MAShelfToolPro 主面板。"""

from PySide6 import QtWidgets, QtCore

from MA.common import ShelfToolsSettingsManager, ShelfToolsCacheManager
from MA.common.animation_helper import elastic_resize
from MA.shelf_tool_pro.styles import (
    BG_PRIMARY, BG_SECONDARY, BG_INPUT, TEXT_PRIMARY, TEXT_SECONDARY, BORDER_COLOR,
    SETTINGS_BUTTON_STYLE, THUMB_SLIDER_STYLE,
)
from MA.shelf_tool_pro.shelf_loader import _TOOL_NAMES, _TOOL_REGISTRY
from MA.shelf_tool_pro.thumbnail_widget import ThumbnailWidget

_DEFAULT_SIZE = 130


def load_thumb_size():
    """从缓存加载缩略图大小。"""
    data = ShelfToolsSettingsManager.load()
    return max(70, min(250, data.get("thumb_size", _DEFAULT_SIZE)))


def save_thumb_size(value):
    """保存缩略图大小到缓存。"""
    ShelfToolsSettingsManager.update("thumb_size", value)


class MAShelfToolProPanel(QtWidgets.QWidget):
    """MA ShelfTools Pro 主面板。"""

    def __init__(self):
        super().__init__()
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

    def _create_toolbar(self, init_size):
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)

        self.settings_btn = QtWidgets.QPushButton("Settings")
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet(SETTINGS_BUTTON_STYLE)
        self.settings_btn.clicked.connect(self._toggle_settings)
        layout.addWidget(self.settings_btn)

        layout.addSpacing(10)

        lbl_thumb_size = QtWidgets.QLabel("Thumbnail Size")
        lbl_thumb_size.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 13px; font-weight: bold; background-color: transparent;")
        layout.addWidget(lbl_thumb_size)

        self.thumb_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.thumb_slider.setObjectName("thumbSizeSlider")
        self.thumb_slider.setMinimum(70)
        self.thumb_slider.setMaximum(250)
        self.thumb_slider.setValue(init_size)
        self.thumb_slider.setStyleSheet(THUMB_SLIDER_STYLE)
        self.thumb_slider.setCursor(QtCore.Qt.PointingHandCursor)
        self.thumb_slider.valueChanged.connect(self._on_size_changed)
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

        layout.addStretch()
        return layout

    def _create_settings_panel(self):
        self.settings_widget = QtWidgets.QWidget()
        self.settings_widget.setVisible(False)
        settings_layout = QtWidgets.QVBoxLayout(self.settings_widget)
        settings_layout.setContentsMargins(8, 4, 8, 4)
        settings_layout.setSpacing(8)

        dir_row = QtWidgets.QHBoxLayout()
        dir_row.addWidget(QtWidgets.QLabel("Thumbnail Path:"))
        self.thumb_path_edit = QtWidgets.QLineEdit()
        self.thumb_path_edit.setText(ShelfToolsSettingsManager.get_thumbnail_directory())
        self.thumb_path_edit.setStyleSheet(
            f"background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_COLOR}; "
            f"border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        dir_row.addWidget(self.thumb_path_edit)

        self.browse_btn = QtWidgets.QPushButton("Browse")
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
        tools_layout = QtWidgets.QHBoxLayout(self.tools_container)
        tools_layout.setContentsMargins(6, 6, 6, 6)
        tools_layout.setSpacing(12)
        tools_layout.setAlignment(QtCore.Qt.AlignTop)

        if not _TOOL_NAMES:
            info = QtWidgets.QLabel("No tools found")
            info.setAlignment(QtCore.Qt.AlignCenter)
            info.setStyleSheet(f"color: #888888; font-size: 14px; padding: 20px; background: transparent;")
            tools_layout.addWidget(info)
        else:
            self._thumb_widgets = []
            for unique_id in _TOOL_NAMES:
                # 从注册表获取显示名称
                if unique_id in _TOOL_REGISTRY:
                    _, display_name, _ = _TOOL_REGISTRY[unique_id]
                else:
                    display_name = unique_id.split("_", 1)[-1]

                custom_name = ShelfToolsCacheManager.get_custom_name(unique_id)
                custom_image = ShelfToolsCacheManager.get_custom_image(unique_id)
                tw = ThumbnailWidget(unique_id, display_name, init_size, custom_name=custom_name, custom_image_info=custom_image)
                self._thumb_widgets.append(tw)
                tools_layout.addWidget(tw)
            tools_layout.addStretch()

        self.scroll_area.setWidget(self.tools_container)
        return self.scroll_area

    def _toggle_settings(self):
        is_visible = self.settings_widget.isVisible()
        elastic_resize(self.settings_widget, not is_visible)

    def _browse_thumbnail_directory(self):
        current_dir = self.thumb_path_edit.text()
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Thumbnail Directory", current_dir)
        if dir_path:
            self.thumb_path_edit.setText(dir_path)
            ShelfToolsSettingsManager.set_thumbnail_directory(dir_path)

    def _on_size_changed(self, value):
        self.size_label.setText(str(value))
        save_thumb_size(value)
        if hasattr(self, '_thumb_widgets'):
            for tw in self._thumb_widgets:
                tw.updateSize(value)

    def _on_size_edit(self):
        try:
            v = int(self.size_label.text().strip())
            v = max(70, min(250, v))
            self.thumb_slider.setValue(v)
        except ValueError:
            self.size_label.setText(str(self.thumb_slider.value()))
