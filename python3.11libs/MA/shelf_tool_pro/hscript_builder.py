"""将 Houdini 节点转换为 hscript 命令生成器。

完全复刻 Houdini 原生 shelf 工具的 hscript 输出格式：
- opadd 创建节点（含 -v 版本标志）
- opparm 设置参数
- opcolor 节点颜色
- opset 设置 flags（含 -p select 标志）
- opexprlanguage 表达式语言
- opuserdata 版本/工具追踪数据
- oporder 节点排序（子网络内部）
- opwire 连接节点
- opspareds 自定义 spare 参数
- chblockbegin/chadd/chkey/chblockend 参数表达式

核心策略：
1. 主方案：hou.Node.asCode().output() → 解析 setParms() 提取修改参数
2. 备方案：遍历所有 parm，检测非默认值

关键修复：
- _var_map 使用 node.path() 作为键，避免不同子网中同名节点冲突
- 参数检测正确处理 ramp/folder/float 等类型
- opcolor 只保存非默认颜色
"""

import ast
import logging
import re
from typing import Optional

import hou

logger = logging.getLogger("MA")


def _escape_hscript(value: str) -> str:
    """转义 hscript 字符串值中的特殊字符。

    hscript 在单引号字符串内不支持 \\' 转义。
    在单引号字符串中包含字面单引号的正确方式是：
      断串 → 字面引号 → 开新串，即 '"'"'（等价于 '\''）。

    Note: 双引号在 hscript 单引号字符串内无需转义。
    """
    return value.replace("'", "'\\''")


# ── asCode 输出解析 ──────────────────────────────────────────────

_SETCOLOR_RE = re.compile(
    r'\.setColor\(hou\.Color\(\((.*?)\)\)\)',
    re.DOTALL,
)


def _extract_setparms(code_str: str) -> dict:
    """从 asCode 输出的 Python 代码中提取 setParms 字典。

    使用逐字符括号计数法定位字典边界。
    对非 Python 字面量值（如 hou.Ramp(...)），
    _parse_setparms_dict 会逐键跳过而非丢弃整个字典。
    """
    match = re.search(r'\.setParms\(\s*(\{)', code_str)
    if not match:
        return {}

    start = match.start(1)
    depth = 0
    i = start
    in_string = False
    string_char = None

    while i < len(code_str):
        c = code_str[i]

        if in_string:
            if c == '\\':
                i += 2
                continue
            if c == string_char:
                in_string = False
        else:
            if c in ('"', "'"):
                in_string = True
                string_char = c
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return _parse_setparms_dict(code_str[start:i + 1])
        i += 1

    return {}


def _parse_setparms_dict(dict_str: str) -> dict:
    """解析 setParms 字典字符串，处理非字面量值。

    优先尝试 ast.literal_eval 解析整个字典（快速路径可处理简单值），
    失败时通过 AST 逐键提取，跳过非字面量值（如 hou.Ramp(...) 构造调用）。
    """
    # 快速路径：整个字典 literal_eval
    try:
        return ast.literal_eval(dict_str)
    except (SyntaxError, ValueError, MemoryError):
        pass

    # 慢速路径：通过 AST 逐键提取
    result = {}
    try:
        tree = ast.parse(dict_str, mode="eval")
        if not isinstance(tree.body, ast.Dict):
            return result

        for key_node, value_node in zip(tree.body.keys, tree.body.values):
            if key_node is None or value_node is None:
                continue
            try:
                key = ast.literal_eval(key_node)
                if not isinstance(key, str):
                    continue
                value = ast.literal_eval(value_node)
                result[key] = value
            except (SyntaxError, ValueError, MemoryError):
                continue  # 跳过非字面量值（hou.Ramp, hou.Color 等）
    except SyntaxError:
        return result

    return result


def _extract_parm_sets(code_str: str) -> dict:
    """从 asCode 输出中提取 .parm("name").set(value) 调用。

    Houdini 某些版本的 asCode 可能使用这种格式代替 setParms。
    处理嵌套括号、字符串和转义。
    """
    result = {}
    pattern = re.compile(r'\.parm\(["\']([^"\']+)["\']\)\.set\(')

    for m in pattern.finditer(code_str):
        name = m.group(1)
        start = m.end()  # 在 '(' 之后
        depth = 1
        i = start
        in_string = False
        string_char = None

        while i < len(code_str) and depth > 0:
            c = code_str[i]
            if in_string:
                if c == '\\':
                    i += 2
                    continue
                if c == string_char:
                    in_string = False
            else:
                if c in ('"', "'"):
                    in_string = True
                    string_char = c
                elif c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
            i += 1

        if depth == 0:
            value_str = code_str[start:i - 1]
            try:
                value = ast.literal_eval(value_str)
                result[name] = value
            except (SyntaxError, ValueError, MemoryError):
                pass  # 跳过非字面量值（如 hou.Ramp(...)）

    return result


def _extract_color_from_ascode(code_str: str) -> Optional[tuple]:
    """从 asCode 输出中提取颜色值。

    asCode 可能将 setColor 调用格式化为多行（含换行和缩进），
    因此先移除所有空白再匹配，防止正则因换行/空格失败。
    """
    # 移除所有空白，处理多行 asCode 格式，如:
    #   n.setColor(
    #       hou.Color((0.999, 0.933, 0.0))
    #   )
    # → setColor(hou.Color((0.999,0.933,0.0)))
    normed = re.sub(r'\s+', '', code_str)
    match = _SETCOLOR_RE.search(normed)
    if not match:
        return None
    rgb_str = match.group(1)
    try:
        parts = [float(x.strip()) for x in rgb_str.split(",")]
        if len(parts) == 3:
            return (parts[0], parts[1], parts[2])
    except (ValueError, TypeError):
        pass
    return None


def _format_opparm_value(name: str, value) -> str:
    """将单个参数格式化为 'name ( value )' 格式，与原生完全一致。"""
    if isinstance(value, str):
        return f"{name} ( '{_escape_hscript(value)}' )"
    elif isinstance(value, bool):
        return f"{name} ( {'on' if value else 'off'} )"
    elif isinstance(value, (int, float)):
        if isinstance(value, float) and value == int(value):
            return f"{name} ( {int(value)} )"
        return f"{name} ( {value} )"
    elif isinstance(value, (tuple, list)):
        vals = " ".join(str(v) for v in value)
        return f"{name} ( {vals} )"
    else:
        return f"{name} ( '{_escape_hscript(str(value))}' )"


_RAMP_STR_RE = re.compile(r"<hou\.Ramp[^>]*num_keys=(\d+)")


def _normalize_ramp_value(value) -> object:
    """将 asCode 输出的 `<hou.Ramp ...>` 字符串转为 hscript 键数格式。

    asCode 的 setParms 字典中 ramp 类型的参数值为 Python repr，
    但 Houdini 原生 hscript 只需要键数。例如:
    '<hou.Ramp is_color=False num_keys=2 data=((t=0, 0), (t=1, 1))>' → '2'
    非 ramp 字符串原样返回。
    """
    if isinstance(value, str):
        m = _RAMP_STR_RE.search(value)
        if m:
            return m.group(1)  # 只返回键数，如 "2"
    return value


class HScriptBuilder:
    """将节点网络转换为 hscript 命令构建器。

    输出格式与 Houdini 原生 shelf 工具完全一致。
    """

    def __init__(self, nodes: list):
        self.nodes = nodes
        self._var_map: dict[str, str] = {}
        self._first_pos = nodes[0].position() if nodes else hou.Vector2(0, 0)
        self._root_parent = nodes[0].parent() if nodes else None

    # ── 公共接口 ──────────────────────────────────────────────

    def build(self) -> str:
        """构建完整的 hscript 命令字符串。

        顺序完全复刻 Houdini 原生 shelf 输出：
        - 每个根节点创建后立即 opset -p on + opcf $arg1（最终化）
        - 若根节点是子网（有内部子节点），创建后立即 opcf $var 进入子网
        - 子网内节点创建完毕后，oporder → 退出 → opset -p on → opcf $arg1
        - 最后统一处理连接命令
        """
        cmds = []
        self._var_map = {}

        # 预生成所有变量名（使用 node.path() 为键，避免同名冲突）
        for node in self.nodes:
            self._generate_var_name(node)

        # 排序节点：先按父路径分组，组内按 childIndex 排序
        # 注意：某些节点类型（如 ObjNode）不支持 childIndex，需要降级处理
        def _sort_key(n):
            parent = n.parent()
            try:
                idx = parent.childIndex(n)
            except (AttributeError, hou.OperationFailed):
                idx = list(parent.children()).index(n)
            return (parent.path(), idx)

        self.nodes = sorted(self.nodes, key=_sort_key)

        # 按父节点分组：根节点 vs 子网内节点
        root_nodes = []
        subnet_children = {}
        subnet_parent_names = set()

        for node in self.nodes:
            var_name = self._var_map[node.path()]
            if self._root_parent is not None and node.parent() != self._root_parent:
                parent_name = node.parent().name()
                subnet_parent_names.add(parent_name)
                subnet_children.setdefault(parent_name, []).append((node, var_name))
            else:
                root_nodes.append((node, var_name))

        cmds.append("opcf $arg1")

        # 内联处理：每个根节点 → 创建 → 最终化（或进入子网）
        for node, var_name in root_nodes:
            self._append_create_header(node, var_name, cmds)

            if node.name() in subnet_parent_names and node.name() in subnet_children:
                # 子网父节点：不 opset，直接进入子网（匹配原生行为）
                cmds.append(f"opcf ${var_name}")

                children = subnet_children[node.name()]
                for child_node, child_var in children:
                    self._append_create_header(child_node, child_var, cmds)

                # [FIX] 子网内节点连线：在子网上下文内生成，确保 $var 解析正确
                for child_node, child_var in children:
                    self._append_wire_commands(child_node, cmds)

                # oporder（退出再进入确保在子网根层级）
                child_names = [cn.name() for cn, _ in children]
                if len(child_names) >= 2:
                    cmds.append("opcf ..")
                    cmds.append(f"opcf ${var_name}")
                    cmds.append(f"oporder -e {' '.join(child_names)}")

                # 退出子网并最终化父节点
                cmds.append("opcf ..")
                cmds.append(f"opset -p on ${var_name}")
                cmds.append("opcf $arg1")
            else:
                # 普通根节点：直接最终化
                cmds.append(f"opset -p on ${var_name}")
                cmds.append("opcf $arg1")

        # [FIX] 根节点之间连线（子网内节点已在上面子网块中处理）
        for node in self.nodes:
            if node.parent() != self._root_parent:
                continue
            self._append_wire_commands(node, cmds)

        return "\n".join(c for c in cmds if c)

    # ── 变量名生成 ────────────────────────────────────────────

    def _generate_var_name(self, node):
        """生成 hscript 变量名。使用 path 中的节点名链保证唯一性。

        例如 /obj/geo1/popnet3/output → _obj_geo1_popnet3_output
        """
        # 从 path 中提取所有节点名
        parts = node.path().strip("/").split("/")
        safe_name = "_" + "_".join(
            p.replace("-", "_").replace(".", "_") for p in parts
        )
        # 存两套映射：path→var 和 parent→var（子网络通过 parent.name 查找）
        self._var_map[node.path()] = safe_name
        self._var_map[node.name()] = safe_name
        return safe_name

    # ── 节点创建序列 ──────────────────────────────────────────

    def _append_create_header(
        self, node: hou.Node, var_name: str, cmds: list
    ) -> None:
        """追加节点创建命令序列。"""
        node_type = node.type().name()
        flags = "-e -n -v"

        # 1. opadd
        cmds.append(
            f'set {var_name} = `run("opadd {flags} {node_type} {node.name()}")`'
        )

        # 2. oplocate
        pos = node.position()
        if self._first_pos is not None:
            dx = float(pos[0]) - float(self._first_pos[0])
            dy = float(pos[1]) - float(self._first_pos[1])
        else:
            dx = float(pos[0])
            dy = float(pos[1])

        dx_str = f"{dx:.10g}" if dx != int(dx) else str(int(dx))
        dy_str = f"{dy:.10g}" if dy != int(dy) else str(int(dy))
        cmds.append(
            f"oplocate -x `$arg2 + {dx_str}` -y `$arg3 + {dy_str}` ${var_name}"
        )

        # 3-9. 后续命令（顺序重要）
        # opcolor 必须在最后，因为 opuserdata 写入 __last_invoked_recipes__
        # 等 recipe 数据后，Houdini 的 recipe preset 系统可能回调重设颜色。
        # 执行顺序：parm → spareparm → expr → flag → exprl → userdata → color
        self._append_parm_commands(node, var_name, cmds)
        self._append_spareparm_commands(node, var_name, cmds)
        self._append_expression_commands(node, var_name, cmds)
        self._append_flag_command(var_name, node, cmds)
        self._append_exprlang_command(node, var_name, cmds)
        self._append_userdata_commands(node, var_name, cmds)
        self._append_color_command(node, var_name, cmds)

    # ── 参数命令 ───────────────────────────────────────────────

    def _append_parm_commands(
        self, node: hou.Node, var_name: str, cmds: list
    ) -> None:
        """生成 opparm 命令。

        策略：
        1. 优先用 asCode().output() 解析 setParms 字典（精确且简洁）
        2. 失败时用 fallback 遍历所有 parm 检测非默认值
        3. 支持 ___Version___ 版本标记
        """
        params = self._get_modified_params_via_ascode(node)
        if not params:
            params = self._get_modified_params_fallback(node)
        if not params:
            return

        # 版本标记
        version = node.userData("___Version___")
        has_version = bool(version and version.strip())

        # 规范化 ramp 值：<hou.Ramp ...> → 键数
        params = {k: _normalize_ramp_value(v) for k, v in params.items()}

        # 分组，每行最多 6 个参数
        items = list(params.items())
        for i in range(0, len(items), 6):
            batch = items[i:i + 6]
            parts = [_format_opparm_value(n, v) for n, v in batch]
            is_last = (i + 6 >= len(items))
            if is_last and has_version:
                cmds.append(f"opparm -V {version} ${var_name}  {' '.join(parts)}")
            else:
                cmds.append(f"opparm ${var_name}  {' '.join(parts)}")

    def _get_modified_params_via_ascode(self, node) -> dict:
        """通过 node.asCode() 提取修改参数。

        策略：
        1. 优先尝试从 setParms({...}) 提取（最精确且简洁）
        2. 若不存在，尝试从 .parm("name").set(value) 提取
        3. 均失败时返回空 dict，触发 fallback
        """
        try:
            code_str = node.asCode()
            if not code_str or not code_str.strip():
                return {}

            params = _extract_setparms(code_str)
            if params:
                return params

            return _extract_parm_sets(code_str)
        except Exception as e:
            logger.debug("asCode failed for %s: %s", node.path(), e)
            return {}

    def _get_modified_params_fallback(self, node) -> dict:
        """备用方案：遍历所有 parm，检测非默认值。

        正确处理 ramp、folder、float 等所有参数类型。
        """
        result = {}
        for parm in node.parms():
            try:
                template = parm.parmTemplate()
                if template is None:
                    continue

                ptype = template.type()

                # 跳过非数据参数
                if ptype in (
                    hou.parmTemplateType.FolderSet,
                    hou.parmTemplateType.Separator,
                    hou.parmTemplateType.Label,
                    hou.parmTemplateType.Folder,
                ):
                    continue

                if parm.isHidden():
                    continue

                # 检测是否被修改
                if not self._is_parm_modified(parm, template, ptype):
                    continue

                # 格式化值
                val = self._parm_get_value(parm, template, ptype)
                result[parm.name()] = val
            except Exception as e:
                # 出错时保守处理：尝试获取值
                logger.debug("Parm fallback error for %s: %s", parm.name(), e)
                try:
                    if not parm.isHidden():
                        result[parm.name()] = parm.eval()
                except Exception:
                    pass

        return result

    def _is_parm_modified(
        self, parm, template, ptype
    ) -> bool:
        """判断参数是否被修改（与默认值不同）。

        Ramp 参数的特殊处理：
        - ramps 的 unexpandedString() 只返回键数（如 "2"）
        - 无法可靠判断键值是否被修改
        - 因此对 ramp 始终返回 True（宁可多保存不可漏保存）
        """
        try:
            if ptype == hou.parmTemplateType.Ramp:
                return True  # ramp 始终保存键数

            default = template.defaultValue()
            current = parm.unexpandedString()
            if len(default) == 1:
                default_str = str(default[0])
            else:
                default_str = " ".join(str(d) for d in default)
            return current.strip() != default_str.strip()
        except Exception:
            return True

    def _parm_get_value(self, parm, template, ptype):
        """获取参数值，格式化为适合 hscript opparm 的类型。

        不同类型使用不同的提取方法：
        - Ramp: 返回键数（字符串）
        - 其他: parm.eval()
        """
        try:
            if ptype == hou.parmTemplateType.Ramp:
                # ramp 参数保存键数
                return parm.unexpandedString()
            return parm.eval()
        except Exception:
            try:
                return parm.unexpandedString()
            except Exception:
                return parm.eval()

    # ── Spare Parm 命令 ──────────────────────────────────────────

    def _spare_has_real_parms(self, templates: list) -> bool:
        """递归检测模板列表中是否有非容器类型的实际参数。

        某些 spare 参数（如 attribwrangle 的 Generated Channel Parameters）
        嵌套在 Folder / FolderSet / groupsimple 内部，需要递归检测。
        """
        for t in templates:
            ttype = t.type()
            if ttype not in (
                hou.parmTemplateType.FolderSet,
                hou.parmTemplateType.Folder,
                hou.parmTemplateType.Label,
                hou.parmTemplateType.Separator,
            ):
                return True
            # 递归检查文件夹内部的子模板
            if ttype in (hou.parmTemplateType.FolderSet, hou.parmTemplateType.Folder):
                try:
                    if hasattr(t, 'parmTemplates'):
                        child_templates = t.parmTemplates()
                        if child_templates and self._spare_has_real_parms(child_templates):
                            return True
                except Exception:
                    pass
        return False

    def _append_spareparm_commands(
        self, node: hou.Node, var_name: str, cmds: list
    ) -> None:
        """如果节点有自定义 spare 参数，生成 opspareds 命令。"""
        try:
            spare_group = node.spareParmTemplateGroup()
            if spare_group is None:
                return

            templates = spare_group.parmTemplates()
            if not templates:
                return

            if not self._spare_has_real_parms(templates):
                return

            xml_def = spare_group.asCode()
            safe_xml = xml_def.replace("'", "'\\''")
            cmds.append(f"opspareds '{safe_xml}' ${var_name}")
        except Exception as e:
            logger.debug(
                "Failed to get spare parms for %s: %s", node.path(), e,
            )

    # ── 表达式命令 ──────────────────────────────────────────────

    def _append_expression_commands(
        self, node: hou.Node, var_name: str, cmds: list
    ) -> None:
        """对有表达式的参数生成 chblockbegin/chadd/chkey/chblockend。"""
        has_any_expr = False
        expr_parts = []

        for parm in node.parms():
            try:
                template = parm.parmTemplate()
                if template is None:
                    continue
                if template.type() in (
                    hou.parmTemplateType.FolderSet,
                    hou.parmTemplateType.Separator,
                    hou.parmTemplateType.Label,
                ):
                    continue
                if parm.isHidden():
                    continue

                expr = parm.expression()
                if expr is None:
                    continue

                has_any_expr = True
                expr_lang = parm.expressionLanguage()
                try:
                    raw_val = parm.unexpandedString()
                except Exception:
                    raw_val = "0"

                expr_parts.append((parm.name(), expr, raw_val, expr_lang))
            except Exception:
                pass

        if not has_any_expr:
            return

        cmds.append("chblockbegin")
        for parm_name, expr, raw_val, expr_lang in expr_parts:
            cmds.append(f"chadd -t `eval(1000.0/$FPS)` `eval(1000.0/$FPS)` ${var_name} {parm_name}")
            lang_flag = "-L python " if expr_lang == hou.exprLanguage.Python else ""
            safe_expr = expr.replace("'", "'\\''")
            cmds.append(
                f"chkey -t `eval(1000.0/$FPS)` -v {raw_val} -m 0 -a 0 -A 0 -T a "
                f"{lang_flag}-F '{safe_expr}' "
                f"${var_name}/{parm_name}"
            )
        cmds.append("chblockend")

    # ── 颜色命令 ────────────────────────────────────────────────

    def _append_color_command(
        self, node: hou.Node, var_name: str, cmds: list
    ) -> None:
        """如果节点颜色被用户修改（非该类型默认色），生成 opcolor 命令。

        使用 node.type().defaultColor() 获取该节点类型的工厂默认色，
        而非硬编码 (0.8, 0.8, 0.8)。不同节点类型有不同的默认色：
        - Sop/Obj: (0.8, 0.8, 0.8)
        - Null: (0.6, 0.7, 0.77)
        - output: (0.6, 0.6, 0.6)
        - popsolver: (0.5, 0.8, 0.5)
        等等。

        颜色检测策略（按优先级）：
        1. 直接读取 node.color() 获取当前实际颜色（最可靠）
        2. 如果 node.color() 不可用，从 asCode 中解析 setColor 调用
        3. 与类型默认色比较，差异超过 0.001 则生成 opcolor 命令
        """
        node_path = node.path()

        # 获取该节点类型的工厂默认色
        try:
            type_default = node.type().defaultColor()
            dr, dg, db = type_default.rgb()
        except Exception:
            dr, dg, db = 0.8, 0.8, 0.8

        # 1. 主路径：直接读取 node.color()（最可靠，不受 asCode 输出格式影响）
        color_rgb = None
        try:
            color = node.color()
            if color is not None:
                color_rgb = color.rgb()
        except Exception as e:
            logger.debug("node.color() failed for %s: %s", node_path, e)

        # 2. 备路径：从 asCode 中解析 setColor（当 node.color() 不可用时）
        if color_rgb is None:
            try:
                code_str = node.asCode()
                color_rgb = _extract_color_from_ascode(code_str)
            except Exception as e:
                logger.debug("asCode color extraction failed for %s: %s", node_path, e)

        # 3. 比较并生成 opcolor 命令
        if color_rgb is not None:
            cr, cg, cb = color_rgb
            if (
                abs(cr - dr) > 0.001
                or abs(cg - dg) > 0.001
                or abs(cb - db) > 0.001
            ):
                cmds.append(
                    f"opcolor -c {cr:.16g} {cg:.16g} {cb:.16g} ${var_name}"
                )
        else:
            # 两个路径都失败了，记录警告
            logger.debug("Could not determine color for %s (no node.color() or asCode setColor)", node_path)

    # ── 标志命令 ────────────────────────────────────────────────

    def _append_flag_command(
        self, var_name: str, node: hou.Node, cmds: list
    ) -> None:
        """生成 opset 命令（不含 -p select 标志）。

        安全处理 VopNode 等没有 display/render/template 标志的节点类型。
        """
        def _safe_flag(method_name):
            """安全读取节点标志，不支持该标志的节点返回 'off'。"""
            try:
                method = getattr(node, method_name)
                return "on" if method() else "off"
            except AttributeError:
                return "off"

        bypass = _safe_flag("isBypassed")
        display = _safe_flag("isDisplayFlagSet")
        hide = _safe_flag("isHidden")
        render = _safe_flag("isRenderFlagSet")
        template = _safe_flag("isTemplateFlagSet")
        lock_hard = _safe_flag("isHardLocked")
        lock_soft = _safe_flag("isSoftLocked")

        # VopNode 需要额外的 opset flags（参考 native test.shelf 的 geometryvopglobal1）
        vop_flags = ""
        if isinstance(node, hou.VopNode):
            vop_flags = "-L off -M off -H on -E off "

        cmds.append(
            f"opset -d {display} -r {render} -h {hide} "
            f"-f off -y off -t {template} -l {lock_hard} "
            f"-s {lock_soft} -u off -F on -c on -e on "
            f"-b {bypass} {vop_flags}${var_name}"
        )

    # ── 表达式语言 ──────────────────────────────────────────────

    def _append_exprlang_command(
        self, node: hou.Node, var_name: str, cmds: list
    ) -> None:
        """生成 opexprlanguage 命令。"""
        expr_lang = "hscript"
        try:
            if hasattr(node, "expressionLanguage"):
                lang = node.expressionLanguage()
                if lang == hou.exprLanguage.Python:
                    expr_lang = "python"
        except Exception:
            pass
        cmds.append(f"opexprlanguage -s {expr_lang} ${var_name}")

    # ── User Data ──────────────────────────────────────────────

    def _append_userdata_commands(
        self, node: hou.Node, var_name: str, cmds: list
    ) -> None:
        """生成 opuserdata 命令。
        
        捕获节点上的所有自定义 userdata，包括：
        - ___Version___ / ___toolcount___ / ___toolid___（工具追踪数据）
        - __last_invoked_recipes__（ramp recipe 预设数据，影响颜色等参数外观）
        - 其他第三方脚本添加的自定义 userdata
        
        使用 node.userDataDict() 获取全部 userdata 键值对。
        """
        try:
            user_data_dict = node.userDataDict()
            if not user_data_dict:
                return
            for key, val in user_data_dict.items():
                if not val:
                    continue
                # 转义单引号，防止 hscript 解析错误
                safe_val = str(val).replace("'", "'\\''")
                cmds.append(
                    f"opuserdata -n '{key}' -v '{safe_val}' ${var_name}"
                )
        except Exception as e:
            logger.debug("Failed to get userdata for %s: %s", node.path(), e)

    # ── 连接命令 ──────────────────────────────────────────────

    def _append_wire_commands(self, node: hou.Node, cmds: list) -> None:
        """生成 opwire 连接命令。"""
        var = self._var_map.get(node.path())
        if var is None:
            return

        for i, input_node in enumerate(node.inputs()):
            if input_node is None:
                continue
            input_var = self._var_map.get(input_node.path())
            if input_var is None:
                continue
            if input_node.parent() != node.parent():
                continue

            cmds.append(f"opwire -n ${input_var} -{i} ${var}")
