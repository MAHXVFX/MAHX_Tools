"""
MA Automation — 主窗口 UI
=========================
Singleton QDialog，非模态独立窗口。
提供任务槽列表编辑、持久化保存、ExecutionEngine 集成。
"""

import logging

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QWidget,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QLabel,
    QStackedWidget,
)
from PySide6.QtCore import Qt

from MA.ma_automation.data_manager import MA_Automation_DataManager
from MA.ma_automation.task_types import (
    TaskItem,
    TaskType,
    ButtonClickParams,
    FlipbookParams,
    HomeAssistantParams,
)
from MA.ma_automation.execution_engine import ExecutionEngine

logger = logging.getLogger("MA")

# ── Singleton ────────────────────────────────────────────────

_window = None

# ── 样式表 ───────────────────────────────────────────────────

STYLE_SHEET = """
QDialog { background-color: #18181b; }
QPushButton { background-color: #2d2d2d; color: #e0e0e0; border: none;
              padding: 6px 16px; border-radius: 4px; font-size: 13px; }
QPushButton:hover { background-color: #3d3d3d; }
QPushButton:pressed { background-color: #0d6399; }
QPushButton#startBtn { background-color: #0d6399; color: white; font-weight: bold; }
QPushButton#startBtn:hover { background-color: #0e7bc9; }
QComboBox { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d;
            padding: 4px 8px; border-radius: 4px; }
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView { background-color: #2d2d2d; color: #e0e0e0;
                               selection-background-color: #0d6399; }
QLineEdit { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d;
            padding: 4px 8px; border-radius: 4px; }
QCheckBox { color: #e0e0e0; spacing: 6px; }
QScrollArea { border: none; background-color: transparent; }
QLabel { background-color: transparent; color: #e0e0e0; border: none; }
"""


def show_automation_window():
    """打开 MA Automation 主窗口（单例）。

    若窗口已存在且可见则将其激活并置顶，否则创建新实例。
    """
    global _window
    if _window is not None and _window.isVisible():
        _window.raise_()
        _window.activateWindow()
        return _window
    _window = AutomationWindow()
    _window.show()
    return _window


class AutomationWindow(QDialog):
    """MA Automation 主窗口。

    包含可动态增删的任务槽列表、工具栏（Start / Auto Fill / Clear / + / -）、
    数据持久化加载/保存以及 ExecutionEngine 后台执行集成。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MA Automation")
        self.setMinimumSize(600, 450)
        self.setWindowFlags(Qt.Window)
        self.setStyleSheet(STYLE_SHEET)

        # ── 状态 ──
        self._slot_widgets: list[QWidget] = []
        self._running = False
        self._engine: ExecutionEngine | None = None

        self._build_ui()
        self._load_data()

    # ── UI 构建 ────────────────────────────────────────────

    def _build_ui(self):
        """构建完整 UI：工具栏 + 滚动槽列表。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── 工具栏 ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self._start_btn = QPushButton("Start")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.clicked.connect(self._on_start)

        auto_fill_btn = QPushButton("Auto Fill")
        auto_fill_btn.clicked.connect(self._on_auto_fill)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear)

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(32)
        add_btn.clicked.connect(self._add_slot)

        remove_btn = QPushButton("-")
        remove_btn.setFixedWidth(32)
        remove_btn.clicked.connect(self._remove_slot)

        toolbar.addWidget(self._start_btn)
        toolbar.addWidget(auto_fill_btn)
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()
        toolbar.addWidget(add_btn)
        toolbar.addWidget(remove_btn)

        layout.addLayout(toolbar)

        # ── 槽列表滚动区域 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._slot_container = QWidget()
        self._slot_layout = QVBoxLayout(self._slot_container)
        self._slot_layout.setContentsMargins(0, 0, 0, 0)
        self._slot_layout.setSpacing(6)
        self._slot_layout.addStretch()  # 将槽推至顶部

        scroll.setWidget(self._slot_container)
        layout.addWidget(scroll)

    def _create_slot_widget(self, index: int, data: dict | None = None) -> QWidget:
        """创建一个任务槽控件。"""
        slot = QWidget()

        hbox = QHBoxLayout(slot)
        hbox.setContentsMargins(4, 4, 4, 4)
        hbox.setSpacing(8)

        # ── 序号标签 ──
        idx_label = QLabel(str(index + 1))
        idx_label.setFixedWidth(24)
        idx_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # ── 类型下拉框 ──
        combo = QComboBox()
        combo.setObjectName("taskType")
        combo.addItems(["按钮点击", "Flipbook", "HomeAssistant Webhook"])
        combo.setFixedWidth(160)

        # ── 参数区域（QStackedWidget） ──
        stacked = QStackedWidget()
        stacked.setObjectName("paramsStacked")

        # Page 0: 按钮点击
        page0 = QWidget()
        p0_layout = QHBoxLayout(page0)
        p0_layout.setContentsMargins(0, 0, 0, 0)
        p0_layout.setSpacing(4)
        node_path_le = QLineEdit()
        node_path_le.setObjectName("nodePath")
        node_path_le.setPlaceholderText("节点路径")
        parm_name_le = QLineEdit()
        parm_name_le.setObjectName("parmName")
        parm_name_le.setPlaceholderText("参数名")
        p0_layout.addWidget(node_path_le)
        p0_layout.addWidget(parm_name_le)
        stacked.addWidget(page0)

        # Page 1: Flipbook
        page1 = QWidget()
        p1_layout = QHBoxLayout(page1)
        p1_layout.setContentsMargins(0, 0, 0, 0)
        p1_layout.setSpacing(4)
        frame_range_le = QLineEdit()
        frame_range_le.setObjectName("frameRange")
        frame_range_le.setPlaceholderText("帧范围 (1-100)")
        output_path_le = QLineEdit()
        output_path_le.setObjectName("outputPath")
        output_path_le.setPlaceholderText("输出路径")
        output_enabled_cb = QCheckBox("输出")
        output_enabled_cb.setObjectName("outputEnabled")
        output_enabled_cb.setChecked(True)
        p1_layout.addWidget(frame_range_le)
        p1_layout.addWidget(output_path_le)
        p1_layout.addWidget(output_enabled_cb)
        stacked.addWidget(page1)

        # Page 2: HomeAssistant Webhook
        page2 = QWidget()
        p2_layout = QHBoxLayout(page2)
        p2_layout.setContentsMargins(0, 0, 0, 0)
        p2_layout.setSpacing(4)
        webhook_url_le = QLineEdit()
        webhook_url_le.setObjectName("webhookUrl")
        webhook_url_le.setPlaceholderText("Webhook URL")
        p2_layout.addWidget(webhook_url_le)
        stacked.addWidget(page2)

        # ── 启用勾选框 ──
        enabled_cb = QCheckBox("启用")
        enabled_cb.setObjectName("slotEnabled")
        enabled_cb.setChecked(True)

        # ── 组装 ──
        hbox.addWidget(idx_label)
        hbox.addWidget(combo)
        hbox.addWidget(stacked, 1)
        hbox.addWidget(enabled_cb)

        # ── 信号：切换类型时切换参数页 ──
        combo.currentIndexChanged.connect(
            lambda idx, s=stacked: s.setCurrentIndex(idx)
        )

        # ── 填充数据（加载时）──
        if data is not None:
            self._populate_slot_from_data(
                slot, data,
                combo, stacked,
                node_path_le, parm_name_le,
                frame_range_le, output_path_le, output_enabled_cb,
                webhook_url_le,
                enabled_cb,
            )

        return slot

    @staticmethod
    def _populate_slot_from_data(
        slot, data, combo, stacked,
        node_path_le, parm_name_le,
        frame_range_le, output_path_le, output_enabled_cb,
        webhook_url_le, enabled_cb,
    ):
        """根据 dict 数据填充一个已创建的槽控件。"""
        type_str = data.get("type", "BUTTON_CLICK")
        params = data.get("params", {})
        enabled = data.get("enabled", True)

        if type_str == "BUTTON_CLICK":
            combo.setCurrentIndex(0)
            node_path_le.setText(params.get("node_path", ""))
            parm_name_le.setText(params.get("parm_name", ""))
        elif type_str == "FLIPBOOK":
            combo.setCurrentIndex(1)
            fr = params.get("frame_range", [1, 100])
            if isinstance(fr, (list, tuple)) and len(fr) == 2:
                frame_range_le.setText(f"{fr[0]}-{fr[1]}")
            output_path_le.setText(params.get("output_path", ""))
            output_enabled_cb.setChecked(params.get("output_enabled", True))
        elif type_str == "HOME_ASSISTANT":
            combo.setCurrentIndex(2)
            webhook_url_le.setText(params.get("webhook_url", ""))

        enabled_cb.setChecked(enabled)
        stacked.setCurrentIndex(combo.currentIndex())

    # ── 槽管理 ─────────────────────────────────────────────

    def _add_slot(self, data: dict | None = None):
        """追加一个新槽。"""
        index = len(self._slot_widgets)
        slot = self._create_slot_widget(index, data)
        self._slot_widgets.append(slot)
        # 插入到 stretch 之前
        self._slot_layout.insertWidget(self._slot_layout.count() - 1, slot)
        self._renumber_slots()

    def _remove_slot(self):
        """移除最后一个槽（至少保留 1 个）。"""
        if len(self._slot_widgets) <= 1:
            return
        slot = self._slot_widgets.pop()
        self._slot_layout.removeWidget(slot)
        slot.deleteLater()
        self._renumber_slots()

    def _renumber_slots(self):
        """更新所有槽的序号。"""
        for i, slot in enumerate(self._slot_widgets):
            label = slot.findChild(QLabel)
            if label is not None:
                label.setText(str(i + 1))

    # ── 数据持久化 ─────────────────────────────────────────

    def _load_data(self):
        """从 DataManager 加载数据并重建 UI 槽。"""
        raw_list = MA_Automation_DataManager.load()

        # 清空现有槽
        for slot in self._slot_widgets:
            self._slot_layout.removeWidget(slot)
            slot.deleteLater()
        self._slot_widgets.clear()

        if raw_list:
            for item_data in raw_list:
                self._add_slot(item_data)

        # 确保至少 1 个空槽
        if not self._slot_widgets:
            self._add_slot()

    def _collect_data(self) -> list[dict]:
        """读取 UI 槽，构建 list[dict]（与 TaskItem.to_dict() 格式一致）。"""
        tasks: list[dict] = []
        for slot in self._slot_widgets:
            combo = slot.findChild(QComboBox, "taskType")
            if combo is None:
                continue
            type_idx = combo.currentIndex()

            enabled_cb = slot.findChild(QCheckBox, "slotEnabled")
            enabled = enabled_cb.isChecked() if enabled_cb else True

            stacked = slot.findChild(QStackedWidget, "paramsStacked")
            current_page = stacked.currentWidget() if stacked else None

            if type_idx == 0:  # 按钮点击
                node_path = ""
                parm_name = ""
                if current_page:
                    np_le = current_page.findChild(QLineEdit, "nodePath")
                    pn_le = current_page.findChild(QLineEdit, "parmName")
                    node_path = np_le.text() if np_le else ""
                    parm_name = pn_le.text() if pn_le else ""
                params = ButtonClickParams(node_path=node_path, parm_name=parm_name)
                item = TaskItem(
                    task_type=TaskType.BUTTON_CLICK,
                    params=params,
                    enabled=enabled,
                )

            elif type_idx == 1:  # Flipbook
                frame_range = (1, 100)
                output_path = ""
                output_enabled = True
                if current_page:
                    fr_le = current_page.findChild(QLineEdit, "frameRange")
                    op_le = current_page.findChild(QLineEdit, "outputPath")
                    oe_cb = current_page.findChild(QCheckBox, "outputEnabled")
                    if oe_cb is not None:
                        output_enabled = oe_cb.isChecked()
                    if fr_le is not None:
                        text = fr_le.text().strip()
                        if text:
                            parts = text.replace(" ", "").split("-")
                            try:
                                fr_start = int(parts[0])
                                fr_end = int(parts[1]) if len(parts) > 1 else 100
                                frame_range = (fr_start, fr_end)
                            except (ValueError, IndexError):
                                pass
                    if op_le is not None:
                        output_path = op_le.text()
                params = FlipbookParams(
                    frame_range=frame_range,
                    output_path=output_path,
                    output_enabled=output_enabled,
                )
                item = TaskItem(
                    task_type=TaskType.FLIPBOOK,
                    params=params,
                    enabled=enabled,
                )

            else:  # HomeAssistant Webhook
                webhook_url = ""
                if current_page:
                    wh_le = current_page.findChild(QLineEdit, "webhookUrl")
                    webhook_url = wh_le.text() if wh_le else ""
                params = HomeAssistantParams(webhook_url=webhook_url)
                item = TaskItem(
                    task_type=TaskType.HOME_ASSISTANT,
                    params=params,
                    enabled=enabled,
                )

            tasks.append(item.to_dict())

        return tasks

    def _save_data(self):
        """收集并持久化任务数据。"""
        tasks_data = self._collect_data()
        MA_Automation_DataManager.save(tasks_data)

    # ── 执行集成 ───────────────────────────────────────────

    def _on_start(self):
        """Start / Cancel 切换按钮。"""
        if self._running:
            self._cancel_execution()
            return
        self._start_execution()

    def _start_execution(self):
        """收集任务 → 创建 ExecutionEngine → 启动后台执行。"""
        tasks_data = self._collect_data()
        task_items = [TaskItem.from_dict(d) for d in tasks_data]

        self._engine = ExecutionEngine(task_items)
        self._engine.task_started.connect(self._on_task_started)
        self._engine.task_completed.connect(self._on_task_completed)
        self._engine.all_completed.connect(self._on_all_completed)

        self._running = True
        self._start_btn.setText("取消")
        self._engine.start()

    def _cancel_execution(self):
        """取消正在执行的任务。"""
        if self._engine is not None:
            self._engine.cancel()
        print("MA Automation: 用户取消执行")
        self._running = False
        self._start_btn.setText("Start")

    def _on_task_started(self, idx: int, task_type: str):
        """单个任务开始时的回调。"""
        print(f"MA Automation: 开始任务 {idx + 1} ({task_type})")

    def _on_task_completed(self, idx: int, ok: bool, msg: str):
        """单个任务完成时的回调。"""
        status = "✓" if ok else "✗"
        print(f"任务 {idx + 1}: {status} - {msg}")

    def _on_all_completed(self, success: int, failed: int):
        """全部任务执行完毕的回调。"""
        print(f"MA Automation: 执行完成 — 成功 {success}, 失败 {failed}")
        self._running = False
        self._start_btn.setText("Start")
        self._engine = None

    # ── 工具栏动作 ──────────────────────────────────────────

    # ── Auto Fill ───────────────────────────────────────────────────

    @staticmethod
    def _on_auto_fill():
        """从当前选中的节点中提取 execute 按钮路径，追加到任务列表。

        遍历 hou.selectedNodes()，对每个有 'execute' 参数的节点，
        构造 BUTTON_CLICK 任务并追加到列表末尾。
        不会覆盖已有任务（追加模式）。
        无选中节点或没有有效节点时打印提示。
        """
        import hou  # Houdini-only, 放入方法内部

        selected = hou.selectedNodes()
        if not selected:
            print("Auto Fill: 当前无选择节点")
            return

        found = 0
        for node in selected:
            parm = node.parm("execute")
            if parm is not None:
                global _window
                if _window is not None and _window.isVisible():
                    data = {
                        "type": "BUTTON_CLICK",
                        "params": {
                            "node_path": node.path(),
                            "parm_name": "execute",
                        },
                        "enabled": True,
                    }
                    _window._add_slot(data)
                    found += 1

        if found > 0:
            print(f"Auto Fill: 已添加 {found} 个按钮点击任务")
        else:
            print("Auto Fill: 当前无有效节点")

    def _on_clear(self):
        """清空所有槽，保留 1 个空槽。"""
        for slot in self._slot_widgets:
            self._slot_layout.removeWidget(slot)
            slot.deleteLater()
        self._slot_widgets.clear()
        self._add_slot()

    # ── 窗口关闭 ───────────────────────────────────────────

    def closeEvent(self, event):
        """关闭前保存数据，清理单例引用。"""
        global _window
        self._save_data()
        _window = None
        super().closeEvent(event)
