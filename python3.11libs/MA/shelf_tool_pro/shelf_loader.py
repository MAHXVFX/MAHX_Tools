"""Shelf 工具加载与执行。

核心设计：直接解析 .shelf XML 文件提取脚本，不调用 hou.shelves.loadFile()。
这样 Houdini 原生工具架不会加载 MA 创建的工具，但 MA 面板可以正常执行。
"""

import os
import sys
import glob
import html
import xml.etree.ElementTree as ET

import hou
import MA

_TOOL_NAMES = []      # 唯一标识列表：["shelfA_cam", "shelfB_cam"]
_TOOL_REGISTRY = {}   # 唯一标识 -> (shelf_stem, tool_name, label, icon, shelf_path)
_TOOL_SCRIPTS = {}    # 唯一标识 -> script content (直接从 XML 解析)


def project_root():
    """返回项目根目录（MAHX_Tools/）。"""
    return os.path.dirname(os.path.dirname(os.path.dirname(MA.__file__)))


def scan_tool_names():
    """解析 MAtoolbar/*.shelf 文件，提取所有 tool name、label 和 script 内容。
    
    Returns:
        list of str: 唯一标识列表，格式 "{shelf_stem}_{tool_name}"
    """
    global _TOOL_SCRIPTS
    names = []
    _TOOL_SCRIPTS = {}
    shelf_dir = os.path.join(project_root(), "MAtoolbar")
    for f in sorted(glob.glob(os.path.join(shelf_dir, "*.shelf"))):
        shelf_stem = os.path.splitext(os.path.basename(f))[0]
        try:
            with open(f, "r", encoding="utf-8") as fp:
                content = fp.read()
            # 解析 XML 提取 script 内容
            root = ET.fromstring(content)
            for tool_elem in root.findall('.//tool'):
                tool_name = tool_elem.get('name', '')
                if not tool_name:
                    continue
                label = html.unescape(tool_elem.get('label', tool_name))
                icon = html.unescape(tool_elem.get('icon', ''))
                
                # 提取 script 内容
                script_elem = tool_elem.find('script')
                script_content = ''
                if script_elem is not None and script_elem.text:
                    script_content = script_elem.text
                
                unique_id = f"{shelf_stem}_{tool_name}"
                names.append(unique_id)
                _TOOL_REGISTRY[unique_id] = (shelf_stem, tool_name, label, icon, f)
                _TOOL_SCRIPTS[unique_id] = script_content
        except Exception:
            pass
    return names


def execute_tool(unique_id, extra_kwargs=None):
    """执行指定 tool 的脚本。

    Args:
        unique_id: 工具唯一标识，格式 "{shelf_stem}_{tool_name}"
        extra_kwargs: 额外的 kwargs 传递给脚本上下文
    """
    # 解析唯一标识，获取实际 tool_name
    if unique_id in _TOOL_REGISTRY:
        _, tool_name, _, _, _ = _TOOL_REGISTRY[unique_id]
    else:
        tool_name = unique_id.split("_", 1)[-1] if "_" in unique_id else unique_id
    
    # 直接从缓存的 XML 解析结果获取脚本，不依赖 hou.shelves.tool()
    script_content = _TOOL_SCRIPTS.get(unique_id)
    if not script_content:
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
        exec(script_content, {"kwargs": kwargs, "hou": hou, "sys": sys, "__builtins__": __builtins__})


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
    global _TOOL_NAMES, _TOOL_REGISTRY, _TOOL_SCRIPTS
    _TOOL_NAMES = []
    _TOOL_REGISTRY = {}
    _TOOL_SCRIPTS = {}
    _TOOL_NAMES = scan_tool_names()


# 模块加载时扫描工具名称
_TOOL_NAMES = scan_tool_names()
