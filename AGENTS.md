# MAHX_Tools Knowledge Base

**Houdini 21.0 PySide6 工具集** — HDR 环境光库 + MA ShelfTools Pro

## Structure

```
root/
├── python3.11libs/MA/          # Python 包（核心代码）
│   ├── common/                 # 共享模块：设置/缓存/过滤器/样式/动画
│   ├── hdr_library/            # HDR 环境光库面板
│   └── shelf_tool_pro/         # 工具架缩略图面板
├── python_panels/              # Pane Tab 定义（XML 入口）
├── toolbar/MA.shelf            # 工具架定义（数据文件）
└── MA_ShelfTools_Pro_Notes/   # 工具备注（.md 用户数据）
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| 全局路径/常量 | `MA/common/constants.py` | `_MA_TOOLS_DIR` 自动计算根目录 |
| 设置/缓存读写 | `MA/common/settings.py` | `BaseJsonManager` 类级缓存 |
| 收藏/筛选逻辑 | `MA/common/filter_manager.py` | property setter 自动重建索引 |
| HDR 面板 | `MA/hdr_library/library_panel.py` | ~614 行主 UI |
| 缩略图生成 | `MA/hdr_library/thumbnail_worker.py` | QThread + ffmpeg |
| Shelf 面板 | `MA/shelf_tool_pro/panel.py` | 主面板 |
| Markdown 渲染 | `MA/shelf_tool_pro/web_renderer.py` | QWebEngineView + marked.js |
| Shelf 加载/执行 | `MA/shelf_tool_pro/shelf_loader.py` | hou.shelves.loadFile + exec |
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

## Commands

(无独立构建/测试命令，运行于 Houdini 环境内)
