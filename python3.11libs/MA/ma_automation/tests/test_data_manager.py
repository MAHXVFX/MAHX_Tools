"""
Unit tests for MA_Automation_DataManager (data_manager.py).

TDD: tests written before implementation.
"""

import unittest
import sys
import os
import json
import tempfile
import typing
from unittest.mock import patch, MagicMock, PropertyMock

# 在导入 ma_automation 前 mock PySide6（因 __init__.py 会加载 execution_engine）
import _pyside_mock  # noqa: F401

# Ensure the parent package is importable
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


# ============================================================================
# Tests 1 & 2: get_data_path()
# ============================================================================
class TestGetDataPath(unittest.TestCase):
    """get_data_path() 路径解析测试。"""

    def setUp(self):
        """在每个测试前确保 hou mock 可用。"""
        self._had_hou = 'hou' in sys.modules
        if not self._had_hou:
            self._mock_hou_mod = MagicMock()
            sys.modules['hou'] = self._mock_hou_mod
        else:
            self._mock_hou_mod = sys.modules['hou']

    def tearDown(self):
        """清理 hou mock，避免影响后续测试。"""
        if not self._had_hou and 'hou' in sys.modules:
            del sys.modules['hou']

    # ---- Test 1: $HIP 路径 ----
    @patch('os.makedirs')
    def test_get_data_path_returns_correct_format(self, mock_makedirs):
        """Test 1: $HIP 存在时路径格式正确,且不创建目录。"""
        # 延迟导入以确保 hou mock 已就位
        from ma_automation.data_manager import MA_Automation_DataManager as DM

        self._mock_hou_mod.getenv.return_value = "/project/my_hip"
        path = DM.get_data_path()
        norm_path = path.replace("\\", "/")
        # 以 MAJson/MA_Automation.json 结尾
        self.assertTrue(
            norm_path.endswith("MAJson/MA_Automation.json"),
            f"路径应结尾为 MAJson/MA_Automation.json，实际: {norm_path}",
        )
        # 包含 $HIP 路径
        self.assertIn("/project/my_hip", norm_path)
        # get_data_path 是纯计算,不创建目录(只有 save() 才会)
        mock_makedirs.assert_not_called()

    # ---- Test 2: fallback 到 tempdir ----
    @patch('os.makedirs')
    def test_get_data_path_fallback_when_hip_none(self, mock_makedirs):
        """Test 2a: $HIP 为 None 时 fallback 到 tempdir。"""
        from ma_automation.data_manager import MA_Automation_DataManager as DM

        self._mock_hou_mod.getenv.return_value = None
        path = DM.get_data_path()
        norm_path = path.replace("\\", "/")
        expected_temp = tempfile.gettempdir().replace("\\", "/")
        self.assertTrue(
            norm_path.startswith(expected_temp),
            f"路径应以 tempdir 开头\n  路径: {norm_path}\n  temp: {expected_temp}",
        )
        self.assertIn("MA_Automation.json", norm_path)

    @patch('os.makedirs')
    def test_get_data_path_fallback_when_hip_empty(self, mock_makedirs):
        """Test 2b: $HIP 为空字符串时 fallback 到 tempdir。"""
        from ma_automation.data_manager import MA_Automation_DataManager as DM

        self._mock_hou_mod.getenv.return_value = ""
        path = DM.get_data_path()
        norm_path = path.replace("\\", "/")
        expected_temp = tempfile.gettempdir().replace("\\", "/")
        self.assertTrue(norm_path.startswith(expected_temp))
        self.assertIn("MA_Automation.json", norm_path)

    def test_get_data_path_fallback_no_hou_module(self):
        """Test 2c: hou 模块完全不可用时 fallback。"""
        # 移除 hou 模拟 hou 不可用的场景
        if 'hou' in sys.modules:
            del sys.modules['hou']

        from ma_automation.data_manager import MA_Automation_DataManager as DM

        path = DM.get_data_path()
        norm_path = path.replace("\\", "/")
        expected_temp = tempfile.gettempdir().replace("\\", "/")
        self.assertTrue(norm_path.startswith(expected_temp))
        self.assertIn("MA_Automation.json", norm_path)


# ============================================================================
# Test 3: serialize / deserialize_task_type
# ============================================================================
class TestSerializeDeserializeTaskType(unittest.TestCase):
    """serialize_task_type / deserialize_task_type 往返测试。"""

    def setUp(self):
        from ma_automation.data_manager import MA_Automation_DataManager as DM
        self.DM = DM

    def test_round_trip_button_click(self):
        """Test 3a: BUTTON_CLICK 往返。"""
        s = self.DM.serialize_task_type(TaskType.BUTTON_CLICK)
        self.assertEqual(s, TaskType.BUTTON_CLICK.value)
        d = self.DM.deserialize_task_type(s)
        self.assertIs(d, TaskType.BUTTON_CLICK)

    def test_round_trip_flipbook(self):
        """Test 3b: FLIPBOOK 往返。"""
        s = self.DM.serialize_task_type(TaskType.FLIPBOOK)
        self.assertEqual(s, TaskType.FLIPBOOK.value)
        d = self.DM.deserialize_task_type(s)
        self.assertIs(d, TaskType.FLIPBOOK)

    def test_round_trip_home_assistant(self):
        """Test 3c: HOME_ASSISTANT 往返。"""
        s = self.DM.serialize_task_type(TaskType.HOME_ASSISTANT)
        self.assertEqual(s, TaskType.HOME_ASSISTANT.value)
        d = self.DM.deserialize_task_type(s)
        self.assertIs(d, TaskType.HOME_ASSISTANT)


# ============================================================================
# Test 4: serialize / deserialize_params
# ============================================================================
class TestSerializeDeserializeParams(unittest.TestCase):
    """serialize_params / deserialize_params 往返测试（3 种类型）。"""

    def setUp(self):
        from ma_automation.data_manager import MA_Automation_DataManager as DM
        self.DM = DM

    def test_button_click_round_trip(self):
        """Test 4a: ButtonClickParams 往返。"""
        params = ButtonClickParams(node_path="/obj/geo1", parm_name="execute")
        d = self.DM.serialize_params(params)
        # 验证序列化：应为普通 dict
        self.assertIsInstance(d, dict)
        self.assertEqual(d["node_path"], "/obj/geo1")
        self.assertEqual(d["parm_name"], "execute")
        # 反序列化（使用 TaskType.value 匹配枚举值）
        restored = self.DM.deserialize_params(TaskType.BUTTON_CLICK.value, d)
        self.assertIsInstance(restored, ButtonClickParams)
        self.assertEqual(restored.node_path, "/obj/geo1")
        self.assertEqual(restored.parm_name, "execute")

    def test_flipbook_round_trip(self):
        """Test 4b: FlipbookParams 往返（frame_range tuple↔list）。"""
        params = FlipbookParams(
            frame_range=(1, 50),
            output_path="$HIP/render.$F4.png",
            output_enabled=True,
        )
        d = self.DM.serialize_params(params)
        # frame_range 应为 list
        self.assertEqual(d["frame_range"], [1, 50])
        self.assertEqual(d["output_path"], "$HIP/render.$F4.png")
        self.assertTrue(d["output_enabled"])
        # 反序列化
        restored = self.DM.deserialize_params(TaskType.FLIPBOOK.value, d)
        self.assertIsInstance(restored, FlipbookParams)
        # frame_range 恢复为 tuple
        self.assertIsInstance(restored.frame_range, tuple)
        self.assertEqual(restored.frame_range, (1, 50))
        self.assertEqual(restored.output_path, "$HIP/render.$F4.png")
        self.assertTrue(restored.output_enabled)

    def test_home_assistant_round_trip(self):
        """Test 4c: HomeAssistantParams 往返。"""
        params = HomeAssistantParams(webhook_url="http://ha.local/webhook/test")
        d = self.DM.serialize_params(params)
        self.assertEqual(d["webhook_url"], "http://ha.local/webhook/test")
        restored = self.DM.deserialize_params(TaskType.HOME_ASSISTANT.value, d)
        self.assertIsInstance(restored, HomeAssistantParams)
        self.assertEqual(restored.webhook_url, "http://ha.local/webhook/test")


# ============================================================================
# Test 5: save_tasks / load_tasks 完整往返
# ============================================================================
class TestSaveLoadTasks(unittest.TestCase):
    """save_tasks() + load_tasks() 完整 I/O 往返测试。"""

    def setUp(self):
        from ma_automation.data_manager import MA_Automation_DataManager as DM
        self.DM = DM

        # 创建临时目录作为数据存储区
        self._tmpdir = tempfile.mkdtemp()
        self._json_path = os.path.join(self._tmpdir, "MAJson", "MA_Automation.json")
        # 确保目录存在（因为 get_data_path 被 mock，不会自动创建）
        os.makedirs(os.path.dirname(self._json_path), exist_ok=True)

        # Mock get_data_path() 指向临时路径
        self._patcher = patch.object(
            DM,
            "get_data_path",
            return_value=self._json_path,
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        # 清理临时文件
        if os.path.exists(self._tmpdir):
            import shutil
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _make_task(self, task_type, params, enabled=True):
        return TaskItem(task_type=task_type, params=params, enabled=enabled)

    def test_round_trip(self):
        """Test 5: 保存 3 种类型后再加载，数据完全一致。"""
        tasks = [
            self._make_task(
                TaskType.BUTTON_CLICK,
                ButtonClickParams(node_path="/obj/geo1", parm_name="execute"),
            ),
            self._make_task(
                TaskType.FLIPBOOK,
                FlipbookParams(
                    frame_range=(1, 50),
                    output_path="$HIP/test.exr",
                    output_enabled=True,
                ),
                enabled=False,
            ),
            self._make_task(
                TaskType.HOME_ASSISTANT,
                HomeAssistantParams(webhook_url="http://ha/webhook/42"),
            ),
        ]
        # 保存
        result = self.DM.save_tasks(tasks)
        self.assertTrue(result, "save_tasks 应返回 True")

        # 验证文件存在并检查原始 JSON 内容
        self.assertTrue(
            os.path.exists(self._json_path),
            f"JSON 文件应存在: {self._json_path}",
        )
        with open(self._json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.assertIn("tasks", raw)
        self.assertEqual(len(raw["tasks"]), 3)

        # 加载
        loaded = self.DM.load_tasks()
        self.assertEqual(len(loaded), 3)

        # 验证第 1 个（ButtonClick）
        self.assertIs(loaded[0].task_type, TaskType.BUTTON_CLICK)
        self.assertIsInstance(loaded[0].params, ButtonClickParams)
        self.assertEqual(loaded[0].params.node_path, "/obj/geo1")
        self.assertEqual(loaded[0].params.parm_name, "execute")
        self.assertTrue(loaded[0].enabled)

        # 验证第 2 个（Flipbook）
        self.assertIs(loaded[1].task_type, TaskType.FLIPBOOK)
        self.assertIsInstance(loaded[1].params, FlipbookParams)
        self.assertEqual(loaded[1].params.frame_range, (1, 50))
        self.assertEqual(loaded[1].params.output_path, "$HIP/test.exr")
        self.assertTrue(loaded[1].params.output_enabled)
        self.assertFalse(loaded[1].enabled)

        # 验证第 3 个（HomeAssistant）
        self.assertIs(loaded[2].task_type, TaskType.HOME_ASSISTANT)
        self.assertIsInstance(loaded[2].params, HomeAssistantParams)
        self.assertEqual(loaded[2].params.webhook_url, "http://ha/webhook/42")
        self.assertTrue(loaded[2].enabled)


# ============================================================================
# Tests 6 & 7: 边界情况
# ============================================================================
class TestLoadEdgeCases(unittest.TestCase):
    """load() 在异常情况下的行为。"""

    def setUp(self):
        from ma_automation.data_manager import MA_Automation_DataManager as DM
        self.DM = DM
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self._tmpdir):
            import shutil
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_load_file_not_exists_returns_empty_list(self):
        """Test 6: 文件不存在时 load() 返回空列表。"""
        nonexistent = os.path.join(self._tmpdir, "no_such_file.json")
        with patch.object(self.DM, "get_data_path", return_value=nonexistent):
            result = self.DM.load()
            self.assertEqual(result, [])

    def test_load_corrupt_json_returns_empty_list(self):
        """Test 7: JSON 损坏时 load() 返回空列表并打印警告。"""
        corrupt_path = os.path.join(self._tmpdir, "corrupt.json")
        os.makedirs(os.path.dirname(corrupt_path), exist_ok=True)
        with open(corrupt_path, "w", encoding="utf-8") as f:
            f.write("not valid json {")

        with patch.object(self.DM, "get_data_path", return_value=corrupt_path):
            result = self.DM.load()
            self.assertEqual(result, [])

    def test_load_missing_tasks_key_returns_empty_list(self):
        """Test 7b: JSON 中没有 'tasks' 键时返回空列表。"""
        valid_path = os.path.join(self._tmpdir, "valid_no_tasks.json")
        os.makedirs(os.path.dirname(valid_path), exist_ok=True)
        with open(valid_path, "w", encoding="utf-8") as f:
            json.dump({"other_key": [1, 2, 3]}, f)

        with patch.object(self.DM, "get_data_path", return_value=valid_path):
            result = self.DM.load()
            self.assertEqual(result, [])


# ============================================================================
# Extra: save() 直接测试
# ============================================================================
class TestSaveDirect(unittest.TestCase):
    """save() 直接写入和错误处理。"""

    def setUp(self):
        from ma_automation.data_manager import MA_Automation_DataManager as DM
        self.DM = DM
        self._tmpdir = tempfile.mkdtemp()
        self._json_path = os.path.join(self._tmpdir, "MAJson", "MA_Automation.json")
        # 确保目录存在（因为 get_data_path 被 mock，不会自动创建）
        os.makedirs(os.path.dirname(self._json_path), exist_ok=True)

        self._patcher = patch.object(
            self.DM,
            "get_data_path",
            return_value=self._json_path,
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        if os.path.exists(self._tmpdir):
            import shutil
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_save_returns_true_on_success(self):
        """save() 成功时应返回 True。"""
        result = self.DM.save([{"name": "test", "type": "BUTTON_CLICK"}])
        self.assertTrue(result)

    def test_save_returns_false_on_error(self):
        """save() 异常时应返回 False。"""
        with patch.object(self.DM, "get_data_path", return_value="/invalid/\x00/path"):
            result = self.DM.save([{"name": "test"}])
            self.assertFalse(result)

    def test_save_writes_utf8_with_ensure_ascii_false(self):
        """save() 写入时应支持中文 (ensure_ascii=False)。"""
        data = [{"name": "测试任务", "description": "中文描述"}]
        self.DM.save(data)
        with open(self._json_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("测试任务", content)
        self.assertIn("中文描述", content)

    def test_save_indent_format(self):
        """save() 写入格式应为 indent=2。"""
        data = [{"name": "test"}]
        self.DM.save(data)
        with open(self._json_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 验证有缩进
        self.assertIn('  "', content)


# ============================================================================
# 副作用契约测试:open panel + 编辑 + 关闭 = 0 文件副作用
# ============================================================================
class TestSideEffects(unittest.TestCase):
    """DataManager 三方法的副作用边界测试。

    设计目标(配合"仅在 Start 时落盘"语义):
      - ``get_data_path()`` 纯计算路径,不创建目录
      - ``load()`` 纯只读,文件/目录不存在时返回 [],不创建任何东西
      - ``save()`` 唯一允许创建 MAJson 目录的入口

    打开 MA Automation 面板 + 编辑 + 关闭 = 不应在 $HIP 下出现 MAJson 目录
    或 MA_Automation.json 文件。只有点 Start 才会真正落盘。
    """

    def setUp(self):
        from ma_automation.data_manager import MA_Automation_DataManager as DM
        self.DM = DM
        # 不预创建任何目录,验证各方法的真实副作用
        self._tmpdir = tempfile.mkdtemp()
        self._json_path = os.path.join(self._tmpdir, "MAJson", "MA_Automation.json")

    def tearDown(self):
        if os.path.exists(self._tmpdir):
            import shutil
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _ensure_hou_mock(self, hip_value):
        """确保 hou mock 在 sys.modules 中,getenv 返回给定值。"""
        if 'hou' not in sys.modules:
            mock_hou = MagicMock()
            sys.modules['hou'] = mock_hou
        sys.modules['hou'].getenv.return_value = hip_value

    @patch('ma_automation.data_manager.os.makedirs')
    def test_get_data_path_does_not_create_directory(self, mock_makedirs):
        """get_data_path() 不应调用 os.makedirs(纯计算)。"""
        self._ensure_hou_mock(self._tmpdir)
        path = self.DM.get_data_path()
        self.assertEqual(path, self._json_path)
        mock_makedirs.assert_not_called()
        # 目录也不应在文件系统上被创建
        self.assertFalse(
            os.path.exists(os.path.dirname(path)),
            f"get_data_path 不应在 {os.path.dirname(path)} 创建目录",
        )

    def test_save_is_the_only_creator_of_directory(self):
        """save() 写入前应创建 MAJson 目录(若不存在),并写入 JSON 文件。

        不 patch os.makedirs:这里要验证"事后副作用",即目录和文件真实存在。
        配合 ``_ensure_hou_mock`` 让 ``get_data_path`` 返回 ``$HIP = self._tmpdir``,
        实际写到 ``{tmpdir}/MAJson/MA_Automation.json``。
        """
        # 关键:调用前 $HIP 下没有 MAJson 目录
        self.assertFalse(
            os.path.exists(os.path.dirname(self._json_path)),
            f"测试前不应存在 {os.path.dirname(self._json_path)}",
        )

        self._ensure_hou_mock(self._tmpdir)
        result = self.DM.save([{"name": "test", "type": "BUTTON_CLICK"}])
        self.assertTrue(result, "save() 应返回 True")

        # 事后:MAJson 目录 + JSON 文件都应真实存在
        self.assertTrue(
            os.path.isdir(os.path.dirname(self._json_path)),
            f"save() 后应创建目录 {os.path.dirname(self._json_path)}",
        )
        self.assertTrue(
            os.path.isfile(self._json_path),
            f"save() 后应写入文件 {self._json_path}",
        )

    @patch('ma_automation.data_manager.os.makedirs')
    def test_load_does_not_create_directory(self, mock_makedirs):
        """load() 不应创建任何文件/目录(纯只读,文件不存在时返回 [])。"""
        nonexistent = os.path.join(self._tmpdir, "no_such_dir", "no_such.json")
        with patch.object(self.DM, 'get_data_path', return_value=nonexistent):
            result = self.DM.load()
        self.assertEqual(result, [])
        mock_makedirs.assert_not_called()
        # 父目录也不应在文件系统上被创建
        self.assertFalse(
            os.path.exists(os.path.dirname(nonexistent)),
            "load() 不应在不存在的路径上创建目录",
        )


if __name__ == "__main__":
    unittest.main()
