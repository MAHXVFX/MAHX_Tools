# builtin_tools — 内置工具

随项目提交的只读工具，数据由 `builtin_tools.json` 管理。

## Where to Look

| File | Purpose |
|------|---------|
| `builtin_tools.json` | 内置工具配置：图标、标签、元数据 |
| `MA Builtin Tools.shelf` | 工具架定义：注册入口、脚本调用 |
| `MAscripts/` | 功能代码目录：每个工具一个 `.py` 文件 |
| `notes/` | 备注文件目录：按 `unique_id.md` 命名 |

## 内置工具列表

| unique_id | 标签 | 脚本 | 图标 | 说明 |
|-----------|------|------|------|------|
| `built_MA Builtin Tools_MA_Automation` | `MA Automation` | `MA_automation_tool.py` | `MAShelfToolsPro Automation Tool.jpg` | 自动化批处理工具 |
| `built_MA Builtin Tools_MA_VideoToSequence` | `MA 视频转序列图` | `MA_video_to_sequence.py` | `MAShelfToolsPro Automation Tool.jpg` | 视频转序列图工具 |

### MA 视频转序列图

将 mov、mp4、avi 等视频格式转换为 JPG 序列图。

**核心功能：**
- 支持多种视频格式（mov、mp4、avi、mkv、wmv、flv、webm 等）
- 可自定义 JPG 质量（1%-100%）
- 可设置起始帧号（默认从 $RFSTART 获取）
- 可自定义帧号位数和文件名前缀
- 自动检测场景相机，转换完成后自动设置 Background Image
- ffmpeg 单进程直接输出 JPEG 序列，支持实时进度报告

**技术特点：**
- QThread 后台线程执行，支持取消操作
- ffprobe 优先获取元数据，ffmpeg 作为回退方案
- 通过 -progress pipe:1 实现帧级进度追踪

## Conventions

- **只读设计**：内置工具随项目提交，用户不可修改
- **配置管理**：`builtin_tools.json` 定义图标、标签、元数据
- **脚本调用**：`.shelf` 文件通过 `MA.__file__` 定位项目根目录，动态加载 `MAscripts/` 下的模块
- **备注存储**：`notes/` 目录下按 `{unique_id}.md` 命名，使用 Markdown 格式
- **图标引用**：`builtin_tools.json` 中的 `icon` 字段使用相对路径指向 `python3.11libs/MA/icons/` 下的图标文件

## 工具开发流程

1. 在 `MAscripts/` 创建 `{tool_name}.py`，实现 `run(kwargs)` 入口函数
2. 在 `builtin_tools.json` 添加工具配置（unique_id、icon、label、tags）
3. 在 `MA Builtin Tools.shelf` 添加 tool 定义和 toolshelf 成员
4. 在 `notes/` 创建 `{unique_id}.md` 备注文件

## Anti-Patterns

- **修改内置工具**：内置工具为只读，用户不应直接修改
- **硬编码路径**：脚本应使用 `MA.__file__` 动态定位路径，而非硬编码绝对路径
- **缺少入口函数**：每个脚本必须实现 `run(kwargs)` 函数作为入口
