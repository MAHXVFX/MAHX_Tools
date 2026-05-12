# AGENTS.md

## 项目概述

MAHX_Tools 是一个 Houdini 工具包，提供以下功能：
- HDR 环境光库面板
- 常用工具（设置、过滤器、动画辅助）
- 与 Houdini 菜单系统的集成

## 项目结构

```
MAHX_Tools/
├── ffmpeg.exe                    # 内置的 ffmpeg，用于视频处理
├── MainMenuCommon.xml            # Houdini 菜单配置
├── MAHX_HDR_Library_Settings.json # HDR 库设置（已 gitignore）
└── python3.11libs/
    └── MAHX/
        ├── __init__.py           # 包入口点
        ├── common/               # 共享工具
        │   ├── constants.py      # HDR_EXTENSIONS, HDR_PARAMETER_NAMES
        │   ├── settings.py       # SettingsManager（带缓存的 JSON 读写）
        │   ├── filter_manager.py # FilterManager（收藏、最近使用）
        │   ├── styles.py         # UI 样式定义
        │   ├── animation_helper.py
        │   └── utils.py          # find_ffmpeg(), _collect_hdr_files()
        └── hdr_library/          # HDR 库面板
            ├── main.py           # Panel 入口点
            ├── library_panel.py  # HDRLibraryPanel UI 类
            ├── thumbnail_widget.py
            ├── thumbnail_worker.py
            └── thumbnail_manager.py
```

## 关键入口点

- `Panel()` - 打开 HDR 库面板（来自 `MAHX.hdr_library`）
- `MainMenuCommon.xml` - 在 Houdini 中注册菜单项

## 代码规范

- Python 3.11（Houdini 内置的 Python）
- Qt 界面（PySide6）
- 设置存储在 `MAHX_HDR_Library_Settings.json` 中
- 视频处理使用 `MAHX.common.utils` 中的 `find_ffmpeg()`

## 开发注意事项

- 这是 Houdini 专用工具；在 Houdini 环境外没有独立测试
- 设置文件已 gitignore；不要提交个人设置
- HDR 文件扩展名定义在 `MAHX.common.constants.HDR_EXTENSIONS`

## 重要提醒

**AI 每次对项目进行代码更改后，必须同步更新本文件（AGENTS.md）以反映最新的项目结构、功能或规范变更。**
