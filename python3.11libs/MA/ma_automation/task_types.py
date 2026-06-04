"""
MA Automation — 任务类型定义
=============================
TaskType 枚举 + TaskParams 数据类 + TaskItem 容器（可序列化）。
"""

from enum import Enum
from dataclasses import dataclass
from typing import Union


class TaskType(Enum):
    """自动化任务类型枚举。"""
    BUTTON_CLICK = "BUTTON_CLICK"
    FLIPBOOK = "FLIPBOOK"
    HOME_ASSISTANT = "HOME_ASSISTANT"


@dataclass
class ButtonClickParams:
    """按钮点击参数：指定节点路径和参数名。"""
    node_path: str
    parm_name: str


@dataclass
class FlipbookParams:
    """Flipbook 渲染参数（空）。

    Flipbook 不再使用自定义参数，执行时直接读取 Houdini 工程的
    ``SceneViewer.flipbookSettings()``。保留此类是为了维持
    ``TaskType.FLIPBOOK`` 的类型标识和 JSON 序列化兼容性。
    """


@dataclass
class HomeAssistantParams:
    """Home Assistant 自动化参数：Webhook URL。"""
    webhook_url: str


TaskParams = Union[ButtonClickParams, FlipbookParams, HomeAssistantParams]


@dataclass
class TaskItem:
    """任务项 —— 组合了类型、参数和启用状态。"""
    task_type: TaskType
    params: TaskParams
    enabled: bool

    def to_dict(self) -> dict:
        """序列化为 dict，frame_range 转为列表。"""
        base = {
            "type": self.task_type.value,
            "enabled": self.enabled,
        }

        if self.task_type == TaskType.BUTTON_CLICK:
            assert isinstance(self.params, ButtonClickParams)
            base["params"] = {
                "node_path": self.params.node_path,
                "parm_name": self.params.parm_name,
            }
        elif self.task_type == TaskType.FLIPBOOK:
            assert isinstance(self.params, FlipbookParams)
            base["params"] = {}
        elif self.task_type == TaskType.HOME_ASSISTANT:
            assert isinstance(self.params, HomeAssistantParams)
            base["params"] = {
                "webhook_url": self.params.webhook_url,
            }
        else:
            raise ValueError(f"Unknown task type: {self.task_type}")

        return base

    @staticmethod
    def from_dict(data: dict) -> "TaskItem":
        """从 dict 反序列化，frame_range 列表恢复为 tuple。"""
        type_str = data["type"]

        if type_str == "BUTTON_CLICK":
            task_type = TaskType.BUTTON_CLICK
            params: TaskParams = ButtonClickParams(
                node_path=data["params"]["node_path"],
                parm_name=data["params"]["parm_name"],
            )
        elif type_str == "FLIPBOOK":
            task_type = TaskType.FLIPBOOK
            params = FlipbookParams()
        elif type_str == "HOME_ASSISTANT":
            task_type = TaskType.HOME_ASSISTANT
            params = HomeAssistantParams(
                webhook_url=data["params"]["webhook_url"],
            )
        else:
            raise ValueError(f"Unknown task type string: {type_str}")

        return TaskItem(
            task_type=task_type,
            params=params,
            enabled=data["enabled"],
        )
