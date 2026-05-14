# AGENTS.md

## 概述

Houdini PySide6 工具包，主要功能是 HDR 环境光库面板。支持两种打开方式：
- 菜单栏：`MainMenuCommon.xml` → `MAHX.Panel()`
- 内嵌面板：`python_panels/MAHDR.pypanel` → `HDRLibraryPanel`

## 架构

```
MAHX_Tools/
├── MainMenuCommon.xml             # 菜单栏入口（HDR Library 菜单项）
├── python_panels/
│   └── MAHDR.pypanel              # Houdini 内嵌面板入口（Pane Tab 菜单）
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

## 关键数据流

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
