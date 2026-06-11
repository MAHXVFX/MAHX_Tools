# MA/hdr_library — HDR 环境光库面板

ffmpeg 驱动的 HDR/EXR 缩略图生成 + 网格浏览 + 一键加载到 Houdini 环境光。

## Where to Look

| File | Purpose |
|------|---------|
| `library_panel.py` | 主 UI: 工具栏、设置面板、滚动网格、状态栏 |
| `thumbnail_manager.py` | 网格管理: QGridLayout 填充、可见范围优化、延迟加载 |
| `thumbnail_worker.py` | QThread 后台: ffmpeg 缩略图生成、进度信号 |
| `thumbnail_widget.py` | 单个缩略图控件: 圆角绘制、收藏星标、右键菜单 |
| `main.py` | 弹窗窗口入口: `Panel()` 函数 + `SavedSizeDialog` 窗口几何记忆 |
| `__init__.py` | 公共 API 导出: `HDRLibraryPanel` + `Panel` |

## Conventions

- **Async thumbnail gen**: `ThumbnailWorker(QThread)` — `progress` + `finished` + `error` 信号
- **Lazy loading**: `ensure_loaded()` / `unload()` 方法，根据 `ThumbnailManager.update_visible_range()` 的滚动位置加载/卸载
- **Shared placeholder**: 生成失败的缩略图统一使用 `_placeholder_gray.jpg` (256×256 dark gray)
- **Memory cache**: `ThumbnailManager._pixmap_cache` (上限 500) + 磁盘
- **Window singleton**: `_panel_window` 模块级变量，`Panel()` 复用已打开窗口（处理 `RuntimeError`）
- **Settings/Cache 分离**: `SettingsManager`（小数据实时写）+ `CacheManager`（大数据关闭时写）
- **Settings persist**: `SavedSizeDialog.closeEvent()` 保存几何 + HDR 目录 + 筛选状态
- **圆角绘制**: 不用 `border-radius`（DPI 兼容问题），用 `QPainterPath` + `setClipPath` 代码绘制
- **动画助手**: 使用 `elastic_resize` 实现设置面板的展开/收起动画
- **FilterManager 集成**: 筛选/收藏/最近使用逻辑，property setter 自动重建索引

## Anti-Patterns

- **Broad exception in thumbnail gen**: `thumbnail_worker.py` 第 43、87 行 `except Exception: pass` / `print`
- **Mixed import style**: 部分从 `MA.common.xxx` 导入，部分从 `MA.common.constants` — 应统一
- **Module-level singleton**: `_panel_window` 在 `main.py` 中 — 只应有一个实例，需处理 `RuntimeError`
