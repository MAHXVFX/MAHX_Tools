# MA/hdr_library — HDR 环境光库面板

ffmpeg 驱动的 HDR/EXR 缩略图生成 + 网格浏览 + 一键加载到 Houdini 环境光。

## Where to Look

| File | Purpose |
|------|---------|
| `library_panel.py` | 主 UI (614 行): 工具栏、设置面板、滚动网格、状态栏 |
| `thumbnail_manager.py` | 网格管理: QGridLayout 填充、可见范围优化、延迟加载 |
| `thumbnail_worker.py` | QThread 后台: ffmpeg 缩略图生成、进度信号 |
| `thumbnail_widget.py` | 单个缩略图控件: 圆角绘制、收藏星标、右键菜单 |
| `main.py` | 弹窗窗口入口: `Panel()` 函数 + `SavedSizeDialog` 窗口几何记忆 |

## Conventions

- **Async thumbnail gen**: `ThumbnailWorker(QThread)` — `progress` + `finished` 信号
- **Lazy loading**: 根据 `ThumbnailManager.update_visible_range()` 的滚动位置加载/卸载
- **Shared placeholder**: 生成失败的缩略图统一使用 `_placeholder_gray.jpg` (256×256 dark gray)
- **Memory cache**: `ThumbnailManager._pixmap_cache` (上限 500) + 磁盘
- **Window singleton**: `_panel_window` 模块级变量，`Panel()` 复用已打开窗口
- **Settings persist**: `SavedSizeDialog.closeEvent()` 保存几何 + HDR 目录 + 筛选状态

## Anti-Patterns

- **Broad exception in thumbnail gen**: `thumbnail_worker.py` 多处 `except Exception: pass` / `print`
- **Mixed import style**: 部分从 `MA.common.xxx` 导入，部分从 `MA.common.constants` — 应统一
