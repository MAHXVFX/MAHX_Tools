"""
Unit tests for ExecutionEngine (execution_engine.py).

TDD: tests written before implementation (Wave 2 — stub executors).

注意：PySide6 仅在 Houdini 环境中可用，因此通过共享的
_pyside_mock 模块在导入 ma_automation 前 mock PySide6。
"""

import sys
import os

# 在导入 ma_automation 前 mock PySide6
import _pyside_mock  # noqa: F401

# ═════════════════════════════════════════════════════════════════════
# 现在安全地导入测试目标
# ═════════════════════════════════════════════════════════════════════

import builtins
import unittest
from unittest.mock import MagicMock, patch

_test_dir = os.path.dirname(os.path.abspath(__file__))
_ma_automation_dir = os.path.dirname(_test_dir)
_ma_dir = os.path.dirname(_ma_automation_dir)
if _ma_dir not in sys.path:
    sys.path.insert(0, _ma_dir)

from ma_automation.task_types import (
    TaskType,
    ButtonClickParams,
    FlipbookParams,
    HomeAssistantParams,
    TaskItem,
)
from ma_automation.execution_engine import ExecutionEngine


class TestExecutionEngine(unittest.TestCase):
    """ExecutionEngine 核心逻辑测试。

    通过直接调用 ``run()`` 方法（而非 ``start()``）同步执行，
    避免多线程复杂性。执行器方法通过实例属性覆盖的方式 Mock。
    """

    def setUp(self):
        """每个测试前创建通用任务列表。"""
        self.button_task = TaskItem(
            task_type=TaskType.BUTTON_CLICK,
            params=ButtonClickParams(node_path="/obj/geo1", parm_name="execute"),
            enabled=True,
        )
        self.flipbook_task = TaskItem(
            task_type=TaskType.FLIPBOOK,
            params=FlipbookParams(
                frame_range=(1, 50),
                output_path="$HIP/render.$F4.png",
                output_enabled=True,
            ),
            enabled=True,
        )
        self.ha_task = TaskItem(
            task_type=TaskType.HOME_ASSISTANT,
            params=HomeAssistantParams(webhook_url="http://ha/webhook/test"),
            enabled=True,
        )

    # ── Test 1: Dispatch ────────────────────────────────────────

    def test_dispatch(self):
        """Test 1: 2 个启用任务，验证每个执行器被精确调用一次。"""
        tasks = [self.button_task, self.flipbook_task]
        engine = ExecutionEngine(tasks)
        engine._execute_button_click = MagicMock()
        engine._execute_flipbook = MagicMock()
        engine.msleep = MagicMock()

        engine.run()

        engine._execute_button_click.assert_called_once_with(
            self.button_task.params,
        )
        engine._execute_flipbook.assert_called_once_with(
            self.flipbook_task.params,
        )

    # ── Test 2: Skip disabled ──────────────────────────────────

    def test_skip_disabled(self):
        """Test 2: 1 个禁用 + 1 个启用，验证只有启用的被执行。"""
        disabled_button = TaskItem(
            task_type=TaskType.BUTTON_CLICK,
            params=ButtonClickParams(node_path="/obj/n1", parm_name="exec"),
            enabled=False,
        )
        tasks = [disabled_button, self.flipbook_task]
        engine = ExecutionEngine(tasks)
        engine._execute_button_click = MagicMock()
        engine._execute_flipbook = MagicMock()
        engine.msleep = MagicMock()

        engine.run()

        engine._execute_button_click.assert_not_called()
        engine._execute_flipbook.assert_called_once()

    # ── Test 3: Cancel ─────────────────────────────────────────

    def test_cancel(self):
        """Test 3: 在 run() 前设置 _cancelled=True，验证没有执行发生。"""
        tasks = [self.button_task, self.flipbook_task]
        engine = ExecutionEngine(tasks)
        engine._execute_button_click = MagicMock()
        engine._execute_flipbook = MagicMock()
        engine.msleep = MagicMock()
        engine._cancelled = True

        engine.run()

        engine._execute_button_click.assert_not_called()
        engine._execute_flipbook.assert_not_called()

    # ── Test 4: Error resilience ───────────────────────────────

    def test_error_resilience(self):
        """Test 4: 第一个执行器抛出异常，第二个仍正常执行。

        验证 ``task_completed`` 信号分别发出失败和成功。
        """
        tasks = [self.button_task, self.flipbook_task]
        engine = ExecutionEngine(tasks)
        engine._execute_button_click = MagicMock(
            side_effect=ValueError("button failed"),
        )
        engine._execute_flipbook = MagicMock()
        engine.msleep = MagicMock()

        completed_records = []
        engine.task_completed.connect(
            lambda idx, ok, msg: completed_records.append((idx, ok, msg)),
        )

        engine.run()

        # 两个任务都应触发 task_completed
        self.assertEqual(len(completed_records), 2)

        # 第一个任务失败
        idx0, ok0, msg0 = completed_records[0]
        self.assertEqual(idx0, 0)
        self.assertFalse(ok0)
        self.assertIn("button failed", msg0)

        # 第二个任务成功
        idx1, ok1, msg1 = completed_records[1]
        self.assertEqual(idx1, 1)
        self.assertTrue(ok1)

        # 第二个执行器应被调用
        engine._execute_flipbook.assert_called_once()

    # ── Test 5: all_completed signal ───────────────────────────

    def test_all_completed_signal(self):
        """Test 5: 验证 ``all_completed`` 信号发出正确的成功/失败计数。"""
        tasks = [
            self.button_task,
            self.flipbook_task,
            self.ha_task,
        ]
        engine = ExecutionEngine(tasks)
        engine._execute_button_click = MagicMock()
        engine._execute_flipbook = MagicMock(
            side_effect=RuntimeError("flipbook error"),
        )
        engine._execute_home_assistant = MagicMock()
        engine.msleep = MagicMock()

        summary = []
        engine.all_completed.connect(
            lambda s, f: summary.append((s, f)),
        )

        engine.run()

        self.assertEqual(len(summary), 1)
        success_count, fail_count = summary[0]
        self.assertEqual(success_count, 2)  # button + HA
        self.assertEqual(fail_count, 1)  # flipbook

    # ── Test 6: Signal emission ────────────────────────────────

    def test_signal_emission(self):
        """Test 6: 验证每个启用任务都触发了 task_started 和 task_completed。"""
        tasks = [self.button_task, self.flipbook_task]
        engine = ExecutionEngine(tasks)
        engine._execute_button_click = MagicMock()
        engine._execute_flipbook = MagicMock()
        engine.msleep = MagicMock()

        started = []
        completed = []
        engine.task_started.connect(
            lambda idx, typ: started.append((idx, typ)),
        )
        engine.task_completed.connect(
            lambda idx, ok, msg: completed.append((idx, ok, msg)),
        )

        engine.run()

        # 2 个启用任务 → 2 组信号
        self.assertEqual(len(started), 2)
        self.assertEqual(len(completed), 2)

        # 索引顺序正确
        self.assertEqual(started[0][0], 0)
        self.assertEqual(started[0][1], TaskType.BUTTON_CLICK.value)
        self.assertEqual(completed[0][0], 0)
        self.assertTrue(completed[0][1])

        self.assertEqual(started[1][0], 1)
        self.assertEqual(started[1][1], TaskType.FLIPBOOK.value)
        self.assertEqual(completed[1][0], 1)
        self.assertTrue(completed[1][1])

    # ── Test 7: msleep ─────────────────────────────────────────

    def test_msleep(self):
        """Test 7: 验证 ``msleep(100)`` 在每个任务后被调用。"""
        tasks = [self.button_task, self.flipbook_task, self.ha_task]
        engine = ExecutionEngine(tasks)
        engine._execute_button_click = MagicMock()
        engine._execute_flipbook = MagicMock()
        engine._execute_home_assistant = MagicMock()
        engine.msleep = MagicMock()

        engine.run()

        # 3 个启用任务 → 3 次 msleep 调用
        self.assertEqual(engine.msleep.call_count, 3)
        # 每次调用参数都是 100
        for call_args in engine.msleep.call_args_list:
            self.assertEqual(call_args, ((100,), {}))


class TestExecutionEngineEdgeCases(unittest.TestCase):
    """ExecutionEngine 边界情况测试。"""

    def _make_button_task(self, enabled=True):
        return TaskItem(
            task_type=TaskType.BUTTON_CLICK,
            params=ButtonClickParams(node_path="/obj/n", parm_name="exec"),
            enabled=enabled,
        )

    def test_empty_task_list(self):
        """空任务列表应触发 all_completed(0, 0)。"""
        engine = ExecutionEngine([])
        engine.msleep = MagicMock()

        summary = []
        engine.all_completed.connect(lambda s, f: summary.append((s, f)))

        engine.run()

        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0], (0, 0))
        engine.msleep.assert_not_called()

    def test_all_disabled(self):
        """所有任务禁用时跳过全部，all_completed(0, 0)。"""
        engine = ExecutionEngine([self._make_button_task(enabled=False)])
        engine._execute_button_click = MagicMock()
        engine.msleep = MagicMock()

        summary = []
        engine.all_completed.connect(lambda s, f: summary.append((s, f)))

        engine.run()

        self.assertEqual(summary[0], (0, 0))
        engine._execute_button_click.assert_not_called()
        engine.msleep.assert_not_called()

    def test_cancel_mid_execution(self):
        """中途取消：第一个任务设置 _cancelled=True，后续任务不再执行。"""
        tasks = [
            self._make_button_task(enabled=True),
            self._make_button_task(enabled=True),
        ]
        engine = ExecutionEngine(tasks)
        engine._execute_button_click = MagicMock(
            side_effect=lambda params: setattr(engine, "_cancelled", True),
        )
        engine.msleep = MagicMock()

        engine.run()

        # 第一个任务执行（并将 cancelled 设为 True）
        # 循环在下一个迭代入口检查 _cancelled 后 break
        self.assertEqual(engine._execute_button_click.call_count, 1)

    def test_home_assistant_dispatch(self):
        """验证 HOME_ASSISTANT 正确派发给 _execute_home_assistant。"""
        tasks = [
            self._make_button_task(enabled=False),
            TaskItem(
                task_type=TaskType.HOME_ASSISTANT,
                params=HomeAssistantParams(webhook_url="http://ha/webhook/test"),
                enabled=True,
            ),
        ]
        engine = ExecutionEngine(tasks)
        engine._execute_button_click = MagicMock()
        engine._execute_home_assistant = MagicMock()
        engine.msleep = MagicMock()

        engine.run()

        engine._execute_button_click.assert_not_called()
        engine._execute_home_assistant.assert_called_once()


class TestExecutionEngineExecutors(unittest.TestCase):
    """ExecutionEngine 执行器实际逻辑测试。

    测试 ``_execute_button_click``、``_execute_flipbook``、
    ``_execute_home_assistant`` 的真实实现（非 Mock 方法）。
    Houdini API (hou) 和 requests 在模块级别进行 Mock。
    """

    # ── 按钮点击执行器 ─────────────────────────────────────

    _BUTTON_SENTINEL = "ButtonType"  # 与 hou.parmTemplateType.Button 对应的哨兵值

    def _make_mock_hou_for_button(self, parm_type=None):
        """创建 button click 测试所需的 mock hou 模块。

        Args:
            parm_type: 模拟参数模板类型，默认使用与 Button 哨兵相同的值
                       以实现成功路径；传入不同值以测试非按钮类型检测。
        """
        mock_hou = MagicMock()
        mock_hou.parmTemplateType.Button = self._BUTTON_SENTINEL

        mock_node = MagicMock()
        mock_parm = MagicMock()
        mock_parm_template = MagicMock()
        mock_parm_template.type.return_value = (
            parm_type if parm_type is not None else self._BUTTON_SENTINEL
        )

        mock_hou.node.return_value = mock_node
        mock_node.parm.return_value = mock_parm
        mock_parm.parmTemplate.return_value = mock_parm_template

        return mock_hou, mock_node, mock_parm, mock_parm_template

    def test_execute_button_click_success(self):
        """验证按钮点击成功：pressButton 被正确调用。"""
        engine = ExecutionEngine([])
        params = ButtonClickParams(node_path="/obj/geo1", parm_name="execute")

        mock_hou, mock_node, mock_parm, _ = self._make_mock_hou_for_button()

        with patch.dict("sys.modules", {"hou": mock_hou}):
            engine._execute_button_click(params)

        mock_hou.node.assert_called_once_with("/obj/geo1")
        mock_node.parm.assert_called_once_with("execute")
        mock_parm.pressButton.assert_called_once()

    def test_execute_button_click_invalid_node(self):
        """节点不存在时抛出 ValueError。"""
        engine = ExecutionEngine([])
        params = ButtonClickParams(node_path="/obj/nonexistent", parm_name="exec")

        mock_hou = MagicMock()
        mock_hou.node.return_value = None

        with patch.dict("sys.modules", {"hou": mock_hou}):
            with self.assertRaises(ValueError) as ctx:
                engine._execute_button_click(params)

        self.assertIn("/obj/nonexistent", str(ctx.exception))

    def test_execute_button_click_invalid_parm(self):
        """参数不存在时抛出 ValueError。"""
        engine = ExecutionEngine([])
        params = ButtonClickParams(node_path="/obj/geo1", parm_name="bad_parm")

        mock_hou = MagicMock()
        mock_node = MagicMock()
        mock_node.parm.return_value = None
        mock_hou.node.return_value = mock_node

        with patch.dict("sys.modules", {"hou": mock_hou}):
            with self.assertRaises(ValueError) as ctx:
                engine._execute_button_click(params)

        self.assertIn("bad_parm", str(ctx.exception))

    def test_execute_button_click_non_button_parm(self):
        """非 Button 类型参数时抛出 ValueError。"""
        engine = ExecutionEngine([])
        params = ButtonClickParams(node_path="/obj/geo1", parm_name="tx")

        mock_hou, _, mock_parm, _ = self._make_mock_hou_for_button(
            parm_type="FloatType",  # 不同于 _BUTTON_SENTINEL
        )

        with patch.dict("sys.modules", {"hou": mock_hou}):
            with self.assertRaises(ValueError) as ctx:
                engine._execute_button_click(params)

        self.assertIn("不是按钮参数", str(ctx.exception))

    def test_execute_button_click_dl_submit_saves_hip(self):
        """dl_Submit 按钮按下后自动保存场景。"""
        engine = ExecutionEngine([])
        params = ButtonClickParams(
            node_path="/obj/geo1", parm_name="dl_Submit",
        )

        mock_hou, _, _, _ = self._make_mock_hou_for_button()

        with patch.dict("sys.modules", {"hou": mock_hou}):
            engine._execute_button_click(params)

        mock_hou.hipFile.save.assert_called_once()

    # ── Flipbook 执行器 ────────────────────────────────────

    def test_execute_flipbook_success(self):
        """验证 flipbook 成功执行：scene.flipbook 被正确调用。"""
        engine = ExecutionEngine([])
        params = FlipbookParams(
            frame_range=(1, 50),
            output_path="$HIP/render.$F4.png",
            output_enabled=True,
        )

        mock_hou = MagicMock()
        mock_hou.paneTabType.SceneViewer = "SceneViewerType"

        mock_scene = MagicMock()
        mock_viewport = MagicMock()
        mock_settings = MagicMock()

        mock_hou.ui.paneTabOfType.return_value = mock_scene
        mock_scene.curViewport.return_value = mock_viewport
        mock_hou.flipbookSettings.return_value = mock_settings

        with patch.dict("sys.modules", {"hou": mock_hou}):
            engine._execute_flipbook(params)

        mock_hou.ui.paneTabOfType.assert_called_once_with("SceneViewerType")
        mock_settings.frameRange.assert_called_once_with((1, 50))
        mock_settings.output.assert_called_once_with("$HIP/render.$F4.png")
        mock_scene.flipbook.assert_called_once_with(mock_viewport, mock_settings)

    def test_execute_flipbook_output_disabled(self):
        """output_enabled=False 时不应设置 output。"""
        engine = ExecutionEngine([])
        params = FlipbookParams(
            frame_range=(10, 30),
            output_path="$HIP/test.$F4.png",
            output_enabled=False,
        )

        mock_hou = MagicMock()
        mock_hou.paneTabType.SceneViewer = "SceneViewerType"

        mock_scene = MagicMock()
        mock_viewport = MagicMock()
        mock_settings = MagicMock()

        mock_hou.ui.paneTabOfType.return_value = mock_scene
        mock_scene.curViewport.return_value = mock_viewport
        mock_hou.flipbookSettings.return_value = mock_settings

        with patch.dict("sys.modules", {"hou": mock_hou}):
            engine._execute_flipbook(params)

        mock_settings.frameRange.assert_called_once_with((10, 30))
        mock_settings.output.assert_not_called()
        mock_scene.flipbook.assert_called_once()

    def test_execute_flipbook_no_scene_viewer(self):
        """找不到 Scene Viewer 时抛出 RuntimeError。"""
        engine = ExecutionEngine([])
        params = FlipbookParams(
            frame_range=(1, 50),
            output_path="",
            output_enabled=False,
        )

        mock_hou = MagicMock()
        mock_hou.paneTabType.SceneViewer = "SceneViewerType"
        mock_hou.ui.paneTabOfType.return_value = None

        with patch.dict("sys.modules", {"hou": mock_hou}):
            with self.assertRaises(RuntimeError) as ctx:
                engine._execute_flipbook(params)

        self.assertIn("Scene Viewer", str(ctx.exception))

    def test_execute_flipbook_date_time_substitution(self):
        """验证 #date 和 #time 占位符被正确替换。"""
        engine = ExecutionEngine([])
        params = FlipbookParams(
            frame_range=(1, 10),
            output_path="$HIP/render.#date_#time.$F4.png",
            output_enabled=True,
        )

        mock_hou = MagicMock()
        mock_hou.paneTabType.SceneViewer = "SceneViewerType"

        mock_scene = MagicMock()
        mock_viewport = MagicMock()
        mock_settings = MagicMock()

        mock_hou.ui.paneTabOfType.return_value = mock_scene
        mock_scene.curViewport.return_value = mock_viewport
        mock_hou.flipbookSettings.return_value = mock_settings

        with patch.dict("sys.modules", {"hou": mock_hou}):
            engine._execute_flipbook(params)

        # 验证 output 包含替换后的日期时间
        call_output = mock_settings.output.call_args[0][0]
        self.assertNotIn("#date", call_output)
        self.assertNotIn("#time", call_output)

    # ── HomeAssistant 执行器 ───────────────────────────────

    def _make_mock_requests(self):
        """创建 mock requests 模块。"""
        mock_req = MagicMock()
        mock_req.Timeout = type("Timeout", (Exception,), {})
        mock_req.ConnectionError = type("ConnectionError", (Exception,), {})
        return mock_req

    def test_execute_home_assistant_success(self):
        """验证 HA webhook 成功调用。"""
        engine = ExecutionEngine([])
        params = HomeAssistantParams(webhook_url="http://ha/webhook/test")

        mock_req = self._make_mock_requests()
        mock_resp = MagicMock()
        mock_req.post.return_value = mock_resp

        with patch.dict("sys.modules", {"requests": mock_req}):
            engine._execute_home_assistant(params)

        mock_req.post.assert_called_once_with(
            "http://ha/webhook/test", timeout=5,
        )
        mock_resp.raise_for_status.assert_called_once()

    def test_execute_home_assistant_empty_url(self):
        """空 webhook_url 时抛出 ValueError。"""
        engine = ExecutionEngine([])
        params = HomeAssistantParams(webhook_url="")

        with self.assertRaises(ValueError) as ctx:
            engine._execute_home_assistant(params)

        self.assertIn("Webhook URL 为空", str(ctx.exception))

    def test_execute_home_assistant_import_error(self):
        """requests 未安装时抛出 ImportError。"""
        engine = ExecutionEngine([])
        params = HomeAssistantParams(webhook_url="http://ha/webhook/test")

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "requests":
                raise ImportError("No module named 'requests'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with self.assertRaises(ImportError) as ctx:
                engine._execute_home_assistant(params)

        self.assertIn("requests 模块未安装", str(ctx.exception))

    def test_execute_home_assistant_timeout(self):
        """请求超时时抛出 TimeoutError。"""
        engine = ExecutionEngine([])
        params = HomeAssistantParams(webhook_url="http://ha/webhook/test")

        mock_req = self._make_mock_requests()
        mock_req.post.side_effect = mock_req.Timeout("timed out")

        with patch.dict("sys.modules", {"requests": mock_req}):
            with self.assertRaises(TimeoutError) as ctx:
                engine._execute_home_assistant(params)

        self.assertIn("请求超时", str(ctx.exception))

    def test_execute_home_assistant_connection_error(self):
        """连接失败时抛出 ConnectionError。"""
        engine = ExecutionEngine([])
        params = HomeAssistantParams(webhook_url="http://ha/webhook/test")

        mock_req = self._make_mock_requests()
        mock_req.post.side_effect = mock_req.ConnectionError("connection failed")

        with patch.dict("sys.modules", {"requests": mock_req}):
            with self.assertRaises(ConnectionError) as ctx:
                engine._execute_home_assistant(params)

        self.assertIn("连接失败", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
