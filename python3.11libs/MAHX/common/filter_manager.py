import os
import logging

from .constants import MAX_RECENT_HDRS, FAVORITE_NOT_FOUND, HDR_EXTENSIONS

logger = logging.getLogger("MAHX")


class FilterManager:
    def __init__(self):
        self._thumbnails = []
        self._subfolders = []
        self._favorite_hdrs = []
        self._recent_hdrs = []
        self._hdr_directory = ""
        self._normalized_path_cache = {}
        self._folder_cache = {}
        self._rebuild_indices()

    @property
    def thumbnails(self):
        return self._thumbnails

    @thumbnails.setter
    def thumbnails(self, value):
        self._thumbnails = value
        self._rebuild_indices()

    @property
    def subfolders(self):
        return self._subfolders

    @subfolders.setter
    def subfolders(self, value):
        self._subfolders = value

    @property
    def favorite_hdrs(self):
        return self._favorite_hdrs

    @favorite_hdrs.setter
    def favorite_hdrs(self, value):
        self._favorite_hdrs = value
        self._rebuild_favorite_set()

    @property
    def recent_hdrs(self):
        return self._recent_hdrs

    @recent_hdrs.setter
    def recent_hdrs(self, value):
        self._recent_hdrs = value

    @property
    def hdr_directory(self):
        return self._hdr_directory

    @hdr_directory.setter
    def hdr_directory(self, value):
        self._hdr_directory = value
        self._rebuild_indices()

    def _rebuild_indices(self):
        self._normalized_path_cache = {}
        self._folder_cache = {}
        for t in self._thumbnails:
            hdr_path = t['hdr_path']
            self._normalized_path_cache[hdr_path] = os.path.normpath(hdr_path).lower()
            self._folder_cache[hdr_path] = os.path.normpath(os.path.dirname(hdr_path)).lower()
        self._rebuild_favorite_set()

    def _rebuild_favorite_set(self):
        self._favorite_set = set(
            os.path.normpath(p).lower() for p in self._favorite_hdrs
        )

    def favorite_index(self, hdr_path):
        norm = os.path.normpath(hdr_path).lower()
        for idx, fav in enumerate(self._favorite_hdrs):
            if os.path.normpath(fav).lower() == norm:
                return idx
        return FAVORITE_NOT_FOUND

    def is_favorite(self, hdr_path):
        norm = self._normalized_path_cache.get(hdr_path, os.path.normpath(hdr_path).lower())
        return norm in self._favorite_set

    def toggle_favorite(self, hdr_path):
        hdr_path = os.path.normpath(hdr_path)
        idx = self.favorite_index(hdr_path)
        is_fav = idx != FAVORITE_NOT_FOUND
        if is_fav:
            self._favorite_hdrs.pop(idx)
            self._rebuild_favorite_set()
            return False
        else:
            self._favorite_hdrs.insert(0, hdr_path)
            self._rebuild_favorite_set()
            return True

    def add_to_recent(self, hdr_path):
        if hdr_path in self._recent_hdrs:
            self._recent_hdrs.remove(hdr_path)
        self._recent_hdrs.insert(0, hdr_path)
        if len(self._recent_hdrs) > MAX_RECENT_HDRS:
            self._recent_hdrs = self._recent_hdrs[:MAX_RECENT_HDRS]

    def has_root_hdrs(self):
        if not self._hdr_directory:
            return False
        base_dir = os.path.normpath(self._hdr_directory).lower()
        return any(
            self._folder_cache.get(t['hdr_path']) == base_dir
            for t in self._thumbnails
        )

    def _folder_has_valid_thumbnails(self, folder_path):
        return any(
            self._folder_cache.get(t['hdr_path']) == folder_path
            and not t.get('is_placeholder', False)
            for t in self._thumbnails
        )

    def get_filter_options(self, hide_placeholders=False):
        options = ["ALL"]
        if self._favorite_hdrs:
            options.append("\u2605 \u6536\u85cf")
        if self._recent_hdrs:
            options.append("\u6700\u8fd1")
        if self.has_root_hdrs():
            if not hide_placeholders or self._folder_has_valid_thumbnails(
                os.path.normpath(self._hdr_directory).lower()
            ):
                options.append("Root Only")
        for folder in self._subfolders:
            if not hide_placeholders or self._folder_has_valid_thumbnails(
                os.path.normpath(os.path.join(self._hdr_directory, folder)).lower()
            ):
                options.append(folder)
        return options

    def apply_filter(self, selected):
        if selected == "ALL":
            return self._thumbnails
        elif selected == "\u2605 \u6536\u85cf":
            return self._filter_favorites()
        elif selected == "\u6700\u8fd1":
            return self._filter_recent()
        elif selected == "Root Only":
            return self._filter_root_only()
        else:
            return self._filter_by_folder(selected)

    def _filter_favorites(self):
        if not self._thumbnails:
            return []
        filtered = [
            t for t in self._thumbnails
            if self._normalized_path_cache.get(t['hdr_path'], '') in self._favorite_set
        ]
        filtered.sort(key=lambda t: self.favorite_index(t['hdr_path']))
        return filtered

    def _filter_recent(self):
        if not self._thumbnails:
            return []
        recent_set = set(self._recent_hdrs)
        filtered = [t for t in self._thumbnails if t['hdr_path'] in recent_set]
        filtered.sort(
            key=lambda t: self._recent_hdrs.index(t['hdr_path'])
            if t['hdr_path'] in self._recent_hdrs else 999
        )
        return filtered

    def _filter_root_only(self):
        base_dir = os.path.normpath(self._hdr_directory).lower()
        return [
            t for t in self._thumbnails
            if self._folder_cache.get(t['hdr_path']) == base_dir
        ]

    def _filter_by_folder(self, folder_name):
        folder_path = os.path.normpath(os.path.join(self._hdr_directory, folder_name)).lower()
        return [
            t for t in self._thumbnails
            if self._folder_cache.get(t['hdr_path']) == folder_path
        ]

    def group_thumbnails_by_folder(self, cache_directory):
        grouped = {}
        for thumb in self._thumbnails:
            try:
                rel_path = os.path.relpath(thumb['thumbnail_path'], cache_directory)
            except ValueError:
                continue
            folder = os.path.dirname(rel_path)
            thumbnail_filename = os.path.basename(thumb['thumbnail_path'])
            if folder == '.':
                folder = '__root__'
            if folder not in grouped:
                grouped[folder] = []
            grouped[folder].append({
                'filename': thumbnail_filename,
                'is_placeholder': thumb.get('is_placeholder', False),
            })
        return grouped
