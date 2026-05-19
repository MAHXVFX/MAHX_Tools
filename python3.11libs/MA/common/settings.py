import os
import json
import copy
import logging

from .constants import HDR_SETTINGS_FILE, HDR_CACHE_FILE, SHELFTOOLS_SETTINGS_FILE, SHELFTOOLS_CACHE_FILE, SHELFTOOLS_NOTES_DIR, DEFAULT_SHELFTOOLS_THUMBNAIL_DIR

logger = logging.getLogger("MA")


class BaseJsonManager:
    """带类级缓存的 JSON 文件管理器基类。子类设置 _file 路径即可。"""
    _file = ""
    _cache = None
    _saved_state = None

    @classmethod
    def load(cls):
        if cls._cache is not None:
            return cls._cache
        try:
            if os.path.exists(cls._file):
                with open(cls._file, 'r', encoding='utf-8') as f:
                    cls._cache = json.load(f)
                    cls._saved_state = copy.deepcopy(cls._cache)
                    return cls._cache
        except Exception as e:
            logger.warning("Failed to load %s: %s", cls._file, e)
        cls._cache = {}
        cls._saved_state = {}
        return cls._cache

    @classmethod
    def save(cls, data):
        try:
            if cls._saved_state is not None and cls._saved_state == data:
                return False
            with open(cls._file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            cls._cache = data
            cls._saved_state = copy.deepcopy(data)
            return True
        except Exception as e:
            logger.warning("Failed to save %s: %s", cls._file, e)
            return False

    @classmethod
    def update(cls, key, value):
        data = cls.load()
        if data.get(key) != value:
            data[key] = value
            return cls.save(data)
        return False

    @classmethod
    def invalidate_cache(cls):
        cls._cache = None
        cls._saved_state = None


class SettingsManager(BaseJsonManager):
    _file = HDR_SETTINGS_FILE


class CacheManager(BaseJsonManager):
    _file = HDR_CACHE_FILE


class ShelfToolsSettingsManager(BaseJsonManager):
    _file = SHELFTOOLS_SETTINGS_FILE

    @classmethod
    def get_thumbnail_directory(cls):
        """获取自定义缩略图目录路径。"""
        data = cls.load()
        return data.get("thumbnail_directory", DEFAULT_SHELFTOOLS_THUMBNAIL_DIR)

    @classmethod
    def set_thumbnail_directory(cls, path):
        """设置自定义缩略图目录，目录不存在时自动创建。"""
        os.makedirs(path, exist_ok=True)
        cls.update("thumbnail_directory", path)


class ShelfToolsCacheManager(BaseJsonManager):
    _file = SHELFTOOLS_CACHE_FILE

    @classmethod
    def get_note(cls, tool_name):
        """获取工具的备注内容，未设置时返回 None。"""
        note_path = os.path.join(SHELFTOOLS_NOTES_DIR, f"{tool_name}.md")
        if not os.path.exists(note_path):
            return None
        with open(note_path, "r", encoding="utf-8") as f:
            return f.read()

    @classmethod
    def set_note(cls, tool_name, note):
        """设置工具的备注，保存为独立 .md 文件。"""
        os.makedirs(SHELFTOOLS_NOTES_DIR, exist_ok=True)
        note_path = os.path.join(SHELFTOOLS_NOTES_DIR, f"{tool_name}.md")
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(note)

    # ── 图标缓存 ────────────────────────────────
    _ICON_KEY = "icon_{}"

    @classmethod
    def get_tool_icon(cls, tool_name):
        """获取工具自定义图标路径，未设置返回 None。"""
        return cls.load().get(cls._ICON_KEY.format(tool_name))

    @classmethod
    def set_tool_icon(cls, tool_name, icon_path):
        """设置工具图标路径（空字符串则清除）。"""
        if icon_path:
            cls.update(cls._ICON_KEY.format(tool_name), icon_path)
        else:
            cls.remove_tool_icon(tool_name)

    @classmethod
    def remove_tool_icon(cls, tool_name):
        """清除工具图标缓存。"""
        data = cls.load()
        key = cls._ICON_KEY.format(tool_name)
        if key in data:
            del data[key]
            cls.save(data)
