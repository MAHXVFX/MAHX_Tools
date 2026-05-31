import os
import json
import copy
import shutil
import logging

from .constants import HDR_SETTINGS_FILE, HDR_CACHE_FILE, SHELFTOOLS_SETTINGS_FILE, SHELFTOOLS_CACHE_FILE, SHELFTOOLS_NOTES_DIR, DEFAULT_SHELFTOOLS_THUMBNAIL_DIR, _MA_TOOLS_DIR

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

    # ── 收藏管理 ────────────────────────────────
    _FAVORITES_KEY = "favorite_tools"

    @classmethod
    def get_favorites(cls) -> list:
        """获取收藏的工具 unique_id 列表。"""
        return cls.load().get(cls._FAVORITES_KEY, [])

    @classmethod
    def set_favorites(cls, fav_list: list):
        """设置收藏列表。"""
        cls.update(cls._FAVORITES_KEY, fav_list)

    @classmethod
    def toggle_favorite(cls, unique_id: str) -> bool:
        """切换收藏状态。返回 True=已收藏, False=已取消。
        
        注意：必须复制列表，避免因同一个对象引用导致 update() 跳过写入。
        """
        favs = list(cls.get_favorites())  # 复制，确保 set_favorites → update 能检测到变化
        if unique_id in favs:
            favs.remove(unique_id)
            cls.set_favorites(favs)
            return False
        else:
            favs.insert(0, unique_id)
            cls.set_favorites(favs)
            return True

    @classmethod
    def is_favorite(cls, unique_id: str) -> bool:
        """检查是否已收藏。"""
        return unique_id in cls.get_favorites()

    # ── 筛选状态 ────────────────────────────────
    _FILTER_KEY = "last_filter"

    @classmethod
    def get_filter(cls) -> str:
        """获取上次关闭时的筛选项。"""
        return cls.load().get(cls._FILTER_KEY, "all")

    @classmethod
    def set_filter(cls, filter_value: str):
        """保存当前筛选项。"""
        cls.update(cls._FILTER_KEY, filter_value)


class ShelfToolsCacheManager(BaseJsonManager):
    _file = SHELFTOOLS_CACHE_FILE

    @classmethod
    def _is_builtin_tool(cls, tool_name: str) -> bool:
        """检查工具是否为内置工具（unique_id 包含 builtin_tools 目录下的 shelf_stem）。"""
        from MA.shelf_tool_pro.shelf_loader import _TOOL_REGISTRY
        if tool_name in _TOOL_REGISTRY:
            _, _, _, _, shelf_path = _TOOL_REGISTRY[tool_name]
            return "builtin_tools" in shelf_path
        return False

    @classmethod
    def get_note(cls, tool_name):
        """获取工具的备注内容，未设置时返回 None。内置工具返回 None。"""
        if cls._is_builtin_tool(tool_name):
            return None
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

    # ── 标签管理 ────────────────────────────────
    _TAGS_KEY = "tags_{}"

    @classmethod
    def get_tags(cls, tool_name: str) -> list:
        """获取工具的标签列表。内置工具返回空列表。"""
        if cls._is_builtin_tool(tool_name):
            return []
        return cls.load().get(cls._TAGS_KEY.format(tool_name), [])

    @classmethod
    def set_tags(cls, tool_name: str, tags: list):
        """设置工具的标签列表。"""
        cls.update(cls._TAGS_KEY.format(tool_name), tags)

    @classmethod
    def add_tag(cls, tool_name: str, tag: str) -> bool:
        """为工具添加标签。返回 True=已添加, False=已存在。"""
        tags = list(cls.get_tags(tool_name))
        if tag in tags:
            return False
        tags.append(tag)
        cls.set_tags(tool_name, tags)
        return True

    @classmethod
    def remove_tag(cls, tool_name: str, tag: str) -> bool:
        """从工具移除标签。返回 True=已移除, False=不存在。"""
        tags = list(cls.get_tags(tool_name))
        if tag not in tags:
            return False
        tags.remove(tag)
        cls.set_tags(tool_name, tags)
        return True

    @classmethod
    def get_all_tags(cls) -> list:
        """获取所有工具中使用过的唯一标签列表（按字母排序）。排除内置工具。"""
        data = cls.load()
        all_tags = set()
        for key, value in data.items():
            if key.startswith("tags_") and isinstance(value, list):
                tool_name = key[5:]  # 去掉 "tags_" 前缀
                if not cls._is_builtin_tool(tool_name):
                    all_tags.update(value)
        return sorted(all_tags)

    # ── 图标缓存 ────────────────────────────────
    _ICON_KEY = "icon_{}"

    @classmethod
    def _get_tools_root(cls):
        """获取项目根目录（_MA_TOOLS_DIR），用作相对路径的基准。"""
        return os.path.dirname(cls._file)  # SHELFTOOLS_CACHE_FILE 所在目录

    @classmethod
    def _abs_icon_path(cls, path):
        """将缓存中的路径解析为绝对路径：相对路径拼接根目录，绝对路径直接返回（向后兼容）。"""
        if not path or os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(cls._get_tools_root(), path))

    @classmethod
    def _rel_icon_path(cls, path):
        """将绝对路径转为相对于项目根目录的路径；跨盘符时返回原路径。"""
        if not path:
            return path
        root = cls._get_tools_root()
        try:
            return os.path.relpath(path, root)
        except ValueError:
            return path

    @classmethod
    def get_tool_icon(cls, tool_name):
        """获取工具自定义图标路径，未设置返回 None。内置工具返回 None。"""
        if cls._is_builtin_tool(tool_name):
            return None
        path = cls.load().get(cls._ICON_KEY.format(tool_name))
        return cls._abs_icon_path(path)

    @classmethod
    def _cleanup_old_thumbnails(cls, tool_name, thumb_dir, skip_path=""):
        """清理该工具的旧缩略图文件（按缓存路径删除，O(1)）。
        
        优先使用缓存中的旧路径删除，不扫描目录，不盲目尝试扩展名。
        静默处理文件锁定（QMovie 占用）。
        """
        old_icon_path = cls.get_tool_icon(tool_name)
        if not old_icon_path:
            return
        
        abs_skip = os.path.abspath(skip_path) if skip_path else ""
        old_abs = os.path.abspath(old_icon_path)
        
        # 跳过即将使用的新文件（同扩展名替换时）
        if abs_skip and old_abs == abs_skip:
            return
        
        # 仅当旧文件在缩略图目录中时才删除（不碰用户原始文件）
        if os.path.dirname(old_abs) == os.path.abspath(thumb_dir) and os.path.isfile(old_icon_path):
            try:
                os.remove(old_icon_path)
            except OSError:
                # 文件被 QMovie 锁定，跳过
                pass

    @classmethod
    def set_tool_icon(cls, tool_name, icon_path):
        """设置工具图标路径（空字符串则清除）。
        
        将用户选择的图标复制到缩略图目录 {tool_name}.{ext}，
        清理所有旧扩展名残留文件，缓存中存储复制后的新路径。
        """
        if not icon_path:
            cls.remove_tool_icon(tool_name)
            return
        
        # 确保缩略图目录存在
        thumb_dir = ShelfToolsSettingsManager.get_thumbnail_directory()
        os.makedirs(thumb_dir, exist_ok=True)
        
        # 构建新路径：保持原始扩展名
        ext = os.path.splitext(icon_path)[1]
        new_icon_path = os.path.join(thumb_dir, f"{tool_name}{ext}")
        
        # 检查源文件和目标文件是否相同（避免复制到自身）
        abs_icon_path = os.path.abspath(icon_path)
        abs_new_path = os.path.abspath(new_icon_path)
        if abs_icon_path == abs_new_path:
            # 文件已在目标位置，只需更新缓存
            cls.update(cls._ICON_KEY.format(tool_name), cls._rel_icon_path(new_icon_path))
            return
        
        # 先清理旧文件（不同扩展名残留），再复制新文件
        cls._cleanup_old_thumbnails(tool_name, thumb_dir, skip_path=new_icon_path)
        
        # 复制文件
        try:
            shutil.copy2(icon_path, new_icon_path)
        except Exception as e:
            logger.warning("Failed to copy icon %s to %s: %s", icon_path, new_icon_path, e)
            return
        
        # 缓存新路径（存储相对路径，便于跨机器/用户共享）
        cls.update(cls._ICON_KEY.format(tool_name), cls._rel_icon_path(new_icon_path))

    @classmethod
    def remove_tool_icon(cls, tool_name):
        """清除工具图标缓存，同时删除磁盘上的缩略图文件。"""
        # 先删除磁盘文件（使用缓存中的路径）
        cls._cleanup_old_thumbnails(tool_name, "")
        
        # 再清除缓存
        data = cls.load()
        key = cls._ICON_KEY.format(tool_name)
        if key in data:
            del data[key]
            cls.save(data)


class BuiltinToolsCacheManager(BaseJsonManager):
    """内置工具配置管理器，读取 builtin_tools/builtin_tools.json。"""
    _file = os.path.join(_MA_TOOLS_DIR, "builtin_tools", "builtin_tools.json")

    @classmethod
    def _get_tools_root(cls):
        """返回项目根目录（MAHX_Tools/）。"""
        return _MA_TOOLS_DIR

    @classmethod
    def _abs_icon_path(cls, path):
        """将相对路径解析为绝对路径。"""
        if not path or os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(cls._get_tools_root(), path))

    @classmethod
    def get_tool_data(cls, unique_id: str) -> dict:
        """获取内置工具的配置数据。"""
        data = cls.load()
        return data.get("tools", {}).get(unique_id, {})

    @classmethod
    def get_tool_icon(cls, unique_id: str):
        """获取内置工具的图标路径。"""
        tool_data = cls.get_tool_data(unique_id)
        icon_path = tool_data.get("icon", "")
        if icon_path:
            return cls._abs_icon_path(icon_path)
        return None

    @classmethod
    def get_tool_tags(cls, unique_id: str) -> list:
        """获取内置工具的标签列表。"""
        tool_data = cls.get_tool_data(unique_id)
        return tool_data.get("tags", [])

    @classmethod
    def get_tool_label(cls, unique_id: str) -> str:
        """获取内置工具的显示名称。"""
        tool_data = cls.get_tool_data(unique_id)
        return tool_data.get("label", "")
