# MA/shelf_tool_pro — 工具架缩略图面板

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
- **Shelf loading**: `scan_tool_names()` 解析 `.shelf` XML，扫描 `MAtoolbar/` + `builtin_tools/` 两个目录
- **Tool execution**: `exec(tool.script(), {"kwargs": ..., "hou": hou, "__builtins__": __builtins__})`
- **GIF animation**: `QMovie.frameChanged` → `update()` 手动缩放 + 居中 + 圆角
- **Smart Markdown editor**: `keyPressEvent` 重写 — `re.match` 检测有序/任务/无序列表/blockquote
- **Custom images/names**: 用户工具通过 `ShelfToolsCacheManager` JSON 读写；内置工具通过 `BuiltinToolsCacheManager` 读取 `builtin_tools.json`
- **ToolSettingsDialog**: 统一对话框，`mode="create"` / `mode="edit"` 双模式，QTabWidget 双标签页
- **Favorite icon**: SVG 矢量图标，模块级 `_FAVORITE_PIXMAP` 只加载一次，QLabel + QPixmap 显示
- **Dialog positioning**: `_position_dialog()` 统一定位，`_clamp_to_screen()` 约束在屏幕可用区域
- **Builtin tools protection**: 内置工具右键菜单只显示"收藏"，数据由 `builtin_tools.json` + `builtin_tools/notes/` 管理，`_get_note()` 统一读取逻辑

## Anti-Patterns

- **exec() for tool scripts**: 安全风险（Houdini 原生限制），上下文必须注入完整
- **print() debug logging**: `shelf_loader.py` 中使用 `print` 而非 `logger`
