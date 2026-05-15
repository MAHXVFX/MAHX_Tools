import os
import json
import copy
import logging

from .constants import HDR_SETTINGS_FILE, HDR_CACHE_FILE, SHELFTOOLS_SETTINGS_FILE, SHELFTOOLS_CACHE_FILE

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


class ShelfToolsCacheManager(BaseJsonManager):
    _file = SHELFTOOLS_CACHE_FILE
