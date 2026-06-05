# MA/about — 关于面板

显示插件信息的关于面板，复用 WebRenderer 渲染 Markdown 内容。

## Where to Look

| File | Purpose |
|------|---------|
| `about_panel.py` | 关于面板 UI：单例对话框、WebRenderer 复用、Win32 窗口样式 |

## Conventions

- **WebRenderer 复用**：从 `MA.shelf_tool_pro.web_renderer` 导入 `WebRenderer`，渲染 Markdown 内容
- **单例模式**：模块级 `_panel_window` 变量，`Panel()` 复用已打开窗口（与 `hdr_library/main.py` 同款模式）
- **Win32 窗口样式**：`_apply_window_flags()` 设置 `WS_EX_APPWINDOW` 扩展样式，`AppUserModelID` 为 `'MA.MATools.About.1'`
- **入口函数**：`Panel()` 函数，检查 `_panel_window` 是否存在，存在则 `raise_()` + `activateWindow()`，否则创建新窗口
- **样式**：使用 `MA.common.styles.DIALOG_BG_STYLE`（暗色背景）
- **Markdown 内容**：`ABOUT_MARKDOWN` 常量定义完整的关于信息（版本、功能、技术栈）
- **窗口属性**：`Qt.WA_DeleteOnClose` 属性，关闭时自动清理 `_panel_window`

## Anti-Patterns

- **Broad exception**：`_apply_window_flags()` 中 `except Exception: pass`（Win32 API 调用失败静默处理）
- **import hou 在函数内**：`Panel()` 中 `import hou`，避免模块级依赖 Houdini 环境
