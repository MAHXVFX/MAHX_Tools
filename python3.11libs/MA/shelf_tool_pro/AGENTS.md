# MA/shelf_tool_pro — 加强版工具架

Houdini shelf tools 可视化面板，支持点击/拖拽放置、GIF 动画、Markdown 备注渲染。

## Where to Look

| File | Purpose |
|------|---------|
| `panel.py` | 主面板 UI: 工具栏、设置面板、ThumbnailWidget 容器 |
| `thumbnail_widget.py` | 缩略图控件: 点击执行、拖拽、右键菜单、GIF 动画、收藏图标 |
| `save_tool_dialog.py` | 统一工具对话框: 创建/编辑工具，双标签页（首选项+内容） |
| `shelf_loader.py` | Shelf 文件加载: 扫描 `MAtoolbar/` + `builtin_tools/`，`exec(tool.script())` |
| `shelf_saver.py` | Shelf 文件保存: 创建/更新/重命名工具到 .shelf 文件 |
| `web_renderer.py` | Markdown 渲染: QWebEngineView + marked.js + highlight.js |
| `markdown_text_edit.py` | 智能编辑器: 列表延续、Ctrl+B/I/` 快捷键 |
| `python_code_editor.py` | Python 代码编辑器: 语法高亮、行号 |
| `styles.py` | 样式常量 (独立于 common/styles.py) |
| `vendor/` | Vendored 前端库: marked.min.js, highlight.min.js, template.html |

## Conventions

- **WebRendererPool singleton**: 共享悬停备注面板，类级 `_renderer`，generation 编号防竞态
- **Fade-out**: `hide_notes()` 用 `QTimer.singleShot(FADE_OUT_MS)` 延迟隐藏
- **Shelf loading**: `scan_tool_names()` 解析 `.shelf` XML，扫描 `MAtoolbar/` + `builtin_tools/` + 额外路径目录
- **Tool execution**: `exec(tool.script(), {"kwargs": ..., "hou": hou, "__builtins__": __builtins__})`
- **GIF animation**: `QMovie.frameChanged` → `update()` 手动缩放 + 居中 + 圆角
- **Smart Markdown editor**: `keyPressEvent` 重写 — `re.match` 检测有序/任务/无序列表/blockquote
- **Custom images/names**: 用户工具通过 `ShelfToolsCacheManager` JSON 读写；内置工具通过 `BuiltinToolsCacheManager` 读取 `builtin_tools.json`
- **ToolSettingsDialog**: 统一对话框，`mode="create"` / `mode="edit"` 双模式，QTabWidget 双标签页
- **Favorite icon**: SVG 矢量图标，模块级 `_FAVORITE_PIXMAP` 只加载一次，QLabel + QPixmap 显示，带阴影效果
- **Dialog positioning**: `_position_dialog()` 统一定位，`_clamp_to_screen()` 约束在屏幕可用区域
- **Builtin tools protection**: 内置工具右键菜单只显示"收藏"，数据由 `builtin_tools.json` + `builtin_tools/notes/` 管理，`_get_note()` 统一读取逻辑
- **Shelf color mapping**: `_get_shelf_color_map()` 为每个 shelf 来源分配彩虹背景色，内置工具统一白色，用户工具按来源循环 6 色
- **Extra shelf paths**: `ShelfToolsSettingsManager.get_extra_shelf_paths()` 支持用户添加额外 shelf 目录，`path_prefix()` 用 MD5 哈希生成前缀
- **Chinese encoding fix**: `_fix_encoding()` 修复 .shelf 文件中 UTF-8 字节被当 Latin-1 处理导致的中文乱码
- **Unique ID format**: `{prefix}_{shelfStem}_{toolName}`，prefix 由 `path_prefix()` 生成（builtin→`built`，default→`deflt`，额外→6位hex）
- **Search hint**: `_SearchHintWidget` 浮动提示，搜索框获得焦点且内容为空时显示搜索选项（直接输入/name:/shelf:/tag:），白色加粗字体，无边框
- **Path filter**: 路径筛选下拉菜单在设置面板中，支持"全部路径/内置/默认/用户自定义名称"，与 shelf/标签/搜索筛选取交集
- **Path naming**: 用户可为额外 shelf 路径设置自定义中文名称，内置和默认路径不可命名，命名存储在 `ShelfToolsSettingsManager` 的 `shelf_path_names` 字段
- **Path filter persistence**: 路径筛选状态持久化，关闭时保存，首次加载时恢复；内置/默认使用相对标识符（`builtin`/`default`），避免存储绝对路径
- **ShelfPathsDialog confirm/cancel**: Shelf 路径管理弹窗使用确认/取消按钮模式，变更记录在临时列表中，确认时批量保存

## Anti-Patterns

- **exec() for tool scripts**: 安全风险（Houdini 原生限制），上下文必须注入完整
- **print() debug logging**: `shelf_loader.py` 中使用 `print` 而非 `logger`
