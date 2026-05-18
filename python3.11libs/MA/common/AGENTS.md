# MA/common — 共享模块

两个面板（HDR / ShelfTools）的公共基础设施。

## Where to Look

| File | Purpose | Key Classes |
|------|---------|-------------|
| `settings.py` | JSON 配置管理器 | `BaseJsonManager`, `SettingsManager`, `CacheManager`, `ShelfToolsSettingsManager`, `ShelfToolsCacheManager` |
| `filter_manager.py` | HDR 筛选/收藏/最近 | `FilterManager` (property setter 驱动) |
| `styles.py` | Qt 样式常量 | `STYLE_SHEET`, 颜色/组件样式变量 |
| `constants.py` | 全局路径/参数 | `_MA_TOOLS_DIR`, `HDR_EXTENSIONS`, UI 默认值 |
| `animation_helper.py` | 动画辅助 | `animate_widget_height`, `elastic_resize`, `pulse_button` |
| `utils.py` | 工具函数 | `find_ffmpeg`, `_collect_hdr_files` |

## Conventions

- **Class-level caching**: `BaseJsonManager._cache` / `_saved_state` — 类变量，所有实例共享
- **Change detection**: `save()` 比较 `_saved_state == data`，未变更则跳过写入
- **Styles separation**: `styles.py` 定义颜色常量 + 完整 `STYLE_SHEET`，HDR 面板直接引用
- **Property-driven rebuild**: `FilterManager.thumbnails.setter` / `hdr_directory.setter` 自动触发 `_rebuild_indices()`

## Anti-Patterns

- **import hou 不在模块顶部**: 各模块在顶部 try/except ImportError，不应全局依赖 hou
