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
_STEM_PATH_MAP = {}   # shelf_stem -> prefix（用于外部构造 unique_id）


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
    仅当目录位于项目根目录下时才使用固定标识符，避免用户额外路径恰好同名时冲突。
    """
    norm = os.path.normpath(shelf_dir)
    basename = os.path.basename(norm)
    root = os.path.normpath(project_root())
    if os.path.dirname(norm) == root:
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
    若 stem 未在映射中（极端情况），回退到 "__none__" 占位符。
    """
    path_hash = _STEM_PATH_MAP.get(shelf_stem, "__none__")
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
        norm_dir = os.path.normpath(shelf_dir)
        # 仅当目录在项目根目录下且名称为 builtin_tools 时才视为内置目录
        is_builtin_dir = (
            os.path.basename(norm_dir) == _BUILTIN_SHELF_DIR_NAME
            and os.path.dirname(norm_dir) == os.path.normpath(project_root())
        )
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


# 模块加载时扫描工具名称
_TOOL_NAMES, _TOOL_REGISTRY, _TOOL_SCRIPTS, _BUILTIN_TOOL_IDS = scan_tool_names()/r/n