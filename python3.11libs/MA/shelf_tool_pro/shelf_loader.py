"""Shelf 工具加载与执行。

核心设计：直接解析 .shelf XML 文件提取脚本，不调用 hou.shelves.loadFile()。
这样 Houdini 原生工具架不会加载 MA 创建的工具，但 MA 面板可以正常执行。
"""

import os
import sys
import glob
import html
import hashlib
import logging
import xml.etree.ElementTree as ET

import hou
import MA

_logger = logging.getLogger("MA")


def _fix_encoding(text: str) -> str:
    """修复 Houdini .shelf 文件中的中文乱码。

    某些情况下 .shelf 文件中的中文被错误编码（UTF-8 字节被当作 Latin-1 处理），
    导致中文变成乱码（如 "获取" 变成 "è·åæ"）。

    修复方法：将字符串编码为 Latin-1 字节，再用 UTF-8 解码。
    """
    if not text:
        return text

    try:
        # 尝试修复：Latin-1 编码 → UTF-8 解码
        fixed = text.encode('latin-1').decode('utf-8')
        # 验证修复后是否包含中文字符
        if any('\u4e00' <= c <= '\u9fff' for c in fixed):
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    return text

_TOOL_NAMES = []      # 唯一标识列表：["{prefix}_{shelfStem}_{toolName}", ...]
_TOOL_REGISTRY = {}   # 唯一标识 -> (shelf_stem, tool_name, label, icon, shelf_path)
_TOOL_SCRIPTS = {}    # 唯一标识 -> script content (直接从 XML 解析)
_BUILTIN_TOOL_IDS = set()  # 内置工具 unique_id 集合（来自 builtin_tools/ 目录下的 .shelf）
_STEM_PATH_MAP = {}   # shelf_stem -> prefix（用于迁移和外部构造 unique_id）


# 内置工具目录名（与 shelf_loader.scan_tool_names() 中判断 shelf 是否属于内置的逻辑对应）
_BUILTIN_SHELF_DIR_NAME = "builtin_tools"

# 默认用户工具目录名
_DEFAULT_SHELF_DIR_NAME = "MAtoolbar"


def is_builtin_tool(unique_id: str) -> bool:
    """判断 unique_id 是否对应内置工具。模块级唯一入口，封装判断细节。"""
    return unique_id in _BUILTIN_TOOL_IDS


def project_root():
    """返回项目根目录（MAHX_Tools/）。"""
    return os.path.dirname(os.path.dirname(os.path.dirname(MA.__file__)))


def _path_hash(shelf_dir: str) -> str:
    """生成目录路径的标识符，用于区分不同路径下的同名 shelf 文件。

    内置工具目录（builtin_tools/）和默认用户目录（MAtoolbar/）使用固定标识符，
    确保跨机器可移植（不依赖绝对路径）。
    额外路径使用 MD5 前 6 位 hex 哈希。
    """
    norm = os.path.normpath(shelf_dir)
    basename = os.path.basename(norm)
    if basename == _BUILTIN_SHELF_DIR_NAME:
        return "built"
    if basename == _DEFAULT_SHELF_DIR_NAME:
        return "deflt"
    normalized = norm.replace("\\", "/")
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:6]


def make_unique_id(shelf_stem: str, tool_name: str) -> str:
    """根据 shelf_stem 和 tool_name 构造完整 unique_id（含路径前缀）。

    前缀规则：builtin_tools/ → ``built``，MAtoolbar/ → ``deflt``，
    额外路径 → 6 位 hex 哈希。
    依赖 _STEM_PATH_MAP（由 scan_tool_names() 构建）。
    若 stem 未在映射中（极端情况），回退到 "000000" 前缀。
    """
    path_hash = _STEM_PATH_MAP.get(shelf_stem, "000000")
    return f"{path_hash}_{shelf_stem}_{tool_name}"


def _find_network_editor(prefer_current=True):
    """查找 NetworkEditor。

    Args:
        prefer_current: 是否优先返回当前激活的 tab。

    Returns:
        hou.NetworkEditor or None
    """
    panes = hou.ui.paneTabs()
    if prefer_current:
        for pane in panes:
            if isinstance(pane, hou.NetworkEditor) and pane.isCurrentTab():
                return pane
    for pane in panes:
        if isinstance(pane, hou.NetworkEditor):
            return pane
    return None


def scan_tool_names():
    """解析所有 shelf 目录中的 .shelf 文件，提取工具信息。

    扫描目录（按优先级）：
    1. MAtoolbar/（默认用户工具）
    2. builtin_tools/（内置工具）
    3. 设置面板中用户手动添加的额外路径

    unique_id 格式：``{prefix}_{shelfStem}_{toolName}``
    prefix 规则：builtin_tools/ → ``built``，MAtoolbar/ → ``deflt``，
    额外路径 → 目录路径的 6 位 MD5 前缀 hex（确保不同路径下同名 shelf 不冲突）。

    Returns:
        tuple: (names, registry, scripts, builtin_ids) 四元组
    """
    global _STEM_PATH_MAP

    names = []
    registry = {}
    scripts = {}
    builtin_ids = set()
    stem_path_map = {}  # shelf_stem -> path_hash
    
    # 扫描两个目录：MAtoolbar（用户工具）和 builtin_tools（内置工具）
    shelf_dirs = [
        os.path.join(project_root(), "MAtoolbar"),
        os.path.join(project_root(), "builtin_tools"),
    ]

    # 追加用户手动添加的额外 shelf 路径（来自设置面板）
    try:
        from MA.common.settings import ShelfToolsSettingsManager
        extra_paths = ShelfToolsSettingsManager.get_extra_shelf_paths()
        for ep in extra_paths:
            norm_ep = os.path.normpath(ep)
            # 去重：避免与默认目录重复扫描
            if norm_ep not in [os.path.normpath(d) for d in shelf_dirs]:
                shelf_dirs.append(norm_ep)
    except Exception as e:
        _logger.debug("Failed to load extra shelf paths: %s", e)
    
    for shelf_dir in shelf_dirs:
        if not os.path.isdir(shelf_dir):
            continue
        path_hash = _path_hash(shelf_dir)
        # 整个目录都是内置工具：扫描时一次性标记，目录内所有工具都属 builtin
        is_builtin_dir = _BUILTIN_SHELF_DIR_NAME in shelf_dir
        for f in sorted(glob.glob(os.path.join(shelf_dir, "*.shelf"))):
            shelf_stem = os.path.splitext(os.path.basename(f))[0]
            stem_path_map[shelf_stem] = path_hash
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    content = fp.read()
                root = ET.fromstring(content)
                for tool_elem in root.findall('.//tool'):
                    tool_name = tool_elem.get('name', '')
                    if not tool_name:
                        continue
                    label = html.unescape(tool_elem.get('label', tool_name))
                    icon = html.unescape(tool_elem.get('icon', ''))
                    # 修复可能的中文乱码
                    label = _fix_encoding(label)
                    
                    script_elem = tool_elem.find('script')
                    script_content = ''
                    if script_elem is not None:
                        script_content = ''.join(script_elem.itertext())
                        # 修复可能的中文乱码
                        script_content = _fix_encoding(script_content)
                    
                    unique_id = f"{path_hash}_{shelf_stem}_{tool_name}"
                    if is_builtin_dir:
                        builtin_ids.add(unique_id)
                    names.append(unique_id)
                    registry[unique_id] = (shelf_stem, tool_name, label, icon, f)
                    scripts[unique_id] = script_content
            except ET.ParseError as e:
                _logger.warning("Failed to parse shelf XML: %s — %s", f, e)
            except Exception as e:
                _logger.warning("Failed to scan shelf file: %s — %s", f, e)

    _STEM_PATH_MAP = stem_path_map
    return names, registry, scripts, builtin_ids


def execute_tool(unique_id, extra_kwargs=None):
    """执行指定 tool 的脚本。

    Args:
        unique_id: 工具唯一标识，格式 "{prefix}_{shelfStem}_{toolName}"
        extra_kwargs: 额外的 kwargs 传递给脚本上下文
    """
    # 解析唯一标识，获取实际 tool_name
    if unique_id in _TOOL_REGISTRY:
        _, tool_name, _, _, _ = _TOOL_REGISTRY[unique_id]
    else:
        # fallback: 跳过 prefix 前缀，提取 shelfStem_toolName 再提取 toolName
        parts = unique_id.split("_", 1)
        tool_name = parts[-1].split("_", 1)[-1] if len(parts) > 1 and "_" in parts[-1] else parts[-1]
    
    # 直接从缓存的 XML 解析结果获取脚本，不依赖 hou.shelves.tool()
    script_content = _TOOL_SCRIPTS.get(unique_id)
    if not script_content:
        return
        
    # 查找当前 NetworkEditor，确保节点放置在正确的层级
    ne = _find_network_editor(prefer_current=True)
                
    # 注入 pane 和必要参数，防止脚本走错分支或回退到 /obj
    kwargs = {
        "pane": ne, "autoplace": True,
        "outputnodename": "", "inputindex": -1,
    }
    if extra_kwargs:
        kwargs.update(extra_kwargs)
        
    # 将 kwargs 注入执行上下文（sys 注入以支持检查不兼容上下文时 sys.exit）
    # 用 undo group 包装整个执行，确保 Ctrl+Z 一步撤销所有操作
    with hou.undos.group(f"MA Shelf: {tool_name}"):
        exec(script_content, {"kwargs": kwargs, "hou": hou, "sys": sys, "__builtins__": __builtins__})


def drop_at_cursor(unique_id):
    """在 NetworkEditor 光标位置放置工具节点。"""
    ne = _find_network_editor(prefer_current=False)
    if ne is not None:
        pos = ne.cursorPosition()
        try:
            execute_tool(unique_id, {
                "pane": ne, "autoplace": False,
                "nodepositionx": str(pos[0]), "nodepositiony": str(pos[1]),
                "outputnodename": "", "inputindex": -1,
            })
            return
        except SystemExit:
            return
    try:
        execute_tool(unique_id)
    except SystemExit:
        pass


def refresh_tools():
    """重新扫描所有 .shelf 文件并更新全局工具注册表。

    在创建新工具并写入 .shelf 文件后调用此函数。
    同时清除 MAHX_Tools 项目根目录下所有模块缓存（builtin_tools/MAscripts、
    MA/* 子包等），确保修改后的 .py 代码在下次 import 时重新加载。
    不再需要重启 Houdini 即可看到工具代码变更。

    注意：MA.shelf_tool_pro 及其子模块不会被清除（由本函数主动更新数据），
    其余 MA/* 单例状态（如 ``_panel_window`` / ``_window``）会被重置，
    已打开的面板需重新打开。
    """
    global _TOOL_NAMES, _TOOL_REGISTRY, _TOOL_SCRIPTS, _BUILTIN_TOOL_IDS

    # 清除项目根目录下所有模块缓存，确保修改后的 .py 代码生效
    _clear_module_cache()

    _TOOL_NAMES, _TOOL_REGISTRY, _TOOL_SCRIPTS, _BUILTIN_TOOL_IDS = scan_tool_names()


def _clear_module_cache():
    """清除 sys.modules 中 MAHX_Tools 项目根目录下的所有模块缓存。

    扫描范围：MA/、builtin_tools/、MAtoolbar/ 等所有项目子目录。
    保证刷新按钮能完整热重载项目内任意 .py 文件。

    排除 MA.shelf_tool_pro 及其子模块：
    保留 shelf_loader / panel / thumbnail_widget 等模块的引用链，
    防止 re-import 创建新模块对象导致 execute_tool 等全局引用断裂。
    shelf_tool_pro 的工具数据由 refresh_tools() → scan_tool_names() 主动更新，
    不需要依赖模块重载。
    """
    import sys
    root = os.path.abspath(project_root())
    if not os.path.isdir(root):
        return

    modules_to_remove = [
        key for key, mod in list(sys.modules.items())
        if hasattr(mod, '__file__') and mod.__file__
        and os.path.abspath(mod.__file__).startswith(root)
        # 保留 shelf_tool_pro 包及其所有子模块（panel, shelf_loader, thumbnail_widget 等）
        # 这些模块通过 refresh_tools() 主动更新全局数据，无需模块重载
        and not (key == "MA.shelf_tool_pro" or key.startswith("MA.shelf_tool_pro."))
    ]
    for mod_name in modules_to_remove:
        del sys.modules[mod_name]

    if modules_to_remove:
        _logger.debug("Cleared module cache: %s", modules_to_remove)


def _migrate_unique_ids():
    """迁移 unique_id 到新格式。

    处理两种迁移：
    1. 旧格式 ``{shelfStem}_{toolName}`` → ``{prefix}_{shelfStem}_{toolName}``
    2. 前缀变更（如 hex 哈希 → 稳定标识符 built/deflt）

    迁移范围：Settings JSON（收藏）、Cache JSON（标签/图标/缩略图路径）、
    builtin_tools.json、Notes 文件、缩略图文件。
    仅在需要时执行（旧格式 ID 不再存在时自动跳过）。
    """
    if not _STEM_PATH_MAP:
        return

    from MA.common.constants import (
        SHELFTOOLS_SETTINGS_FILE, SHELFTOOLS_CACHE_FILE, SHELFTOOLS_NOTES_DIR
    )
    import json

    def _convert_any(old_id):
        """将任意格式的 ID 转为当前正确格式。

        处理：无哈希前缀 → 添加前缀，旧前缀（如 hex）→ 更新为当前前缀。
        已是正确格式时返回 None。
        """
        for stem, new_prefix in _STEM_PATH_MAP.items():
            prefix = f"{stem}_"
            if old_id.startswith(prefix):
                new_id = f"{new_prefix}_{old_id}"
                return new_id if new_id != old_id else None

            if old_id.startswith(f"{new_prefix}_{prefix}"):
                return None  # 已是正确格式

            # 检查是否有旧前缀：{old_prefix}_{stem}_{...}
            if f"_{prefix}" in old_id:
                idx = old_id.index(f"_{prefix}")
                candidate_prefix = old_id[:idx]
                is_hex = len(candidate_prefix) == 6 and all(c in "0123456789abcdef" for c in candidate_prefix)
                is_alpha = candidate_prefix.isalpha() and candidate_prefix != new_prefix
                if is_hex or is_alpha:
                    new_id = f"{new_prefix}_{old_id[idx + 1:]}"
                    return new_id if new_id != old_id else None
        return None

    # ── 1. Settings JSON: favorites ──
    try:
        if os.path.exists(SHELFTOOLS_SETTINGS_FILE):
            with open(SHELFTOOLS_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            changed = False
            if "favorite_tools" in settings:
                new_favs = []
                for fid in settings["favorite_tools"]:
                    new_id = _convert_any(fid)
                    if new_id:
                        new_favs.append(new_id)
                        changed = True
                    else:
                        new_favs.append(fid)
                settings["favorite_tools"] = new_favs
            if changed:
                with open(SHELFTOOLS_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=4, ensure_ascii=False)
                _logger.info("Migrated favorites in settings")
    except Exception as e:
        _logger.warning("Failed to migrate settings: %s", e)

    # ── 2. Cache JSON: tags + icons ──
    try:
        if os.path.exists(SHELFTOOLS_CACHE_FILE):
            with open(SHELFTOOLS_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            changed = False
            new_cache = {}
            for key, value in cache.items():
                new_key = key
                for prefix in ("icon_", "tags_"):
                    if key.startswith(prefix):
                        old_id = key[len(prefix):]
                        new_id = _convert_any(old_id)
                        if new_id:
                            new_key = f"{prefix}{new_id}"
                            changed = True
                        break
                new_cache[new_key] = value
            if changed:
                with open(SHELFTOOLS_CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_cache, f, indent=4, ensure_ascii=False)
                _logger.info("Migrated cache keys (tags/icons)")
    except Exception as e:
        _logger.warning("Failed to migrate cache: %s", e)

    # ── 3. Notes 文件重命名 ──
    try:
        if os.path.isdir(SHELFTOOLS_NOTES_DIR):
            for fname in os.listdir(SHELFTOOLS_NOTES_DIR):
                if not fname.endswith(".md"):
                    continue
                old_id = fname[:-3]
                new_id = _convert_any(old_id)
                if new_id:
                    old_path = os.path.join(SHELFTOOLS_NOTES_DIR, fname)
                    new_path = os.path.join(SHELFTOOLS_NOTES_DIR, f"{new_id}.md")
                    if not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                        _logger.info("Renamed note: %s -> %s", fname, f"{new_id}.md")
    except Exception as e:
        _logger.warning("Failed to migrate notes: %s", e)

    # ── 4. builtin_tools.json ──
    try:
        bt_json = os.path.join(project_root(), "builtin_tools", "builtin_tools.json")
        if os.path.exists(bt_json):
            with open(bt_json, 'r', encoding='utf-8') as f:
                bt_data = json.load(f)
            changed = False
            if "tools" in bt_data:
                new_tools = {}
                for old_key, value in bt_data["tools"].items():
                    new_key = _convert_any(old_key)
                    if new_key:
                        new_tools[new_key] = value
                        changed = True
                    else:
                        new_tools[old_key] = value
                bt_data["tools"] = new_tools
            if changed:
                with open(bt_json, 'w', encoding='utf-8') as f:
                    json.dump(bt_data, f, indent=4, ensure_ascii=False)
                _logger.info("Migrated builtin_tools.json keys")
    except Exception as e:
        _logger.warning("Failed to migrate builtin_tools.json: %s", e)

    # ── 5. builtin_tools/notes/ 文件重命名 ──
    try:
        bt_notes = os.path.join(project_root(), "builtin_tools", "notes")
        if os.path.isdir(bt_notes):
            for fname in os.listdir(bt_notes):
                if not fname.endswith(".md"):
                    continue
                old_id = fname[:-3]
                new_id = _convert_any(old_id)
                if new_id:
                    old_path = os.path.join(bt_notes, fname)
                    new_path = os.path.join(bt_notes, f"{new_id}.md")
                    if not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                        _logger.info("Renamed builtin note: %s -> %s", fname, f"{new_id}.md")
    except Exception as e:
        _logger.warning("Failed to migrate builtin notes: %s", e)

    # ── 6. 缩略图文件重命名 + Cache JSON 路径更新 ──
    try:
        if os.path.exists(SHELFTOOLS_CACHE_FILE):
            with open(SHELFTOOLS_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            thumb_changed = False
            new_cache = {}

            for key, value in cache.items():
                if key.startswith("icon_") and isinstance(value, str) and value:
                    old_uid = key[len("icon_"):]
                    new_uid = _convert_any(old_uid)
                    if new_uid:
                        # 获取缩略图目录
                        thumb_dir = os.path.dirname(
                            os.path.join(project_root(), value)
                        ) if not os.path.isabs(value) else os.path.dirname(value)

                        old_filename = os.path.basename(value)
                        _, ext = os.path.splitext(old_filename)
                        new_filename = f"{new_uid}{ext}"
                        new_value = os.path.join(os.path.dirname(value), new_filename)

                        # 重命名磁盘上的文件
                        old_abs = os.path.join(project_root(), value) if not os.path.isabs(value) else value
                        new_abs = os.path.join(project_root(), new_value) if not os.path.isabs(new_value) else new_value

                        if os.path.isfile(old_abs) and not os.path.isfile(new_abs):
                            os.rename(old_abs, new_abs)
                            _logger.info("Renamed thumbnail: %s -> %s", old_filename, new_filename)

                        new_cache[f"icon_{new_uid}"] = new_value
                        thumb_changed = True
                        continue
                new_cache[key] = value

            if thumb_changed:
                with open(SHELFTOOLS_CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_cache, f, indent=4, ensure_ascii=False)
                _logger.info("Migrated thumbnail paths in cache")
    except Exception as e:
        _logger.warning("Failed to migrate thumbnails: %s", e)


# 模块加载时扫描工具名称
_TOOL_NAMES, _TOOL_REGISTRY, _TOOL_SCRIPTS, _BUILTIN_TOOL_IDS = scan_tool_names()

# 首次加载时迁移旧格式 unique_id
_migrate_unique_ids()
