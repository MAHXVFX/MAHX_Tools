import os
import json
import copy
import logging

from .constants import _MAHX_TOOLS_DIR

logger = logging.getLogger("MAHX")


class SettingsManager:
    _settings_file = os.path.join(_MAHX_TOOLS_DIR, "MAHX_HDR_Library_Settings.json")
    _cache = None
    _saved_state = None

    @classmethod
    def load(cls):
        if cls._cache is not None:
            return cls._cache
        try:
            if os.path.exists(cls._settings_file):
                with open(cls._settings_file, 'r', encoding='utf-8') as f:
                    cls._cache = json.load(f)
                    cls._saved_state = copy.deepcopy(cls._cache)
                    return cls._cache
        except Exception as e:
            logger.warning("Failed to load settings: %s", e)
        cls._cache = {}
        cls._saved_state = {}
        return cls._cache

    @classmethod
    def save(cls, settings):
        try:
            if cls._saved_state is not None and cls._saved_state == settings:
                return False
            with open(cls._settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            cls._cache = settings
            cls._saved_state = copy.deepcopy(settings)
            return True
        except Exception as e:
            logger.warning("Failed to save settings: %s", e)
            return False

    @classmethod
    def update(cls, key, value):
        settings = cls.load()
        if settings.get(key) != value:
            settings[key] = value
            return cls.save(settings)
        return False

    @classmethod
    def invalidate_cache(cls):
        cls._cache = None
        cls._saved_state = None
