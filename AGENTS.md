# AGENTS.md

## 概述

Houdini PySide6 工具包，主要功能：
- **HDR 环境光库面板**：管理 HDR 环境光缩略图，一键加载到场景环境光节点
- **MA ShelfTool Pro**：自定义工具架面板，以缩略图展示工具架上的工具，支持点击自动放置和拖拽到 NetworkEditor 定位放置

### 面板入口

| 面板 | 打开方式 |
|---|---|
| HDR 环境光库 | 菜单栏 `MainMenuCommon.xml` → `MAHX.Panel()`；内嵌面板 `MAHDR.pypanel` |
| MA ShelfTools Pro | 内嵌面板 `MAShelfToolPro.pypanel`（Pane Tab 菜单 → MA ShelfTools Pro） |

## 架构

```
MAHX_Tools/
├── MainMenuCommon.xml             # 菜单栏入口（HDR Library 菜单项）
├── toolbar/
│   ├── test.shelf                 # 工具架定义文件（SOP 工具：Lines particles）
│   └── Houdini_Shelf_Tool_Trigger_Guide.md
├── python_panels/
│   ├── MAHDR.pypanel              # HDR 环境光库面板
│   └── MAShelfToolPro.pypanel     # 工具架缩略图面板
└── python3.11libs/MAHX/
    ├── __init__.py                # 导出所有公共接口
    ├── common/
    │   ├── constants.py           # HDR_EXTENSIONS, 参数名, UI 常量
    │   ├── settings.py            # SettingsManager（类级缓存的 JSON 读写）
    │   ├── filter_manager.py      # FilterManager（筛选/收藏/最近/占位图过滤）
    │   ├── styles.py              # Qt 样式表
    │   ├── animation_helper.py    # UI 动画
    │   └── utils.py               # find_ffmpeg(), _collect_hdr_files()
    └── hdr_library/
        ├── main.py                # Panel() 入口, SavedSizeDialog（弹窗模式下 closeEvent 保存设置）
        ├── library_panel.py       # HDRLibraryPanel 主 UI 类（含 _save_on_close / closeEvent 用于嵌入模式）
        ├── thumbnail_worker.py    # ThumbnailWorker QThread（ffmpeg 生成缩略图）
        ├── thumbnail_manager.py   # ThumbnailManager（网格布局/懒加载/虚拟滚动）
        └── thumbnail_widget.py    # HDRThumbnailWidget 单个缩略图控件
```

## MA ShelfTool Pro 设计

### 核心流程

```
toolbar/test.shelf
    ↓ hou.shelves.loadFile()     （启动时加载一次，替换需重启 Houdini）
Houdini Shelf 系统（内存注册）
    ↓ hou.shelves.tool(name)     按工具名称查找
Tool 对象
    ↓ exec(tool.script())        在 kwargs 上下文中执行工具脚本
创建节点 → 定位到 NetworkEditor
```

### 关键数据流

1. **缩略图加载流**：`MAShelfToolPro.pypanel` → `ThumbnailWidget` → 灰色占位图（当前），后续支持自定义 `.jpg/.png` 缩略图
2. **点击触发流**：`mouseReleaseEvent` → `execute_tool({"autoplace": True})` → 自动放置到 NetworkEditor
3. **拖拽触发流**：`mouseMoveEvent` → `QDrag.exec_()` → `_drop_at_cursor()` → `ne.cursorPosition()` → `execute_tool()` 带精确坐标
4. **shelf 加载流**：`ensure_shelf()` → `MAHX.__file__` 定位项目根 → `toolbar/test.shelf` → `hou.shelves.loadFile()`

### 关键陷阱（Shelf Tool 触发）

详见 `toolbar/Houdini_Shelf_Tool_Trigger_Guide.md`

- `hou.shelves` **是模块不是函数**：正确调用 `hou.shelves.shelfSets()`、`hou.shelves.tool(name)`
- **Tool 没有 run()**：只能用 `exec(tool.script())`
- **必须传 `"pane": ne` 到 kwargs**：否则脚本走错分支，不处理坐标
- **`num_args` 必须拉高**：默认 `num_args=1` → hscript 里 `$argc < 2` 会重置 `$arg2/$arg3` 为 0。传 `"outputnodename": ""` 让 `num_args=6`
- **`cursorPosition()` 直接获取网络坐标**：不要自己算 `visibleBounds` + `screenPosition` 映射
- **`sys.exit()` 捕获 `SystemExit`**：脚本中的 `sys.exit()` 抛出 `SystemExit`，不被 `except Exception` 捕获，需单独处理

## 关键数据流（HDR Library）

1. 菜单流：`MainMenuCommon.xml` → `Panel()` → `SavedSizeDialog` 包裹 `HDRLibraryPanel` → `_load_settings()`
2. 内嵌面板流：Pane Tab 菜单 → `MAHDR.pypanel` → `HDRLibraryPanel`（直接返回）→ `_load_settings()`
3. 缩略图加载优先级：缓存(`_try_load_cached_thumbnails`) → 文件系统扫描(`_load_existing_thumbnails`) → 用户手动扫描(`_scan_hdr_files`)
4. 关闭保存：弹窗模式由 `SavedSizeDialog.closeEvent()` 保存；嵌入模式由 `HDRLibraryPanel.closeEvent()` → `_save_on_close()` 保存

## 关键陷阱

### SettingsManager 是类级单例缓存
- `SettingsManager.load()` 返回同一 dict 引用，修改即修改缓存
- `save()` 会与 `_saved_state` 比较，相同则跳过写入
- 同一 Houdini 会话中多次打开面板共享同一缓存

### 关闭保存：两种模式对应不同路径
- **弹窗模式**（`Panel()`）：`SavedSizeDialog.closeEvent()` 保存窗口几何 + 面板设置 + 缩略图缓存
- **嵌入模式**（`MAHDR.pypanel`）：`HDRLibraryPanel.closeEvent()` → `_save_on_close()` 保存面板设置 + 缩略图缓存
- 两者互不干扰：Qt 子控件不会随父对话框触发 `closeEvent`
- `_save_on_close()` 有 `_saved_on_close` 守卫防止重复保存
- 只要 `_filter_mgr.thumbnails` 非空就保存，不依赖 `_thumbnail_cache_dirty`
- 这确保 `is_placeholder` 标记在面板关闭时持久化

### 占位图机制
- `ThumbnailWorker._generate_thumbnail()` 失败时返回共享占位图 `_placeholder_gray.jpg`
- 所有失败的 HDR 共享同一张占位图文件
- `is_placeholder=True` 标记在扫描时写入，通过缓存持久化
- "Hide gray thumbnails" 按 `is_placeholder` 过滤，不检查文件是否存在

### hide_gray 信号处理
- 使用 `toggled` 信号（非 `stateChanged`），专用处理器 `_on_hide_gray_toggled`
- `_update_folder_combo` 和 `_apply_filter` 都接受可选参数，默认回退到 `isChecked()`
- 加载设置期间 `_loading_settings=True` 阻止信号处理器执行保存

## 开发约束

- **无独立测试**：依赖 Houdini 运行时（`import hou`），无法在外部运行
- **Python 3.11**：Houdini 21.0 内置
- **PySide6**：Qt 绑定，信号/槽机制
- **ffmpeg**：缩略图生成依赖 ffmpeg，优先级：打包的 `ffmpeg.exe` → Houdini 的 `hffmpeg` → PATH
- **设置文件** `MAHX_HDR_Library_Settings.json` 已 gitignore，不要提交
- **`_collect_hdr_files`** 只扫描两层（根目录 + 一级子目录）
