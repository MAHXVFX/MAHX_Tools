import os
import logging

from PySide6.QtWidgets import QGridLayout

from .thumbnail_widget import HDRThumbnailWidget

logger = logging.getLogger("MA")


class ThumbnailManager:
    MAX_CACHE_SIZE = 500

    def __init__(self):
        self._widgets = []
        self._pixmap_cache = {}
        self._current_columns = 0
        self._thumbnail_size = 180
        self._thumbnail_image_size = 170
        self._current_visible_range = (-1, -1)

    @property
    def widgets(self):
        return self._widgets

    @property
    def current_columns(self):
        return self._current_columns

    @current_columns.setter
    def current_columns(self, value):
        self._current_columns = value

    @property
    def thumbnail_size(self):
        return self._thumbnail_size

    @thumbnail_size.setter
    def thumbnail_size(self, value):
        self._thumbnail_size = value
        self._thumbnail_image_size = value - 10

    @property
    def thumbnail_image_size(self):
        return self._thumbnail_image_size

    @property
    def pixmap_cache(self):
        return self._pixmap_cache

    def create_widget(self, thumb_data, is_favorite=False):
        widget = HDRThumbnailWidget(
            thumb_data['hdr_path'],
            thumb_data['thumbnail_path'],
            self._thumbnail_size,
            self._thumbnail_image_size,
            lazy_load=True,
            is_favorite=is_favorite
        )
        return widget

    def populate_grid(self, layout, filtered_thumbnails, is_favorite_fn, double_click_fn, favorite_toggle_fn):
        self._clear_widgets(layout)
        self._current_visible_range = (-1, -1)

        for idx, thumb_data in enumerate(filtered_thumbnails):
            row = idx // self._current_columns
            col = idx % self._current_columns
            widget = self.create_widget(thumb_data, is_favorite_fn(thumb_data['hdr_path']))
            widget.doubleClicked.connect(double_click_fn)
            widget.favoriteToggled.connect(favorite_toggle_fn)
            layout.addWidget(widget, row, col)
            self._widgets.append(widget)

    def _clear_widgets(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._widgets = []

    def update_visible_range(self, scroll_value, viewport_height, row_height):
        if not self._widgets or self._current_columns <= 0:
            return

        if row_height <= 0:
            row_height = 200

        start_row = max(0, scroll_value // row_height - 1)
        end_row = (scroll_value + viewport_height) // row_height + 2
        total_rows = (len(self._widgets) + self._current_columns - 1) // self._current_columns
        end_row = min(end_row, total_rows)

        start_idx = start_row * self._current_columns
        end_idx = min(end_row * self._current_columns, len(self._widgets))

        if self._current_visible_range == (start_idx, end_idx):
            return

        self._current_visible_range = (start_idx, end_idx)

        for i, widget in enumerate(self._widgets):
            if start_idx <= i < end_idx:
                widget.ensure_loaded(self._thumbnail_image_size)
            else:
                if i < start_idx - self._current_columns * 3 or i >= end_idx + self._current_columns * 3:
                    widget.unload()

    def update_all_sizes(self, new_size):
        self._thumbnail_size = new_size
        self._thumbnail_image_size = new_size - 10
        for widget in self._widgets:
            widget.updateSize(new_size, new_size - 10, self._pixmap_cache)

    def _cache_pixmap(self, key, pixmap):
        if len(self._pixmap_cache) >= self.MAX_CACHE_SIZE:
            oldest_key = next(iter(self._pixmap_cache))
            del self._pixmap_cache[oldest_key]
        self._pixmap_cache[key] = pixmap
