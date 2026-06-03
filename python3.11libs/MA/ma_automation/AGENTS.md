# MA/ma_automation — 自动化批处理工具

可配置任务列表，按顺序执行 Houdini 节点按钮、Flipbook 拍屏、HomeAssistant Webhook。
Qt 面板 UI + JSON 持久化 + QThread 后台执行。

## Where to Look

| File | Purpose | Key Classes |
|------|---------|-------------|
| `__init__.py` | 公共 API 导出 | 顶层立即导出类型/引擎；`show_automation_window` 走 `__getattr__` 懒加载（避免无 PySide6 环境 ImportError）|
| `task_types.py` | 任务类型定义 | `TaskType` 枚举（3 种）、`ButtonClickParams` / `FlipbookParams` / `HomeAssistantParams` dataclass、`TaskItem` 容器（`to_dict` / `from_dict`）|
| `data_manager.py` | JSON 持久化 | `MA_Automation_DataManager`（全部 `@classmethod`），路径 `$HIP/MA Automation/json/{filename}.json`（`filename=None` 默认 `MA_Automation`），fallback 到 `tempfile.gettempdir()`；`list_configs()` 列配置目录下所有 .json basename |
| `execution_engine.py` | 后台执行器 | `ExecutionEngine(QThread)`，3 个 Signal（`task_started` / `task_completed` / `all_completed`），Houdini API 经 `hdefereval.executeDeferred` 派发主线程 |
| `styles.py` | 样式常量 | `STYLE_SHEET` 字符串（与 `hdr_library/` / `shelf_tool_pro/` 拆分 styles.py 的项目约定保持一致）|
| `automation_window.py` | 主窗口 UI | `AutomationWindow(QDialog)` + 模块级 `_window` 单例；含 `_create_slot_widget` / `_get_button_click_widgets` / `_is_slot_empty_at` / `_fill_slot_at` / `_find_trailing_empty_slots` / `_on_auto_fill` |
| `tests/` | 单元测试 | 4 个测试文件 + `_pyside_mock.py` 模拟 PySide6（无 Houdini 环境跑测）|

## Conventions

- **3 种任务类型**：`BUTTON_CLICK`（节点参数按钮）、`FLIPBOOK`（视口拍屏）、`HOME_ASSISTANT`（Webhook POST），对应 `TaskType` 枚举值
- **Singleton QDialog**：模块级 `_window` + `isVisible()` 判定；二次打开时 `raise_()` + `activateWindow()` 激活；窗口挂到 Houdini 主窗口下（`parent=hou.qt.mainWindow()`），与 `hdr_library/main.py` 同款做法
- **Win32 窗口样式（保持在前）**：`__init__` 中 `setWindowFlags(Qt.Window)` 之后调用 `_apply_window_flags(self)`，通过 `ctypes.windll` 设置 `WS_EX_APPWINDOW` (0x00040000) 扩展样式，标记窗口为独立应用窗口；与 Houdini 父子关系配合，确保激活 Houdini 时面板不被主窗口遮挡；同时 `SetCurrentProcessExplicitAppUserModelID('MA.Automation.1')` 让任务栏分组正确。与 `hdr_library/main.py` 同款实现（仅 AppUserModelID 不同）
- **数据持久化**：所有槽状态序列化为 `list[dict]`，**仅在点击 Start 时落盘**（`_start_execution` → `_save_data`），关窗不保存。语义：JSON = 用户决定执行的任务，不是当前 UI 状态；编辑后未点 Start 直接关窗 = 丢弃未执行编辑（有意为之）。加载在 `__init__._load_data()`
  - **副作用契约**：`DataManager` 三方法严格分离副作用 —— `get_data_path()` 纯计算不创建目录、`load()` 纯只读（文件/目录不存在时返回 `[]`，不创建任何东西）、`save()` 是**唯一**允许创建配置目录的入口（`os.makedirs(exist_ok=True)` 在写入前）。这保证"打开面板 + 编辑 + 关闭 = 0 文件副作用"，配置目录和 JSON 文件只在点 Start 时才出现
  - **多文件支持**:`get_data_path(filename)` / `load(filename)` / `save(data, filename)` 三方法均接受可选文件名(无 `.json` 后缀),`filename=None` 走默认 `MA_Automation.json`(完全向后兼容)。配合 `list_configs()` 列出配置目录下所有 `.json` 文件 basename(无后缀,sorted,纯只读不创建目录),让 UI 提供"可编辑配置下拉"——用户可选已有配置 / 键入新名 + Start 创建新文件
- **Houdini 隔离**：`import hou` / `import hdefereval` / `import requests` 全部 try/except；测试/非 Houdini 环境可正常 import 模块
- **线程安全**：`ExecutionEngine.run()` 是 QThread 内部循环；Houdini API 调用经 `_run_deferred()` → `hdefereval.executeDeferred` + `threading.Event` 同步等待；Webhook 是纯网络请求，不需派发
- **可取消**：`cancel()` 置 `_cancelled` 标志，`run()` 在任务间隙（`msleep(100)`）检查；Start 按钮在 Start / 取消 文案间切换
- **`__getattr__` 懒加载**：`__init__.py` 顶层不导入 PySide6 依赖的 `automation_window`，避免 IDE/测试环境误触发 GUI
- **路径 fallback**：`$HIP` 不可用时降级到 `tempfile.gettempdir()`，保证测试环境可写
- **Flipbook 路径占位符**：`output_path` 中 `#date` → `YYYYMMDD`、`#time` → `HHMMSS`（`ExecutionEngine._execute_flipbook`）
- **`dl_Submit` 特殊处理**：`parm_name == "dl_Submit"` 时按钮按下后自动 `hou.hipFile.save()`（`ExecutionEngine._execute_button_click`）
- **样式**：`STYLE_SHEET` 字符串集中定义在 `styles.py`，复用项目暗色主题 `#18181b` / `#0d6399`；任务槽卡片化用 `QWidget#taskSlot { background-color: #252528; }`（**直角无圆角**）+ `setAutoFillBackground(True)`；关键 objectName：`startBtn`（蓝色 Start 按钮）、`addBtn` / `removeBtn`（± 任务槽增减，padding 8px、字号 16px）、`taskSlot`（任务槽卡片容器）、`taskSlotHandle`（序号手柄，单击选中 / 按住拖动重排）
- **拖动重排 + 选中删除**：序号区是 `_SlotHandle(QLabel)` 子类，发送 3 个 Signal (`handlePressed` / `Moved` / `Released`)。`AutomationWindow` 通过信号处理：单击 → `_select_slot(index)` 高亮；按住超过 5px 阈值后激活拖动 → `_move_slot(from, to)` 实时换位；松开 → 结束。选中状态由 `QWidget#taskSlot[selected="true"]` 动态属性 + 蓝色手柄文字 (`#0d6399`) 表达。`Delete` 键在 `keyPressEvent` 中删除当前选中槽。所有路径都会调 `_renumber_slots()` 更新序号文字
- **屏蔽 hover 滚轮改值 `_NoWheelComboBox`**：任务槽内 combo 用 `_NoWheelComboBox(QComboBox)` 子类，override `wheelEvent` 调 `event.ignore()`（不调 super）。原因：默认 `QComboBox.wheelEvent` 会循环选项，误触率高（用户想滚动任务列表却改了任务类型）。`event.ignore()` 让事件穿透到父 `QScrollArea` 自然接管滚动。`_create_slot_widget` 全部用此子类，不要直接 `QComboBox()`
- **`clicked.connect` 必须 lambda 包装**：`QPushButton.clicked` 是带 `bool` 参数的信号（`clicked(checked: bool)`），直接 `connect(self.method)` 会把 `False` 当作第一个位置参数传给 method。**正确做法**：`btn.clicked.connect(lambda: self.method())`。`_build_ui` 中 5 个按钮全部遵循此约定
- **`startBtn` 必须 `setAutoDefault(False)` + `setDefault(False)`**:`QDialog` 默认 Enter 触发 default 按钮,而 `QPushButton` 默认 `autoDefault=True`,用户在可编辑 `_config_combo` 键入新名按 Enter 提交文字时,会被错误地转成 Start 触发。**要求 Start 只能手动鼠标点击**(键盘 Enter 不应触发任何执行动作,只是 commit combo 文本)。`autoFill` / `clear` / `+` / `-` 同样建议关闭 autoDefault,保持一致性
- **槽卡片锁高 `_create_slot_widget`**：`slot.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)`。`QScrollArea` 用 `setWidgetResizable(True)` 时会强制容器高度 = 视口高度,默认 `Preferred` 会让单个槽撑满空间;`Fixed` 强制 `sizeHint` (~42px) 紧凑布局,槽数多少都一致
- **`_get_button_click_widgets` 统一 widget 查找**：`_is_slot_empty_at` 和 `_fill_slot_at` 通过该 helper 取单字段 ``parmPath_le``(UI 层把 ``node_path`` + ``parm_name`` 合并显示,数据收集时再拆分),避免两处镜像的 `findChild` + `None` 守卫。Auto Fill 子系统(槽定位 / 填充)任何新增需求都应先扩此 helper
- **Auto Fill 末尾保留**：`_find_trailing_empty_slots` 返回索引列表（**从小到大**），使填充从前往后消费、**末尾空槽保留**给用户手动填。这与"贪婪追加到末尾"的直觉相反，是有意的设计选择
- **Auto Fill 静默**:`_on_auto_fill` 无 print / 无 logger / 无弹窗,所有路径(无选中 / 无有效节点 / 正常完成)都静默返回。用户不要任何提醒。测试用 `mock_print.assert_not_called()` 锁死
- **`_slot_widgets` / `_slot_handles` 平行列表契约**:两个 list 同长、同顺序、同生命周期。任何增/删/清空槽的代码必须**同步**操作两个列表,漏掉 `clear` 会让 `_renumber_slots` 拿到已 `deleteLater()` 的 handle 调 `setText` → `RuntimeError: Internal C++ object (_SlotHandle) already deleted`。`_add_slot` / `_remove_slot` / `_on_clear` 都遵守契约;回归测试 `test_on_clear_clears_handles_in_sync` 锁死
- **Houdini 拖入支持 `_ParmPathLineEdit`**:parmPath 字段用 `_ParmPathLineEdit(QLineEdit)` 子类(不要直接 `QLineEdit()`),接受 Houdini 参数面板拖入 —— 行为对齐 Houdini Python shell:拖按钮产生 `hou.parm('/obj/.../parm')` 表达式,本控件识别后**只填纯路径**(`/obj/.../parm`,剥 wrapper)。实现:`setAcceptDrops(True)` + override `dragEnterEvent` / `dragMoveEvent` / `dropEvent`,文本提取走 module-level helper `_extract_parm_path`(单/双引号 + 前后空白容错,纯路径原样返回,空串返回空)
- **点击空白处取消任务槽选中(单路径 + walk-up)**:`AutomationWindow` override `mousePressEvent` 单点实现"点空白 deselect",对齐 Houdini 主窗口风格(用 Delete 键连删多个槽时,先 deselect 再选下一个)。
  - **核心实现**:`mousePressEvent` 用 `QApplication.widgetAt(event.globalPos())` 拿全局最顶层 widget,再调 `_is_widget_on_slot` 沿 `widget.parent()` 父链 walk-up 判定。**不用 `childAt`** —— `childAt` 只看**直接子**,点滚动区里 `slot_container` 的 stretch 留白时会被 `QScrollArea`(直接子)拦住,误判"在子上"不 deselect
  - **`_is_widget_on_slot` helper**:`while widget is not None` 沿父链 walk,任一节点是 `self._slot_widgets` 中某 slot(`is` identity 比对)即返回 True。slot 上的子 widget(手柄 / combo / line edit / 卡片空隙)走 walk-up 必经过 slot → True;滚动区空白(父链是 `slot_container → viewport → scroll_area → dialog`,**不经过**任何 slot)→ False
  - **统一契约**:只响应左键 + 有选中态;无选中 / 右键都 no-op。**eventFilter 已移除**(本轮从 viewport 撤掉 `installEventFilter` + `AutomationWindow.eventFilter` override),dialog 的 `mousePressEvent` 单点足够。`self._scroll_area` 仍是成员但仅用于布局(不参与 click 处理)。回归测试 `TestClickDeselect` 7 个 case(行为 + 源码契约)+ `TestIsWidgetOnSlot` 9 个 case(walk-up 边界)共 16 个锁死
- **可编辑配置下拉 `_config_combo`**:工具栏在 `startBtn` **前**方放一个 `QLabel("配置:")` + `QComboBox`(`setEditable(True)` + `setInsertPolicy(NoInsert)` + `setPlaceholderText("选择 / 键入配置名")`),让用户选择/键入配置文件名。
  - **下拉内容**:`MA_Automation_DataManager.list_configs()` 返回的配置目录下所有 `.json` 文件 basename(**无后缀**),按字典序 sorted,排除子目录/非 .json 文件。**不验证 JSON 有效性**(空 / 损坏文件也列出,由 `load()` 容错)
  - **选 vs 键入**:**选择**已有项(`currentIndexChanged`)→ 立即重新加载该文件覆盖面板;**键入**新名(无匹配项)→ **不立即加载**,`Start` 时 `_save_data` 把当前面板状态写到 `{name}.json`(不存在则创建;键入空 / 全空白 / 含路径分隔符 → fall back 到默认 `MA_Automation.json`)
  - **状态同步**:`_current_config_name` 跟踪"当前加载的文件名"(`__init__` 默认 `"MA_Automation"`)。`_load_data` 先调 `_refresh_config_dropdown` 再 `load(self._current_config_name)`;`_save_data` 先保存到 `_get_save_target_name()` 决定的 filename,再更新 `_current_config_name` + 刷新下拉(让新文件出现在列表中)
  - **关键契约**:`_refresh_config_dropdown` **必须** `blockSignals(True)` 包住 `clear()` / `addItems()` / `setCurrentIndex()`,否则 `setCurrentIndex` 触发 `currentIndexChanged` → `_on_config_changed` → `_load_data` 死循环。当前配置名不在列表中时**不强制切换**(`setCurrentIndex` 不调),避免覆盖用户已键入但未保存的新名
  - **样式突出**(防暗色主题看不见):`_config_label` 蓝色加粗(`#0d6399`)+ `_config_combo` 在 `styles.py` 有专属 `QComboBox#configCombo` 段(2px 蓝色边框 + 透明下拉按钮区 + SVG 图标由 combo-level stylesheet 注入)。**不可拆 label/combo** —— label 是控件用途的显式标识,移除会让裸 `QComboBox` 与其他 QComboBox 混淆
  - **下拉图标 SVG 注入**:`python3.11libs/MA/icons/drop down button.svg` 蓝色圆+下箭头,绝对路径在 `automation_window.py` 顶部用 `Path(__file__).resolve().parent.parent / "icons"` 计算后注入到 combo 级 stylesheet(`self._config_combo.setStyleSheet(_CONFIG_COMBO_ICON_STYLE)`)。**不在 styles.py 写死路径** —— Houdini 启动 CWD 不固定,相对路径会失效;绝对路径 + combo 级覆盖是唯一可靠方案
  - **回归测试**:`TestConfigComboSaveTarget` 9 case(sanitize)+ `TestConfigComboRefresh` 5 case + `TestConfigComboSelectionChange` 3 case + `TestSaveUsesConfigName` 4 case + `TestConfigComboSourceContract` 5 case(源码契约:combo 存在 / 3 helper / label 存在且在 combo 前 / styles.py 专属样式 / **SVG 文件存在 + Path(__file__) 注入**)+ `TestConfigFileSelection` 17 case(DataManager 层),共 **43 个 case** 锁死
  - **`_save_data` 失败不更新状态**:`MA_Automation_DataManager.save()` 返回 `False`(磁盘满 / 权限 / OS 拒绝保留名)→ `logger.warning("MA Automation: 保存失败 filename=...")` + `return tasks_data`。**不**更新 `_current_config_name`、**不**调 `_refresh_config_dropdown`。意图:让用户保留旧状态可重试,而不是"假装成功"导致后续 `_load_data` 加载错的文件。`save()` 仍被调用(数据已 `_collect_data` 完,即使失败也记录到日志)。回归测试 `TestSaveUsesConfigName.test_save_failure_does_not_update_state` + `TestConfigComboEndToEnd.test_save_failure_flow` 双锁
  - **`_get_save_target_name` REJECT 清单**:键入文件名 sanitize 三类 REJECT 返回 `None`(让 save 端 fall back 到默认 `MA_Automation.json`):
    1. **Windows 保留名** `text.upper() in _WINDOWS_RESERVED`(`CON/PRN/AUX/NUL/COM1-9/LPT1-9`,大小写不敏感)—— 源码顶部 `frozenset` 定义
    2. **NUL 字节** `"\x00" in text` —— POSIX 文件名拒绝
    3. **纯点号** `text.replace(".", "") == ""` —— 避免 `....json` 怪文件
    另三类 KEEP 原样透传(让 save 端 / OS 处理):前导点 `.hidden`(Unix 隐藏但 list_configs 仍会列出)、超长名 250 字符、中段 `\n`/`\t`。`re.search(r'[\\/:*?"<>|\x00]', text)` 是更激进的策略,但项目选"OS 可能能救"原则(让 save 端报真实错误而非静默改名)
- **设置面板 `_open_settings`**:工具栏 `startBtn` 右侧放 `settings_btn`（`objectName="settingsBtn"`），点击弹出 `QDialog`。
  - **选项**:"将日志输出到磁盘" checkbox，勾选后执行日志保存到 `$HIP/MA Automation/logs/` 目录
  - **日志路径**:`YYYYMMDDHHMM.log`（精确到分钟），避免同名覆盖
  - **日志头部**:执行前写入任务列表摘要（类型、启用状态、参数详情）
  - **设置持久化**:`MA_Automation_DataManager.load_settings()` / `save_settings()` 读写 JSON 中 `settings` 字段，与 `tasks` 并列存储
  - **加载时机**:`__init__` 中 `_load_data()` 之后调 `_load_settings()`，确保 `_current_config_name` 已确定

## Anti-Patterns

- **print() 而非 logger**：UI 执行回调（`_on_task_started` / `_on_task_completed` / `_on_all_completed`）用 `print()`(用户要看执行进度,刻意保持)。Auto Fill 改用**完全静默**(无 print 无 logger)。`logging.getLogger("MA")` 仅在模块级 + 业务错误场景使用
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
