"""
MA Automation — 主窗口 UI
=========================
Singleton QDialog，非模态独立窗口。
提供任务槽列表编辑、持久化保存、ExecutionEngine 集成。
"""

import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QLineEdit, QStackedWidget, QCheckBox, QWidget, QScrollArea, QSizePolicy,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor

from MA.ma_automation.data_manager import MA_Automation_DataManager
from MA.ma_automation.task_types import (
    TaskItem,
    TaskType,
    ButtonClickParams,
    FlipbookParams,
    HomeAssistantParams,
)
from MA.ma_automation.execution_engine import ExecutionEngine
from MA.ma_automation.styles import STYLE_SHEET

logger = logging.getLogger("MA")

# ── Singleton ────────────────────────────────────────────────

_window = None


def _apply_window_flags(window):
    """应用 Win32 扩展样式，让 MA Automation 窗口在 Houdini 中保持在前。

    复用 hdr_library/main.py 同款实现：
    通过 SetWindowLongW 设置 ``WS_EX_APPWINDOW`` (0x00040000)，
    标记窗口为独立应用窗口，避免 Houdini 宿主进程把它压到 Z 序底部。
    ``SetCurrentProcessExplicitAppUserModelID`` 让任务栏图标和窗口分组正确。

    必须在 ``setWindowFlags`` 之后调用（``winId()`` 第一次访问会触发原生窗口创建）。
    失败时静默忽略（跨平台兼容、ctypes 缺失等场景）。
    """
    try:
        from ctypes import windll
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        hwnd = int(window.winId())
        SetWindowLong = windll.user32.SetWindowLongW
        GetWindowLong = windll.user32.GetWindowLongW
        style = GetWindowLong(hwnd, GWL_EXSTYLE)
        style |= WS_EX_APPWINDOW
        SetWindowLong(hwnd, GWL_EXSTYLE, style)
        windll.shell32.SetCurrentProcessExplicitAppUserModelID('MA.Automation.1')
    except Exception:
        pass


def show_automation_window():
    """打开 MA Automation 主窗口（单例）。

    若窗口已存在且可见则将其激活并置顶，否则创建新实例。
    窗口挂到 Houdini 主窗口下作为子窗口，确保 Z 序由 Houdini 内部管理
    （与 hdr_library/main.py 同款做法）。
    """
    global _window
    if _window is not None and _window.isVisible():
        _window.raise_()
        _window.activateWindow()
        return _window

    # 获取 Houdini 主窗口作为 parent —— 关键：建立父子关系后，
    # WS_EX_APPWINDOW 才能配合 Houdini 内部 Z 序保持面板在前。
    parent_window = None
    try:
        import hou  # noqa: WPS433 — Houdini-only, 函数内导入
        parent_window = hou.qt.mainWindow()
    except (ImportError, AttributeError):
        pass

    _window = AutomationWindow(parent_window)
    _window.show()
    return _window


# ── 任务槽手柄 ────────────────────────────────────────────────

class _SlotHandle(QLabel):
    """任务槽"手柄"标签,即序号所在区域。

    设计意图:
    - 序号区不只是显示数字,还是一个**可交互的拖动手柄 + 选中触发器**
    - 左键单击 → 选中该槽(高亮)
    - 左键按住 + 拖动 → 重排任务顺序
    - 拖动时 cursor 切换 OpenHand → ClosedHand

    通过 3 个 Signal 把事件转发给 ``AutomationWindow`` 处理,
    避免在 widget 内部维护复杂状态。

    Signals:
        handlePressed(slot_widget, global_pos): 左键按下
        handleMoved(slot_widget, global_pos): 鼠标移动(无论是否按下都发,接收方按需过滤)
        handleReleased(slot_widget, global_pos): 左键松开
    """

    handlePressed = Signal(object, object)  # slot_widget, QPoint
    handleMoved = Signal(object, object)
    handleReleased = Signal(object, object)

    def __init__(self, slot_widget: QWidget) -> None:
        """``slot_widget`` 同时也是 Qt parent(单参避免调用方传错)。

        设计:手柄的 Qt parent == 任务槽卡片自身,故 ``self.parentWidget()`` 即槽。
        唯一参数 ``slot_widget`` 显式声明这个意图,杜绝把"序号文字"误传成槽引用。
        """
        super().__init__(slot_widget)
        self._slot = slot_widget
        self.setObjectName("taskSlotHandle")
        self.setCursor(Qt.OpenHandCursor)
        self.setMouseTracking(True)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.grabMouse()  # 捕获所有鼠标事件,确保 drag 过程不出丢 release
            self.setCursor(Qt.ClosedHandCursor)
            self.handlePressed.emit(self._slot, event.globalPos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        # 注意:无论是否按下都发,接收方按 _drag_active 过滤
        self.handleMoved.emit(self._slot, event.globalPos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            if self.mouseGrabber() == self:
                self.releaseMouse()
            self.setCursor(Qt.OpenHandCursor)
            self.handleReleased.emit(self._slot, event.globalPos())
        super().mouseReleaseEvent(event)


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
        _apply_window_flags(self)
        self.setStyleSheet(STYLE_SHEET)

        # ── 状态 ──
        self._slot_widgets: list[QWidget] = []
        # 平行于 _slot_widgets 的 handle 引用列表,在 _create_slot_widget 时
        # 一次性存到 slot._handle,之后 _add_slot 同步 append。替掉原来 3 处
        # (renumber / index_at_global_y) 的 findChild 热路径,O(N×M) → O(N)
        self._slot_handles: list[QLabel] = []
        self._running = False
        self._engine: ExecutionEngine | None = None

        # 选中 + 拖动状态
        self._selected_index: int | None = None  # 单选,None=无选中
        self._last_selected_index: int | None = None  # 差量更新 _update_selection_style 用
        self._drag_active: bool = False  # 拖动是否已激活(超过阈值)
        self._drag_source_index: int | None = None  # 拖动起点槽索引
        self._drag_press_pos = None  # type: QPoint | None  # 拖动按下时的全局坐标
        self._drag_threshold: int = 5  # 像素,超过才认作拖动

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
        # 用 lambda 包装避免 Qt clicked(bool) 信号把 False 当作 data 参数传入
        self._start_btn.clicked.connect(lambda: self._on_start())

        auto_fill_btn = QPushButton("Auto Fill")
        auto_fill_btn.clicked.connect(lambda: self._on_auto_fill())

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self._on_clear())

        add_btn = QPushButton("+")
        add_btn.setObjectName("addBtn")
        add_btn.setFixedWidth(32)
        add_btn.clicked.connect(lambda: self._add_slot())

        remove_btn = QPushButton("-")
        remove_btn.setObjectName("removeBtn")
        remove_btn.setFixedWidth(32)
        remove_btn.clicked.connect(lambda: self._remove_slot())

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
        slot.setObjectName("taskSlot")
        slot.setAutoFillBackground(True)
        # 锁高：滚动区 setWidgetResizable(True) 会把容器拉到视口大小，
        # 默认 Preferred 会让 slot 在槽数少时撑满空间。Fixed 强制 sizeHint (~42px)
        slot.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        hbox = QHBoxLayout(slot)
        hbox.setContentsMargins(8, 6, 8, 6)
        hbox.setSpacing(8)

        # ── 序号手柄(可点击选中 + 拖动重排)──
        # 关键:第一个位置参数是"任务槽"本身(同时也是 Qt parent),不是序号文字。
        # 之前误传 str(index+1) 导致 handlePressed 发出的 slot 是字符串,
        # handler 里 list.index(str) 抛 ValueError 提前返回,选中/拖动全失效。
        idx_label = _SlotHandle(slot)
        idx_label.setText(str(index + 1))
        idx_label.setFixedWidth(32)
        idx_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        idx_label.handlePressed.connect(self._on_handle_pressed)
        idx_label.handleMoved.connect(self._on_handle_moved)
        idx_label.handleReleased.connect(self._on_handle_released)
        # 把 handle 引用存到 slot 上,让 _add_slot 能 append 到 _slot_handles
        # 替掉 findChild 热路径;handle 生命周期 = slot 生命周期,无泄漏
        slot._handle = idx_label

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
        # 同步 append handle(平行列表,_renumber / _index_at_global_y 用)
        self._slot_handles.append(slot._handle)
        # 插入到 stretch 之前
        self._slot_layout.insertWidget(self._slot_layout.count() - 1, slot)
        self._renumber_slots()

    def _remove_slot(self, index: int | None = None) -> None:
        """移除指定索引的槽(默认末尾,兼容工具栏 - 按钮)。

        Args:
            index: 要移除的槽索引;``None`` 表示末尾(工具栏 - 按钮的行为)。

        边界:
        - 列表为空:no-op
        - 索引越界:no-op
        - 删除后自动调整 ``_selected_index``(被删则清空,大于被删索引则 -1)
        """
        if not self._slot_widgets:
            return
        if index is None:
            index = len(self._slot_widgets) - 1
        if not (0 <= index < len(self._slot_widgets)):
            return

        slot = self._slot_widgets.pop(index)
        self._slot_handles.pop(index)  # 同步 pop handle
        self._slot_layout.removeWidget(slot)
        slot.deleteLater()

        # 调整选中索引
        if self._selected_index is not None:
            if self._selected_index == index:
                self._selected_index = None
            elif self._selected_index > index:
                self._selected_index -= 1

        # _last_selected_index 也要跟着挪(否则下次更新会用错槽)
        if self._last_selected_index is not None:
            if self._last_selected_index == index:
                self._last_selected_index = None
            elif self._last_selected_index > index:
                self._last_selected_index -= 1

        self._renumber_slots()
        self._update_selection_style()

    def _renumber_slots(self):
        """更新所有槽的序号(序号手柄的文字)。

        用 ``_slot_handles`` 平行列表替原来 ``findChild`` 树走 ——
        ``_renumber_slots`` 会在增/删/拖动结束时调,O(N×M) → O(N)。
        """
        for i, handle in enumerate(self._slot_handles):
            handle.setText(str(i + 1))

    # ── 选中(单击手柄) ─────────────────────────────────────

    def _select_slot(self, index: int) -> None:
        """选中指定索引的槽(单选)。

        已选中同一索引则 no-op。索引越界忽略。选中后通过
        ``_update_selection_style`` 刷新视觉。
        """
        if not (0 <= index < len(self._slot_widgets)):
            return
        if self._selected_index == index:
            return
        self._selected_index = index
        self._update_selection_style()

    def _update_selection_style(self) -> None:
        """根据 ``_selected_index`` **差量更新**槽的 ``selected`` 动态属性。

        拖动期 N 次 unpolish/polish → 2 次:仅重绘 prev 槽(False) + curr 槽(True)。
        prev/curr 索引相同时完全 no-op(连 setProperty 都不调)。

        配合 ``styles.py`` 的 ``QWidget#taskSlot[selected="true"]`` 选择器
        实现选中视觉。Qt 不会自动检测动态属性变化,所以需要 unpolish + polish
        强制重评估。
        """
        prev = self._last_selected_index
        curr = self._selected_index
        if prev == curr:
            return
        if prev is not None and 0 <= prev < len(self._slot_widgets):
            s = self._slot_widgets[prev]
            s.setProperty("selected", False)
            s.style().unpolish(s)
            s.style().polish(s)
        if curr is not None and 0 <= curr < len(self._slot_widgets):
            s = self._slot_widgets[curr]
            s.setProperty("selected", True)
            s.style().unpolish(s)
            s.style().polish(s)
        self._last_selected_index = curr

    # ── 拖动重排(按住手柄拖动) ──────────────────────────────

    def _on_handle_pressed(self, slot: QWidget, global_pos: QPoint) -> None:
        """手柄被按下:选中该槽 + 准备拖动(尚未激活,等超过阈值) + 应用"抬起"样式。"""
        # 用 ``is`` 身份比较(不依赖 QWidget.__eq__,QWidget 的 __eq__ 语义不一定身份比较)
        index = None
        for i, s in enumerate(self._slot_widgets):
            if s is slot:
                index = i
                break
        if index is None:
            return
        self._select_slot(index)
        self._drag_source_index = index
        self._drag_press_pos = global_pos
        self._drag_active = False
        # 加阴影 + CSS dragging 状态,视觉上"浮起来"
        self._apply_drag_effect(slot, True)

    def _on_handle_moved(self, slot: QWidget, global_pos: QPoint) -> None:
        """手柄被拖动:超过阈值后实时换位(序号在 release 时统一刷新)。"""
        if self._drag_source_index is None or self._drag_press_pos is None:
            return
        if not self._drag_active:
            # 距离按下点 < 阈值 → 仍认作点击,不算拖动
            if (global_pos - self._drag_press_pos).manhattanLength() < self._drag_threshold:
                return
            self._drag_active = True
        # 计算目标索引
        target = self._index_at_global_y(global_pos.y())
        if target is None or target == self._drag_source_index:
            return
        # 换位后,从新位置继续跟踪(否则下一次 move 会基于旧索引)
        # 注:_move_slot 不再调 _renumber_slots,序号保持"过期"直到 release
        self._move_slot(self._drag_source_index, target)
        self._drag_source_index = target

    def _on_handle_released(self, slot: QWidget, global_pos: QPoint) -> None:
        """手柄松开:移除抬起样式 + 统一刷新序号。"""
        if self._drag_source_index is None:
            return
        # 移除阴影 + dragging 状态
        self._apply_drag_effect(slot, False)
        # 拖动结束后统一刷一次序号(配合 _move_slot 不再自动刷新,实现
        # "拖动期序号不刷新、松开统一更新"的交互)
        self._renumber_slots()
        # 重置 drag 状态
        self._drag_source_index = None
        self._drag_press_pos = None
        self._drag_active = False

    def _apply_drag_effect(self, slot: QWidget, enabled: bool) -> None:
        """应用 / 移除"抬起"拖动视觉效果。

        视觉组合:
        - ``QGraphicsDropShadowEffect``:真实阴影,槽在视觉上"浮"在布局上方
        - ``setProperty("dragging", ...)`` + CSS:让 Qt 样式表可以单独定制
          dragging 状态(目前用于蓝色边框 + 更亮的背景)
        """
        if enabled:
            effect = QGraphicsDropShadowEffect(slot)
            effect.setBlurRadius(24)
            effect.setColor(QColor(0, 0, 0, 200))
            effect.setOffset(0, 6)
            slot.setGraphicsEffect(effect)
            slot.setProperty("dragging", True)
        else:
            slot.setGraphicsEffect(None)
            slot.setProperty("dragging", False)
        # Qt 不会自动检测动态属性变化 → 强制重评估
        slot.style().unpolish(slot)
        slot.style().polish(slot)

    def _move_slot(self, from_index: int, to_index: int) -> None:
        """把槽从 ``from_index`` 移到 ``to_index``(同时更新 list + 布局 + 选中索引)。

        ``_slot_layout.insertWidget(to_index, slot)`` 会把 slot 插到布局的
        ``to_index`` 位置(布局末尾的 stretch 自动推后,不需要手动 +1)。

        **不在此调** ``_renumber_slots()`` **:拖动期序号保持"过期",只在 release 时
        统一刷新,符合"按下拖动时序号不变"的交互预期(与 Finder / Explorer
        拖动行为一致)。调用方负责 release 时刷新。
        """
        if not (0 <= from_index < len(self._slot_widgets)):
            return
        if not (0 <= to_index < len(self._slot_widgets)):
            return
        if from_index == to_index:
            return

        slot = self._slot_widgets.pop(from_index)
        handle = self._slot_handles.pop(from_index)  # 同步 pop handle
        self._slot_widgets.insert(to_index, slot)
        self._slot_handles.insert(to_index, handle)  # 同步 insert handle
        self._slot_layout.removeWidget(slot)
        self._slot_layout.insertWidget(to_index, slot)

        # 调整 _selected_index(槽在 list 中的位置变了,选中指针要跟着挪)
        if self._selected_index is not None:
            if from_index < to_index:
                # 向下挪:[from, to] 之间的索引都 -1
                if from_index < self._selected_index <= to_index:
                    self._selected_index -= 1
            else:  # from_index > to_index
                # 向上挪:[to, from) 之间的索引都 +1
                if to_index <= self._selected_index < from_index:
                    self._selected_index += 1

        # _last_selected_index 同理挪(否则 _update_selection_style 会用错槽)
        if self._last_selected_index is not None:
            if from_index < to_index:
                if from_index < self._last_selected_index <= to_index:
                    self._last_selected_index -= 1
            else:
                if to_index <= self._last_selected_index < from_index:
                    self._last_selected_index += 1

        self._update_selection_style()

    def _index_at_global_y(self, global_y: int) -> int:
        """根据全局 Y 坐标返回对应的目标槽索引(中心锚定算法)。

        算法:取每个 handle 的**中心 Y** 作为"分隔线"。
        - cursor Y < handle[0] 中心 → 返回 0(最前)
        - handle[i] 中心 <= cursor Y < handle[i+1] 中心 → 返回 i+1
        - cursor Y >= 末位 handle 中心 → 返回 N-1(末尾)

        旧实现用 ``top <= y < bottom``(handle 的精确边界),但 handle 只 32px 宽,
        槽间间隙 (8-16px 间距) cursor 完全不命中 handle,fallback 落到 ``return N-1``
        导致"拖到间隙就瞬移末尾"。中心锚定后,间隙也被正确归到相邻槽。

        用 ``_slot_handles`` 平行列表替 findChild,拖动期每次 move 调,
        O(N×M) → O(N)。
        """
        for i, handle in enumerate(self._slot_handles):
            top_y = handle.mapToGlobal(QPoint(0, 0)).y()
            center_y = top_y + (handle.height() >> 1)
            if global_y < center_y:
                return i
        return len(self._slot_handles) - 1

    # ── 键盘事件(Delete 删除选中) ──────────────────────────

    def keyPressEvent(self, event) -> None:
        """Delete 键:删除当前选中槽。无选中则交给父类处理。"""
        if event.key() == Qt.Key_Delete and self._selected_index is not None:
            self._remove_slot(self._selected_index)
            event.accept()
            return
        super().keyPressEvent(event)

    # ── 数据持久化 ─────────────────────────────────────────

    def _load_data(self):
        """从 DataManager 加载数据并重建 UI 槽。

        尊重持久化的空状态：若 JSON 存的是空列表，重开后保持 0 槽。
        用户可点 + 自行添加。
        """
        raw_list = MA_Automation_DataManager.load()

        # 清空现有槽
        for slot in self._slot_widgets:
            self._slot_layout.removeWidget(slot)
            slot.deleteLater()
        self._slot_widgets.clear()
        self._slot_handles.clear()  # 同步清空 handle 平行列表
        self._last_selected_index = None  # 重置差量状态

        for item_data in raw_list:
            self._add_slot(item_data)

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

    def _save_data(self) -> list[dict]:
        """收集并持久化任务数据,返回收集到的 ``list[dict]`` 供调用方使用。"""
        tasks_data = self._collect_data()
        MA_Automation_DataManager.save(tasks_data)
        return tasks_data

    # ── 执行集成 ───────────────────────────────────────────

    def _on_start(self):
        """Start / Cancel 切换按钮。"""
        if self._running:
            self._cancel_execution()
            return
        self._start_execution()

    def _start_execution(self):
        """收集任务 → 落盘 JSON → 创建 ExecutionEngine → 启动后台执行。

        JSON 仅在 Start 时落盘,关窗不保存。
        语义:JSON = 用户决定执行的任务,不是当前 UI 状态;
        编辑后未点 Start 直接关窗 = 丢弃未执行编辑(有意为之)。
        """
        tasks_data = self._save_data()  # 收集 + 落盘(只此一处)
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

    def _is_slot_empty_at(self, index: int) -> bool:
        """检查指定索引的槽是否为空（仅对 BUTTON_CLICK 类型判断）。

        判定条件：BUTTON_CLICK 类型 + nodePath 和 parmName 都为空字符串。
        索引越界 或 非 BUTTON_CLICK → 返回 False（避免误覆盖其他类型任务）。
        """
        widgets = self._get_button_click_widgets(index)
        if widgets is None:
            return False
        np_le, pn_le = widgets
        return not np_le.text().strip() and not pn_le.text().strip()

    def _get_button_click_widgets(self, index: int) -> tuple[QLineEdit, QLineEdit] | None:
        """定位指定槽的 BUTTON_CLICK 参数 LineEdit。

        返回 ``(nodePath_le, parmName_le)``；任一前置条件不满足返回 ``None``：
          - 索引越界
          - 槽内缺少 ``taskType`` combo / 当前不是 BUTTON_CLICK
          - 缺少 ``paramsStacked`` / 当前 page 为空
          - 缺少 ``nodePath`` / ``parmName`` LineEdit

        统一 ``_is_slot_empty_at`` 和 ``_fill_slot_at`` 的 widget 查找逻辑，
        避免两处镜像的 findChild + None 守卫代码。
        """
        if not (0 <= index < len(self._slot_widgets)):
            return None
        slot = self._slot_widgets[index]

        combo = slot.findChild(QComboBox, "taskType")
        if combo is None or combo.currentIndex() != 0:  # 0 = BUTTON_CLICK
            return None

        stacked = slot.findChild(QStackedWidget, "paramsStacked")
        current_page = stacked.currentWidget() if stacked is not None else None
        if current_page is None:
            return None

        np_le = current_page.findChild(QLineEdit, "nodePath")
        pn_le = current_page.findChild(QLineEdit, "parmName")
        if np_le is None or pn_le is None:
            return None
        return np_le, pn_le

    def _fill_slot_at(self, index: int, data: dict) -> None:
        """用 data 填充指定索引的槽的输入控件（不创建新槽）。

        仅处理 BUTTON_CLICK 类型；其他类型直接 noop（防御性）。
        """
        if data.get("type") != "BUTTON_CLICK":
            return

        widgets = self._get_button_click_widgets(index)
        if widgets is None:
            return
        np_le, pn_le = widgets
        params = data.get("params", {})
        np_le.setText(params.get("node_path", ""))
        pn_le.setText(params.get("parm_name", ""))

    def _find_trailing_empty_slots(self) -> list[int]:
        """从后往前扫描连续空槽（BUTTON_CLICK），返回索引列表（从小到大）。

        "连续"：从末尾往前，遇到第一个非空槽时停止扫描。
        返回从小到大：填充时从前往后顺序消费，**末尾保留空槽**
        （用户可继续手动填，而非末尾被填掉）。

        例：列表 [填, 填, 空, 空, 空] → 返回 [2, 3, 4]。
        """
        result = []
        for i in range(len(self._slot_widgets) - 1, -1, -1):
            if self._is_slot_empty_at(i):
                result.append(i)
            else:
                break
        result.reverse()
        return result

    def _on_auto_fill(self):
        """从当前选中的节点中提取 execute 按钮路径，填入任务列表。

        遍历 hou.selectedNodes()，对每个有 'execute' 参数的节点，
        构造 BUTTON_CLICK 任务：
          - 预扫描连续空槽队列（从后往前），逐个填入（不新增）
          - 空槽用完后仍有节点剩余 → 追加新槽
        无选中节点或没有有效节点时打印提示。

        注意：``_find_trailing_empty_slots`` 只在循环开始前调用一次，
        维护索引队列逐个消费。否则 fill 后 widget text 立即更新，
        循环内重新扫描会把"刚填的槽"误判为非空，导致后续节点走新增分支。
        """
        import hou  # Houdini-only, 放入方法内部

        selected = hou.selectedNodes()
        if not selected:
            print("Auto Fill: 当前无选择节点")
            return

        # 预扫描一次，连续空槽索引队列（从小到大：填充时从前往后消费，
        # **末尾保留** 空槽给用户手动填，详见 _find_trailing_empty_slots 注释）
        empty_iter = iter(self._find_trailing_empty_slots())

        processed = 0
        for node in selected:
            parm = node.parm("execute")
            if parm is None:
                continue
            data = {
                "type": "BUTTON_CLICK",
                "params": {
                    "node_path": node.path(),
                    "parm_name": "execute",
                },
                "enabled": True,
            }
            try:
                idx = next(empty_iter)
                self._fill_slot_at(idx, data)
            except StopIteration:
                # 连续空槽已用完，新增
                self._add_slot(data)
            processed += 1

        if processed > 0:
            print(f"Auto Fill: 已处理 {processed} 个按钮点击任务")
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
        """关闭时清理单例引用,不保存数据(JSON 仅在 Start 时落盘)。"""
        global _window
        _window = None
        super().closeEvent(event)
