"""将 Houdini 节点保存为 .shelf 工具。"""

import os
import re
import logging
import tempfile
from datetime import datetime

import hou

logger = logging.getLogger("MA")

# 共享验证正则（save_tool_dialog.py 也引用）
_VALID_TOOL_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _atomic_write(file_path: str, content: str) -> None:
    """原子写入文件，避免 Windows 下 Houdini 占用导致的 Permission denied。"""
    dir_name = os.path.dirname(os.path.normpath(file_path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".shelf")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(tmp_path, file_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

# ── 相对位置偏移（类似原生工具架的 $arg2/arg3 + offset） ──

def _build_rel_pos_block(nodes: list) -> str:
    """计算所有节点的相对位置（相对于第一个节点），生成 _K8s_REL_POS 字典代码。

    类似 Houdini 原生 toolutils 的做法：保存节点时记录相对偏移，
    执行时用 `光标 + 偏移` 定位，消除 postamble 偏移的时序问题。
    """
    if not nodes:
        return "{}"
    first_pos = nodes[0].position()
    lines = []
    for n in nodes:
        p = n.position()
        dx = p[0] - first_pos[0]
        dy = p[1] - first_pos[1]
        lines.append(f'    "{n.name()}": ({dx:.10g}, {dy:.10g})')
    return "{\n" + ",\n".join(lines) + "\n}"


_PREAMBLE_TRACK_RELPOS = """# === MA_ShelfTools_Pro: kwargs-aware positioning ===
_K8s_REQUESTED = {}  # requested_name -> actual node (handles rename scenarios)
_K8s_REL_POS = %s  # name -> (dx, dy) relative position offset (like $arg2/$arg3)
_K8s_PARENT_CATEGORY = "%s"  # parent network type at save time (for context compatibility check)
_kwargs = globals().get("kwargs", {})
_pane = _kwargs.get("pane")

# Override hou_parent to current context instead of asCode's hardcoded path.
if _pane is not None:
    hou_parent = _pane.pwd()
    # Validate context compatibility (similar to Houdini native toolutils pattern)
    if hou_parent.childTypeCategory().name() != _K8s_PARENT_CATEGORY:
        hou.ui.displayMessage(
            "Node creation failed: current network type mismatch\\n\\n"
            "This tool requires placement in a " + _K8s_PARENT_CATEGORY + " network, "
            "but the current network is " + hou_parent.childTypeCategory().name() + ".\\n\\n"
            "Please switch to the corresponding network editor and try again."
        )
        import sys; sys.exit(0)
    # Clear old selection state
    hou_parent.setSelected(False, True)

_autoplace = _kwargs.get("autoplace", True)
_nx = _kwargs.get("nodepositionx")
_ny = _kwargs.get("nodepositiony")
_has_pos = not _autoplace and _nx is not None and _ny is not None
# === end preamble ===

"""

_POSTAMBLE_RELPOS = """
# === MA_ShelfTools_Pro: drag reposition ===
# 用保存时的相对偏移（_K8s_REL_POS）+ 光标位置直接定位。
# 和 Houdini 原生工具架一致：position = cursor + relative_offset
if _has_pos and _K8s_REL_POS:
    _cx = float(_nx)
    _cy = float(_ny)
    for _name, _n in _K8s_REQUESTED.items():
        _rel = _K8s_REL_POS.get(_name)
        if _rel is not None:
            _n.setPosition(hou.Vector2(_cx + _rel[0], _cy + _rel[1]))
# === end reposition ===
"""

# 匹配 asCode 中的 createNode 行，在其后插入节点跟踪
# asCode 输出的 createNode 通常格式为：
#   hou_node = hou_parent.createNode("type", "name", ...)
_TRACK_RE = re.compile(
    r'(hou_node\s*=\s*hou_parent\.createNode\([^)]*\))'
)

# 从 createNode("type", "requested_name", ...) 中提取请求名
_NAME_IN_CREATENODE_RE = re.compile(r'createNode\([^,]+,\s*"([^"]+)"')


def _inject_tracking(code: str) -> str:
    """在 asCode 生成的每个 createNode 行后注入请求名映射。

    注入内容：
        _K8s_REQUESTED["scatter1"] = hou_node  # 请求名 → 实际节点
    """
    def _replacer(m: re.Match) -> str:
        line = m.group(1)
        name_m = _NAME_IN_CREATENODE_RE.search(line)
        if name_m:
            req_name = name_m.group(1)
            return (
                f'{line}\n'
                f'_K8s_REQUESTED["{req_name}"] = hou_node'
            )
        return line
    return _TRACK_RE.sub(_replacer, code)


# ── 连接代码提取（确保全部节点创建后再连接） ──────────────────────

_CONNECTION_HEADER_RE = re.compile(
    r'^# Code to establish connections for ',
    re.MULTILINE,
)


def _split_connections(code: str) -> tuple[str, str]:
    """将 asCode 块拆分为"节点创建"和"连接"两部分。

    连接代码必须在所有节点创建完成后执行，否则上游节点可能尚未创建。
    Returns (node_creation_code, connection_code)。
    """
    match = _CONNECTION_HEADER_RE.search(code)
    if not match:
        return code, ""
    split_pos = match.start()
    return code[:split_pos], code[split_pos:]


# ── 连接代码节点替换：用运行时实际的节点替换名称查找 ────────

_CONNECTION_NODE_LOOKUP_RE = re.compile(
    r'hou_parent\.node\("([^"]+)"\)',
)


def _use_new_nodes(conn_code: str) -> str:
    """将连接代码中的 hou_parent.node("name") 替换为 _K8s_REQUESTED.get("name")。

    第二次执行时 createNode 可能自动重命名（scatter1 → scatter2），
    但连接代码硬编码了原始名称。通过请求名→实际节点的映射，
    确保连接始终使用本次新创建的节点。
    """
    return _CONNECTION_NODE_LOOKUP_RE.sub(
        r'_K8s_REQUESTED.get("\1")',
        conn_code,
    )


def check_name_conflict(tool_name: str, shelf_file_path: str) -> bool:
    """检查 .shelf 文件中是否已存在同名 tool。

    Args:
        tool_name: 要检查的工具名称
        shelf_file_path: .shelf 文件路径

    Returns:
        True 如果同名工具已存在，False 否则
    """
    if not os.path.isfile(shelf_file_path):
        return False  # 文件不存在，一定无冲突

    try:
        with open(shelf_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 查找 <tool name="tool_name"> 模式
        pattern = re.compile(r'<tool\s+name="' + re.escape(tool_name) + r'"')
        return bool(pattern.search(content))
    except Exception:
        return False  # 读取失败时保守处理，假设无冲突


def save_node_to_shelf(
    node_paths: list[str],
    tool_name: str,
    label: str,
    shelf_file_path: str,
) -> bool:
    """Save Houdini nodes as a shelf tool in a .shelf file.

    Steps:
    1. Validate all node paths exist via hou.node()
    2. Generate Python script using hou.Node.asCode() for each node
    3. Assemble complete tool script
    4. Create tool via hou.shelves.newTool()
    5. The .shelf file is auto-written by Houdini API

    Note: Custom icon paths are NOT written to the .shelf file.
          Use ShelfToolsCacheManager for user icon storage.

    Args:
        node_paths: List of Houdini node paths (e.g., ["/obj/geo1/box1"])
        tool_name: Internal tool name (must match ``^[a-zA-Z_][a-zA-Z0-9_]*$``)
        label: Display label for the shelf tool
        shelf_file_path: Path to .shelf file

    Returns:
        bool: True if tool was saved successfully

    Raises:
        ValueError: if node_paths is empty or tool_name is invalid
        RuntimeError: if .shelf file cannot be written
    """
    # ------------------------------------------------------------------
    # 1. Validate inputs
    # ------------------------------------------------------------------
    if not node_paths:
        raise ValueError("node_paths cannot be empty")

    if not tool_name or not _VALID_TOOL_NAME_RE.match(tool_name):
        raise ValueError(f"Invalid tool name: {tool_name}")

    # ------------------------------------------------------------------
    # 2. Validate all node paths exist
    # ------------------------------------------------------------------
    nodes: list[hou.Node] = []
    for path in node_paths:
        node = hou.node(path)
        if node is None:
            raise ValueError(f"Node not found: {path}")
        nodes.append(node)

    # ------------------------------------------------------------------
    # 3. Generate Python script header
    # ------------------------------------------------------------------
    script_parts = [
        f"# Saved from MA_ShelfTools_Pro on "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ]
    script_parts.append(f"# Original node(s): {', '.join(node_paths)}")
    script_parts.append("")

    # ------------------------------------------------------------------
    # 4. Generate code for each node, inject node tracking
    # ------------------------------------------------------------------
    all_connections: list[str] = []
    for node in nodes:
        if hasattr(node, "isHDA") and node.isHDA():
            try:
                lib_path = node.type().definition().libraryFilePath()
                script_parts.append(f"# Requires OTL: {lib_path}")
            except Exception:
                pass

        script_parts.append(f"# Code for {node.path()}")
        try:
            code = node.asCode(
                brief=True,
                recurse=True,
                save_creation_commands=True,
                save_spare_parms=True,
                save_outgoing_wires=True,
            )
            node_code, conn_code = _split_connections(code)
            node_code = _inject_tracking(node_code)
            script_parts.append(node_code)
            if conn_code:
                all_connections.append(conn_code)
        except Exception as e:
            raise RuntimeError(
                f"Failed to generate script for {node.path()}: {e}"
            )

    mapped_connections = [_use_new_nodes(c) for c in all_connections]

    # ------------------------------------------------------------------
    # 5. 获取节点所在网络类型（用于执行时校验上下文兼容性）
    # ------------------------------------------------------------------
    parent_category = nodes[0].parent().childTypeCategory().name()

    # ------------------------------------------------------------------
    # 6. Build relative position dict → assemble script
    # ------------------------------------------------------------------
    rel_pos_dict = _build_rel_pos_block(nodes)
    preamble = _PREAMBLE_TRACK_RELPOS % (rel_pos_dict, parent_category)
    full_script = (
        preamble
        + "\n\n".join(script_parts)
        + "\n\n"
        + "\n\n".join(mapped_connections)
        + _POSTAMBLE_RELPOS
    )

    # ------------------------------------------------------------------
    # 6. Ensure parent directory exists
    # ------------------------------------------------------------------
    try:
        os.makedirs(os.path.dirname(shelf_file_path), exist_ok=True)
    except Exception as e:
        raise RuntimeError(
            f"Failed to create directory for shelf file: {e}"
        )

    # ------------------------------------------------------------------
    # 7. Create shelf tool (API auto-writes to .shelf file)
    # ------------------------------------------------------------------
    try:
        hou.shelves.newTool(
            file_path=shelf_file_path,
            name=tool_name,
            label=tool_name,  # placeholder — Houdini API may garble non-ASCII
            script=full_script,
            language=hou.scriptLanguage.Python,
        )
    except Exception as e:
        raise RuntimeError(f"Failed to create shelf tool: {e}")

    # Houdini API may escape non-ASCII chars in label as XML entities.
    # Overwrite with original Unicode via direct XML edit.
    # Also inject a default icon, <toolMenuContext>, and <toolshelf> wrapper
    # so the native shelf UI can display the tool correctly.
    try:
        with open(shelf_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 构建 toolMenuContext 块（让原生 TAB 菜单能正确显示）
        parent_cat = nodes[0].parent().childTypeCategory().name()
        node_type = nodes[0].type().name()
        context_xml = f'\n    <toolMenuContext name="network">\n      <contextOpType>{parent_cat}/{node_type}</contextOpType>\n    </toolMenuContext>'
        
        # 构建 toolshelf 包装（让原生工具架 UI 能正确分组显示）
        shelf_stem = os.path.splitext(os.path.basename(shelf_file_path))[0]
        toolshelf_xml = f'\n  <toolshelf name="{shelf_stem}" label="{shelf_stem}">\n    <memberTool name="{tool_name}"/>\n  </toolshelf>\n'
        
        tag_re = re.compile(
            r'(<tool\s+name="' + re.escape(tool_name) + r'"[^>]*?)>'
        )
        def _inject_attrs(m):
            tag = m.group(1)
            # 去掉旧 label/icon，写入新值
            tag = re.sub(r'\s+label="[^"]*"', '', tag)
            tag = re.sub(r'\s+icon="[^"]*"', '', tag)
            tag += f' label="{label}"'
            tag += f' icon="hicon:/SVGIcons.index?BUTTONS_mask_track.svg"'
            return f'{tag}>{context_xml}'
        new_content = tag_re.sub(_inject_attrs, content)
        
        # 注入 toolshelf 包装（在 </shelfDocument> 之前）
        if toolshelf_xml not in new_content:
            new_content = new_content.replace(
                '</shelfDocument>',
                f'{toolshelf_xml}</shelfDocument>'
            )
        
        if new_content != content:
            _atomic_write(shelf_file_path, new_content)
    except Exception as exc:
        logger.debug("Label/icon/context/toolshelf fix skipped for '%s': %s", tool_name, exc)

    logger.info(
        "Saved shelf tool '%s' to %s (%d node(s))",
        tool_name,
        shelf_file_path,
        len(nodes),
    )

    return True


def remove_tool_from_shelf(tool_name: str, shelf_file_path: str) -> bool:
    """从 .shelf 文件中删除指定 tool 定义。

    Args:
        tool_name: 工具名称（<tool name="xxx">）
        shelf_file_path: .shelf 文件路径

    Returns:
        True 成功，False 未找到或文件错误。
    """
    if not os.path.isfile(shelf_file_path):
        return False

    try:
        with open(shelf_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 匹配整个 <tool name="xxx" ...>...</tool> 块（非贪婪）
        pattern = re.compile(
            r'<tool\s+name="' + re.escape(tool_name) + r'"'
            r'[^>]*>.*?</tool>',
            re.DOTALL,
        )
        match = pattern.search(content)
        if not match:
            logger.warning("Tool '%s' not found in %s", tool_name, shelf_file_path)
            return False

        # 移除匹配块
        new_content = content[:match.start()] + content[match.end():]
        # 压缩多余空行
        new_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', new_content)

        _atomic_write(shelf_file_path, new_content)

        # 检查是否还有剩余 tool 定义，若无则删除空的 .shelf 文件
        if not re.search(r'<tool\s+name="', new_content):
            try:
                os.remove(shelf_file_path)
                logger.info(
                    "Removed empty shelf file '%s' (last tool deleted)",
                    shelf_file_path,
                )
            except OSError as exc:
                logger.warning(
                    "Failed to remove empty shelf file '%s': %s",
                    shelf_file_path, exc,
                )

        logger.info("Removed tool '%s' from %s", tool_name, shelf_file_path)
        return True
    except Exception as e:
        logger.error("Failed to remove tool '%s' from %s: %s", tool_name, shelf_file_path, e)
        return False


def update_tool_in_shelf(
    shelf_file: str,
    tool_name: str,
    new_label: str | None = None,
) -> bool:
    """更新 .shelf 文件中指定 tool 的 label 属性。

    Note: icon 属性只支持 Houdini 内部图标名，不支持文件路径。
          自定义图标路径请通过 ShelfToolsCacheManager 缓存。

    Args:
        shelf_file: .shelf 文件路径
        tool_name: 工具名称（<tool name="xxx">）
        new_label: 新的 label 值，None 表示不修改

    Returns:
        True 成功，False 未找到或写入失败。
    """
    if not os.path.isfile(shelf_file):
        return False

    try:
        with open(shelf_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 匹配 <tool name="xxx" ...> 开始标签
        pattern = re.compile(
            r'(<tool\s+name="' + re.escape(tool_name) + r'"[^>]*?)>'
        )
        match = pattern.search(content)
        if not match:
            logger.warning("Tool '%s' not found in %s", tool_name, shelf_file)
            return False

        tag = match.group(1)
        # 替换 label 属性
        if new_label is not None:
            if re.search(r'label="[^"]*"', tag):
                tag = re.sub(r'label="[^"]*"', f'label="{new_label}"', tag)
            else:
                tag += f' label="{new_label}"'
        new_content = content[:match.start()] + tag + '>' + content[match.end():]

        _atomic_write(shelf_file, new_content)

        logger.info(
            "Updated tool '%s' in %s (label=%s)",
            tool_name, shelf_file, new_label,
        )
        return True
    except Exception as e:
        logger.error("Failed to update tool '%s' in %s: %s", tool_name, shelf_file, e)
        return False
