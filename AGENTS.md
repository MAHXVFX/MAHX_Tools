# MAHX_Tools Knowledge Base

**Houdini 21.0 PySide6 工具集** — HDR 环境光库 + MA ShelfTools Pro

## Structure

```
root/
├── python3.11libs/MA/          # Python 包（核心代码）
│   ├── common/                 # 共享模块：设置/缓存/过滤器/样式/动画
│   ├── icons/                  # 项目级图标资源
│   ├── hdr_library/            # HDR 环境光库面板
│   └── shelf_tool_pro/         # 工具架缩略图面板
│       ├── panel.py            # 主面板 UI
│       ├── thumbnail_widget.py # 缩略图控件
│       ├── shelf_loader.py     # Shelf 加载执行
│       ├── shelf_saver.py      # Shelf 保存（节点→.shelf）
│       ├── create_tool_dialog.py # 创建工具对话框
│       ├── save_tool_dialog.py # 工具设置对话框（创建/编辑）
│       ├── python_code_editor.py # Python 代码编辑器
│       ├── web_renderer.py     # Markdown 渲染器
│       ├── markdown_text_edit.py # 智能编辑器
│       ├── styles.py           # 样式常量
│       └── vendor/             # Vendored 前端库
├── builtin_tools/              # 内置工具（只读，随项目提交）
│   ├── builtin_tools.json      # 内置工具配置（图标/标签/元数据）
│   ├── MA_*.shelf              # 工具注册入口
│   ├── MAscripts/              # 功能代码（.py）
│   └── notes/                  # 备注文件（.md），按 unique_id 命名
├── python_panels/              # Pane Tab 定义（XML 入口）
├── MAtoolbar/                  # 用户工具目录（.shelf 文件）
└── MA_ShelfTools_Pro_Notes/   # 工具备注（.md 用户数据）
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| 全局路径/常量 | `MA/common/constants.py` | `_MA_TOOLS_DIR` 自动计算根目录 |
| 设置/缓存读写 | `MA/common/settings.py` | `BaseJsonManager` 类级缓存 |
| 内置工具配置 | `MA/common/settings.py` | `BuiltinToolsCacheManager` 读取 `builtin_tools.json` |
| 收藏/筛选逻辑 | `MA/common/filter_manager.py` | property setter 自动重建索引 |
| HDR 面板 | `MA/hdr_library/library_panel.py` | ~614 行主 UI |
| 缩略图生成 | `MA/hdr_library/thumbnail_worker.py` | QThread + ffmpeg |
| Shelf 面板 | `MA/shelf_tool_pro/panel.py` | 主面板 |
| Markdown 渲染 | `MA/shelf_tool_pro/web_renderer.py` | QWebEngineView + marked.js |
| Shelf 加载/执行 | `MA/shelf_tool_pro/shelf_loader.py` | 扫描 `MAtoolbar/` + `builtin_tools/` |
| Shelf 保存 | `MA/shelf_tool_pro/shelf_saver.py` | 节点→.shelf 文件保存 |
| 创建工具对话框 | `MA/shelf_tool_pro/create_tool_dialog.py` | 从 Python 代码创建 shelf 工具 |
| 工具设置对话框 | `MA/shelf_tool_pro/save_tool_dialog.py` | 创建/编辑工具属性 |
| Python 代码编辑器 | `MA/shelf_tool_pro/python_code_editor.py` | 语法高亮编辑器 |
| Panel 入口 | `python_panels/*.pypanel` | XML 中 `onCreateInterface` |

## Conventions

- **Logger**: 统一 `logging.getLogger("MA")`
- **__init__.py**: 重新导出核心类，显式 `__all__`
- **配置管理**: `BaseJsonManager` 子类，类级缓存 + change-detection (`_saved_state`)
- **样式**: `MA/common/styles.py` 共享样式表，各模块也可定义自有样式常量
- **缩略图圆角**: 不用 `border-radius`（DPI 兼容问题），用 `QPainterPath.setClipPath` 代码绘制
- **ffmpeg 调用**: `subprocess.CREATE_NO_WINDOW` 抑制控制台窗口
- **GIF 动画**: `QMovie.frameChanged` → 每帧手动缩放/居中/圆角遮罩
- **异步与线程**: `QThread` + `Signal`（非 `QThreadPool`）

## Anti-Patterns (This Project)

- **Module-level singleton**: 如 `_panel_window` 在 `hdr_library/main.py` — 只应有一个实例，需处理 `RuntimeError`
- **Broad exception**: `except Exception as e: pass` 多处用于 ffmpeg、Houdini API 调用失败
- **exec() 执行脚本**: `shelf_loader.py` 中 `exec(tool.script(), globals_dict)` — Houdini 原生限制，运行时上下文需注入完整
- **import hou**: 放在函数内或 try/except 中（Houdini 环境外不可用）

## Unique Styles

- **暗色主题**: 主色 `#18181b` / `#1D1D20` / `#2d2d2d`，强调色 `#0d6399`(蓝) / `#8a5cf5`(紫)
- **设置与缓存分离**: 小数据实时写 JSON，大数据关闭时写
- **三级缓存**: 内存缓存 → 磁盘缓存 → 重新生成

## Submodule Documentation

各子模块包含独立的 `AGENTS.md` 文件，提供详细的模块级文档：

| Module | AGENTS.md Location | Content |
|--------|-------------------|---------|
| `MA/common/` | `python3.11libs/MA/common/AGENTS.md` | 共享模块：设置/缓存/过滤器/样式/动画 |
| `MA/hdr_library/` | `python3.11libs/MA/hdr_library/AGENTS.md` | HDR 环境光库面板详细文档 |
| `MA/shelf_tool_pro/` | `python3.11libs/MA/shelf_tool_pro/AGENTS.md` | 工具架缩略图面板详细文档 |

**使用场景**：
- 需要深入了解特定模块的实现细节时
- 修改某个子模块前，先阅读其 AGENTS.md 了解约定和反模式
- 查找特定功能的实现位置时

## Commands

(无独立构建/测试命令，运行于 Houdini 环境内)
