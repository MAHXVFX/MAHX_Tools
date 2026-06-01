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
        """选中带 execute 参数的节点时应追加 BUTTON_CLICK 任务。

        MagicMock 环境下 ``_find_trailing_empty_slots`` 默认返回空 list，
        因此走 ``_add_slot`` 分支。
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
        mock_print.assert_called_once_with("Auto Fill: 已处理 1 个按钮点击任务")

    # ── Test 5: 存在连续空槽时直接填充，不新增 ─────────────────

    @patch('builtins.print')
    def test_auto_fill_fills_empty_last_slot(self, mock_print):
        """当 ``_find_trailing_empty_slots`` 返回非空列表时，Auto Fill 应调用
        ``_fill_slot_at`` 填充最近的空槽，而非 ``_add_slot`` 新增。
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
        mock_print.assert_called_once_with("Auto Fill: 已处理 1 个按钮点击任务")

    # ── Test 6: 连续多个空槽时从前往后填入，末尾保留 ───────────

    @patch('builtins.print')
    def test_auto_fill_fills_multiple_consecutive_empty_slots(self, mock_print):
        """当从后往前有 3 个连续空槽（索引 0、1、2），
        选中 3 个节点时，Auto Fill 应从前往后填入 0、1、2（不调用 ``_add_slot``）。

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
        mock_print.assert_called_once_with("Auto Fill: 已处理 3 个按钮点击任务")

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


if __name__ == "__main__":
    unittest.main()
