"""将 Houdini 节点转换为 hscript 命令生成器。

参考 Houdini 原生 shelf 工具的实现方式：
- opadd 创建节点
- opparm 设置参数
- opset 设置 flags
- opwire 连接节点
- hou.hscript() 执行所有命令
"""

import logging
from typing import Optional

import hou

logger = logging.getLogger("MA")


def _escape_hscript(value: str) -> str:
    """转义 hscript 字符串中的特殊字符。"""
    return value.replace("'", "\\'").replace('"', '\\"')


class HScriptBuilder:
    """将节点网络转换为 hscript 命令构建器。"""

    def __init__(self, nodes: list):
        self.nodes = nodes
        self._var_map = {}  # node.name() -> hscript variable name
        self._cmd_parts = []
        self._first_pos = nodes[0].position() if nodes else None

    def build(self) -> str:
        """构建完整的 hscript 命令字符串。"""
        self._cmd_parts = []

        for i, node in enumerate(self.nodes):
            var_name = self._generate_var_name(node, i)
            self._build_node_commands(node, var_name)

        # 建立连接
        for i, node in enumerate(self.nodes):
            self._build_wire_commands(node)

        return "\n".join(self._cmd_parts)

    def _generate_var_name(self, node, index):
        """为节点生成 hscript 变量名。"""
        # 简化路径作为变量名
        stem = node.parent().name() or "obj"
        safe_name = f"_{stem}_{node.name()}".replace("-", "_").replace(".", "_")
        self._var_map[node.name()] = safe_name
        return safe_name

    def _build_node_commands(self, node, var_name):
        """为单个节点生成创建命令。"""
        node_type = node.type().name()
        is_exact = "::" in node_type

        # 1. opadd 创建节点
        if is_exact:
            flags = "-e -n -v "
            cmd = f'set {var_name} = `run("opadd {flags}{node_type} {node.name()}")`'
        else:
            flags = "-e -n "
            cmd = f'set {var_name} = `run("opadd {flags}{node_type} {node.name()}")`'
        self._cmd_parts.append(cmd)

        # 2. oplocate 设置位置（相对于第一个节点的偏移）
        pos = node.position()
        if self._first_pos is not None:
            dx = float(pos[0]) - float(self._first_pos[0])
            dy = float(pos[1]) - float(self._first_pos[1])
        else:
            dx = float(pos[0])
            dy = float(pos[1])
        loc_cmd = f'oplocate -x `$arg2 + {dx}` -y `$arg3 + {dy}` ${var_name}'
        self._cmd_parts.append(loc_cmd)

        # 3. opparm 设置参数（只保存被修改过的）
        param_cmds = self._build_param_commands(node)
        if param_cmds:
            self._cmd_parts.extend(param_cmds)

        # 4. opset 设置 flags
        flag_cmd = self._build_flag_command(node)
        self._cmd_parts.append(flag_cmd)

        # 5. user data（版本信息）
        version = node.userData("___Version___")
        if version:
            user_data_cmd = f"opuserdata -n '___Version___' -v '{version}' ${var_name}"
            self._cmd_parts.append(user_data_cmd)

        # 6. 表达式语言
        expr_lang = "hscript"  # 默认
        try:
            if hasattr(node, "expressionLanguage"):
                lang = node.expressionLanguage()
                if lang == hou.exprLanguage.Python:
                    expr_lang = "python"
        except:
            pass
        expr_cmd = f'opexprlanguage -s {expr_lang} ${var_name}'
        self._cmd_parts.append(expr_cmd)

    def _build_param_commands(self, node) -> list:
        """生成参数设置命令（只保存被修改过的参数）。"""
        cmds = []

        # 切换到节点所在目录（使用 $arg1 运行时路径）
        cmds.append("opcf $arg1")

        has_params = False

        for parm in node.parms():
            # 安全获取模板
            p_template = parm.parmTemplate()
            if p_template is None:
                continue

            # 跳过文件夹和不可见参数
            if p_template.type() in (
                hou.parmTemplateType.FolderSet,
                hou.parmTemplateType.Separator,
                hou.parmTemplateType.Label,
            ):
                continue
            if parm.isHidden():
                continue

            # 检查参数是否被修改过
            is_modified = self._is_parm_modified(parm)
            if not is_modified:
                continue

            # 处理带 keyframe 的参数
            if len(parm.keyframes()) > 0:
                # 简单处理：直接设置值（不导出 keyframes）
                try:
                    val = parm.eval()
                    if isinstance(val, str):
                        cmds.append(
                            f"opparm ${self._var_map[node.name()]} {parm.name()} ( '{_escape_hscript(str(val))}' )"
                        )
                    else:
                        cmds.append(
                            f"opparm ${self._var_map[node.name()]} {parm.name()} ( {val} )"
                        )
                    has_params = True
                except:
                    pass
            else:
                # 普通参数
                try:
                    val = parm.eval()
                    if isinstance(val, str):
                        cmds.append(
                            f"opparm ${self._var_map[node.name()]} {parm.name()} ( '{_escape_hscript(str(val))}' )"
                        )
                    elif isinstance(val, (int, float)):
                        cmds.append(
                            f"opparm ${self._var_map[node.name()]} {parm.name()} ( {val} )"
                        )
                    elif isinstance(val, tuple):
                        vals = " ".join(str(v) for v in val)
                        cmds.append(
                            f"opparm ${self._var_map[node.name()]} {parm.name()} ( {vals} )"
                        )
                    else:
                        cmds.append(
                            f"opparm ${self._var_map[node.name()]} {parm.name()} ( '{_escape_hscript(str(val))}' )"
                        )
                    has_params = True
                except:
                    pass

        if not has_params:
            # 移除多余的 opcf
            if cmds and cmds[-1].startswith("opcf"):
                cmds.pop()

        return cmds if cmds else []

    def _is_parm_modified(self, parm) -> bool:
        """检查参数是否被修改过（非默认值）。"""
        try:
            template = parm.parmTemplate()
            if template is None:
                return False
            default = template.defaultValue()
            current = parm.unexpandedString()

            if len(default) == 1:
                # 单值参数，尝试字符串比较（保守起见，不比较数值精度）
                return current != default[0]
            else:
                return tuple(current.split()) != tuple(default)
        except:
            return False

    def _build_flag_command(self, node) -> str:
        """生成 opset 标志设置命令。"""
        var = self._var_map[node.name()]
        bypass = "on" if node.isBypassed() else "off"
        display = "on" if node.isDisplayFlagSet() else "off"
        hide = "on" if node.isHidden() else "off"
        render = "on" if node.isRenderFlagSet() else "off"
        template = "on" if node.isTemplateFlagSet() else "off"
        select = "on" if node.isSelected() else "off"
        lock_hard = "on" if node.isHardLocked() else "off"
        lock_soft = "on" if node.isSoftLocked() else "off"
        highlight = "on" if node.isHighlightFlagSet() else "off"

        return (
            f"opset -d {display} -r {render} -h {hide} "
            f"-f off -y off -t {template} -l {lock_hard} "
            f"-s {lock_soft} -u off -F on -c on -e on "
            f"-b {bypass} -H {highlight} ${var}"
        )

    def _build_wire_commands(self, node):
        """生成连接命令。"""
        var = self._var_map[node.name()]

        for i, input_node in enumerate(node.inputs()):
            if input_node is None:
                continue

            # 只连接已保存的节点
            if input_node.name() not in self._var_map:
                continue
            # 排除子网络内部的节点（attribvop 等）
            if input_node.parent() != node.parent():
                continue

            self._cmd_parts.append(
                f"opwire -n ${self._var_map[input_node.name()]} -{i} ${var}"
            )
