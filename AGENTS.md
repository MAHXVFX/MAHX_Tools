# AGENTS.md

## 概述

Houdini PySide6 工具包，主要功能：
- **HDR 环境光库面板**：管理 HDR 环境光缩略图，一键加载到场景环境光节点
- **MA ShelfTools Pro**：自定义工具架面板，以缩略图展示工具架上的工具，支持点击自动放置和拖拽到 NetworkEditor 定位放置

### 面板入口

| 面板 | 打开方式 |
|---|---|
| HDR 环境光库 | 菜单栏 `MainMenuCommon.xml` → `MA.Panel()`；内嵌面板 `MAHDR.pypanel` |
| MA ShelfTools Pro | 内嵌面板 `MAShelfToolPro.pypanel`（Pane Tab 菜单 → MA ShelfTools Pro） |

## 架构

```
MA_Tools/
├── MainMenuCommon.xml             # 菜单栏入口（MA HDR Asset Library 菜单项）
├── toolbar/
│   ├── mahx.shelf                 # 工具架定义文件
│   └── Houdini_Shelf_Tool_Trigger_Guide.md
├── python_panels/
│   ├── MAHDR.pypanel              # HDR 环境光库面板
│   └── MAShelfToolPro.pypanel     # 工具架缩略图面板
└── python3.11libs/MA/
    ├── __init__.py                # 导出所有公共接口
    ├── common/
    │   ├── __init__.py            # 公共模块导出（SettingsManager, CacheManager 等）
    │   ├── constants.py           # 路径常量、HDR_EXTENSIONS、UI 常量
    │   ├── settings.py            # BaseJsonManager + 4 个子类（详见下方）
    │   ├── filter_manager.py      # FilterManager（筛选/收藏/最近/占位图过滤）
    │   ├── styles.py              # Qt 样式表
    │   ├── animation_helper.py    # UI 动画
    │   └── utils.py               # find_ffmpeg(), _collect_hdr_files()
    └── hdr_library/
        ├── main.py                # Panel() 入口, SavedSizeDialog（弹窗模式下 closeEvent 保存）
        ├── library_panel.py       # HDRLibraryPanel 主 UI 类
        ├── thumbnail_worker.py    # ThumbnailWorker QThread（ffmpeg 生成缩略图）
        ├── thumbnail_manager.py   # ThumbnailManager（网格布局/懒加载/虚拟滚动）
        └── thumbnail_widget.py    # HDRThumbnailWidget 单个缩略图控件
```

## 配置文件架构

所有 JSON 配置文件在项目根目录，已 `.gitignore`：

| 文件 | 管理类 | 内容 | 保存时机 |
|---|---|---|---|
| `MA_HDR_Library_Settings.json` | `SettingsManager` | hdr_directory, cache_directory, thumbnail_size, current_filter, recent_hdrs, favorite_hdrs, print_path, hide_gray, window_* | **实时**（改即写） |
| `MA_HDR_Library_Cache.json` | `CacheManager` | thumbnails 路径字典, subfolders, mtime 快照 | **关闭时**（closeEvent） |
| `MA_ShelfTools_Pro_Settings.json` | `ShelfToolsSettingsManager` | thumb_size | **实时**（滑块拖动） |
| `MA_ShelfTools_Pro_Cache.json` | `ShelfToolsCacheManager` | 预留（后续缩略图路径缓存） | 预留 |

### 类层次

```
BaseJsonManager              ← 通用 JSON 读写 + 类级缓存 + diff 跳过写入
  ├── SettingsManager         → HDR 设置（小，实时写）
  ├── CacheManager            → HDR 缓存（大，关闭时写）
  ├── ShelfToolsSettingsManager → ShelfTools 设置（小，实时写）
  └── ShelfToolsCacheManager    → ShelfTools 缓存（大，预留）
```

### 设计原则

- **设置与缓存分离**：小数据（用户偏好）实时写入，大数据（缩略图路径、元数据）只在关闭时写入
- **类级单例**：`load()` 返回同一 dict 引用，修改即改缓存
- **diff 跳过**：`save()` 与 `_saved_state` 比较，无变化则跳过磁盘写入
- **Qt6 滚动条**：`_vscroll` 用 `@property` 实时获取，不能缓存——Qt6 可能重建滚动条

## HDR Library 设计

### 关键数据流

1. **菜单流**：`MainMenuCommon.xml` → `Panel()` → `SavedSizeDialog` → `HDRLibraryPanel` → `_load_settings()`
2. **内嵌面板流**：Pane Tab 菜单 → `MAHDR.pypanel` → `HDRLibraryPanel` → `_load_settings()`
3. **缩略图加载优先级**：缓存(`_try_load_cached_thumbnails`，读 CacheManager) → 文件系统扫描(`_load_existing_thumbnails`) → 用户手动扫描(`_scan_hdr_files`)
4. **关闭保存**：弹窗模式由 `SavedSizeDialog.closeEvent()` 保存（settings + cache 分两次写）；嵌入模式由 `HDRLibraryPanel.closeEvent()` → `_save_on_close()` 保存

### 关键陷阱

#### 关闭保存：两种模式对应不同路径
- **弹窗模式**（`Panel()`）：`SavedSizeDialog.closeEvent()` 保存窗口几何 + 设置 + 缓存
- **嵌入模式**（`MAHDR.pypanel`）：`HDRLibraryPanel.closeEvent()` → `_save_on_close()` 保存设置 + 缓存
- 两者互不干扰：Qt 子控件不会随父对话框触发 `closeEvent`
- `_save_on_close()` 有 `_saved_on_close` 守卫防止重复保存
- 只要 `_filter_mgr.thumbnails` 非空就保存缓存，不依赖 `_thumbnail_cache_dirty`
- 这确保 `is_placeholder` 标记在面板关闭时持久化

#### 占位图机制
- `ThumbnailWorker._generate_thumbnail()` 失败时返回共享占位图 `_placeholder_gray.jpg`
- 所有失败的 HDR 共享同一张占位图文件
- `is_placeholder=True` 标记在扫描时写入，通过缓存持久化
- "Hide gray thumbnails" 按 `is_placeholder` 过滤，不检查文件是否存在

#### hide_gray 信号处理
- 使用 `toggled` 信号（非 `stateChanged`），专用处理器 `_on_hide_gray_toggled`
- `_update_folder_combo` 和 `_apply_filter` 都接受可选参数，默认回退到 `isChecked()`
- 加载设置期间 `_loading_settings=True` 阻止信号处理器执行保存

## MA ShelfTools Pro 设计

### 核心流程

```
toolbar/*.shelf
    ↓ hou.shelves.loadFile()     （启动时加载一次，替换需重启 Houdini）
Houdini Shelf 系统（内存注册）
    ↓ hou.shelves.tool(name)     按工具名称查找
Tool 对象
    ↓ exec(tool.script())        在 kwargs 上下文中执行工具脚本
创建节点 → 定位到 NetworkEditor
```

### 关键数据流

1. **工具名称加载流**：模块加载时 `scan_tool_names()` → 正则解析 `toolbar/*.shelf` 中的 `<tool name="...">`（纯文件操作，不调 Houdini API）
2. **点击触发流**：`mouseReleaseEvent` → `execute_tool({"autoplace": True})` → 自动放置到 NetworkEditor
3. **拖拽触发流**：`mouseMoveEvent` → `QDrag.exec_()` → `_drop_at_cursor()` → `ne.cursorPosition()` → `execute_tool()` 带精确坐标
4. **shelf 加载流**：`ensure_shelves()` → 扫描 `toolbar/*.shelf` → 逐个 `hou.shelves.loadFile()`
5. **缩略图大小设置流**：滑块拖动 → `_on_size_changed()` → `ShelfToolsSettingsManager.update("thumb_size", value)` 实时保存

### 缩略图显示
- 正方形 1:1，圆角 `size // 8`，灰色占位图（后续支持自定义 `.jpg/.png`）
- 滑块可调大小（70~250px），实时保存到 `ShelfToolsSettingsManager`
- 名称在缩略图下方，字号随大小缩放

### 关键陷阱（Shelf Tool 触发）

详见 `toolbar/Houdini_Shelf_Tool_Trigger_Guide.md`

- `hou.shelves` **是模块不是函数**：正确调用 `hou.shelves.shelfSets()`、`hou.shelves.tool(name)`
- **Tool 没有 run()**：只能用 `exec(tool.script())`
- **必须传 `"pane": ne` 到 kwargs**：否则脚本走错分支，不处理坐标
- **`num_args` 必须拉高**：默认 `num_args=1` → hscript 里 `$argc < 2` 会重置 `$arg2/$arg3` 为 0。传 `"outputnodename": ""` 让 `num_args=6`
- **`cursorPosition()` 直接获取网络坐标**：不要自己算 `visibleBounds` + `screenPosition` 映射
- **`sys.exit()` 捕获 `SystemExit`**：脚本中的 `sys.exit()` 抛出 `SystemExit`，不被 `except Exception` 捕获，需单独处理

## 开发约束

- **无独立测试**：依赖 Houdini 运行时（`import hou`），无法在外部运行
- **Python 3.11**：Houdini 21.0 内置
- **PySide6**：Qt 绑定，信号/槽机制
- **ffmpeg**：缩略图生成依赖 ffmpeg，优先级：打包的 `ffmpeg.exe` → Houdini 的 `hffmpeg` → PATH
- **配置文件均已 `.gitignore`**：4 个 JSON（settings × 2 + cache × 2），不要手动提交
- **`_collect_hdr_files`** 只扫描两层（根目录 + 一级子目录）
