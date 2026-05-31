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
from ma_automation.automation_window import AutomationWindow, _window  # noqa: E402


class TestAutoFill(unittest.TestCase):
    """AutomationWindow._on_auto_fill 测试。

    _on_auto_fill 内部 import hou，因此测试通过 sys.modules['hou']
    注入 mock 来模拟 Houdini 环境。
    """

    def setUp(self):
        # 确保 hou mock 就位
        self._had_hou = 'hou' in sys.modules
        self._mock_hou = MagicMock()
        sys.modules['hou'] = self._mock_hou

    def tearDown(self):
        # 清理 hou mock
        if not self._had_hou and 'hou' in sys.modules:
            del sys.modules['hou']

    # ── Test 1: 无选中节点 ───────────────────────────────────

    @patch('builtins.print')
    def test_auto_fill_no_selection(self, mock_print):
        """无选中节点时应打印提示且不添加任务。"""
        self._mock_hou.selectedNodes.return_value = []
        AutomationWindow._on_auto_fill()
        mock_print.assert_called_once_with("Auto Fill: 当前无选择节点")

    # ── Test 2: 选中节点但无 execute 参数 ────────────────────

    @patch('builtins.print')
    def test_auto_fill_no_valid_nodes(self, mock_print):
        """选中节点但都没有 execute 参数时应打印无有效节点。"""
        fake_node = MagicMock()
        fake_node.parm.return_value = None
        fake_node.path.return_value = "/obj/geo1"
        self._mock_hou.selectedNodes.return_value = [fake_node]

        AutomationWindow._on_auto_fill()

        fake_node.parm.assert_called_once_with("execute")
        # 验证打印了无有效节点提示
        mock_print.assert_called_once_with("Auto Fill: 当前无有效节点")

    # ── Test 3: 选中有效节点但窗口不可见 ─────────────────────

    @patch('builtins.print')
    def test_auto_fill_valid_but_window_not_visible(self, mock_print):
        """窗口不可见时不应添加任务（需通过 _window 可见性检查）。"""
        # 确保 _window 为 None（模块初始状态）
        self.assertIsNone(_window)

        parm = MagicMock()
        parm is not None  # parm 非 None → 通过检查

        fake_node = MagicMock()
        fake_node.parm.return_value = parm
        fake_node.path.return_value = "/obj/mantra1"
        self._mock_hou.selectedNodes.return_value = [fake_node]

        AutomationWindow._on_auto_fill()

        # _window 为 None 时不会添加任务
        # 由于 _window 不可见，found 不会增加 → 打印无有效节点
        mock_print.assert_called_once_with("Auto Fill: 当前无有效节点")

    # ── Test 4: 静态方法存在且可调用 ────────────────────────

    def test_auto_fill_is_callable(self):
        """验证 _on_auto_fill 是静态方法且可调用。"""
        self.assertTrue(callable(AutomationWindow._on_auto_fill))


if __name__ == "__main__":
    unittest.main()
