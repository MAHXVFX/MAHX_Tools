"""Shelf 工具加载与执行。"""

import os
import sys
import glob
import re
import html

import hou
import MA

_loaded_shelf_files = set()
_icons_enriched = False    # 防止 _enrich_icons() 被重复调用
_TOOL_NAMES = []      # 唯一标识列表：["shelfA_cam", "shelfB_cam"]
_TOOL_REGISTRY = {}   # 唯一标识 -> (shelf_stem, tool_name, label, icon, shelf_path)


def project_root():
    """返回项目根目录（MAHX_Tools/）。"""
    return os.path.dirname(os.path.dirname(os.path.dirname(MA.__file__)))


def scan_tool_names():
    """解析 toolbar/*.shelf 文件，提取所有 tool name 和 label。
    
    Returns:
        list of str: 唯一标识列表，格式 "{shelf_stem}_{tool_name}"
    """
    names = []
    shelf_dir = os.path.join(project_root(), "toolbar")
    for f in sorted(glob.glob(os.path.join(shelf_dir, "*.shelf"))):
        shelf_stem = os.path.splitext(os.path.basename(f))[0]
        try:
            with open(f, "r", encoding="utf-8") as fp:
                content = fp.read()
            for m in re.finditer(r'<tool\s+name="([^"]+)"', content):
                tool_name = m.group(1)
                # 从同一 tag 中提取 label 和 icon 属性
                tag_end = content.index('>', m.start())
                tag_snippet = content[m.start():tag_end]
                lbl_m = re.search(r'label="([^"]*)"', tag_snippet)
                label = html.unescape(lbl_m.group(1)) if lbl_m else tool_name
                ico_m = re.search(r'icon="([^"]*)"', tag_snippet)
                icon = html.unescape(ico_m.group(1)) if ico_m else ""
                unique_id = f"{shelf_stem}_{tool_name}"
                names.append(unique_id)
                _TOOL_REGISTRY[unique_id] = (shelf_stem, tool_name, label, icon, f)
        except Exception:
            pass
    return names


def ensure_shelves():
    """确保所有 shelf 文件已加载到 Houdini，并用 API 补充图标信息。"""
    shelf_dir = os.path.join(project_root(), "toolbar")
    for f in sorted(glob.glob(os.path.join(shelf_dir, "*.shelf"))):
        if f not in _loaded_shelf_files:
            try:
                hou.shelves.loadFile(f)
            except Exception:
                pass
            _loaded_shelf_files.add(f)
    # 加载完成后，用 Houdini API 补充/覆盖注册表中的 icon
    _enrich_icons()


def _enrich_icons():
    """用 hou.shelves.tool().icon() 覆盖注册表中的 icon 信息（仅执行一次）。"""
    global _icons_enriched
    if _icons_enriched:
        return
    _icons_enriched = True
    for unique_id, (shelf_stem, tool_name, label, _, shelf_path) in list(_TOOL_REGISTRY.items()):
        try:
            tool = hou.shelves.tool(tool_name)
            if tool is not None:
                api_icon = tool.icon()
                if api_icon:
                    _TOOL_REGISTRY[unique_id] = (shelf_stem, tool_name, label, api_icon, shelf_path)
        except Exception:
            pass  # 保留正则解析的原始值


def execute_tool(unique_id, extra_kwargs=None):
    """执行指定 tool 的脚本。

    Args:
        unique_id: 工具唯一标识，格式 "{shelf_stem}_{tool_name}"
        extra_kwargs: 额外的 kwargs 传递给脚本上下文
    """
    ensure_shelves()
    
    # 解析唯一标识，获取实际 tool_name
    if unique_id in _TOOL_REGISTRY:
        _, tool_name, _, _, _ = _TOOL_REGISTRY[unique_id]
    else:
        # 兼容旧格式或回退
        tool_name = unique_id.split("_", 1)[-1] if "_" in unique_id else unique_id
    
    tool = hou.shelves.tool(tool_name)
    if tool is None:
        return
        
    # 查找当前 NetworkEditor，确保节点放置在正确的层级
    ne = None
    for pane in hou.ui.paneTabs():
        if isinstance(pane, hou.NetworkEditor) and pane.isCurrentTab():
            ne = pane
            break
    if ne is None:
        for pane in hou.ui.paneTabs():
            if isinstance(pane, hou.NetworkEditor):
                ne = pane
                break
                
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
        exec(tool.script(), {"kwargs": kwargs, "hou": hou, "sys": sys, "__builtins__": __builtins__})


def drop_at_cursor(unique_id):
    """在 NetworkEditor 光标位置放置工具节点。"""
    ne = None
    for pane in hou.ui.paneTabs():
        if isinstance(pane, hou.NetworkEditor):
            ne = pane
            break
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
    此函数会清除之前的注册信息，重新解析所有 .shelf 文件。
    """
    global _TOOL_NAMES, _TOOL_REGISTRY, _icons_enriched
    _TOOL_NAMES = []
    _TOOL_REGISTRY = {}
    _icons_enriched = False
    _TOOL_NAMES = scan_tool_names()
    # 重新加载 shelf 文件并补充图标
    _loaded_shelf_files.clear()
    ensure_shelves()


# 模块加载时扫描工具名称
_TOOL_NAMES = scan_tool_names()
