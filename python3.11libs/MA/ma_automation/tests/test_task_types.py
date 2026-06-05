"""Unit tests for ma_automation task_types module.

TDD: tests written before implementation.
"""

import unittest
import sys
import os

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
    TaskParams,
)


class TestTaskTypeEnum(unittest.TestCase):
    """Test TaskType enum values."""

    def test_enum_values_exist(self):
        """Test 1: All 3 TaskType enum values exist."""
        self.assertIn(TaskType.BUTTON_CLICK, TaskType)
        self.assertIn(TaskType.FLIPBOOK, TaskType)
        self.assertIn(TaskType.HOME_ASSISTANT, TaskType)

    def test_enum_values_are_distinct(self):
        """Ensure enum values are unique."""
        values = [e.value for e in TaskType]
        self.assertEqual(len(values), len(set(values)))


class TestButtonClickParams(unittest.TestCase):
    """Test ButtonClickParams dataclass."""

    def test_create(self):
        """Test 2: Create ButtonClickParams with node_path and parm_name."""
        params = ButtonClickParams(node_path="/obj/test_node", parm_name="execute")
        self.assertEqual(params.node_path, "/obj/test_node")
        self.assertEqual(params.parm_name, "execute")

    def test_defaults(self):
        """Verify no unexpected default values."""
        params = ButtonClickParams(node_path="/obj/n", parm_name="run")
        self.assertTrue(hasattr(params, "node_path"))
        self.assertTrue(hasattr(params, "parm_name"))


class TestFlipbookParams(unittest.TestCase):
    """Test FlipbookParams dataclass."""

    def test_create(self):
        """Test 3: Create FlipbookParams (empty, no fields)."""
        params = FlipbookParams()
        self.assertIsInstance(params, FlipbookParams)


class TestHomeAssistantParams(unittest.TestCase):
    """Test HomeAssistantParams dataclass."""

    def test_create(self):
        """Test 4: Create HomeAssistantParams with webhook_url."""
        params = HomeAssistantParams(
            webhook_url="http://homeassistant.local:8123/api/webhook/abc123"
        )
        self.assertEqual(
            params.webhook_url,
            "http://homeassistant.local:8123/api/webhook/abc123",
        )


class TestTaskItem(unittest.TestCase):
    """Test TaskItem dataclass."""

    def setUp(self):
        self.button_item = TaskItem(
            task_type=TaskType.BUTTON_CLICK,
            params=ButtonClickParams(node_path="/obj/geo1", parm_name="execute"),
            enabled=True,
        )
        self.flipbook_item = TaskItem(
            task_type=TaskType.FLIPBOOK,
            params=FlipbookParams(),
            enabled=False,
        )
        self.ha_item = TaskItem(
            task_type=TaskType.HOME_ASSISTANT,
            params=HomeAssistantParams(webhook_url="http://ha/webhook/test"),
            enabled=True,
        )

    def test_create(self):
        """Test 5: Create TaskItem with all field combinations."""
        # ButtonClick
        self.assertIs(self.button_item.task_type, TaskType.BUTTON_CLICK)
        self.assertIsInstance(self.button_item.params, ButtonClickParams)
        self.assertTrue(self.button_item.enabled)

        # Flipbook
        self.assertIs(self.flipbook_item.task_type, TaskType.FLIPBOOK)
        self.assertIsInstance(self.flipbook_item.params, FlipbookParams)
        self.assertFalse(self.flipbook_item.enabled)

        # HomeAssistant
        self.assertIs(self.ha_item.task_type, TaskType.HOME_ASSISTANT)
        self.assertIsInstance(self.ha_item.params, HomeAssistantParams)
        self.assertTrue(self.ha_item.enabled)


class TestTaskItemSerialization(unittest.TestCase):
    """Test TaskItem.to_dict() and from_dict()."""

    def setUp(self):
        self.button_item = TaskItem(
            task_type=TaskType.BUTTON_CLICK,
            params=ButtonClickParams(node_path="/obj/geo1", parm_name="execute"),
            enabled=True,
        )
        self.flipbook_item = TaskItem(
            task_type=TaskType.FLIPBOOK,
            params=FlipbookParams(),
            enabled=False,
        )
        self.ha_item = TaskItem(
            task_type=TaskType.HOME_ASSISTANT,
            params=HomeAssistantParams(webhook_url="http://ha/webhook/test"),
            enabled=True,
        )

    def test_to_dict_button_click(self):
        """Test 6a: to_dict() for ButtonClick TaskItem."""
        d = self.button_item.to_dict()
        self.assertEqual(d["type"], "BUTTON_CLICK")
        self.assertEqual(d["params"]["node_path"], "/obj/geo1")
        self.assertEqual(d["params"]["parm_name"], "execute")
        self.assertTrue(d["enabled"])

    def test_to_dict_flipbook(self):
        """Test 6b: to_dict() for Flipbook TaskItem."""
        d = self.flipbook_item.to_dict()
        self.assertEqual(d["type"], "FLIPBOOK")
        self.assertEqual(d["params"]["start_frame"], "$RFSTART")
        self.assertEqual(d["params"]["end_frame"], "$RFEND")
        self.assertEqual(d["params"]["output_path"], "$HIP/FlipBook/$HIPNAME/$HIPNAME.$F4.jpg")
        self.assertTrue(d["params"]["save_to_disk"])
        self.assertFalse(d["enabled"])

    def test_to_dict_home_assistant(self):
        """Test 6c: to_dict() for HomeAssistant TaskItem."""
        d = self.ha_item.to_dict()
        self.assertEqual(d["type"], "HOME_ASSISTANT")
        self.assertEqual(d["params"]["webhook_url"], "http://ha/webhook/test")
        self.assertTrue(d["enabled"])

    def test_from_dict_button_click(self):
        """Test 7a: from_dict() for ButtonClick TaskItem."""
        data = {
            "type": "BUTTON_CLICK",
            "params": {"node_path": "/obj/mynode", "parm_name": "fire"},
            "enabled": False,
        }
        item = TaskItem.from_dict(data)
        self.assertIs(item.task_type, TaskType.BUTTON_CLICK)
        self.assertIsInstance(item.params, ButtonClickParams)
        self.assertEqual(item.params.node_path, "/obj/mynode")
        self.assertEqual(item.params.parm_name, "fire")
        self.assertFalse(item.enabled)

    def test_from_dict_flipbook(self):
        """Test 7b: from_dict() for Flipbook TaskItem (empty params, backward compat)."""
        data = {
            "type": "FLIPBOOK",
            "params": {},
            "enabled": True,
        }
        item = TaskItem.from_dict(data)
        self.assertIs(item.task_type, TaskType.FLIPBOOK)
        self.assertIsInstance(item.params, FlipbookParams)
        self.assertTrue(item.enabled)

    def test_from_dict_flipbook_backward_compat(self):
        """Test 7b+: from_dict() for Flipbook with old format (fields ignored)."""
        data = {
            "type": "FLIPBOOK",
            "params": {
                "frame_range": [100, 200],
                "output_path": "$HIP/test.exr",
                "output_enabled": False,
            },
            "enabled": True,
        }
        item = TaskItem.from_dict(data)
        self.assertIs(item.task_type, TaskType.FLIPBOOK)
        self.assertIsInstance(item.params, FlipbookParams)
        self.assertTrue(item.enabled)

    def test_from_dict_home_assistant(self):
        """Test 7c: from_dict() for HomeAssistant TaskItem."""
        data = {
            "type": "HOME_ASSISTANT",
            "params": {"webhook_url": "http://ha/webhook/42"},
            "enabled": True,
        }
        item = TaskItem.from_dict(data)
        self.assertIs(item.task_type, TaskType.HOME_ASSISTANT)
        self.assertIsInstance(item.params, HomeAssistantParams)
        self.assertEqual(item.params.webhook_url, "http://ha/webhook/42")
        self.assertTrue(item.enabled)

    def test_round_trip_button_click(self):
        """Test 8a: Round-trip consistency for ButtonClick."""
        original = self.button_item
        restored = TaskItem.from_dict(original.to_dict())
        self.assertIs(restored.task_type, original.task_type)
        self.assertEqual(restored.params.node_path, original.params.node_path)
        self.assertEqual(restored.params.parm_name, original.params.parm_name)
        self.assertEqual(restored.enabled, original.enabled)

    def test_round_trip_flipbook(self):
        """Test 8b: Round-trip consistency for Flipbook."""
        original = self.flipbook_item
        restored = TaskItem.from_dict(original.to_dict())
        self.assertIs(restored.task_type, original.task_type)
        self.assertIsInstance(restored.params, FlipbookParams)
        self.assertEqual(restored.enabled, original.enabled)

    def test_round_trip_home_assistant(self):
        """Test 8c: Round-trip consistency for HomeAssistant."""
        original = self.ha_item
        restored = TaskItem.from_dict(original.to_dict())
        self.assertIs(restored.task_type, original.task_type)
        self.assertEqual(restored.params.webhook_url, original.params.webhook_url)
        self.assertEqual(restored.enabled, original.enabled)


class TestTaskParamsTypeAlias(unittest.TestCase):
    """Test that TaskParams type alias resolves correctly."""

    def test_task_params_is_union(self):
        """TaskParams should be a Union of the three param types."""
        import typing

        origin = typing.get_origin(TaskParams)
        self.assertIsNotNone(origin, "TaskParams should be a generic alias")

    def test_task_params_members(self):
        """Verify the Union members are the correct types."""
        import typing

        args = typing.get_args(TaskParams)
        self.assertIn(ButtonClickParams, args)
        self.assertIn(FlipbookParams, args)
        self.assertIn(HomeAssistantParams, args)


if __name__ == "__main__":
    unittest.main()
