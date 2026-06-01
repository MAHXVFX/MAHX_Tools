"""
Integration tests for AutomationWindow — Auto Fill logic.

由于 automation_window.py 使用 ``from MA.ma_automation.xxx import ...``
（MA 前缀），而 MA/__init__.py 存在级联导入，
测试通过预置 MA mock 模块避免 __init__.py 执行。
"""

import sys
import os
import types
import unittest
from unittest.mock import MagicMock, patch

# ── 前置：mock PySide6 ────────────────────────────────────
import _pyside_mock  # noqa: F401

_test_dir = os.path.dirname(os.path.abspath(__file__))
_ma_automation_dir = os.path.dirname(_test_dir)
_ma_dir = os.path.dirname(_ma_automation_dir)
if _ma_dir not in sys.path:
    sys.path.insert(0, _ma_dir)

# ── mock MA 包，避免 MA/__init__.py 级联导入 ─────────────
if 'MA' not in sys.modules:
    _ma_mod = types.ModuleType('MA')
    _ma_mod.__path__ = []
    _ma_mod.__file__ = os.path.join(_ma_dir, '__init__.py')
    sys.modules['MA'] = _ma_mod

# 先正常导入 ma_automation 子模块（无 MA 前缀）
from ma_automation.data_manager import MA_Automation_DataManager  # noqa: E402
from ma_automation.task_types import (  # noqa: E402
    TaskType,
    ButtonClickParams,
    HomeAssistantParams,
    TaskItem,
)
from ma_automation.execution_engine import ExecutionEngine  # noqa: E402

# 将子模块注册到 MA.ma_automation 命名空间下
_ma_auto_mod = sys.modules.get('ma_automation')
sys.modules['MA.ma_automation'] = _ma_auto_mod
sys.modules['MA.ma_automation.data_manager'] = sys.modules.get('ma_automation.data_manager')
sys.modules['MA.ma_automation.task_types'] = sys.modules.get('ma_automation.task_types')
sys.modules['MA.ma_automation.execution_engine'] = sys.modules.get('ma_automation.execution_engine')

# 现在可以安全地导入 automation_window
from ma_automation.automation_window import AutomationWindow  # noqa: E402


class TestAutoFill(unittest.TestCase):
    """AutomationWindow._on_auto_fill 测试（实例方法）。

    _on_auto_fill 内部 import hou，因此测试通过 sys.modules['hou']
    注入 mock 来模拟 Houdini 环境。
    使用 MagicMock 替代 self，绕开 QDialog __init__ 的 PySide6 依赖。
    """

    def setUp(self):
        # 确保 hou mock 就位
        self._had_hou = 'hou' in sys.modules
        self._mock_hou = MagicMock()
        sys.modules['hou'] = self._mock_hou
        # MagicMock 替代 self，避免触发 QDialog __init__
        self._mock_self = MagicMock()

    def tearDown(self):
        # 清理 hou mock
        if not self._had_hou and 'hou' in sys.modules:
            del sys.modules['hou']

    # ── Test 1: 无选中节点 ───────────────────────────────────

    @patch('builtins.print')
    def test_auto_fill_no_selection(self, mock_print):
        """无选中节点时应打印提示且不添加任务。"""
        self._mock_hou.selectedNodes.return_value = []
        AutomationWindow._on_auto_fill(self._mock_self)
        mock_print.assert_called_once_with("Auto Fill: 当前无选择节点")
        self._mock_self._add_slot.assert_not_called()

    # ── Test 2: 选中节点但无 execute 参数 ────────────────────

    @patch('builtins.print')
    def test_auto_fill_no_valid_nodes(self, mock_print):
        """选中节点但都没有 execute 参数时应打印无有效节点。"""
        fake_node = MagicMock()
        fake_node.parm.return_value = None
        fake_node.path.return_value = "/obj/geo1"
        self._mock_hou.selectedNodes.return_value = [fake_node]

        AutomationWindow._on_auto_fill(self._mock_self)

        fake_node.parm.assert_called_once_with("execute")
        # 验证打印了无有效节点提示
        mock_print.assert_called_once_with("Auto Fill: 当前无有效节点")
        self._mock_self._add_slot.assert_not_called()

    # ── Test 3: 选中有效节点，追加 BUTTON_CLICK 任务 ─────────

    @patch('builtins.print')
    def test_auto_fill_adds_slot_for_valid_node(self, mock_print):
        """选中带 execute 参数的节点时应追加 BUTTON_CLICK 任务。"""
        parm = MagicMock()
        fake_node = MagicMock()
        fake_node.parm.return_value = parm
        fake_node.path.return_value = "/obj/mantra1"
        self._mock_hou.selectedNodes.return_value = [fake_node]

        AutomationWindow._on_auto_fill(self._mock_self)

        expected = {
            "type": "BUTTON_CLICK",
            "params": {
                "node_path": "/obj/mantra1",
                "parm_name": "execute",
            },
            "enabled": True,
        }
        self._mock_self._add_slot.assert_called_once_with(expected)
        mock_print.assert_called_once_with("Auto Fill: 已添加 1 个按钮点击任务")

    # ── Test 4: 实例方法存在且可调用 ────────────────────────

    def test_auto_fill_is_callable(self):
        """验证 _on_auto_fill 是实例方法且可调用。"""
        self.assertTrue(callable(AutomationWindow._on_auto_fill))


if __name__ == "__main__":
    unittest.main()
