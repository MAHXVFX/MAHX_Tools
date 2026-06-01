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
from unittest.mock import MagicMock, Mock, patch

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
from ma_automation.automation_window import AutomationWindow, _NoWheelComboBox  # noqa: E402


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
        """无选中节点时静默返回,不打印不弹窗。"""
        self._mock_hou.selectedNodes.return_value = []
        AutomationWindow._on_auto_fill(self._mock_self)
        mock_print.assert_not_called()
        self._mock_self._add_slot.assert_not_called()

    # ── Test 2: 选中节点但无 execute 参数 ────────────────────

    @patch('builtins.print')
    def test_auto_fill_no_valid_nodes(self, mock_print):
        """选中节点但都没有 execute 参数时静默返回,不打印。"""
        fake_node = MagicMock()
        fake_node.parm.return_value = None
        fake_node.path.return_value = "/obj/geo1"
        self._mock_hou.selectedNodes.return_value = [fake_node]

        AutomationWindow._on_auto_fill(self._mock_self)

        fake_node.parm.assert_called_once_with("execute")
        # Auto Fill 完全静默,无 print 无日志
        mock_print.assert_not_called()
        self._mock_self._add_slot.assert_not_called()

    # ── Test 3: 选中有效节点，追加 BUTTON_CLICK 任务 ─────────

    @patch('builtins.print')
    def test_auto_fill_adds_slot_for_valid_node(self, mock_print):
        """选中带 execute 参数的节点时应追加 BUTTON_CLICK 任务。

        MagicMock 环境下 ``_find_trailing_empty_slots`` 默认返回空 list，
        因此走 ``_add_slot`` 分支。Auto Fill 静默完成,不打印。
        """
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
        self._mock_self._fill_slot_at.assert_not_called()
        mock_print.assert_not_called()

    # ── Test 5: 存在连续空槽时直接填充，不新增 ─────────────────

    @patch('builtins.print')
    def test_auto_fill_fills_empty_last_slot(self, mock_print):
        """当 ``_find_trailing_empty_slots`` 返回非空列表时，Auto Fill 应调用
        ``_fill_slot_at`` 填充最近的空槽，而非 ``_add_slot`` 新增。静默完成。
        """
        parm = MagicMock()
        fake_node = MagicMock()
        fake_node.parm.return_value = parm
        fake_node.path.return_value = "/obj/geo1"
        self._mock_hou.selectedNodes.return_value = [fake_node]

        with patch.object(
            self._mock_self, '_find_trailing_empty_slots', return_value=[2],
        ):
            AutomationWindow._on_auto_fill(self._mock_self)

        self._mock_self._fill_slot_at.assert_called_once()
        self._mock_self._add_slot.assert_not_called()
        mock_print.assert_not_called()

    # ── Test 6: 连续多个空槽时从前往后填入，末尾保留 ───────────

    @patch('builtins.print')
    def test_auto_fill_fills_multiple_consecutive_empty_slots(self, mock_print):
        """当从后往前有 3 个连续空槽（索引 0、1、2），
        选中 3 个节点时，Auto Fill 应从前往后填入 0、1、2（不调用 ``_add_slot``）。
        静默完成。

        关键：``_find_trailing_empty_slots`` 只调用一次（迭代器消费），
        且返回顺序为 [0, 1, 2]（从小到大），使末尾槽保留供用户手动填。
        """
        parm = MagicMock()
        nodes = []
        for name in ["/obj/geo1", "/obj/geo2", "/obj/geo3"]:
            n = MagicMock()
            n.parm.return_value = parm
            n.path.return_value = name
            nodes.append(n)
        self._mock_hou.selectedNodes.return_value = nodes

        with patch.object(
            self._mock_self,
            '_find_trailing_empty_slots',
            return_value=[0, 1, 2],
        ) as mock_find:
            AutomationWindow._on_auto_fill(self._mock_self)

        # 关键断言 1：只调用一次（避免循环内重复扫描导致 bug）
        mock_find.assert_called_once()
        # 关键断言 2：填充顺序严格为 0, 1, 2（从前往后，末尾保留）
        fill_indices = [
            call.args[0] for call in self._mock_self._fill_slot_at.call_args_list
        ]
        self.assertEqual(fill_indices, [0, 1, 2])
        self._mock_self._add_slot.assert_not_called()
        mock_print.assert_not_called()

    # ── Test 4: 实例方法存在且可调用 ────────────────────────

    def test_auto_fill_is_callable(self):
        """验证 _on_auto_fill 是实例方法且可调用。"""
        self.assertTrue(callable(AutomationWindow._on_auto_fill))


# ── 测试辅助类 ──────────────────────────────────────────────

class _TrackedList(list):
    """``list`` 子类,用 MagicMock 代理 ``pop``/``index``/``insert``。

    场景:production 代码调 ``self._slot_widgets.pop(index)`` 并期望返回值;测试
    需要断言 ``pop`` 被调用的次数和参数。直接用 ``MagicMock`` 丢失 ``len()`` /
    ``[i]`` 等 list 语义;用纯 ``list`` 又无法 assert 方法调用。折中:在 ``list``
    子类里把 ``pop``/``index``/``insert`` 替换为 ``MagicMock(side_effect=...)``,
    既保留 list 协议又允许断言。
    """

    def __init__(self, items):
        super().__init__(items)
        self.pop = MagicMock(side_effect=self._pop_real)
        self.index = MagicMock(side_effect=self._index_real)
        self.insert = MagicMock(side_effect=self._insert_real)

    def _pop_real(self, *args, **kwargs):
        return super().pop(*args, **kwargs)

    def _index_real(self, value):
        # 用 ``is`` 身份比较而非 ``==``:Mock/MagicMock 的 ``__eq__`` 行为不一
        # (``object.__eq__`` 是 is-based,但 MagicMock 重写过),身份比较 100% 可靠
        for i, item in enumerate(self):
            if item is value:
                return i
        raise ValueError(f"{value!r} not in list")

    def _insert_real(self, idx, value):
        return super().insert(idx, value)


class _FakePoint:
    """``QPoint`` 替身,实现生产代码用的方法:``x()`` / ``y()`` / 减法 / ``manhattanLength()``。"""

    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y

    def __sub__(self, other):
        return _FakePoint(self._x - other._x, self._y - other._y)

    def manhattanLength(self):
        return abs(self._x) + abs(self._y)


class TestSlotInteraction(unittest.TestCase):
    """AutomationWindow 槽交互(选中/删除/重排)的单元测试。

    复用 MagicMock-as-self 模式:把要测的方法作为 ``AutomationWindow.X.unbound``
    解绑函数调用,显式传入 mock 替代 self。Slot widget 列表、layout、state 都
    在 mock 上手动挂载,精确控制被测对象的依赖。
    """

    def setUp(self):
        # 准备 slot widgets: 5 个 Mock,模拟 _slot_widgets 列表
        # 注:用 Mock 而非 MagicMock —— MagicMock 自动实现 __eq__(返回 Mock),
        # 会被 list.index(slot) 比较时拿到 Mock 而非 bool,导致 ValueError;
        # Mock 不实现 __eq__,list.index 走 object.__eq__ 身份比较,正常返回索引。
        self._mock_self = MagicMock()
        self._mock_self._slot_widgets = _TrackedList(
            [Mock(name=f"slot{i}") for i in range(5)]
        )
        # 平行 handle 列表(_renumber / _index_at_global_y 用),
        # 真实 _add_slot 会同步 append,这里直接准备好
        self._mock_self._slot_handles = _TrackedList(
            [Mock(name=f"handle{i}") for i in range(5)]
        )
        self._mock_self._slot_layout = MagicMock()
        # state
        self._mock_self._selected_index = None
        self._mock_self._last_selected_index = None  # _update_selection_style 差量用
        self._mock_self._drag_active = False
        self._mock_self._drag_source_index = None
        self._mock_self._drag_press_pos = None
        self._mock_self._drag_threshold = 5
        # 绑定真实方法到 mock self:生产代码里 ``self._select_slot(index)`` 这种
        # 写法会在 MagicMock 上拿到子 Mock(无副作用、不改 state),必须把真方法
        # 绑到 mock self 上,chain 才能跑出可观察的状态变化
        self._bind_method('_select_slot')
        self._bind_method('_remove_slot')
        self._bind_method('_move_slot')
        self._bind_method('_apply_drag_effect')

    def _bind_method(self, name: str) -> None:
        """把 ``AutomationWindow.<name>`` 用 ``MethodType`` 绑到 ``self._mock_self``。

        这样生产代码里 ``self._select_slot(...)`` 才会调真方法,而不是 MagicMock
        自动生成的子 Mock(后者只记录调用,不改 ``_selected_index`` 等 state)。
        """
        method = getattr(AutomationWindow, name)
        setattr(self._mock_self, name, types.MethodType(method, self._mock_self))

    # ── 选中 ───────────────────────────────────────────────

    def test_select_slot_sets_index(self):
        """_select_slot 第一次应设置 _selected_index 并刷新样式。"""
        AutomationWindow._select_slot(self._mock_self, 2)
        self.assertEqual(self._mock_self._selected_index, 2)
        self._mock_self._update_selection_style.assert_called_once()

    def test_select_slot_idempotent(self):
        """重复选中同一索引应 no-op,不重绘。"""
        self._mock_self._selected_index = 2
        AutomationWindow._select_slot(self._mock_self, 2)
        self.assertEqual(self._mock_self._selected_index, 2)
        self._mock_self._update_selection_style.assert_not_called()

    def test_select_slot_out_of_range(self):
        """越界索引应被忽略,state 保持不变。"""
        self._mock_self._selected_index = 1
        AutomationWindow._select_slot(self._mock_self, 99)
        self.assertEqual(self._mock_self._selected_index, 1)
        AutomationWindow._select_slot(self._mock_self, -1)
        self.assertEqual(self._mock_self._selected_index, 1)

    def test_update_selection_style_only_updates_changed(self):
        """_update_selection_style 走差量更新:从 None→3 时,只重绘 slot[3],其他 no-op。"""
        self._mock_self._last_selected_index = None
        self._mock_self._selected_index = 3
        AutomationWindow._update_selection_style(self._mock_self)
        # 只 slot[3] 被 setProperty("selected", True)
        self._mock_self._slot_widgets[3].setProperty.assert_called_once_with("selected", True)
        # 其他槽 setProperty 未被调(差量更新)
        for i, slot in enumerate(self._mock_self._slot_widgets):
            if i == 3:
                continue
            slot.setProperty.assert_not_called()
        # _last_selected_index 已更新
        self.assertEqual(self._mock_self._last_selected_index, 3)

    def test_update_selection_style_transitions_prev_to_curr(self):
        """_update_selection_style 应把 prev 设为 False、curr 设为 True,其他不动。"""
        self._mock_self._last_selected_index = 1
        self._mock_self._selected_index = 4
        AutomationWindow._update_selection_style(self._mock_self)
        self._mock_self._slot_widgets[1].setProperty.assert_called_once_with("selected", False)
        self._mock_self._slot_widgets[4].setProperty.assert_called_once_with("selected", True)
        # 其他槽不动
        for i in (0, 2, 3):
            self._mock_self._slot_widgets[i].setProperty.assert_not_called()
        self.assertEqual(self._mock_self._last_selected_index, 4)

    def test_update_selection_style_same_index_noop(self):
        """_update_selection_style 在 prev == curr 时应完全 no-op(连 setProperty 都不调)。"""
        self._mock_self._last_selected_index = 2
        self._mock_self._selected_index = 2
        AutomationWindow._update_selection_style(self._mock_self)
        for slot in self._mock_self._slot_widgets:
            slot.setProperty.assert_not_called()

    # ── 删除 ───────────────────────────────────────────────

    def test_remove_slot_default_removes_last(self):
        """_remove_slot() 无参应删末尾。"""
        self._mock_self._selected_index = None
        last = self._mock_self._slot_widgets[-1]
        AutomationWindow._remove_slot(self._mock_self)
        self._mock_self._slot_widgets.pop.assert_called_once()
        self._mock_self._slot_layout.removeWidget.assert_called_once_with(last)
        last.deleteLater.assert_called_once()
        self._mock_self._renumber_slots.assert_called_once()
        self._mock_self._update_selection_style.assert_called_once()

    def test_remove_slot_by_index_clears_selected_if_match(self):
        """删除当前选中槽时,_selected_index 应清为 None。"""
        self._mock_self._selected_index = 2
        # 提前捕获要删的 slot(pop 之后该位置会被后续元素顶替)
        target = self._mock_self._slot_widgets[2]
        AutomationWindow._remove_slot(self._mock_self, 2)
        self.assertIsNone(self._mock_self._selected_index)
        # 验证 pop 调用和 deleteLater
        self._mock_self._slot_widgets.pop.assert_called_once_with(2)
        target.deleteLater.assert_called_once()

    def test_remove_slot_by_index_shifts_selected(self):
        """删除索引 < _selected_index 时,选中索引应 -1(槽位置前移)。"""
        self._mock_self._selected_index = 3
        AutomationWindow._remove_slot(self._mock_self, 0)
        self.assertEqual(self._mock_self._selected_index, 2)

    def test_remove_slot_by_index_keeps_selected_when_later(self):
        """删除索引 > _selected_index 时,选中索引保持不变。"""
        self._mock_self._selected_index = 1
        AutomationWindow._remove_slot(self._mock_self, 4)
        self.assertEqual(self._mock_self._selected_index, 1)

    def test_remove_slot_on_empty(self):
        """空列表 _remove_slot 应 no-op,不抛错。"""
        self._mock_self._slot_widgets = _TrackedList([])
        AutomationWindow._remove_slot(self._mock_self)  # 不应抛错
        self._mock_self._slot_layout.removeWidget.assert_not_called()
        self._mock_self._renumber_slots.assert_not_called()

    def test_remove_slot_out_of_range_index(self):
        """越界 index 应被忽略,列表不变。"""
        AutomationWindow._remove_slot(self._mock_self, 99)
        AutomationWindow._remove_slot(self._mock_self, -1)
        self._mock_self._slot_widgets.pop.assert_not_called()
        self._mock_self._slot_layout.removeWidget.assert_not_called()

    # ── 清空(回归:_on_clear 必须清 _slot_handles)────

    def test_on_clear_clears_handles_in_sync(self):
        """**回归测试**:`_on_clear` 必须**同步清空** ``_slot_handles`` 平行列表,
        否则下次 ``_renumber_slots``(在 ``_add_slot`` 里调)会拿一堆已经被
        ``deleteLater()`` 的 handle 调 ``setText``,触发
        ``RuntimeError: Internal C++ object (_SlotHandle) already deleted``。

        历史 bug:点击 Auto Fill 后再点 Clear → 后续任何按钮(增/删/拖/选)
        都炸,因为平行列表 ``_slot_handles`` 还指着已 deleteLater 的对象。
        修复:`_on_clear`` 末尾 ``self._slot_handles.clear()``。

        注:``_add_slot`` 不 patch —— production 调 ``self._add_slot()`` 走
        MagicMock 实例属性查找(不是类方法),直接落到 ``self._mock_self``
        上 auto-generated 的 mock,调用被自动记录,直接 assert 即可。
        """
        # 模拟当前有 2 个槽(平行列表契约下 _slot_widgets 和 _slot_handles 同长)
        old_widgets = [MagicMock(), MagicMock()]
        old_handles = [MagicMock(), MagicMock()]
        self._mock_self._slot_widgets = old_widgets
        self._mock_self._slot_handles = old_handles
        self._mock_self._slot_layout = MagicMock()

        AutomationWindow._on_clear(self._mock_self)

        # 1. 两个列表都被清空(平行列表契约)
        self.assertEqual(
            self._mock_self._slot_widgets, [],
            "_on_clear 后 _slot_widgets 应为空",
        )
        self.assertEqual(
            self._mock_self._slot_handles, [],
            "_on_clear 后 _slot_handles 必须为空(回归点!漏掉会触发 RuntimeError)",
        )
        # 2. deleteLater 在每个旧 slot 上被调
        for slot in old_widgets:
            slot.deleteLater.assert_called_once()
        # 3. 保留 1 个空槽的 _add_slot 被调(走 mock 实例属性查找,
        #    self._mock_self._add_slot 是 auto-generated MagicMock)
        self._mock_self._add_slot.assert_called_once_with()

    # ── 重排 ───────────────────────────────────────────────

    def test_move_slot_downward(self):
        """_move_slot(from, to) 向下移动应调整 _selected_index(在区间内则 -1)。

        注:_move_slot **不调** ``_renumber_slots``(拖动期序号保持过期,
        仅在 ``_on_handle_released`` 统一刷新,见下个测试)。
        """
        self._mock_self._selected_index = 2
        AutomationWindow._move_slot(self._mock_self, 1, 3)
        # _selected_index = 2,在 (1, 3] 区间内,应 -1 → 1
        self.assertEqual(self._mock_self._selected_index, 1)
        self._mock_self._renumber_slots.assert_not_called()
        self._mock_self._update_selection_style.assert_called_once()
        # pop 1 + insert 3(槽参数是任意 slot,用 call_args 检索引)
        self._mock_self._slot_widgets.pop.assert_called_once_with(1)
        self._mock_self._slot_layout.insertWidget.assert_called_once()
        self.assertEqual(
            self._mock_self._slot_layout.insertWidget.call_args.args[0], 3,
        )

    def test_move_slot_upward(self):
        """_move_slot(from, to) 向上移动应调整 _selected_index(在区间内则 +1)。"""
        self._mock_self._selected_index = 1
        AutomationWindow._move_slot(self._mock_self, 3, 0)
        # _selected_index = 1,在 [0, 3) 区间内,应 +1 → 2
        self.assertEqual(self._mock_self._selected_index, 2)

    def test_move_slot_keeps_selected_outside_range(self):
        """当 _selected_index 不在移动区间内,应保持不变。"""
        self._mock_self._selected_index = 4
        AutomationWindow._move_slot(self._mock_self, 0, 2)
        # 4 不在 (0, 2] 区间内,保持 4
        self.assertEqual(self._mock_self._selected_index, 4)

    def test_move_slot_same_index_noop(self):
        """_move_slot(x, x) 应 no-op。"""
        AutomationWindow._move_slot(self._mock_self, 2, 2)
        self._mock_self._slot_widgets.pop.assert_not_called()
        self._mock_self._slot_layout.insertWidget.assert_not_called()
        self._mock_self._renumber_slots.assert_not_called()

    def test_move_slot_out_of_range(self):
        """越界索引应 no-op。"""
        AutomationWindow._move_slot(self._mock_self, -1, 2)
        AutomationWindow._move_slot(self._mock_self, 2, 99)
        self._mock_self._slot_widgets.pop.assert_not_called()

    # ── 拖动状态机 ─────────────────────────────────────────

    def test_on_handle_pressed_selects(self):
        """_on_handle_pressed 应立即选中并准备拖动(未激活),并应用抬起样式。"""
        slot = self._mock_self._slot_widgets[2]
        pos = _FakePoint(10, 100)
        AutomationWindow._on_handle_pressed(self._mock_self, slot, pos)
        self.assertEqual(self._mock_self._selected_index, 2)
        self.assertEqual(self._mock_self._drag_source_index, 2)
        self.assertIs(self._mock_self._drag_press_pos, pos)
        self.assertFalse(self._mock_self._drag_active)
        # 抬起样式:setGraphicsEffect + setProperty("dragging", True)
        slot.setGraphicsEffect.assert_called_once()
        slot.setProperty.assert_any_call("dragging", True)

    def test_on_handle_moved_below_threshold_keeps_click(self):
        """拖动距离 < 阈值时仍算点击,不激活拖动。"""
        slot = self._mock_self._slot_widgets[2]
        self._mock_self._drag_source_index = 2
        self._mock_self._drag_press_pos = _FakePoint(10, 100)
        # press at (10, 100), move to (12, 102) → manhattan 4 < 5
        AutomationWindow._on_handle_moved(
            self._mock_self, slot, _FakePoint(12, 102),
        )
        self.assertFalse(self._mock_self._drag_active)
        # _move_slot 是绑定真方法,通过 pop 未被调用证明未触发换位
        self._mock_self._slot_widgets.pop.assert_not_called()

    def test_on_handle_moved_above_threshold_reorders(self):
        """拖动距离 >= 阈值时激活拖动,按 _index_at_global_y 换位。"""
        slot = self._mock_self._slot_widgets[0]
        self._mock_self._drag_source_index = 0
        self._mock_self._drag_press_pos = _FakePoint(10, 100)
        # patch _index_at_global_y 返回 3
        with patch.object(
            self._mock_self, '_index_at_global_y', return_value=3,
        ):
            AutomationWindow._on_handle_moved(
                self._mock_self, slot, _FakePoint(10, 200),
            )
        self.assertTrue(self._mock_self._drag_active)
        # _move_slot 是绑定真方法 → 观察 pop/insertWidget 副作用
        self._mock_self._slot_widgets.pop.assert_called_once_with(0)
        self._mock_self._slot_layout.insertWidget.assert_called_once()
        self.assertEqual(
            self._mock_self._slot_layout.insertWidget.call_args.args[0], 3,
        )
        # _drag_source_index 应更新到 3(连续 drag 时)
        self.assertEqual(self._mock_self._drag_source_index, 3)

    def test_on_handle_moved_same_target_noop(self):
        """目标索引 == 源索引时 _move_slot 不调用。"""
        slot = self._mock_self._slot_widgets[2]
        self._mock_self._drag_source_index = 2
        self._mock_self._drag_press_pos = _FakePoint(10, 100)
        with patch.object(
            self._mock_self, '_index_at_global_y', return_value=2,
        ), patch.object(
            self._mock_self, '_drag_threshold', 0,  # 强制激活
        ):
            AutomationWindow._on_handle_moved(
                self._mock_self, slot, _FakePoint(10, 200),
            )
        # _move_slot 是绑定真方法 → 观察 pop 未被调用
        self._mock_self._slot_widgets.pop.assert_not_called()

    def test_index_at_global_y_center_anchored(self):
        """_index_at_global_y 中心锚定算法:5 个槽的 handle 中心分别在 50/150/250/350/450。

        关键 case:
        - 拖到槽 i 的中心 → 返回 i
        - 拖到两槽之间的间隙(中心 ± height//2 之外)→ 返回正确相邻槽,不再跌到末尾
        - 拖到列表最下方 → 返回 N-1

        直接 stub ``_slot_handles[i]``(生产代码已不再走 findChild,
        handle 引用在 __init__ 时一次性缓存到 ``_slot_handles`` 平行列表)。
        """
        # 5 个 handle 中心:50, 150, 250, 350, 450
        # mapToGlobal(QPoint(0,0)).y() = 中心 - 16 → 34/134/234/334/434
        # 用 MagicMock 替 QPoint(mock 不可解析 PySide6.QtCore.QPoint,不能 import)
        for i, handle in enumerate(self._mock_self._slot_handles):
            handle.height.return_value = 32
            handle.mapToGlobal.return_value.y.return_value = i * 100 + 34

        # 5 个槽中心:50, 150, 250, 350, 450
        # y < 50(第一个中心)→ 0(最前)
        self.assertEqual(
            AutomationWindow._index_at_global_y(self._mock_self, 30), 0,
        )
        # y = 50(在第一个中心上)→ 走第二个 handle(50<150 True)→ 1
        self.assertEqual(
            AutomationWindow._index_at_global_y(self._mock_self, 50), 1,
        )
        # y = 100(在 handle 0/1 间隙)→ 100<150 True → 1
        # 关键:不再跌到末尾(旧 top<=y<bottom 算法会)
        self.assertEqual(
            AutomationWindow._index_at_global_y(self._mock_self, 100), 1,
        )
        # y = 200(在 handle 1/2 间隙)→ 200<250 True → 2
        self.assertEqual(
            AutomationWindow._index_at_global_y(self._mock_self, 200), 2,
        )
        # y = 460(超过最后 handle 中心 450)→ 走完所有 handle → N-1 = 4
        self.assertEqual(
            AutomationWindow._index_at_global_y(self._mock_self, 460), 4,
        )
        # y = 9999(远超末尾)→ N-1 = 4
        self.assertEqual(
            AutomationWindow._index_at_global_y(self._mock_self, 9999), 4,
        )

    def test_on_handle_released_resets_state(self):
        """_on_handle_released 应清空 drag 状态。"""
        self._mock_self._drag_source_index = 2
        self._mock_self._drag_press_pos = MagicMock()
        self._mock_self._drag_active = True
        AutomationWindow._on_handle_released(
            self._mock_self, MagicMock(), MagicMock(),
        )
        self.assertIsNone(self._mock_self._drag_source_index)
        self.assertIsNone(self._mock_self._drag_press_pos)
        self.assertFalse(self._mock_self._drag_active)

    def test_on_handle_released_triggers_renumber(self):
        """_on_handle_released 应在 drag 结束时统一刷一次序号(配合 _move_slot
        不再自动 renumber,实现"拖动期序号不刷新、松开统一更新"交互)。

        验证 3 件事:序号刷新调一次、抬起样式移除、未提前 renumber。
        """
        # 提前在 mock 上挂 setGraphicsEffect 桩,避免 MagicMock 链式调用爆
        target = self._mock_self._slot_widgets[2]
        self._mock_self._drag_source_index = 2
        self._mock_self._drag_press_pos = MagicMock()
        self._mock_self._drag_active = True
        # _move_slot 不调 _renumber,模拟拖动过程中序号没被刷新
        self._mock_self._renumber_slots.assert_not_called()
        AutomationWindow._on_handle_released(
            self._mock_self, target, MagicMock(),
        )
        # release 时统一刷一次
        self._mock_self._renumber_slots.assert_called_once()
        # 抬起样式移除
        target.setGraphicsEffect.assert_called_once_with(None)
        target.setProperty.assert_any_call("dragging", False)

    # ── 键盘 Delete ────────────────────────────────────────

    def test_keypress_delete_removes_selected(self):
        """Delete 键在有选中时应删除当前选中槽。

        由于 ``_remove_slot`` 在 setUp 里已绑定到真方法,这里通过观察 pop/deleteLater
        等副作用来证明调用发生,而不是直接 assert Mock。
        """
        target = self._mock_self._slot_widgets[2]
        self._mock_self._selected_index = 2
        event = MagicMock()
        event.key.return_value = 1
        with patch(
            'ma_automation.automation_window.Qt', MagicMock(Key_Delete=1),
        ):
            AutomationWindow.keyPressEvent(self._mock_self, event)
        # _remove_slot(2) 调过 → pop(2) 调过,target 被 deleteLater
        self._mock_self._slot_widgets.pop.assert_called_once_with(2)
        target.deleteLater.assert_called_once()
        # 选中索引清空
        self.assertIsNone(self._mock_self._selected_index)

    def test_keypress_non_delete_passes_through(self):
        """非 Delete 键不应触发 _remove_slot(只关心 if 守卫,MagicMock self 无
        法走 super().keyPressEvent,所以用 patch 短路 super)。"""
        self._mock_self._selected_index = 2  # 即便有选中
        event = MagicMock()
        event.key.return_value = 999  # 不等于 Key_Delete
        with patch(
            'ma_automation.automation_window.Qt', MagicMock(Key_Delete=1),
        ), patch('builtins.super', return_value=MagicMock()):
            AutomationWindow.keyPressEvent(self._mock_self, event)
        # _remove_slot 是绑定真方法 → 观察 pop 未被调用
        self._mock_self._slot_widgets.pop.assert_not_called()

    # ── 滚轮屏蔽 ──────────────────────────────────────────

    def test_no_wheel_combo_box_ignores_wheel(self):
        """_NoWheelComboBox 应被定义且 ``wheelEvent`` 调 ``event.ignore()``,
        让滚轮事件穿透到父 ``QScrollArea``,不循环选项。

        实现选择说明:mock 环境下 ``QComboBox`` 是 ``MagicMock()`` 实例,
        任何走属性查找的反射(unbound method / ``__dict__`` / ``vars()`` /
        ``inspect.getsource``)都不可控,见 git 历史讨论。改为直接读源文件
        验证 —— 一次 IO,语义等价(本特性就是 ``event.ignore()`` 一行)。
        """
        from pathlib import Path
        import ma_automation.automation_window as aw

        src = Path(aw.__file__).read_text(encoding='utf-8')

        # 1. _NoWheelComboBox 类被定义
        self.assertIn('class _NoWheelComboBox', src, "_NoWheelComboBox 类应被定义")
        # 2. wheelEvent override
        self.assertIn('def wheelEvent', src, "应 override wheelEvent")
        # 3. event.ignore() 让事件穿透
        self.assertIn('event.ignore()', src, "应调 event.ignore() 让事件穿透到父")
        # 4. 不要调 super().wheelEvent,否则 QComboBox 默认行为会循环选项
        self.assertNotIn(
            'super().wheelEvent', src,
            "不要 super().wheelEvent,默认实现会循环选项",
        )
        # 5. _create_slot_widget 用 _NoWheelComboBox 而非裸 QComboBox
        self.assertIn(
            '_NoWheelComboBox()', src,
            "_create_slot_widget 应实例化 _NoWheelComboBox,屏蔽滚轮",
        )

    # ── 参数路径合并/拆分 ─────────────────────────────────

    def test_split_parm_path(self):
        """``_split_parm_path`` 把 ``/obj/foo/aa/execute`` 拆成 ``(node, parm)``。

        边界:
        - 空 → ``("", "")``
        - 无 ``/`` → ``(text, "")``
        - 末尾 ``/`` → ``(node, "")``
        - 多段 → 取最后一个 ``/`` 切
        - 首尾空白 → strip
        """
        from ma_automation.automation_window import _split_parm_path

        # 正常路径
        self.assertEqual(
            _split_parm_path("/obj/billowy_smoke/aa/execute"),
            ("/obj/billowy_smoke/aa", "execute"),
        )
        # 末尾斜杠 → parm_name 为空
        self.assertEqual(
            _split_parm_path("/obj/foo/aa/"),
            ("/obj/foo/aa", ""),
        )
        # 无斜杠 → 整体当 node_path
        self.assertEqual(
            _split_parm_path("execute"),
            ("execute", ""),
        )
        # 空 / 全空白
        self.assertEqual(_split_parm_path(""), ("", ""))
        self.assertEqual(_split_parm_path("   "), ("", ""))
        # 前后空白
        self.assertEqual(
            _split_parm_path("  /obj/foo/bar  "),
            ("/obj/foo", "bar"),
        )
        # 多个斜杠 → 取最后一个
        self.assertEqual(
            _split_parm_path("/obj/a/b/c/d"),
            ("/obj/a/b/c", "d"),
        )

    def test_combine_parm_path(self):
        """``_combine_parm_path`` 把 ``(node, parm)`` 拼回 UI 显示字符串。

        边界:一边空时直接返回另一边(避免多余 ``/``),都空返回空。
        """
        from ma_automation.automation_window import _combine_parm_path

        # 两边都非空
        self.assertEqual(
            _combine_parm_path("/obj/foo/aa", "execute"),
            "/obj/foo/aa/execute",
        )
        # node 为空 → 返回 parm(避免前导斜杠)
        self.assertEqual(
            _combine_parm_path("", "execute"),
            "execute",
        )
        # parm 为空 → 返回 node
        self.assertEqual(
            _combine_parm_path("/obj/foo", ""),
            "/obj/foo",
        )
        # 都空
        self.assertEqual(_combine_parm_path("", ""), "")

    def test_split_combine_roundtrip(self):
        """split 之后 combine 应回到原值(逆运算自洽)。"""
        from ma_automation.automation_window import (
            _combine_parm_path, _split_parm_path,
        )

        for original in (
            "/obj/billowy_smoke/aa/execute",
            "/obj/foo/aa/bar/dl_Submit",
            "/obj/a",
            "",
        ):
            node, parm = _split_parm_path(original)
            self.assertEqual(
                _combine_parm_path(node, parm), original,
                f"split→combine roundtrip 失败: {original!r}",
            )

    def test_parm_path_widget_in_source(self):
        """``parmPath`` 字段应在 production 源码中,且旧的 ``nodePath``/``parmName``
        都不应再出现(已合并为单字段)。
        """
        from pathlib import Path
        import ma_automation.automation_window as aw

        src = Path(aw.__file__).read_text(encoding='utf-8')

        # 1. 新字段在源码里
        self.assertIn('setObjectName("parmPath")', src, "Page 0 应用 parmPath")
        # 2. 旧的两个字段名不再用
        self.assertNotIn('setObjectName("nodePath")', src, "nodePath 字段应已合并掉")
        self.assertNotIn('setObjectName("parmName")', src, "parmName 字段应已合并掉")
        # 3. placeholder 用参数路径
        self.assertIn("参数路径", src, "placeholder 提示完整参数路径")
        # 4. helper 函数被定义
        self.assertIn("def _split_parm_path", src, "拆分 helper 应被定义")
        self.assertIn("def _combine_parm_path", src, "合并 helper 应被定义")

    # ── Houdini 拖入支持 ─────────────────────────────

    def test_extract_parm_path_from_hou_parm_expression(self):
        """``_extract_parm_path`` 识别 Houdini Python shell 的 hou.parm(...) 格式
        并剥掉 wrapper,只留纯 parm 路径。
        """
        from ma_automation.automation_window import _extract_parm_path

        # 标准场景:Houdini 拖到 Python shell 产生的表达式
        self.assertEqual(
            _extract_parm_path("hou.parm('/obj/billowy_smoke/filecache1/execute')"),
            "/obj/billowy_smoke/filecache1/execute",
        )
        # 双引号也支持
        self.assertEqual(
            _extract_parm_path('hou.parm("/obj/foo/bar")'),
            "/obj/foo/bar",
        )
        # 前后空白容错
        self.assertEqual(
            _extract_parm_path("  hou.parm('/obj/foo/bar')  "),
            "/obj/foo/bar",
        )
        # hou. 与 parm( 之间允许空格
        self.assertEqual(
            _extract_parm_path("hou . parm ( '/obj/foo/bar' )"),
            "/obj/foo/bar",
        )

    def test_extract_parm_path_passthrough_pure_path(self):
        """纯 parm 路径输入原样返回(节点面板拖出可能只有 node_path,让用户补 parm)。
        """
        from ma_automation.automation_window import _extract_parm_path

        # 纯节点路径
        self.assertEqual(
            _extract_parm_path("/obj/foo/bar"),
            "/obj/foo/bar",
        )
        # 纯参数名
        self.assertEqual(
            _extract_parm_path("execute"),
            "execute",
        )

    def test_extract_parm_path_empty(self):
        """空字符串 / 纯空白 → 空串。
        """
        from ma_automation.automation_window import _extract_parm_path

        self.assertEqual(_extract_parm_path(""), "")
        self.assertEqual(_extract_parm_path("   "), "")
        self.assertEqual(_extract_parm_path("\n\t  \n"), "")

    def test_extract_parm_path_malformed_passthrough(self):
        """不匹配 hou.parm(...) 格式的非空输入 → 原样返回(让 UI 显示让用户修正)。
        """
        from ma_automation.automation_window import _extract_parm_path

        # hou.parm 没参数 → 原样
        self.assertEqual(
            _extract_parm_path("hou.parm()"),
            "hou.parm()",
        )
        # 别的 Python 表达式 → 原样
        self.assertEqual(
            _extract_parm_path("hou.node('/obj/foo')"),
            "hou.node('/obj/foo')",
        )

    def test_parm_path_line_edit_in_source(self):
        """``_ParmPathLineEdit`` 子类应在 production 源码中,接受 Houdini 拖入。

        **回归点**:`dragEnterEvent` 不能有 ``hasText() or hasUrls()`` 守卫 —
        Houdini 参数拖动用自定义 MIME(类似 ``application/x-houdini-parm``),
        这两个都是 False,守卫会让鼠标显示禁止图标。改用"全接受"策略
        (dragEnter 一律 acceptProposedAction,文本提取下沉到 dropEvent)。

        mock 环境下 Qt 反射不可控(同 _NoWheelComboBox),改用源码检查。
        """
        from pathlib import Path
        import ma_automation.automation_window as aw

        src = Path(aw.__file__).read_text(encoding='utf-8')

        # 1. 类被定义
        self.assertIn(
            'class _ParmPathLineEdit(QLineEdit)', src,
            "_ParmPathLineEdit 子类应被定义",
        )
        # 2. 启用 drop
        self.assertIn(
            'setAcceptDrops(True)', src,
            "_ParmPathLineEdit 应启用 drop 接收",
        )
        # 3. override 三个 drop 事件
        self.assertIn('def dragEnterEvent', src, "应 override dragEnterEvent")
        self.assertIn('def dragMoveEvent', src, "应 override dragMoveEvent")
        self.assertIn('def dropEvent', src, "应 override dropEvent")
        # 4. dropEvent 用 _extract_parm_path 处理文本
        self.assertIn(
            '_extract_parm_path(text)', src,
            "dropEvent 应调 _extract_parm_path 剥 hou.parm wrapper",
        )
        # 5. _create_slot_widget 用 _ParmPathLineEdit 而非裸 QLineEdit
        self.assertIn(
            'parm_path_le = _ParmPathLineEdit()', src,
            "parmPath 字段应用 _ParmPathLineEdit,接收 Houdini 拖入",
        )
        # 6. 【回归】dragEnter 不能有 hasText/hasUrls 守卫 —— Houdini 拖
        #    出来这两个都为 False,守卫会让鼠标变禁止图标
        #    检查 dragEnterEvent 方法体不含这两个调用
        self._assert_drag_enter_has_no_text_url_guard(src)
        # 7. dragEnter 应直接 acceptProposedAction(无守卫)
        #    找 dragEnterEvent 方法体,验证第一句就是 acceptProposedAction
        self._assert_drag_enter_accepts_unconditionally(src)

    def _assert_drag_enter_has_no_text_url_guard(self, src):
        """辅助:定位 ``dragEnterEvent`` 方法体,断言不含 ``hasText()`` / ``hasUrls()`` 守卫。"""
        lines = src.split('\n')
        in_method = False
        body_lines = []
        for line in lines:
            if 'def dragEnterEvent(' in line:
                in_method = True
                continue
            if in_method:
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue  # 跳空行/注释
                if stripped.startswith('def ') or stripped.startswith('class '):
                    break  # 下一个方法/类
                body_lines.append(line)
        self.assertTrue(
            body_lines, "找不到 dragEnterEvent 方法体(非空非注释行)",
        )
        body = '\n'.join(body_lines)
        self.assertNotIn(
            "hasText()", body,
            "dragEnterEvent 不能有 hasText() 守卫(Houdini 自定义 MIME 会 False)",
        )
        self.assertNotIn(
            "hasUrls()", body,
            "dragEnterEvent 不能有 hasUrls() 守卫(Houdini 自定义 MIME 会 False)",
        )

    def _assert_drag_enter_accepts_unconditionally(self, src):
        """辅助:dragEnterEvent 方法体第一句应是 ``acceptProposedAction()``。"""
        lines = src.split('\n')
        in_method = False
        first_code_line = None
        for line in lines:
            if 'def dragEnterEvent(' in line:
                in_method = True
                continue
            if in_method:
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                first_code_line = stripped
                break
        self.assertIsNotNone(
            first_code_line, "dragEnterEvent 方法体为空",
        )
        self.assertIn(
            "acceptProposedAction()", first_code_line,
            f"dragEnterEvent 第一句应直接 acceptProposedAction(全接受策略),"
            f"实际: {first_code_line!r}",
        )

    def test_extract_drag_text_from_mime(self):
        """``_extract_drag_text`` 从 ``QMimeData`` 抽可读文本,兼容 Houdini 自定义 MIME。

        优先级:text/plain → text/uri-list → 任意格式 raw bytes(Houdini 拖参数
        走自定义 MIME,内容仍是 UTF-8 文本)。
        """
        from ma_automation.automation_window import _extract_drag_text
        from unittest.mock import MagicMock

        # 1. hasText() True → mime.text()
        mime = MagicMock()
        mime.hasText.return_value = True
        mime.text.return_value = "hou.parm('/obj/foo/bar')"
        self.assertEqual(
            _extract_drag_text(mime), "hou.parm('/obj/foo/bar')",
            "text/plain 优先",
        )

        # 2. hasText False, hasUrls True → urls[0].toString()
        mime = MagicMock()
        mime.hasText.return_value = False
        mime.hasUrls.return_value = True
        mime.urls.return_value = [MagicMock(toString=MagicMock(return_value="file:///a/b"))]
        # 上面的 toString 不是方法,需要重新设置
        url = MagicMock()
        url.toString.return_value = "file:///a/b"
        mime.urls.return_value = [url]
        self.assertEqual(
            _extract_drag_text(mime), "file:///a/b",
            "text/uri-list 兜底",
        )

        # 3. hasText False, hasUrls False, 但有 Houdini 自定义 MIME
        #    (模拟 raw bytes 是 UTF-8 文本)
        mime = MagicMock()
        mime.hasText.return_value = False
        mime.hasUrls.return_value = False
        mime.formats.return_value = ["application/x-houdini-parm"]
        mime.data.return_value.data.return_value = b"hou.parm('/obj/foo/execute')"
        # QMimeData.data() 返回 QByteArray,bytes(QByteArray) 解码
        # MagicMock 的 .data() 返回 MagicMock,要让它返回 QByteArray-like
        # 实际 production: bytes(mime.data(fmt)) —— 我们用真正的 bytes
        qbytearray_like = b"hou.parm('/obj/foo/execute')"
        mime.data.return_value = qbytearray_like
        self.assertEqual(
            _extract_drag_text(mime), "hou.parm('/obj/foo/execute')",
            "Houdini 自定义 MIME 走 raw bytes 兜底",
        )

        # 4. 完全空 → 返回空串
        mime = MagicMock()
        mime.hasText.return_value = False
        mime.hasUrls.return_value = False
        mime.formats.return_value = []
        self.assertEqual(_extract_drag_text(mime), "")


if __name__ == "__main__":
    unittest.main()
