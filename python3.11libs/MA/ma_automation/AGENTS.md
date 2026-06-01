# MA/ma_automation — 自动化批处理工具

可配置任务列表，按顺序执行 Houdini 节点按钮、Flipbook 拍屏、HomeAssistant Webhook。
Qt 面板 UI + JSON 持久化 + QThread 后台执行。

## Where to Look

| File | Purpose | Key Classes |
|------|---------|-------------|
| `__init__.py` | 公共 API 导出 | 顶层立即导出类型/引擎；`show_automation_window` 走 `__getattr__` 懒加载（避免无 PySide6 环境 ImportError）|
| `task_types.py` | 任务类型定义 | `TaskType` 枚举（3 种）、`ButtonClickParams` / `FlipbookParams` / `HomeAssistantParams` dataclass、`TaskItem` 容器（`to_dict` / `from_dict`）|
| `data_manager.py` | JSON 持久化 | `MA_Automation_DataManager`（全部 `@classmethod`），路径 `$HIP/MAJson/MA_Automation.json`，fallback 到 `tempfile.gettempdir()` |
| `execution_engine.py` | 后台执行器 | `ExecutionEngine(QThread)`，3 个 Signal（`task_started` / `task_completed` / `all_completed`），Houdini API 经 `hdefereval.executeDeferred` 派发主线程 |
| `styles.py` | 样式常量 | `STYLE_SHEET` 字符串（与 `hdr_library/` / `shelf_tool_pro/` 拆分 styles.py 的项目约定保持一致）|
| `automation_window.py` | 主窗口 UI | `AutomationWindow(QDialog)` + 模块级 `_window` 单例；含 `_create_slot_widget` / `_get_button_click_widgets` / `_is_slot_empty_at` / `_fill_slot_at` / `_find_trailing_empty_slots` / `_on_auto_fill` |
| `tests/` | 单元测试 | 4 个测试文件 + `_pyside_mock.py` 模拟 PySide6（无 Houdini 环境跑测）|

## Conventions

- **3 种任务类型**：`BUTTON_CLICK`（节点参数按钮）、`FLIPBOOK`（视口拍屏）、`HOME_ASSISTANT`（Webhook POST），对应 `TaskType` 枚举值
- **Singleton QDialog**：模块级 `_window` + `isVisible()` 判定；二次打开时 `raise_()` + `activateWindow()` 激活；窗口挂到 Houdini 主窗口下（`parent=hou.qt.mainWindow()`），与 `hdr_library/main.py` 同款做法
- **Win32 窗口样式（保持在前）**：`__init__` 中 `setWindowFlags(Qt.Window)` 之后调用 `_apply_window_flags(self)`，通过 `ctypes.windll` 设置 `WS_EX_APPWINDOW` (0x00040000) 扩展样式，标记窗口为独立应用窗口；与 Houdini 父子关系配合，确保激活 Houdini 时面板不被主窗口遮挡；同时 `SetCurrentProcessExplicitAppUserModelID('MA.Automation.1')` 让任务栏分组正确。与 `hdr_library/main.py` 同款实现（仅 AppUserModelID 不同）
- **数据持久化**：所有槽状态序列化为 `list[dict]`，关闭时 `closeEvent` 自动 `_save_data()`；加载在 `__init__._load_data()`
- **Houdini 隔离**：`import hou` / `import hdefereval` / `import requests` 全部 try/except；测试/非 Houdini 环境可正常 import 模块
- **线程安全**：`ExecutionEngine.run()` 是 QThread 内部循环；Houdini API 调用经 `_run_deferred()` → `hdefereval.executeDeferred` + `threading.Event` 同步等待；Webhook 是纯网络请求，不需派发
- **可取消**：`cancel()` 置 `_cancelled` 标志，`run()` 在任务间隙（`msleep(100)`）检查；Start 按钮在 Start / 取消 文案间切换
- **`__getattr__` 懒加载**：`__init__.py` 顶层不导入 PySide6 依赖的 `automation_window`，避免 IDE/测试环境误触发 GUI
- **路径 fallback**：`$HIP` 不可用时降级到 `tempfile.gettempdir()`，保证测试环境可写
- **Flipbook 路径占位符**：`output_path` 中 `#date` → `YYYYMMDD`、`#time` → `HHMMSS`（`ExecutionEngine._execute_flipbook`）
- **`dl_Submit` 特殊处理**：`parm_name == "dl_Submit"` 时按钮按下后自动 `hou.hipFile.save()`（`ExecutionEngine._execute_button_click`）
- **样式**：`STYLE_SHEET` 字符串集中定义在 `styles.py`，复用项目暗色主题 `#18181b` / `#0d6399`；任务槽卡片化用 `QWidget#taskSlot { background-color: #252528; border-radius: 6px; }` + `setAutoFillBackground(True)`；关键 objectName：`startBtn`（蓝色 Start 按钮）、`addBtn` / `removeBtn`（± 任务槽增减，padding 8px、字号 16px）、`taskSlot`（任务槽卡片容器）
- **`clicked.connect` 必须 lambda 包装**：`QPushButton.clicked` 是带 `bool` 参数的信号（`clicked(checked: bool)`），直接 `connect(self.method)` 会把 `False` 当作第一个位置参数传给 method。**正确做法**：`btn.clicked.connect(lambda: self.method())`。`_build_ui` 中 5 个按钮全部遵循此约定
- **`_get_button_click_widgets` 统一 widget 查找**：`_is_slot_empty_at` 和 `_fill_slot_at` 通过该 helper 取 `(np_le, pn_le)`，避免两处镜像的 `findChild` + `None` 守卫。Auto Fill 子系统（槽定位 / 填充）任何新增需求都应先扩此 helper
- **Auto Fill 末尾保留**：`_find_trailing_empty_slots` 返回索引列表（**从小到大**），使填充从前往后消费、**末尾空槽保留**给用户手动填。这与"贪婪追加到末尾"的直觉相反，是有意的设计选择

## Anti-Patterns

- **print() 而非 logger**：UI 回调（`_on_task_started` / `_on_task_completed` / `_on_all_completed`）和 Auto Fill 提示全部 `print()`，与项目统一的 `logging.getLogger("MA")` 风格不一致。已确认保持现状（按用户要求）
- **大量 `findChild(...)` 反查 UI 控件**：`_collect_data()` 通过 `findChild(QComboBox, "taskType")` 等按 objectName 找子控件收集数据；正确做法是 slot 控件保存控件引用为属性。可读性差但当前可用。**注**：Auto Fill 子系统（`_is_slot_empty_at` / `_fill_slot_at`）已通过 `_get_button_click_widgets` helper 集中此模式，仅 `_collect_data` 仍保留散落调用（待后续重构）
- **直接 `clicked.connect(self.method)`**：会把 Qt 的 `clicked(bool)` 信号 `False` 当成 `method` 的第一个位置参数（典型 bug：`method(data: dict)` 收到 `False` → TypeError）。**必须** lambda 包装或 `functools.partial`
- **`closeEvent` 内 `super().closeEvent(event)` 之前清单例**：`_window = None` 在 `super().closeEvent()` 之前调用，依赖 Qt 删除流程不触发额外回调；若 closeEvent 中出现异常，状态可能不一致
- **`__pycache__` 提交**：模块目录下有 4 个 `.pyc` 已提交（与项目其他模块一致，未 `.gitignore` 排除）

## Tests

测试在 Houdini 外部即可运行（`_pyside_mock.py` 桩 PySide6，`hou` / `hdefereval` 走 try/except）：

- `tests/_pyside_mock.py` — PySide6 桩（202 行）
- `tests/test_task_types.py` — TaskType/Params/TaskItem 序列化往返
- `tests/test_data_manager.py` — JSON 读写、$HIP fallback、损坏容错
- `tests/test_execution_engine.py` — QThread 行为、取消标志、executeDeferred 派发
- `tests/test_integration.py` — 端到端：UI → DataManager → Engine
