"""
MA Automation — 执行引擎
=========================
QThread 子类，在后台线程中逐个执行任务列表。
支持 3 种任务类型：BUTTON_CLICK / FLIPBOOK / HOME_ASSISTANT。

执行器通过 ``hdefereval.executeDeferred`` 将 Houdini API 调用
派发到主线程执行，确保线程安全。
"""

import logging
import threading
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from .task_types import (
    TaskItem,
    TaskType,
    ButtonClickParams,
    FlipbookParams,
    HomeAssistantParams,
)

# 尝试导入 hdefereval — Houdini 环境外不可用，此时为 None
try:
    import hdefereval  # noqa: N812 — only available inside Houdini
except ImportError:
    hdefereval = None

logger = logging.getLogger("MA")


class ExecutionEngine(QThread):
    """自动化任务执行引擎。

    接收 ``list[TaskItem]``，在 ``run()`` 中逐项派发给对应的桩执行器。
    通过信号向 UI 层报告进度和结果。
    """

    task_started = Signal(int, str)        # (task_index, task_type_value)
    task_completed = Signal(int, bool, str)  # (task_index, success, message)
    all_completed = Signal(int, int)        # (success_count, fail_count)

    def __init__(self, tasks: list[TaskItem], parent=None):
        super().__init__(parent)
        self._tasks = tasks
        self._cancelled = False

    # ── 主循环 ────────────────────────────────────────────

    def run(self):
        """遍历所有任务，派发给对应的执行器。"""
        success_count = 0
        fail_count = 0

        for idx, task in enumerate(self._tasks):
            if self._cancelled:
                break
            if not task.enabled:
                continue

            self.task_started.emit(idx, task.task_type.value)

            try:
                if task.task_type == TaskType.BUTTON_CLICK:
                    self._execute_button_click(task.params)
                elif task.task_type == TaskType.FLIPBOOK:
                    self._execute_flipbook(task.params)
                elif task.task_type == TaskType.HOME_ASSISTANT:
                    self._execute_home_assistant(task.params)
                else:
                    raise ValueError(f"未知任务类型: {task.task_type}")

                self.task_completed.emit(idx, True, "执行成功")
                success_count += 1
            except Exception as e:
                self.task_completed.emit(idx, False, str(e))
                fail_count += 1

            self.msleep(100)

        self.all_completed.emit(success_count, fail_count)

    # ── 取消 ──────────────────────────────────────────────

    def cancel(self):
        """设置取消标志，``run()`` 将在当前任务完成后提前退出。"""
        self._cancelled = True

    # ── 主线程派发 ────────────────────────────────────────

    def _run_deferred(self, fn):
        """通过 ``hdefereval.executeDeferred`` 在主线程执行 ``fn``。

        若 ``hdefereval`` 不可用（测试环境等），则直接执行。
        """
        if hdefereval is not None:
            exc_info: list[BaseException | None] = [None]
            ready = threading.Event()

            def wrapper():
                try:
                    fn()
                except BaseException as e:
                    exc_info[0] = e
                finally:
                    ready.set()

            hdefereval.executeDeferred(wrapper)
            ready.wait()

            if exc_info[0] is not None:
                raise exc_info[0]  # type: ignore[misc]
        else:
            fn()

    # ── 执行器 ─────────────────────────────────────────────

    def _execute_button_click(self, params: ButtonClickParams):
        """执行按钮点击。

        接收 ``ButtonClickParams(node_path, parm_name)``，
        通过 ``hou.node()`` 查找节点，验证并按下按钮。

        Raises:
            ValueError: 节点不存在、参数不存在、非 Button 类型
        """
        def impl():
            import hou
            target_node = hou.node(params.node_path)
            if target_node is None:
                raise ValueError(f"节点不存在: {params.node_path}")

            target_parm = target_node.parm(params.parm_name)
            if target_parm is None:
                raise ValueError(f"参数不存在: {params.parm_name}")

            parm_template = target_parm.parmTemplate()
            if parm_template.type() != hou.parmTemplateType.Button:
                raise ValueError(f"不是按钮参数: {params.parm_name}")

            target_parm.pressButton()

            # 特殊处理 dl_Submit：先保存场景
            if params.parm_name == "dl_Submit":
                hou.hipFile.save()

        self._run_deferred(impl)

    def _execute_flipbook(self, params: FlipbookParams):
        """执行 Flipbook 拍屏。

        接收 ``FlipbookParams(frame_range, output_path, output_enabled)``，
        通过当前 Scene Viewer 执行 flipbook 渲染。

        Raises:
            RuntimeError: 找不到 Scene Viewer
        """
        def impl():
            import hou
            scene = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
            if scene is None:
                raise RuntimeError("未找到 Scene Viewer")

            settings = hou.flipbookSettings()
            start, end = params.frame_range
            settings.frameRange((start, end))

            if params.output_enabled and params.output_path:
                output = params.output_path
                if "#date" in output:
                    output = output.replace(
                        "#date", datetime.now().strftime("%Y%m%d")
                    )
                if "#time" in output:
                    output = output.replace(
                        "#time", datetime.now().strftime("%H%M%S")
                    )
                settings.output(output)

            scene.flipbook(scene.curViewport(), settings)

        self._run_deferred(impl)

    def _execute_home_assistant(self, params: HomeAssistantParams):
        """执行 HomeAssistant Webhook 调用。

        接收 ``HomeAssistantParams(webhook_url)``，
        通过 ``requests.post()`` 发送 HTTP POST 请求。
        网络请求可直接在后台线程执行，无需 ``executeDeferred``。

        Raises:
            ValueError: webhook_url 为空
            ImportError: requests 模块不存在
            TimeoutError: 请求超时
            ConnectionError: 连接失败
        """
        if not params.webhook_url:
            raise ValueError("Webhook URL 为空")

        try:
            import requests
        except ImportError:
            raise ImportError("requests 模块未安装，请执行 pip install requests")

        try:
            resp = requests.post(params.webhook_url, timeout=5)
            resp.raise_for_status()
        except requests.Timeout:
            raise TimeoutError(f"请求超时: {params.webhook_url}")
        except requests.ConnectionError:
            raise ConnectionError(f"连接失败: {params.webhook_url}")
