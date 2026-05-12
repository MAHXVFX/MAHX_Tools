import os
import json

from .constants import _MAHX_TOOLS_DIR


class SettingsManager:
    _settings_file = os.path.join(_MAHX_TOOLS_DIR, "MAHX_HDR_Library_Settings.json")

    @classmethod
    def load(cls):
        try:
            if os.path.exists(cls._settings_file):
                with open(cls._settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load settings: {e}")
        return {}

    @classmethod
    def save(cls, settings):
        try:
            if os.path.exists(cls._settings_file):
                with open(cls._settings_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if existing == settings:
                    return False
            with open(cls._settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Failed to save settings: {e}")
            return False
