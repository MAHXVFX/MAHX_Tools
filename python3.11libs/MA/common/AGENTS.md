# MA/common — 共享模块

两个面板（HDR / ShelfTools）的公共基础设施。

## Where to Look

| File | Purpose | Key Classes |
|------|---------|-------------|
| `settings.py` | JSON 配置管理器 | `BaseJsonManager`, `SettingsManager`, `CacheManager`, `ShelfToolsSettingsManager` (收藏/筛选/路径筛选/额外shelf路径/路径命名/备注延迟), `ShelfToolsCacheManager` (图标/备注/标签), `BuiltinToolsCacheManager` |
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
- **Builtin tools config**: `BuiltinToolsCacheManager` 读取 `builtin_tools/builtin_tools.json`（图标/标签），备注从 `builtin_tools/notes/{unique_id}.md` 读取，只读，随项目提交
- **Extra shelf paths**: `ShelfToolsSettingsManager.get_extra_shelf_paths()` 支持用户添加额外 shelf 目录，去重（忽略大小写/尾部斜杠），`path_prefix()` 用 MD5 哈希生成前缀
- **Path naming**: `ShelfToolsSettingsManager.get_path_name()` / `set_path_name()` / `remove_path_name()` 支持为额外 shelf 路径设置自定义中文名称，命名存储在 `shelf_path_names` 字段
- **Path filter persistence**: `ShelfToolsSettingsManager.get_path_filter()` / `set_path_filter()` 持久化路径筛选状态，内置/默认使用相对标识符（`builtin`/`default`），避免存储绝对路径
- **Notes hover delay**: `ShelfToolsSettingsManager.get_notes_show_delay()` / `set_notes_show_delay()` 控制鼠标悬停到备注面板出现的延迟（ms），默认 800，范围 [100, 2000]
- **Tag management**: `ShelfToolsCacheManager.get_tags()` / `set_tags()` / `add_tag()` / `remove_tag()` / `get_all_tags()` 支持为工具添加标签，内置工具标签从 `builtin_tools.json` 读取

## Anti-Patterns

- **import hou 不在模块顶部**: 各模块在顶部 try/except ImportError，不应全局依赖 hou
