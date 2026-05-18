# MA/shelf_tool_pro — 工具架缩略图面板

Houdini shelf tools 可视化面板，支持点击/拖拽放置、GIF 动画、Markdown 备注渲染。

## Where to Look

| File | Purpose |
|------|---------|
| `panel.py` | 主面板 UI: 工具栏、设置面板、ThumbnailWidget 容器 |
| `thumbnail_widget.py` | 缩略图控件 (510 行): 点击执行、拖拽、右键菜单、GIF 动画 |
| `shelf_loader.py` | Shelf 文件加载: `hou.shelves.loadFile()` + `exec(tool.script())` |
| `web_renderer.py` | Markdown 渲染: QWebEngineView + marked.js + highlight.js |
| `markdown_text_edit.py` | 智能编辑器: 列表延续、Ctrl+B/I/` 快捷键 |
| `styles.py` | 样式常量 (独立于 common/styles.py) |
| `vendor/` | Vendored 前端库: marked.min.js, highlight.min.js, template.html |

## Conventions

- **WebRendererPool singleton**: 共享悬停备注面板，类级 `_renderer`，generation 编号防竞态
- **Fade-out**: `hide_notes()` 用 `QTimer.singleShot(FADE_OUT_MS)` 延迟隐藏
- **Shelf loading**: `scan_tool_names()` 正则解析 `.shelf` XML；`ensure_shelves()` 去重加载
- **Tool execution**: `exec(tool.script(), {"kwargs": ..., "hou": hou, "__builtins__": __builtins__})`
- **GIF animation**: `QMovie.frameChanged` → `update()` 手动缩放 + 居中 + 圆角
- **Smart Markdown editor**: `keyPressEvent` 重写 — `re.match` 检测有序/任务/无序列表/blockquote
- **Custom images/names**: 通过 `ShelfToolsCacheManager` JSON 读写（持久化）

## Anti-Patterns

- **exec() for tool scripts**: 安全风险（Houdini 原生限制），上下文必须注入完整
- **print() debug logging**: `shelf_loader.py` 中使用 `print` 而非 `logger`
