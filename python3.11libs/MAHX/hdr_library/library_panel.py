import os
import math

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QGraphicsOpacityEffect
from PySide6.QtGui import QCursor

from MAHX.common import HDR_EXTENSIONS, HDR_PARAMETER_NAMES
from MAHX.common import SettingsManager
from MAHX.common import _collect_hdr_files
from .thumbnail_widget import HDRThumbnailWidget
from .thumbnail_worker import ThumbnailWorker

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False


class HDRLibraryPanel(QtWidgets.QWidget):
    LAYOUT_MARGIN = 20
    RESIZE_DELAY = 50
    STATUS_COLOR_SUCCESS = "#87cc8e"
    STATUS_COLOR_WARNING = "#d1283e"
    STATUS_COLOR_NORMAL = "#888888"
    STATUS_STYLE = "font-size: 12px; font-weight: bold;"

    BTN_COLOR_ORIGINAL = "#0d6399"
    BTN_COLOR_PULSE = "#4da6d1"
    BTN_PADDING = "6px 16px"
    BTN_BORDER_RADIUS = "10px"
    BTN_MIN_WIDTH_COLLAPSED = "100px"
    BTN_MIN_WIDTH_EXPANDED = "130px"

    def _set_status(self, color, text):
        self.status_label.setStyleSheet(f"color: {color}; {self.STATUS_STYLE}")
        self.status_label.setText(text)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hdr_directory = ""
        self.cache_directory = ""
        self.thumbnails = []
        self._thumbnail_widgets = []
        self._current_columns = 0
        self._thumbnail_size = 180
        self._thumbnail_image_size = 170
        self._pixmap_cache = {}
        self._subfolders = []
        self._current_filter = "ALL"
        self._recent_hdrs = []
        self._favorite_hdrs = []
        self._skip_filter_apply = False
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._do_resize)
        self._cache_loaded = False
        self._settings_dirty = False
        self._thumbnail_cache_dirty = False
        self._loading_settings = False
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("HDR Asset Library")
        self.setMinimumSize(500, 360)
        self.setStyleSheet("""
            QWidget {
                background-color: #18181b;
                color: #ffffff;
                font-family: "Segoe UI", Arial, sans-serif;
            }
            QPushButton {
                background-color: #0d6399;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 10px;
                min-width: 120px;
                cursor: pointer;
            }
            QPushButton:hover {
                background-color: #0a4d7a;
            }
            QPushButton:pressed {
                background-color: #083a5f;
            }
            QPushButton#settingsButton {
                padding: 6px 16px;
                border-radius: 10px;
                transition: background-color 0.3s ease;
            }
            QPushButton#settingsButton:hover {
                background-color: #1a7bb8;
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                padding: 6px;
                border-radius: 8px;
            }
            QLabel {
                background-color: transparent;
                border: none;
                color: #cccccc;
            }
            QScrollArea {
                background-color: #1D1D20;
                border: 1px solid #3d3d3d;
                border-radius: 5px;
            }
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                text-align: center;
                background-color: #2d2d2d;
            }
            QProgressBar::chunk {
                background-color: #0d6399;
            }
            QSlider {
                background-color: transparent;
                border: none;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 6px;
                background-color: #000000;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background-color: #8a5cf5;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background-color: #ffffff;
                border: 1px solid #8a5cf5;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background-color: #ffffff;
            }
        """)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(self.LAYOUT_MARGIN, 5, self.LAYOUT_MARGIN, 0)
        main_layout.setSpacing(5)

        toolbar_layout = QtWidgets.QHBoxLayout()
        self.btn_toggle_settings = QtWidgets.QPushButton("Settings")
        self.btn_toggle_settings.setObjectName("settingsButton")
        self.btn_toggle_settings.setStyleSheet("background-color: #0d6399; color: white; padding: 6px 16px; border-radius: 10px;")
        self.btn_toggle_settings.setFixedWidth(100)
        self.btn_toggle_settings.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_toggle_settings.clicked.connect(self._toggle_settings)
        toolbar_layout.addWidget(self.btn_toggle_settings)

        lbl_thumb_size = QtWidgets.QLabel("Thumbnail Size")
        lbl_thumb_size.setStyleSheet("background-color: transparent; border: none; font-weight: bold; font-size: 14px;")
        toolbar_layout.addWidget(lbl_thumb_size)
        self.thumb_size_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.thumb_size_slider.setObjectName("thumbSizeSlider")
        self.thumb_size_slider.setMinimum(90)
        self.thumb_size_slider.setMaximum(500)
        self.thumb_size_slider.setValue(180)
        self.thumb_size_slider.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.thumb_size_slider.setMaximumWidth(200)
        self.thumb_size_slider.setCursor(QCursor(Qt.PointingHandCursor))
        self.thumb_size_slider.setStyleSheet("""
            QSlider#thumbSizeSlider {
                background-color: transparent;
                border: none;
            }
            QSlider#thumbSizeSlider::groove:horizontal {
                border: none;
                height: 6px;
                background-color: #000000;
                border-radius: 3px;
            }
            QSlider#thumbSizeSlider::sub-page:horizontal {
                background-color: #8a5cf5;
                border-radius: 3px;
            }
            QSlider#thumbSizeSlider::handle:horizontal {
                background-color: #ffffff;
                border: 1px solid #8a5cf5;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """)
        self.thumb_size_slider.valueChanged.connect(self._on_thumbnail_size_changed)
        toolbar_layout.addWidget(self.thumb_size_slider)
        self.thumb_size_label = QtWidgets.QLineEdit("180")
        self.thumb_size_label.setFixedWidth(45)
        self.thumb_size_label.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 2px 4px;
            }
        """)
        self.thumb_size_label.setAlignment(Qt.AlignCenter)
        self.thumb_size_label.returnPressed.connect(self._on_thumb_size_label_edited)
        self.thumb_size_label.installEventFilter(self)
        toolbar_layout.addWidget(self.thumb_size_label)
        toolbar_layout.addStretch()
        self.folder_label = QtWidgets.QLabel("Filter:")
        self.folder_label.setStyleSheet("background-color: transparent; border: none; color: #cccccc; font-weight: bold;")
        toolbar_layout.addWidget(self.folder_label)
        self.folder_combo = QtWidgets.QComboBox()
        self.folder_combo.setCursor(QCursor(Qt.PointingHandCursor))
        self.folder_combo.setStyleSheet("""
            QComboBox {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 4px 12px;
                min-width: 100px;
            }
            QComboBox:hover {
                background-color: #3d3d3d;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
        """)
        self.folder_combo.currentTextChanged.connect(self._on_folder_filter_changed)
        toolbar_layout.addWidget(self.folder_combo)
        main_layout.addLayout(toolbar_layout)

        self.settings_widget = QtWidgets.QWidget()
        self.settings_widget.setVisible(False)
        settings_layout = QtWidgets.QVBoxLayout(self.settings_widget)
        settings_layout.setSpacing(10)

        hdr_layout = QtWidgets.QHBoxLayout()
        lbl_hdr = QtWidgets.QLabel("HDR Library:")
        hdr_layout.addWidget(lbl_hdr)
        self.hdr_path_edit = QtWidgets.QLineEdit()
        self.hdr_path_edit.setPlaceholderText("Select HDR library directory...")
        hdr_layout.addWidget(self.hdr_path_edit)
        self.btn_browse_hdr = QtWidgets.QPushButton("Browse")
        self.btn_browse_hdr.setStyleSheet("background-color: #e0cb56; color: black; border-radius: 10px; padding: 4px 12px; min-height: 12px;")
        self.btn_browse_hdr.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_browse_hdr.clicked.connect(self.browse_hdr_directory)
        hdr_layout.addWidget(self.btn_browse_hdr)
        settings_layout.addLayout(hdr_layout)

        cache_layout = QtWidgets.QHBoxLayout()
        lbl_cache = QtWidgets.QLabel("Thumbnail Cache:")
        cache_layout.addWidget(lbl_cache)
        self.cache_path_edit = QtWidgets.QLineEdit()
        self.cache_path_edit.setPlaceholderText("Select thumbnail cache directory...")
        cache_layout.addWidget(self.cache_path_edit)
        self.btn_browse_cache = QtWidgets.QPushButton("Browse")
        self.btn_browse_cache.setStyleSheet("background-color: #e0cb56; color: black; border-radius: 10px; padding: 4px 12px; min-height: 12px;")
        self.btn_browse_cache.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_browse_cache.clicked.connect(self.browse_cache_directory)
        cache_layout.addWidget(self.btn_browse_cache)
        settings_layout.addLayout(cache_layout)

        self.print_path_checkbox = QtWidgets.QCheckBox("Log HDR path")
        self.print_path_checkbox.setChecked(True)
        self.print_path_checkbox.setCursor(QCursor(Qt.PointingHandCursor))
        self.print_path_checkbox.stateChanged.connect(self._on_print_path_changed)
        settings_layout.addWidget(self.print_path_checkbox)

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_scan = QtWidgets.QPushButton("Scan HDR Files")
        self.btn_scan.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_scan.setStyleSheet("background-color: #0d6399; color: white; min-height: 28px; padding: 0px 16px; border-radius: 10px;")
        self.btn_scan.clicked.connect(self.scan_hdr_files)
        self.btn_scan.setEnabled(False)
        btn_layout.addWidget(self.btn_scan)
        self.btn_refresh = QtWidgets.QPushButton("Refresh Thumbnails")
        self.btn_refresh.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_refresh.setStyleSheet("background-color: #0d6399; color: white; min-height: 28px; padding: 0px 16px; border-radius: 10px;")
        self.btn_refresh.clicked.connect(self.refresh_thumbnails)
        self.btn_refresh.setEnabled(False)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        settings_layout.addLayout(btn_layout)

        main_layout.addWidget(self.settings_widget)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._vscroll = self.scroll_area.verticalScrollBar()

        self.thumbnail_widget = QtWidgets.QWidget()
        self.thumbnail_widget.setStyleSheet("background-color: #1D1D20;")
        self.thumbnail_layout = QtWidgets.QGridLayout(self.thumbnail_widget)
        self.thumbnail_layout.setSpacing(15)
        self.thumbnail_layout.setContentsMargins(10, 10, 10, 10)
        self.thumbnail_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setWidget(self.thumbnail_widget)

        main_layout.addWidget(self.scroll_area)

        status_layout = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel("No HDR files loaded")
        self.status_label.setStyleSheet(f"color: {self.STATUS_COLOR_NORMAL}; {self.STATUS_STYLE}")
        self.status_label.setFixedHeight(20)
        self.version_label = QtWidgets.QLabel("MAHX Tools 1.0.0")
        self.version_label.setStyleSheet("color: #735ECA; font-size: 12px;")
        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.version_label)
        main_layout.addLayout(status_layout)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

    def _update_folder_combo(self):
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        self.folder_combo.addItem("ALL")
        if self._favorite_hdrs:
            self.folder_combo.addItem("\u2605 \u6536\u85cf")
        if self._recent_hdrs:
            self.folder_combo.addItem("\u6700\u8fd1")
        if self._has_root_hdrs():
            self.folder_combo.addItem("Root Only")
        for folder in self._subfolders:
            self.folder_combo.addItem(folder)
        self.folder_combo.blockSignals(False)

    def _has_root_hdrs(self):
        if not self.hdr_directory:
            return False
        base_dir = os.path.normpath(self.hdr_directory).lower()
        return any(
            os.path.normpath(os.path.dirname(t['hdr_path'])).lower() == base_dir
            for t in self.thumbnails
        )

    def _favorite_index(self, hdr_path):
        hdr_path_norm = os.path.normpath(hdr_path).lower()
        for idx, favorite_path in enumerate(self._favorite_hdrs):
            if os.path.normpath(favorite_path).lower() == hdr_path_norm:
                return idx
        return 999

    def _is_favorite(self, hdr_path):
        hdr_path_norm = os.path.normpath(hdr_path).lower()
        return any(os.path.normpath(path).lower() == hdr_path_norm for path in self._favorite_hdrs)

    def _apply_filter(self):
        selected = self.folder_combo.currentText()
        if selected == "ALL":
            filtered = self.thumbnails
        elif selected == "\u2605 \u6536\u85cf":
            if not self.thumbnails:
                filtered = []
            else:
                favorite_paths = set(os.path.normpath(p).lower() for p in self._favorite_hdrs)
                filtered = [t for t in self.thumbnails if os.path.normpath(t['hdr_path']).lower() in favorite_paths]
                filtered = sorted(filtered, key=lambda t: self._favorite_index(t['hdr_path']))
                if not filtered and self._favorite_hdrs:
                    filtered = self.thumbnails
                    self.folder_combo.setCurrentText("ALL")
        elif selected == "\u6700\u8fd1":
            if not self.thumbnails:
                filtered = []
            else:
                hdr_dir_norm = os.path.normpath(self.hdr_directory).lower()
                recent_paths = set(os.path.normpath(p).lower() for p in self._recent_hdrs)
                filtered = [t for t in self.thumbnails if os.path.normpath(t['hdr_path']).lower() in recent_paths]
                filtered = sorted(filtered, key=lambda t: self._recent_hdrs.index(t['hdr_path']) if t['hdr_path'] in self._recent_hdrs else 999)
                if not filtered and self._recent_hdrs:
                    filtered = self.thumbnails
                    self.folder_combo.setCurrentText("ALL")
        elif selected == "Root Only":
            base_dir = os.path.normpath(self.hdr_directory).lower()
            filtered = [t for t in self.thumbnails if os.path.normpath(os.path.dirname(t['hdr_path'])).lower() == base_dir]
        else:
            folder_path = os.path.normpath(os.path.join(self.hdr_directory, selected)).lower()
            filtered = [t for t in self.thumbnails if os.path.normpath(os.path.dirname(t['hdr_path'])).lower() == folder_path]
        self._display_filtered_thumbnails(filtered)

    def _create_thumbnail_widget(self, thumb_data):
        thumb_widget = HDRThumbnailWidget(
            thumb_data['hdr_path'],
            thumb_data['thumbnail_path'],
            self._thumbnail_size,
            self._thumbnail_image_size,
            lazy_load=True,
            is_favorite=self._is_favorite(thumb_data['hdr_path'])
        )
        thumb_widget.doubleClicked.connect(self.on_thumbnail_double_clicked)
        thumb_widget.favoriteToggled.connect(self.on_thumbnail_favorite_toggled)
        return thumb_widget

    def _display_filtered_thumbnails(self, filtered_thumbnails):
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        try:
            self._vscroll.disconnect(self._on_scroll)
        except:
            pass
        self._thumbnail_widgets = []
        self._current_visible_range = (-1, -1)

        columns = max(1, (self.width() - self.LAYOUT_MARGIN * 2) // (self._thumbnail_size + 15))
        self._current_columns = columns

        for idx, thumb_data in enumerate(filtered_thumbnails):
            row = idx // columns
            col = idx % columns
            thumb_widget = self._create_thumbnail_widget(thumb_data)
            self.thumbnail_layout.addWidget(thumb_widget, row, col)
            self._thumbnail_widgets.append(thumb_widget)

        self._vscroll.valueChanged.connect(self._on_scroll)
        QTimer.singleShot(0, self._load_visible_thumbnails)

    def _on_folder_filter_changed(self, text):
        self._current_filter = text
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
        self._recent_hdrs = settings.get('recent_hdrs', [])
        self._favorite_hdrs = settings.get('favorite_hdrs', [])
        self._skip_filter_apply = True
        thumb_size = settings.get('thumbnail_size', 130)
        self._thumbnail_size = thumb_size
        self._thumbnail_image_size = thumb_size - 10
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

        missing_count = sum(1 for t in self.thumbnails if os.path.exists(t['hdr_path']) and not os.path.exists(t['thumbnail_path']))
        if len(self.thumbnails) == 0 and self.hdr_directory:
            status_text = "No HDR files found"
            color = self.STATUS_COLOR_NORMAL
        elif missing_count > 0:
            status_text = f"Loaded {len(self.thumbnails)} HDR files ({missing_count} missing - scan to regenerate)"
            color = self.STATUS_COLOR_WARNING
        else:
            status_text = "Ready" if self.hdr_directory else "No HDR library path set"
            color = self.STATUS_COLOR_SUCCESS if self.hdr_directory else self.STATUS_COLOR_NORMAL
        self._set_status(color, status_text)

        saved_filter = settings.get('current_filter', 'ALL')
        self._skip_filter_apply = True
        self.folder_combo.blockSignals(True)
        if saved_filter in [self.folder_combo.itemText(i) for i in range(self.folder_combo.count())]:
            self.folder_combo.setCurrentText(saved_filter)
        else:
            self.folder_combo.setCurrentText('ALL')
        self.folder_combo.blockSignals(False)
        self._skip_filter_apply = False
        self._apply_filter()
        self._settings_dirty = False
        self._thumbnail_cache_dirty = False
        self._loading_settings = False

    def _group_thumbnails_by_folder(self):
        grouped = {}
        for thumb in self.thumbnails:
            try:
                rel_path = os.path.relpath(thumb['thumbnail_path'], self.cache_directory)
            except ValueError:
                continue
            folder = os.path.dirname(rel_path)
            thumbnail_filename = os.path.basename(thumb['thumbnail_path'])
            if folder == '.':
                folder = '__root__'
            if folder not in grouped:
                grouped[folder] = []
            grouped[folder].append(thumbnail_filename)
        return grouped

    def _try_load_cached_thumbnails(self, settings=None):
        if settings is None:
            settings = SettingsManager.load()
        cached_thumbnails = settings.get('thumbnails', {})
        cached_root_mtime = settings.get('hdr_dir_mtime')
        cached_subfolders_mtime = settings.get('subfolders_mtime', {})

        if not cached_thumbnails:
            return False

        if not os.path.exists(self.hdr_directory):
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

        for folder in current_subfolders_mtime.keys():
            if folder not in cached_subfolders_mtime:
                return False

        subfolders = []
        missing_thumbnails = 0
        all_thumbnails = []

        current_subfolders_set = set()
        if os.path.exists(self.hdr_directory):
            for item in os.listdir(self.hdr_directory):
                item_path = os.path.join(self.hdr_directory, item)
                if os.path.isdir(item_path):
                    current_subfolders_set.add(item)

        for folder, thumbnails in cached_thumbnails.items():
            if thumbnails:
                if folder and folder != '__root__':
                    if folder not in current_subfolders_set:
                        continue
                    subfolders.append(folder)
                folder_path = folder if folder != '__root__' else ''
                for thumbnail_filename in thumbnails:
                    thumbnail_path = os.path.normpath(os.path.join(self.cache_directory, folder_path, thumbnail_filename))
                    hdr_base = thumbnail_filename.replace('_Thumbnail.jpg', '')
                    hdr_path = None
                    for ext in HDR_EXTENSIONS:
                        candidate_path = os.path.normpath(os.path.join(self.hdr_directory, folder_path, hdr_base + ext))
                        if os.path.exists(candidate_path):
                            hdr_path = candidate_path
                            break
                    if not hdr_path:
                        hdr_path = os.path.normpath(os.path.join(self.hdr_directory, folder_path, hdr_base + '.hdr'))
                    if os.path.exists(hdr_path):
                        if not os.path.exists(thumbnail_path):
                            missing_thumbnails += 1
                        all_thumbnails.append({
                            'hdr_path': hdr_path,
                            'thumbnail_path': thumbnail_path,
                            'filename': os.path.basename(hdr_path)
                        })

        if not all_thumbnails:
            return False

        self.thumbnails = all_thumbnails
        self._subfolders = sorted(subfolders)
        self._update_folder_combo()
        self._apply_filter()

        self._cache_loaded = True
        if missing_thumbnails > 0:
            self._set_status(self.STATUS_COLOR_WARNING, f"Loaded {len(all_thumbnails)} HDR files ({missing_thumbnails} missing - scan to regenerate)")
        else:
            self._set_status(self.STATUS_COLOR_SUCCESS, f"Loaded {len(all_thumbnails)} HDR files (from cache)")
        return True

    def _toggle_settings(self):
        is_visible = self.settings_widget.isVisible()
        self.settings_widget.setVisible(not is_visible)
        self._pulse_button(self.btn_toggle_settings, not is_visible)
        self._animate_button_width(self.btn_toggle_settings, not is_visible)
        self._elastic_resize(self.settings_widget, not is_visible)

    def _animate_button_width(self, button, expanding):
        start_w = 100 if expanding else 130
        end_w = 130 if expanding else 100
        duration = 200
        steps = 20
        interval = duration // steps

        def animate(step=0):
            if step >= steps:
                button.setFixedWidth(end_w)
                return
            t = step / steps
            if expanding:
                current_w = start_w + (end_w - start_w) * (1 - math.pow(1 - t, 3))
            else:
                current_w = start_w * (1 - math.pow(t, 2)) + end_w * math.pow(t, 2)
            button.setFixedWidth(int(current_w))
            QTimer.singleShot(interval, lambda: animate(step + 1))

        button.setFixedWidth(start_w)
        QTimer.singleShot(0, lambda: animate())

    def _elastic_resize(self, widget, expanding):
        if expanding:
            widget.setFixedHeight(0)
            self._animate_height(widget, 0, widget.sizeHint().height(), 200, True, True)
        else:
            current_height = widget.height()
            widget.setFixedHeight(current_height)
            self._animate_height(widget, current_height, 0, 200, False, False)

    def _animate_height(self, widget, start_h, end_h, duration, visible, fade_in):
        steps = 30
        interval = duration // steps

        def animate(step=0):
            if step >= steps:
                widget.setFixedHeight(end_h)
                if not visible:
                    widget.setVisible(False)
                    widget.setGraphicsEffect(None)
                else:
                    self._set_widget_opacity(widget, 1.0)
                return

            t = step / steps
            if end_h > start_h:
                current_h = start_h + (end_h - start_h) * (1 - math.pow(1 - t, 3))
                opacity = t
            else:
                current_h = start_h * (1 - math.pow(t, 2))
                opacity = 1.0 - t

            widget.setFixedHeight(int(current_h))
            if fade_in or (not fade_in and step > 0):
                self._set_widget_opacity(widget, opacity)
            QTimer.singleShot(interval, lambda: animate(step + 1))

        widget.setVisible(True)
        if fade_in:
            self._set_widget_opacity(widget, 0.0)
        QTimer.singleShot(0, lambda: animate())

    def _set_widget_opacity(self, widget, opacity):
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(opacity)
        widget.setGraphicsEffect(effect)

    def _pulse_button(self, button, expanding):
        duration = 150
        steps = 6
        interval = duration // steps

        def animate(step=0):
            if step >= steps:
                button.setStyleSheet(f"background-color: {self.BTN_COLOR_ORIGINAL}; color: white; padding: {self.BTN_PADDING}; border-radius: {self.BTN_BORDER_RADIUS};")
                return
            ratio = math.sin(step / steps * math.pi)
            r1, g1, b1 = int(self.BTN_COLOR_ORIGINAL[1:3], 16), int(self.BTN_COLOR_ORIGINAL[3:5], 16), int(self.BTN_COLOR_ORIGINAL[5:7], 16)
            r2, g2, b2 = int(self.BTN_COLOR_PULSE[1:3], 16), int(self.BTN_COLOR_PULSE[3:5], 16), int(self.BTN_COLOR_PULSE[5:7], 16)
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            button.setStyleSheet(f"background-color: #{r:02x}{g:02x}{b:02x}; color: white; padding: {self.BTN_PADDING}; border-radius: {self.BTN_BORDER_RADIUS};")
            QTimer.singleShot(interval, lambda: animate(step + 1))

        QTimer.singleShot(0, lambda: animate())

    def _on_thumbnail_size_changed(self, value):
        self.thumb_size_label.setText(str(value))
        self._thumbnail_size = value
        self._thumbnail_image_size = value - 10
        if not self._loading_settings:
            self._settings_dirty = True

        if not self.thumbnails:
            return

        new_columns = max(1, (self.width() - self.LAYOUT_MARGIN * 2) // (self._thumbnail_size + 15))

        if new_columns != self._current_columns:
            self.display_thumbnails()
        else:
            for widget in self._thumbnail_widgets:
                widget.updateSize(value, value - 10, self._pixmap_cache)

        self._resize_timer.start(self.RESIZE_DELAY)

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

    def _load_existing_thumbnails(self):
        if not self.hdr_directory or not os.path.exists(self.hdr_directory):
            return
        if not self.cache_directory or not os.path.exists(self.cache_directory):
            return

        self._cache_loaded = False
        thumbnails = []
        hdr_files, subfolders = _collect_hdr_files(self.hdr_directory)
        self._subfolders = sorted(subfolders)
        missing_count = 0

        for hdr_path in hdr_files:
            rel_path = os.path.relpath(hdr_path, self.hdr_directory)
            thumbnail_rel = rel_path.rsplit('.', 1)[0] + '_Thumbnail.jpg'
            thumbnail_path = os.path.normpath(os.path.join(self.cache_directory, thumbnail_rel))
            thumbnails.append({
                'hdr_path': os.path.normpath(hdr_path),
                'thumbnail_path': thumbnail_path,
                'filename': os.path.basename(hdr_path)
            })
            if not os.path.exists(thumbnail_path):
                missing_count += 1

        self.thumbnails = thumbnails
        self._update_folder_combo()
        self._apply_filter()

        if len(thumbnails) == 0:
            self._set_status(self.STATUS_COLOR_NORMAL, "No HDR files found")
        elif missing_count > 0:
            self._set_status(self.STATUS_COLOR_WARNING, f"Loaded {len(thumbnails)} HDR files ({missing_count} missing - scan to regenerate)")
        else:
            self._set_status(self.STATUS_COLOR_SUCCESS, f"Loaded {len(thumbnails)} HDR files (existing thumbnails only)")

    def browse_hdr_directory(self):
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select HDR Library Directory",
            self.hdr_directory if self.hdr_directory else os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if dir_path:
            self.hdr_directory = dir_path
            self.hdr_path_edit.setText(dir_path)
            self.btn_scan.setEnabled(True)
            self._set_status(self.STATUS_COLOR_SUCCESS, f"HDR Library: {dir_path}")
            self._save_settings()

    def browse_cache_directory(self):
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Thumbnail Cache Directory",
            self.cache_directory if self.cache_directory else os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if dir_path:
            self.cache_directory = dir_path
            self.cache_path_edit.setText(dir_path)
            self.btn_refresh.setEnabled(True)
            self._save_settings()

    def _on_print_path_changed(self, state):
        if self._loading_settings:
            return
        self._save_settings()

    def _save_settings(self):
        settings = SettingsManager.load()
        settings['hdr_directory'] = self.hdr_directory
        settings['cache_directory'] = self.cache_directory
        settings['print_path'] = self.print_path_checkbox.isChecked()
        settings['recent_hdrs'] = self._recent_hdrs
        settings['favorite_hdrs'] = self._favorite_hdrs
        settings['current_filter'] = self.folder_combo.currentText()
        SettingsManager.save(settings)

    def scan_hdr_files(self):
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

        self.worker = ThumbnailWorker(self.hdr_directory, self.cache_directory)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.error.connect(self.on_scan_error)
        self.worker.start()

    def update_progress(self, current, total):
        if total <= 0:
            self.progress_bar.setValue(0)
            self.status_label.setText("No HDR files found")
            return
        percentage = int((current / total) * 100)
        self.progress_bar.setValue(percentage)
        self.status_label.setText(f"Generating thumbnails: {current}/{total} ({percentage}%)")

    def on_scan_finished(self, thumbnails, subfolders):
        self._thumbnail_cache_dirty = True
        self._cache_loaded = False
        self.thumbnails = thumbnails
        self._subfolders = sorted(subfolders)
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self._update_folder_combo()
        self._apply_filter()
        self._set_status(self.STATUS_COLOR_SUCCESS, f"Loaded {len(thumbnails)} HDR files")

    def on_scan_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to scan HDR files:\n{error_msg}")

    def refresh_thumbnails(self):
        if self.thumbnails:
            failed = []
            for thumb_data in self.thumbnails:
                thumbnail_path = thumb_data['thumbnail_path']
                if os.path.exists(thumbnail_path):
                    try:
                        os.remove(thumbnail_path)
                    except OSError as e:
                        failed.append((thumbnail_path, e))
            if failed:
                self._set_status(self.STATUS_COLOR_WARNING, f"Could not delete {len(failed)} thumbnails")
                print("Failed to delete thumbnails:")
                for thumbnail_path, error in failed:
                    print(f"{thumbnail_path}: {error}")
                QMessageBox.warning(
                    self,
                    "Refresh Thumbnails",
                    f"Could not delete {len(failed)} thumbnail files. Check the console for details."
                )
            self.scan_hdr_files()

    def display_thumbnails(self):
        self.thumbnail_widget = QtWidgets.QWidget()
        self.thumbnail_widget.setStyleSheet("background-color: #1D1D20;")
        self.thumbnail_layout = QtWidgets.QGridLayout(self.thumbnail_widget)
        self.thumbnail_layout.setSpacing(15)
        self.thumbnail_layout.setContentsMargins(10, 10, 10, 10)
        self.thumbnail_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setWidget(self.thumbnail_widget)

        if not self.thumbnails:
            no_files_label = QtWidgets.QLabel("No HDR files found")
            no_files_label.setStyleSheet("color: #888888; font-size: 14px;")
            self.thumbnail_layout.addWidget(no_files_label, 0, 0)
            return

        missing_count = sum(1 for t in self.thumbnails if not os.path.exists(t['thumbnail_path']))
        if missing_count > 0:
            self._set_status(self.STATUS_COLOR_WARNING, f"{len(self.thumbnails)} HDR files ({missing_count} missing thumbnails - please scan)")
        else:
            self._set_status(self.STATUS_COLOR_SUCCESS, f"Loaded {len(self.thumbnails)} HDR files")

        try:
            self._vscroll.disconnect(self._on_scroll)
        except:
            pass
        self._thumbnail_widgets = []

        columns = max(1, (self.width() - self.LAYOUT_MARGIN * 2) // (self._thumbnail_size + 15))
        self._current_columns = columns

        for idx, thumb_data in enumerate(self.thumbnails):
            row = idx // columns
            col = idx % columns

            thumb_widget = self._create_thumbnail_widget(thumb_data)
            self.thumbnail_layout.addWidget(thumb_widget, row, col)
            self._thumbnail_widgets.append(thumb_widget)

        self._current_visible_range = (-1, -1)
        self._vscroll.valueChanged.connect(self._on_scroll)
        QTimer.singleShot(0, self._load_visible_thumbnails)

    def _on_scroll(self, value=None):
        self._load_visible_thumbnails()

    def _load_visible_thumbnails(self):
        if not self._thumbnail_widgets or self._current_columns <= 0:
            return

        scroll_y = self._vscroll.value()
        viewport_height = self.scroll_area.viewport().height()
        if viewport_height <= 0:
            viewport_height = self.height() - 100
        row_height = self._thumbnail_size + 20 + 15
        if row_height <= 0:
            row_height = 200

        start_row = max(0, scroll_y // row_height - 1)
        end_row = (scroll_y + viewport_height) // row_height + 2
        total_rows = (len(self._thumbnail_widgets) + self._current_columns - 1) // self._current_columns
        end_row = min(end_row, total_rows)

        start_idx = start_row * self._current_columns
        end_idx = min(end_row * self._current_columns, len(self._thumbnail_widgets))

        if self._current_visible_range == (start_idx, end_idx):
            return

        self._current_visible_range = (start_idx, end_idx)

        for i, widget in enumerate(self._thumbnail_widgets):
            if start_idx <= i < end_idx:
                widget.ensure_loaded(self._thumbnail_image_size)
            else:
                if i < start_idx - self._current_columns * 3 or i >= end_idx + self._current_columns * 3:
                    widget.unload()

    def on_thumbnail_double_clicked(self, hdr_path):
        self.load_hdr_to_environment_light(hdr_path)

    def on_thumbnail_favorite_toggled(self, hdr_path):
        hdr_path = os.path.normpath(hdr_path)
        favorite_index = self._favorite_index(hdr_path)
        is_favorite = favorite_index != 999

        if is_favorite:
            self._favorite_hdrs.pop(favorite_index)
            status_text = f"Removed from favorites: {os.path.basename(hdr_path)}"
        else:
            self._favorite_hdrs.insert(0, hdr_path)
            status_text = f"Added to favorites: {os.path.basename(hdr_path)}"

        self._settings_dirty = True
        self._save_settings()
        self._set_status(self.STATUS_COLOR_SUCCESS, status_text)

        current_filter = self.folder_combo.currentText()
        self._update_folder_combo()
        available_filters = [self.folder_combo.itemText(i) for i in range(self.folder_combo.count())]
        self.folder_combo.blockSignals(True)
        self.folder_combo.setCurrentText(current_filter if current_filter in available_filters else "ALL")
        self.folder_combo.blockSignals(False)

        if current_filter == "\u2605 \u6536\u85cf":
            self._apply_filter()
        else:
            for widget in self._thumbnail_widgets:
                if os.path.normpath(widget.hdr_path).lower() == os.path.normpath(hdr_path).lower():
                    widget.setFavorite(not is_favorite)

    def _add_to_recent(self, hdr_path):
        if hdr_path in self._recent_hdrs:
            self._recent_hdrs.remove(hdr_path)
        self._recent_hdrs.insert(0, hdr_path)
        if len(self._recent_hdrs) > 20:
            self._recent_hdrs = self._recent_hdrs[:20]
        self._save_settings()
        current_filter = self.folder_combo.currentText()
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        self.folder_combo.addItem("ALL")
        if self._favorite_hdrs:
            self.folder_combo.addItem("\u2605 \u6536\u85cf")
        if self._recent_hdrs:
            self.folder_combo.addItem("\u6700\u8fd1")
        if self._has_root_hdrs():
            self.folder_combo.addItem("Root Only")
        for folder in self._subfolders:
            self.folder_combo.addItem(folder)
        if current_filter in [self.folder_combo.itemText(i) for i in range(self.folder_combo.count())]:
            self.folder_combo.setCurrentText(current_filter)
        self.folder_combo.blockSignals(False)

    def load_hdr_to_environment_light(self, hdr_path):
        if not HOU_AVAILABLE:
            return

        applied = False
        try:
            import hou
            selected_nodes = hou.selectedNodes()
            if not selected_nodes:
                return

            for selected_node in selected_nodes:
                parm = None
                for parm_name in HDR_PARAMETER_NAMES:
                    parm = selected_node.parm(parm_name)
                    if parm:
                        break
                if parm:
                    parm.set(hdr_path)
                    applied = True

            if applied and self.print_path_checkbox.isChecked():
                print(hdr_path, end="\r")
            if applied:
                self._add_to_recent(hdr_path)
        except Exception as e:
            print(f"Error loading HDR: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.thumbnails and self._thumbnail_widgets:
            new_columns = max(1, (self.width() - self.LAYOUT_MARGIN * 2) // (self._thumbnail_size + 15))
            if new_columns != self._current_columns:
                self._current_columns = new_columns
                self._current_visible_range = (-1, -1)
                self._apply_filter()
        QTimer.singleShot(10, self._load_visible_thumbnails)

    def eventFilter(self, obj, event):
        if obj == self.thumb_size_label and event.type() == QtCore.QEvent.KeyPress:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self._validate_thumb_size_input()
                self.thumb_size_label.clearFocus()
                return True
        return super().eventFilter(obj, event)

    def _do_resize(self):
        pass
