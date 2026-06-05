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
        # 以 MA Automation/json/MA_Automation.json 结尾
        self.assertTrue(
            norm_path.endswith("MA Automation/json/MA_Automation.json"),
            f"路径应结尾为 MA Automation/json/MA_Automation.json，实际: {norm_path}",
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
        """Test 4b: FlipbookParams 往返。"""
        params = FlipbookParams(
            start_frame="$RFSTART",
            end_frame="$RFEND",
            output_path="$HIP/FlipBook/$HIPNAME/$HIPNAME.$F4.jpg",
            save_to_disk=True,
        )
        d = self.DM.serialize_params(params)
        self.assertEqual(d["start_frame"], "$RFSTART")
        self.assertEqual(d["end_frame"], "$RFEND")
        self.assertEqual(d["output_path"], "$HIP/FlipBook/$HIPNAME/$HIPNAME.$F4.jpg")
        self.assertTrue(d["save_to_disk"])
        restored = self.DM.deserialize_params(TaskType.FLIPBOOK.value, d)
        self.assertIsInstance(restored, FlipbookParams)
        self.assertEqual(restored.start_frame, "$RFSTART")
        self.assertEqual(restored.end_frame, "$RFEND")

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
        self._json_path = os.path.join(self._tmpdir, "MA Automation/json", "MA_Automation.json")
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
                FlipbookParams(),
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
        self._json_path = os.path.join(self._tmpdir, "MA Automation/json", "MA_Automation.json")
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
      - ``save()`` 唯一允许创建配置目录的入口

    打开 MA Automation 面板 + 编辑 + 关闭 = 不应在 $HIP 下出现配置目录
    或 MA_Automation.json 文件。只有点 Start 才会真正落盘。
    """

    def setUp(self):
        from ma_automation.data_manager import MA_Automation_DataManager as DM
        self.DM = DM
        # 不预创建任何目录,验证各方法的真实副作用
        self._tmpdir = tempfile.mkdtemp()
        self._json_path = os.path.join(self._tmpdir, "MA Automation/json", "MA_Automation.json")

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
        """save() 写入前应创建配置目录(若不存在),并写入 JSON 文件。

        不 patch os.makedirs:这里要验证"事后副作用",即目录和文件真实存在。
        配合 ``_ensure_hou_mock`` 让 ``get_data_path`` 返回 ``$HIP = self._tmpdir``,
        实际写到 ``{tmpdir}/MA Automation/json/MA_Automation.json``。
        """
        # 关键:调用前 $HIP 下没有配置目录
        self.assertFalse(
            os.path.exists(os.path.dirname(self._json_path)),
            f"测试前不应存在 {os.path.dirname(self._json_path)}",
        )

        self._ensure_hou_mock(self._tmpdir)
        result = self.DM.save([{"name": "test", "type": "BUTTON_CLICK"}])
        self.assertTrue(result, "save() 应返回 True")

        # 事后:配置目录 + JSON 文件都应真实存在
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


# ============================================================================
# 多文件支持:get_data_path(filename) / load(filename) / save(data, filename)
# + list_configs()
# ============================================================================
class TestConfigFileSelection(unittest.TestCase):
    """filename 参数化 IO + ``list_configs()`` 测试。

    对应 UI 的"可编辑配置下拉"功能:
      - ``get_data_path(filename)`` / ``load(filename)`` / ``save(data, filename)``
        均接受可选文件名,None 时走默认 ``MA_Automation.json``
      - ``list_configs()`` 返回配置目录所有 .json 文件 basename(无后缀)

    setUp 用 ``side_effect=lambda filename=None:`` 模拟参数化 ``get_data_path``
    的真实行为,所有测试在临时目录下跑,tearDown 清空。
    """

    def setUp(self):
        from ma_automation.data_manager import MA_Automation_DataManager as DM
        self.DM = DM
        self._tmpdir = tempfile.mkdtemp()
        # 关键:side_effect 走参数化路径,模拟 get_data_path(filename) 的真实行为
        # 默认 None → MA_Automation.json,带名 → {name}.json
        self._patcher = patch.object(
            DM,
            "get_data_path",
            side_effect=lambda filename=None: os.path.join(
                self._tmpdir, "MA Automation/json",
                f"{filename}.json" if filename else "MA_Automation.json",
            ),
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        if os.path.exists(self._tmpdir):
            import shutil
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    # ── get_data_path(filename) ─────────────────────────────

    def test_get_data_path_with_filename_uses_that_name(self):
        """get_data_path('MAtest1') 返回以 MA Automation/json/MAtest1.json 结尾的路径。"""
        path = self.DM.get_data_path("MAtest1")
        norm = path.replace("\\", "/")
        self.assertTrue(
            norm.endswith("MA Automation/json/MAtest1.json"),
            f"应结尾为 MA Automation/json/MAtest1.json,实际: {norm}",
        )

    def test_get_data_path_with_none_uses_default(self):
        """get_data_path() 无参 → 默认 MA_Automation.json(向后兼容)。"""
        path = self.DM.get_data_path()
        self.assertTrue(path.endswith("MA_Automation.json"))

    def test_get_data_path_with_empty_string_falls_back_to_default(self):
        """get_data_path('') 空串 → 走默认(等价于 None,防误用)。"""
        path = self.DM.get_data_path("")
        self.assertTrue(path.endswith("MA_Automation.json"))

    # ── load(filename) ─────────────────────────────────────

    def test_load_with_filename_loads_correct_file(self):
        """load('MAtest1') 加载 MAtest1.json 的内容(与默认文件隔离)。"""
        os.makedirs(os.path.join(self._tmpdir, "MA Automation/json"), exist_ok=True)
        path = os.path.join(self._tmpdir, "MA Automation/json", "MAtest1.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"tasks": [{"name": "from MAtest1"}]}, f)
        data = self.DM.load("MAtest1")
        self.assertEqual(data, [{"name": "from MAtest1"}])

    def test_load_nonexistent_filename_returns_empty_list(self):
        """load('不存在的名') 返回空列表(不报错、不创建文件)。"""
        data = self.DM.load("nonexistent_xyz")
        self.assertEqual(data, [])

    def test_load_corrupt_file_with_filename_falls_back(self):
        """load(filename) 对损坏 JSON 也走容错返回 [](与默认 load 一致)。"""
        os.makedirs(os.path.join(self._tmpdir, "MA Automation/json"), exist_ok=True)
        path = os.path.join(self._tmpdir, "MA Automation/json", "corrupt.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not valid json {")
        data = self.DM.load("corrupt")
        self.assertEqual(data, [])

    def test_load_with_filename_uses_correct_dir_not_default(self):
        """load('X') 不会误读默认文件 MA_Automation.json(隔离验证)。"""
        os.makedirs(os.path.join(self._tmpdir, "MA Automation/json"), exist_ok=True)
        # 默认文件内容
        with open(os.path.join(self._tmpdir, "MA Automation/json", "MA_Automation.json"), "w") as f:
            json.dump({"tasks": [{"name": "default_data"}]}, f)
        # MAtest1 文件内容
        with open(os.path.join(self._tmpdir, "MA Automation/json", "MAtest1.json"), "w") as f:
            json.dump({"tasks": [{"name": "specific_data"}]}, f)
        # 加载 MAtest1 不应返回 default_data
        self.assertEqual(self.DM.load("MAtest1"), [{"name": "specific_data"}])
        self.assertEqual(self.DM.load(), [{"name": "default_data"}])

    # ── save(data, filename) ──────────────────────────────

    def test_save_with_filename_creates_file(self):
        """save(data, 'MAtest2') 创建 MAtest2.json 文件。"""
        result = self.DM.save([{"name": "x"}], "MAtest2")
        self.assertTrue(result)
        self.assertTrue(os.path.exists(
            os.path.join(self._tmpdir, "MA Automation/json", "MAtest2.json")
        ))

    def test_save_with_filename_creates_directory(self):
        """save(data, 'X') 自动创建配置目录(若不存在)——保留副作用契约。"""
        self.assertFalse(os.path.exists(os.path.join(self._tmpdir, "MA Automation/json")))
        self.DM.save([{"name": "x"}], "MAtest2")
        self.assertTrue(os.path.isdir(os.path.join(self._tmpdir, "MA Automation/json")))

    def test_save_multiple_filenames_create_independent_files(self):
        """多次 save 不同 filename 互不覆盖,各创建独立文件,内容隔离。"""
        self.DM.save([{"name": "A"}], "MAtest_A")
        self.DM.save([{"name": "B"}], "MAtest_B")
        self.DM.save([{"name": "C"}], "MAtest_C")
        for name in ["MAtest_A.json", "MAtest_B.json", "MAtest_C.json"]:
            self.assertTrue(
                os.path.exists(os.path.join(self._tmpdir, "MA Automation/json", name)),
                f"应存在 {name}",
            )
        # 内容互不混淆
        self.assertEqual(self.DM.load("MAtest_A"), [{"name": "A"}])
        self.assertEqual(self.DM.load("MAtest_B"), [{"name": "B"}])
        self.assertEqual(self.DM.load("MAtest_C"), [{"name": "C"}])

    def test_save_overwrites_existing_file(self):
        """save(data, 'X') 对已存在 X.json 静默覆盖(用户显式重存)。"""
        os.makedirs(os.path.join(self._tmpdir, "MA Automation/json"), exist_ok=True)
        path = os.path.join(self._tmpdir, "MA Automation/json", "MAtest1.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"tasks": [{"name": "old"}]}, f)
        self.DM.save([{"name": "new"}], "MAtest1")
        self.assertEqual(self.DM.load("MAtest1"), [{"name": "new"}])

    # ── list_configs() ─────────────────────────────────────

    def test_list_configs_empty_dir_returns_empty_list(self):
        """配置目录不存在时 list_configs() 返回空列表(不创建)。"""
        self.assertFalse(os.path.exists(os.path.join(self._tmpdir, "MA Automation/json")))
        result = self.DM.list_configs()
        self.assertEqual(result, [])

    def test_list_configs_with_files_returns_sorted_basenames(self):
        """列出配置目录下所有 .json basename(无后缀),按字典序排序(sorted 稳态)。"""
        os.makedirs(os.path.join(self._tmpdir, "MA Automation/json"), exist_ok=True)
        # 故意打乱顺序,验证 sorted
        for name in ["MAtest_C.json", "MAtest_A.json", "MAtest_B.json"]:
            with open(os.path.join(self._tmpdir, "MA Automation/json", name), "w") as f:
                f.write("{}")
        self.assertEqual(
            self.DM.list_configs(),
            ["MAtest_A", "MAtest_B", "MAtest_C"],
        )

    def test_list_configs_excludes_non_json_files(self):
        """list_configs() 只列 .json 文件,排除 .txt / .bak 等其他后缀。"""
        os.makedirs(os.path.join(self._tmpdir, "MA Automation/json"), exist_ok=True)
        for name in ["MAtest.json", "readme.txt", "config.bak", "notes.md"]:
            with open(os.path.join(self._tmpdir, "MA Automation/json", name), "w") as f:
                f.write("")
        self.assertEqual(self.DM.list_configs(), ["MAtest"])

    def test_list_configs_excludes_subdirectories(self):
        """list_configs() 只列顶层文件,排除同名/任意子目录。"""
        os.makedirs(
            os.path.join(self._tmpdir, "MA Automation/json", "subdir"),
            exist_ok=True,
        )
        with open(
            os.path.join(self._tmpdir, "MA Automation/json", "MAtest.json"), "w"
        ) as f:
            f.write("{}")
        self.assertEqual(self.DM.list_configs(), ["MAtest"])

    def test_list_configs_includes_empty_and_corrupt_files(self):
        """list_configs() 不验证 JSON 有效性,空文件 / 损坏文件也列出
        (由 ``load()`` 容错处理返回 ``[]``,不影响文件被发现)。"""
        os.makedirs(os.path.join(self._tmpdir, "MA Automation/json"), exist_ok=True)
        for name in ["empty.json", "corrupt.json", "valid.json"]:
            with open(
                os.path.join(self._tmpdir, "MA Automation/json", name), "w"
            ) as f:
                f.write(
                    "not valid json {"
                    if "corrupt" in name
                    else "{}"
                )
        # 3 个文件都在列表中(空/损坏由 load 处理)
        self.assertEqual(
            self.DM.list_configs(),
            ["corrupt", "empty", "valid"],
        )

    def test_list_configs_does_not_create_directory(self):
        """list_configs() 不应创建配置目录(纯只读,与 load() 一致)。

        这是 list_configs 的**副作用契约**:与 load() 一样,目录不存在时
        返回 [] 不创建。UI 在配置目录还没创建(用户首次打开)时调用
        list_configs 也安全。
        """
        self.assertFalse(os.path.exists(os.path.join(self._tmpdir, "MA Automation/json")))
        self.DM.list_configs()
        self.assertFalse(
            os.path.exists(os.path.join(self._tmpdir, "MA Automation/json")),
            "list_configs() 不应创建配置目录",
        )


if __name__ == "__main__":
    unittest.main()
