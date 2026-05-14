import os
import logging

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtGui import QCursor

from MAHX.common import HDR_EXTENSIONS, HDR_PARAMETER_NAMES
from MAHX.common import SettingsManager, CacheManager, _collect_hdr_files
from MAHX.common.constants import (
    LAYOUT_MARGIN, RESIZE_DELAY_MS, DEFAULT_THUMBNAIL_SIZE,
    DEFAULT_THUMBNAIL_IMAGE_SIZE, THUMBNAIL_GRID_SPACING,
)
from MAHX.common.styles import (
    STYLE_SHEET, SETTINGS_BUTTON_STYLE, THUMB_SLIDER_STYLE,
    THUMB_SIZE_LABEL_STYLE, BROWSE_BUTTON_STYLE, ACTION_BUTTON_STYLE,
    COMBO_BOX_STYLE, FILTER_LABEL_STYLE, THUMB_SIZE_TITLE_STYLE,
    STATUS_STYLE, VERSION_STYLE, THUMBNAIL_NAME_STYLE, THUMBNAIL_BG_STYLE,
    NO_FILES_STYLE, THUMBNAIL_WIDGET_STYLE,
    STATUS_SUCCESS, STATUS_WARNING, TEXT_STATUS, ACCENT_BLUE, ACCENT_BLUE_LIGHT,
    BTN_PADDING, BTN_BORDER_RADIUS,
)
from MAHX.common.filter_manager import FilterManager
from MAHX.common.animation_helper import (
    elastic_resize, animate_button_width, pulse_button,
)
from .thumbnail_manager import ThumbnailManager
from .thumbnail_worker import ThumbnailWorker

logger = logging.getLogger("MAHX")

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False


class HDRLibraryPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hdr_directory = ""
        self.cache_directory = ""
        self._settings_dirty = False
        self._thumbnail_cache_dirty = False
        self._loading_settings = False
        self._skip_filter_apply = False

        self._filter_mgr = FilterManager()
        self._thumb_mgr = ThumbnailManager()
        self._saved_on_close = False

        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._do_resize)

        self._init_ui()

    def _set_status(self, color, text):
        self.status_label.setStyleSheet(f"color: {color}; {STATUS_STYLE}")
        self.status_label.setText(text)

    def _init_ui(self):
        self.setWindowTitle("HDR Asset Library")
        self.setStyleSheet(STYLE_SHEET)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(LAYOUT_MARGIN, 5, LAYOUT_MARGIN, 0)
        main_layout.setSpacing(5)
        main_layout.addLayout(self._create_toolbar())
        main_layout.addWidget(self._create_settings_panel())
        main_layout.addWidget(self._create_scroll_area())
        main_layout.addLayout(self._create_status_bar())
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

    def _create_toolbar(self):
        layout = QtWidgets.QHBoxLayout()

        self.btn_toggle_settings = QtWidgets.QPushButton("Settings")
        self.btn_toggle_settings.setObjectName("settingsButton")
        self.btn_toggle_settings.setStyleSheet(SETTINGS_BUTTON_STYLE)
        self.btn_toggle_settings.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_toggle_settings.clicked.connect(self._toggle_settings)
        layout.addWidget(self.btn_toggle_settings)

        lbl_thumb_size = QtWidgets.QLabel("Thumbnail Size")
        lbl_thumb_size.setStyleSheet(THUMB_SIZE_TITLE_STYLE)
        layout.addWidget(lbl_thumb_size)

        self.thumb_size_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.thumb_size_slider.setObjectName("thumbSizeSlider")
        self.thumb_size_slider.setMinimum(90)
        self.thumb_size_slider.setMaximum(500)
        self.thumb_size_slider.setValue(DEFAULT_THUMBNAIL_SIZE)
        self.thumb_size_slider.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.thumb_size_slider.setMaximumWidth(200)
        self.thumb_size_slider.setCursor(QCursor(Qt.PointingHandCursor))
        self.thumb_size_slider.setStyleSheet(THUMB_SLIDER_STYLE)
        self.thumb_size_slider.valueChanged.connect(self._on_thumbnail_size_changed)
        layout.addWidget(self.thumb_size_slider)

        self.thumb_size_label = QtWidgets.QLineEdit(str(DEFAULT_THUMBNAIL_SIZE))
        self.thumb_size_label.setFixedWidth(45)
        self.thumb_size_label.setStyleSheet(THUMB_SIZE_LABEL_STYLE)
        self.thumb_size_label.setAlignment(Qt.AlignCenter)
        self.thumb_size_label.returnPressed.connect(self._on_thumb_size_label_edited)
        self.thumb_size_label.installEventFilter(self)
        layout.addWidget(self.thumb_size_label)
        layout.addStretch()

        self.folder_label = QtWidgets.QLabel("Filter:")
        self.folder_label.setStyleSheet(FILTER_LABEL_STYLE)
        layout.addWidget(self.folder_label)

        self.folder_combo = QtWidgets.QComboBox()
        self.folder_combo.setCursor(QCursor(Qt.PointingHandCursor))
        self.folder_combo.setStyleSheet(COMBO_BOX_STYLE)
        self.folder_combo.currentTextChanged.connect(self._on_folder_filter_changed)
        layout.addWidget(self.folder_combo)

        return layout

    def _create_settings_panel(self):
        self.settings_widget = QtWidgets.QWidget()
        self.settings_widget.setVisible(False)
        settings_layout = QtWidgets.QVBoxLayout(self.settings_widget)
        settings_layout.setSpacing(10)

        hdr_layout = QtWidgets.QHBoxLayout()
        hdr_layout.addWidget(QtWidgets.QLabel("HDR Library:"))
        self.hdr_path_edit = QtWidgets.QLineEdit()
        self.hdr_path_edit.setPlaceholderText("Select HDR library directory...")
        hdr_layout.addWidget(self.hdr_path_edit)
        btn_browse_hdr = QtWidgets.QPushButton("Browse")
        btn_browse_hdr.setStyleSheet(BROWSE_BUTTON_STYLE)
        btn_browse_hdr.setCursor(QCursor(Qt.PointingHandCursor))
        btn_browse_hdr.clicked.connect(self._browse_hdr_directory)
        hdr_layout.addWidget(btn_browse_hdr)
        settings_layout.addLayout(hdr_layout)

        cache_layout = QtWidgets.QHBoxLayout()
        cache_layout.addWidget(QtWidgets.QLabel("Thumbnail Cache:"))
        self.cache_path_edit = QtWidgets.QLineEdit()
        self.cache_path_edit.setPlaceholderText("Select thumbnail cache directory...")
        cache_layout.addWidget(self.cache_path_edit)
        btn_browse_cache = QtWidgets.QPushButton("Browse")
        btn_browse_cache.setStyleSheet(BROWSE_BUTTON_STYLE)
        btn_browse_cache.setCursor(QCursor(Qt.PointingHandCursor))
        btn_browse_cache.clicked.connect(self._browse_cache_directory)
        cache_layout.addWidget(btn_browse_cache)
        settings_layout.addLayout(cache_layout)

        self.print_path_checkbox = QtWidgets.QCheckBox("Log HDR path")
        self.print_path_checkbox.setChecked(True)
        self.print_path_checkbox.setCursor(QCursor(Qt.PointingHandCursor))
        self.print_path_checkbox.stateChanged.connect(self._on_setting_changed)
        settings_layout.addWidget(self.print_path_checkbox)

        self.hide_gray_checkbox = QtWidgets.QCheckBox("Hide gray thumbnails")
        self.hide_gray_checkbox.setChecked(False)
        self.hide_gray_checkbox.setCursor(QCursor(Qt.PointingHandCursor))
        self.hide_gray_checkbox.toggled.connect(self._on_hide_gray_toggled)
        settings_layout.addWidget(self.hide_gray_checkbox)

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_scan = QtWidgets.QPushButton("Scan HDR Files")
        self.btn_scan.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_scan.setStyleSheet(ACTION_BUTTON_STYLE)
        self.btn_scan.clicked.connect(self._scan_hdr_files)
        self.btn_scan.setEnabled(False)
        btn_layout.addWidget(self.btn_scan)

        self.btn_refresh = QtWidgets.QPushButton("Refresh Thumbnails")
        self.btn_refresh.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_refresh.setStyleSheet(ACTION_BUTTON_STYLE)
        self.btn_refresh.clicked.connect(self._refresh_thumbnails)
        self.btn_refresh.setEnabled(False)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        settings_layout.addLayout(btn_layout)

        return self.settings_widget

    def _create_scroll_area(self):
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.thumbnail_widget = QtWidgets.QWidget()
        self.thumbnail_widget.setStyleSheet(THUMBNAIL_WIDGET_STYLE)
        self.thumbnail_layout = QtWidgets.QGridLayout(self.thumbnail_widget)
        self.thumbnail_layout.setSpacing(THUMBNAIL_GRID_SPACING)
        self.thumbnail_layout.setContentsMargins(10, 10, 10, 10)
        self.thumbnail_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setWidget(self.thumbnail_widget)

        return self.scroll_area

    @property
    def _vscroll(self):
        """实时获取滚动条（Qt6 可能重建滚动条，不能缓存引用）"""
        return self.scroll_area.verticalScrollBar()

    def _create_status_bar(self):
        layout = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel("No HDR files loaded")
        self.status_label.setStyleSheet(f"color: {TEXT_STATUS}; {STATUS_STYLE}")
        self.status_label.setFixedHeight(20)
        self.version_label = QtWidgets.QLabel("MAHX Tools 1.0.0")
        self.version_label.setStyleSheet(VERSION_STYLE)
        layout.addWidget(self.status_label, 1)
        layout.addWidget(self.version_label)
        return layout

    def _update_folder_combo(self, hide_placeholders=None):
        if hide_placeholders is None:
            hide_placeholders = self.hide_gray_checkbox.isChecked()
        self.folder_combo.blockSignals(True)
        current_text = self.folder_combo.currentText()
        self.folder_combo.clear()
        for option in self._filter_mgr.get_filter_options(hide_placeholders):
            self.folder_combo.addItem(option)
        available = [self.folder_combo.itemText(i) for i in range(self.folder_combo.count())]
        self.folder_combo.setCurrentText(current_text if current_text in available else 'ALL')
        self.folder_combo.blockSignals(False)

    def _apply_filter(self, hide_gray=None):
        if hide_gray is None:
            hide_gray = self.hide_gray_checkbox.isChecked()
        selected = self.folder_combo.currentText()
        filtered = self._filter_mgr.apply_filter(selected)
        if hide_gray:
            filtered = [t for t in filtered if not t.get('is_placeholder', False)]
        self._display_thumbnails(filtered)

    def _display_thumbnails(self, filtered_thumbnails):
        try:
            self._vscroll.disconnect(self._on_scroll)
        except Exception:
            pass

        columns = max(1, (self.width() - LAYOUT_MARGIN * 2) // (self._thumb_mgr.thumbnail_size + THUMBNAIL_GRID_SPACING))
        self._thumb_mgr.current_columns = columns
        self._thumb_mgr.populate_grid(
            self.thumbnail_layout, filtered_thumbnails,
            self._filter_mgr.is_favorite,
            self._on_thumbnail_double_clicked,
            self._on_thumbnail_favorite_toggled,
        )
        self._vscroll.valueChanged.connect(self._on_scroll)
        QTimer.singleShot(0, self._load_visible_thumbnails)

    def _on_folder_filter_changed(self, text):
        if not self._skip_filter_apply:
            if not self._loading_settings:
                self._settings_dirty = True
            self._apply_filter()

    def _load_settings(self):
        self._loading_settings = True
        settings = SettingsManager.load()

        self.hdr_directory = settings.get('hdr_directory', '')
        self.cache_directory = settings.get('cache_directory', '')
        self.print_path_checkbox.setChecked(settings.get('print_path', True))
        self.hide_gray_checkbox.setChecked(settings.get('hide_gray_thumbnails', False))
        self._filter_mgr.recent_hdrs = settings.get('recent_hdrs', [])
        self._filter_mgr.favorite_hdrs = settings.get('favorite_hdrs', [])
        self._filter_mgr.hdr_directory = self.hdr_directory

        self._skip_filter_apply = True
        thumb_size = settings.get('thumbnail_size', DEFAULT_THUMBNAIL_SIZE)
        self._thumb_mgr.thumbnail_size = thumb_size
        self.thumb_size_slider.setValue(thumb_size)
        self.thumb_size_label.setText(str(thumb_size))

        if self.hdr_directory:
            self.hdr_path_edit.setText(self.hdr_directory)
        if self.cache_directory:
            self.cache_path_edit.setText(self.cache_directory)
        if self.hdr_directory and os.path.exists(self.hdr_directory):
            self.btn_scan.setEnabled(True)
            self.btn_refresh.setEnabled(True)
            if self._try_load_cached_thumbnails():
                self._update_folder_combo()
            else:
                self._load_existing_thumbnails()
        else:
            self._update_folder_combo()

        self._update_status_text()

        saved_filter = settings.get('current_filter', 'ALL')
        self._skip_filter_apply = True
        self.folder_combo.blockSignals(True)
        available = [self.folder_combo.itemText(i) for i in range(self.folder_combo.count())]
        self.folder_combo.setCurrentText(saved_filter if saved_filter in available else 'ALL')
        self.folder_combo.blockSignals(False)
        self._skip_filter_apply = False
        self._apply_filter()

        self._settings_dirty = False
        self._thumbnail_cache_dirty = False
        self._loading_settings = False

    def _update_status_text(self):
        thumbnails = self._filter_mgr.thumbnails
        missing_count = sum(
            1 for t in thumbnails
            if os.path.exists(t['hdr_path'])
            and not t.get('is_placeholder', False)
            and not os.path.exists(t['thumbnail_path'])
        )
        if len(thumbnails) == 0 and self.hdr_directory:
            self._set_status(TEXT_STATUS, "No HDR files found")
        elif missing_count > 0:
            self._set_status(STATUS_WARNING, f"Loaded {len(thumbnails)} HDR files ({missing_count} missing - scan to regenerate)")
        else:
            color = STATUS_SUCCESS if self.hdr_directory else TEXT_STATUS
            text = "Ready" if self.hdr_directory else "No HDR library path set"
            self._set_status(color, text)

    def _try_load_cached_thumbnails(self, cache=None):
        if cache is None:
            cache = CacheManager.load()
        cached_thumbnails = cache.get('thumbnails', {})
        cached_root_mtime = cache.get('hdr_dir_mtime')
        cached_subfolders_mtime = cache.get('subfolders_mtime', {})

        if not cached_thumbnails or not os.path.exists(self.hdr_directory):
            return False
        if cached_root_mtime is None:
            return False

        current_root_mtime = os.path.getmtime(self.hdr_directory)
        if current_root_mtime != cached_root_mtime:
            return False

        current_subfolders_mtime = {}
        for folder in os.listdir(self.hdr_directory):
            folder_path = os.path.join(self.hdr_directory, folder)
            if os.path.isdir(folder_path):
                current_subfolders_mtime[folder] = os.path.getmtime(folder_path)

        for folder, mtime in cached_subfolders_mtime.items():
            if folder in current_subfolders_mtime and current_subfolders_mtime[folder] != mtime:
                return False
        for folder in current_subfolders_mtime:
            if folder not in cached_subfolders_mtime:
                return False

        subfolders = []
        missing_thumbnails = 0
        all_thumbnails = []
        current_subfolders_set = set(current_subfolders_mtime.keys())

        for folder, thumbnails in cached_thumbnails.items():
            if not thumbnails:
                continue
            if folder and folder != '__root__':
                if folder not in current_subfolders_set:
                    continue
                subfolders.append(folder)
            folder_path = '' if folder == '__root__' else folder
            for thumbnail_entry in thumbnails:
                thumbnail_filename = thumbnail_entry['filename']
                is_placeholder = thumbnail_entry.get('is_placeholder', False)
                thumbnail_path = os.path.normpath(os.path.join(self.cache_directory, folder_path, thumbnail_filename))
                hdr_base = thumbnail_filename.replace('_Thumbnail.jpg', '')
                hdr_path = None
                for ext in HDR_EXTENSIONS:
                    candidate = os.path.normpath(os.path.join(self.hdr_directory, folder_path, hdr_base + ext))
                    if os.path.exists(candidate):
                        hdr_path = candidate
                        break
                if not hdr_path:
                    hdr_path = os.path.normpath(os.path.join(self.hdr_directory, folder_path, hdr_base + '.hdr'))
                if os.path.exists(hdr_path):
                    if not os.path.exists(thumbnail_path) and not is_placeholder:
                        missing_thumbnails += 1
                    all_thumbnails.append({
                        'hdr_path': hdr_path,
                        'thumbnail_path': thumbnail_path,
                        'filename': os.path.basename(hdr_path),
                        'is_placeholder': is_placeholder,
                    })

        if not all_thumbnails:
            return False

        self._filter_mgr.thumbnails = all_thumbnails
        self._filter_mgr.subfolders = sorted(subfolders)
        self._update_folder_combo()
        self._apply_filter()

        if missing_thumbnails > 0:
            self._set_status(STATUS_WARNING, f"Loaded {len(all_thumbnails)} HDR files ({missing_thumbnails} missing - scan to regenerate)")
        else:
            self._set_status(STATUS_SUCCESS, f"Loaded {len(all_thumbnails)} HDR files (from cache)")
        return True

    def _load_existing_thumbnails(self):
        if not self.hdr_directory or not os.path.exists(self.hdr_directory):
            return
        if not self.cache_directory or not os.path.exists(self.cache_directory):
            return

        thumbnails = []
        hdr_files, subfolders = _collect_hdr_files(self.hdr_directory)

        for hdr_path in hdr_files:
            rel_path = os.path.relpath(hdr_path, self.hdr_directory)
            thumbnail_rel = rel_path.rsplit('.', 1)[0] + '_Thumbnail.jpg'
            thumbnail_path = os.path.normpath(os.path.join(self.cache_directory, thumbnail_rel))
            is_placeholder = not os.path.exists(thumbnail_path)
            thumbnails.append({
                'hdr_path': os.path.normpath(hdr_path),
                'thumbnail_path': thumbnail_path,
                'filename': os.path.basename(hdr_path),
                'is_placeholder': is_placeholder,
            })

        self._filter_mgr.thumbnails = thumbnails
        self._filter_mgr.subfolders = sorted(subfolders)
        self._update_folder_combo()
        self._apply_filter()

        if len(thumbnails) == 0:
            self._set_status(TEXT_STATUS, "No HDR files found")
        else:
            self._set_status(STATUS_SUCCESS, f"Loaded {len(thumbnails)} HDR files (existing thumbnails only)")

    def _toggle_settings(self):
        is_visible = self.settings_widget.isVisible()
        elastic_resize(self.settings_widget, not is_visible)

    def _on_thumbnail_size_changed(self, value):
        self.thumb_size_label.setText(str(value))
        self._thumb_mgr.thumbnail_size = value
        if not self._loading_settings:
            self._settings_dirty = True

        if not self._filter_mgr.thumbnails:
            return

        new_columns = max(1, (self.width() - LAYOUT_MARGIN * 2) // (value + THUMBNAIL_GRID_SPACING))
        if new_columns != self._thumb_mgr.current_columns:
            self._apply_filter()
        else:
            self._thumb_mgr.update_all_sizes(value)

        self._resize_timer.start(RESIZE_DELAY_MS)

    def _on_thumb_size_label_edited(self):
        self._validate_thumb_size_input()
        self.thumb_size_label.clearFocus()

    def _validate_thumb_size_input(self):
        try:
            value = int(self.thumb_size_label.text())
            if self.thumb_size_slider.minimum() <= value <= self.thumb_size_slider.maximum():
                self.thumb_size_slider.setValue(value)
            else:
                self.thumb_size_label.setText(str(self.thumb_size_slider.value()))
        except ValueError:
            self.thumb_size_label.setText(str(self.thumb_size_slider.value()))

    def _browse_hdr_directory(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select HDR Library Directory",
            self.hdr_directory or os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if dir_path:
            self.hdr_directory = dir_path
            self.hdr_path_edit.setText(dir_path)
            self.btn_scan.setEnabled(True)
            self._set_status(STATUS_SUCCESS, f"HDR Library: {dir_path}")
            self._save_settings()

    def _browse_cache_directory(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Thumbnail Cache Directory",
            self.cache_directory or os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if dir_path:
            self.cache_directory = dir_path
            self.cache_path_edit.setText(dir_path)
            self.btn_refresh.setEnabled(True)
            self._save_settings()

    def _on_hide_gray_toggled(self, checked):
        hide_gray = self.hide_gray_checkbox.isChecked()
        self._update_folder_combo(hide_placeholders=hide_gray)
        self._apply_filter(hide_gray=hide_gray)
        if not self._loading_settings:
            self._save_settings()

    def _on_setting_changed(self, state):
        if not self._loading_settings:
            self._save_settings()

    def _save_settings(self):
        settings = SettingsManager.load()
        settings['hdr_directory'] = self.hdr_directory
        settings['cache_directory'] = self.cache_directory
        settings['print_path'] = self.print_path_checkbox.isChecked()
        settings['hide_gray_thumbnails'] = self.hide_gray_checkbox.isChecked()
        settings['recent_hdrs'] = self._filter_mgr.recent_hdrs
        settings['favorite_hdrs'] = self._filter_mgr.favorite_hdrs
        settings['current_filter'] = self.folder_combo.currentText()
        SettingsManager.save(settings)

    def _save_on_close(self):
        """关闭时保存全部状态。
        设置（小）→ SettingsManager 实时兼容
        缓存（大）→ CacheManager 独立文件，避免拖累实时写入"""
        if self._saved_on_close:
            return
        self._saved_on_close = True

        # ── 设置（小数据） ──
        settings = SettingsManager.load()
        if self._settings_dirty:
            settings['thumbnail_size'] = self._thumb_mgr.thumbnail_size
            settings['current_filter'] = self.folder_combo.currentText()
            settings['recent_hdrs'] = self._filter_mgr.recent_hdrs
            settings['favorite_hdrs'] = self._filter_mgr.favorite_hdrs
            settings['hdr_directory'] = self.hdr_directory
            settings['cache_directory'] = self.cache_directory
            settings['print_path'] = self.print_path_checkbox.isChecked()
        SettingsManager.save(settings)

        # ── 缓存（大数据） ──
        if self._filter_mgr.thumbnails:
            cache = CacheManager.load()
            cache['subfolders'] = self._filter_mgr.subfolders
            cache['thumbnails'] = self._filter_mgr.group_thumbnails_by_folder(self.cache_directory)
            if os.path.exists(self.hdr_directory):
                cache['hdr_dir_mtime'] = os.path.getmtime(self.hdr_directory)
                subfolders_mtime = {}
                for folder in self._filter_mgr.subfolders:
                    folder_path = os.path.join(self.hdr_directory, folder)
                    if os.path.exists(folder_path):
                        subfolders_mtime[folder] = os.path.getmtime(folder_path)
                cache['subfolders_mtime'] = subfolders_mtime
            CacheManager.save(cache)

    def closeEvent(self, event):
        """嵌入面板模式下由 Houdini 触发的关闭事件。"""
        self._save_on_close()
        super().closeEvent(event)

    def _scan_hdr_files(self):
        if not self.hdr_directory or not os.path.exists(self.hdr_directory):
            QMessageBox.warning(self, "Error", "Please select a valid HDR library directory.")
            return
        if not self.cache_directory:
            QMessageBox.warning(self, "Error", "Please select a thumbnail cache directory.")
            return

        os.makedirs(self.cache_directory, exist_ok=True)
        self.btn_scan.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self._worker = ThumbnailWorker(self.hdr_directory, self.cache_directory)
        self._worker.progress.connect(self._update_progress)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.error.connect(self._on_scan_error)
        self._worker.start()

    def _update_progress(self, current, total):
        if total <= 0:
            self.progress_bar.setValue(0)
            self.status_label.setText("No HDR files found")
            return
        percentage = int((current / total) * 100)
        self.progress_bar.setValue(percentage)
        self.status_label.setText(f"Generating thumbnails: {current}/{total} ({percentage}%)")

    def _on_scan_finished(self, thumbnails, subfolders):
        self._thumbnail_cache_dirty = True
        self._filter_mgr.thumbnails = thumbnails
        self._filter_mgr.subfolders = sorted(subfolders)
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self._update_folder_combo()
        self._apply_filter()
        self._set_status(STATUS_SUCCESS, f"Loaded {len(thumbnails)} HDR files")

    def _on_scan_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to scan HDR files:\n{error_msg}")

    def _refresh_thumbnails(self):
        if not self._filter_mgr.thumbnails:
            return
        failed = []
        for thumb_data in self._filter_mgr.thumbnails:
            thumbnail_path = thumb_data['thumbnail_path']
            if os.path.exists(thumbnail_path):
                try:
                    os.remove(thumbnail_path)
                except OSError as e:
                    failed.append((thumbnail_path, e))
        if failed:
            self._set_status(STATUS_WARNING, f"Could not delete {len(failed)} thumbnails")
            logger.warning("Failed to delete %d thumbnails", len(failed))
            for path, error in failed:
                logger.warning("  %s: %s", path, error)
            QMessageBox.warning(
                self, "Refresh Thumbnails",
                f"Could not delete {len(failed)} thumbnail files. Check the console for details."
            )
        self._scan_hdr_files()

    def _on_scroll(self, value=None):
        self._load_visible_thumbnails()

    def _load_visible_thumbnails(self):
        scroll_y = self._vscroll.value()
        viewport_height = self.scroll_area.viewport().height()
        if viewport_height <= 0:
            viewport_height = self.height() - 100
        row_height = self._thumb_mgr.thumbnail_size + 20 + THUMBNAIL_GRID_SPACING
        self._thumb_mgr.update_visible_range(scroll_y, viewport_height, row_height)

    def _on_thumbnail_double_clicked(self, hdr_path):
        self._load_hdr_to_environment_light(hdr_path)

    def _on_thumbnail_favorite_toggled(self, hdr_path):
        hdr_path = os.path.normpath(hdr_path)
        is_now_favorite = self._filter_mgr.toggle_favorite(hdr_path)
        status_text = (f"Added to favorites: {os.path.basename(hdr_path)}" if is_now_favorite
                       else f"Removed from favorites: {os.path.basename(hdr_path)}")
        self._settings_dirty = True
        self._save_settings()
        self._set_status(STATUS_SUCCESS, status_text)

        current_filter = self.folder_combo.currentText()
        self._update_folder_combo()
        available = [self.folder_combo.itemText(i) for i in range(self.folder_combo.count())]
        self.folder_combo.blockSignals(True)
        self.folder_combo.setCurrentText(current_filter if current_filter in available else "ALL")
        self.folder_combo.blockSignals(False)

        if current_filter == "\u2605 \u6536\u85cf":
            self._apply_filter()
        else:
            for widget in self._thumb_mgr.widgets:
                if os.path.normpath(widget.hdr_path).lower() == os.path.normpath(hdr_path).lower():
                    widget.setFavorite(is_now_favorite)

    def _load_hdr_to_environment_light(self, hdr_path):
        if not HOU_AVAILABLE:
            return
        applied = False
        try:
            import hou
            selected_nodes = hou.selectedNodes()
            if not selected_nodes:
                return
            for node in selected_nodes:
                parm = None
                for parm_name in HDR_PARAMETER_NAMES:
                    parm = node.parm(parm_name)
                    if parm:
                        break
                if parm:
                    parm.set(hdr_path)
                    applied = True
            if applied and self.print_path_checkbox.isChecked():
                print(hdr_path, end="\r")
            if applied:
                self._filter_mgr.add_to_recent(hdr_path)
                self._save_settings()
        except Exception as e:
            logger.error("Error loading HDR: %s", e)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._filter_mgr.thumbnails and self._thumb_mgr.widgets:
            new_columns = max(1, (self.width() - LAYOUT_MARGIN * 2) // (self._thumb_mgr.thumbnail_size + THUMBNAIL_GRID_SPACING))
            if new_columns != self._thumb_mgr.current_columns:
                self._thumb_mgr.current_columns = new_columns
                self._apply_filter()
        QTimer.singleShot(10, self._load_visible_thumbnails)

    def eventFilter(self, obj, event):
        if obj == self.thumb_size_label and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._validate_thumb_size_input()
                self.thumb_size_label.clearFocus()
                return True
        return super().eventFilter(obj, event)

    def _do_resize(self):
        pass
