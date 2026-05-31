"""
MA Automation — Data Manager 数据持久化模块
==============================================
提供 MA_Automation_DataManager 类，负责 JSON 文件的读写和任务对象的
序列化/反序列化。

所有方法均为 @classmethod，因为全局只需一个逻辑实例，
但数据路径依赖 $HIP（动态计算），不使用 BaseJsonManager。
"""

import os
import json
import tempfile
import logging
from dataclasses import asdict
from typing import Optional

from .task_types import (
    TaskType,
    TaskItem,
    ButtonClickParams,
    FlipbookParams,
    HomeAssistantParams,
)

logger = logging.getLogger("MA")


class MA_Automation_DataManager:
    """MA Automation 数据持久化管理器。

    所有方法均为类方法，无需实例化即可使用。
    数据以 JSON 格式存储在 ``{HIP}/MAJson/MA_Automation.json``，
    $HIP 不可用时 fallback 到系统临时目录。
    """

    # ── 路径管理 ─────────────────────────────────────────

    @classmethod
    def get_data_path(cls) -> str:
        """返回数据文件的绝对路径，并确保目录存在。

        优先级:
          1. ``hou.getenv("HIP")`` — Houdini $HIP 环境变量
          2. ``tempfile.gettempdir()`` — 系统临时目录（fallback）

        ``hou`` 只在函数内部 try/except 导入，避免 Houdini 外 ImportError。
        """
        try:
            import hou  # noqa: N812 — only available inside Houdini
            hip = hou.getenv("HIP")
            if hip:
                base = hip
            else:
                base = tempfile.gettempdir()
        except ImportError:
            base = tempfile.gettempdir()

        path = os.path.join(base, "MAJson", "MA_Automation.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    # ── 核心 IO ──────────────────────────────────────────

    @classmethod
    def load(cls) -> list[dict]:
        """从 JSON 文件读取任务数据列表。

        返回 ``data["tasks"]``，若文件不存在或 JSON 损坏则返回空列表。
        """
        path = cls.get_data_path()
        try:
            if not os.path.exists(path):
                return []
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("tasks", [])
        except json.JSONDecodeError:
            print("警告: JSON 解析失败")
            return []
        except Exception:
            return []

    @classmethod
    def save(cls, tasks_data: list[dict]) -> bool:
        """将任务 dict 列表写入 JSON 文件。

        写入结构: ``{"tasks": tasks_data}``
        使用 ``ensure_ascii=False``（支持中文）和 ``indent=2``。

        Returns:
            True 写入成功，False 写入异常。
        """
        try:
            path = cls.get_data_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {"tasks": tasks_data},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            return True
        except Exception:
            return False

    # ── 序列化 / 反序列化 ─────────────────────────────────

    @classmethod
    def serialize_task_type(cls, task_type: TaskType) -> str:
        """TaskType 枚举 → 字符串（枚举的 value）。"""
        return task_type.value

    @classmethod
    def deserialize_task_type(cls, type_str: str) -> TaskType:
        """字符串 → TaskType 枚举。"""
        return TaskType(type_str)

    @classmethod
    def serialize_params(cls, params) -> dict:
        """Params dataclass → dict。

        特殊处理:
          - ``FlipbookParams.frame_range``: tuple → list
        """
        d = asdict(params)
        if isinstance(params, FlipbookParams):
            d["frame_range"] = list(d["frame_range"])
        return d

    @classmethod
    def deserialize_params(
        cls,
        type_str: str,
        params_dict: dict,
    ):
        """dict → Params dataclass。

        根据 ``type_str``（匹配 ``TaskType`` 的 value）决定返回的参数类型。
        特殊处理:
          - ``flipbook`` 的 ``frame_range``: list → tuple
        """
        task_type = TaskType(type_str)
        p = dict(params_dict)

        if task_type == TaskType.FLIPBOOK and "frame_range" in p:
            p["frame_range"] = tuple(p["frame_range"])

        if task_type == TaskType.BUTTON_CLICK:
            return ButtonClickParams(**p)
        elif task_type == TaskType.FLIPBOOK:
            return FlipbookParams(**p)
        elif task_type == TaskType.HOME_ASSISTANT:
            return HomeAssistantParams(**p)
        else:
            raise ValueError(f"未知参数类型: {type_str}")

    # ── 高层便捷方法 ─────────────────────────────────────

    @classmethod
    def save_tasks(cls, tasks: list[TaskItem]) -> bool:
        """直接接受 ``TaskItem`` 列表，自动序列化后保存。"""
        tasks_data = [t.to_dict() for t in tasks]
        return cls.save(tasks_data)

    @classmethod
    def load_tasks(cls) -> list[TaskItem]:
        """加载并自动反序列化为 ``TaskItem`` 列表。"""
        data_list = cls.load()
        return [TaskItem.from_dict(d) for d in data_list]
