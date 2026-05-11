# MAHX HDR Library 项目说明

## 项目定位

这是一个面向 Houdini 21.0 的 Python 工具模块，核心功能是提供一个 HDR 资产库面板。用户可以在 Houdini 中打开面板，浏览 HDR/EXR 等环境贴图，生成并缓存缩略图，按目录、最近使用、收藏等方式过滤，并将选中的 HDR 路径写入当前选中的 Houdini 节点参数。

当前项目不是完整 Python 包，而是一个 Houdini 可直接 import 的单文件工具。

## 当前目录结构

- `HDR_LibraryPanel.py`：核心实现文件，包含 UI、设置、扫描、缩略图生成、过滤、收藏、Houdini 参数写入等逻辑。
- `MAHX.code-workspace`：VS Code workspace 配置，当前只包含本目录。
- `__pycache__/`：Python 编译缓存，不属于源代码维护重点。
- `AGENTS.md`：项目说明和维护约定。

## 运行环境

- Python：Houdini 21.0 自带 Python 3.11 环境。
- UI 框架：`PySide6`。
- Houdini 集成：运行在 Houdini 内时会 import `hou`，并使用 `hou.qt.mainWindow()` 作为窗口父级。
- 缩略图生成：优先使用工具目录下的 `ffmpeg.exe`，其次查找 Houdini `HFS/bin/hffmpeg.exe` 或 `ffmpeg.exe`，最后查找系统 PATH。

## 入口函数

主要入口是：

```python
Panel()
```

`Panel()` 会创建 `SavedSizeDialog`，把 `HDRLibraryPanel` 放进独立对话框中，并恢复上次保存的窗口大小、位置和面板设置。

## 核心类和职责

### `SettingsManager`

负责加载和保存配置文件：

```text
MAHX_Tools/MAHX_HDR_Library_Settings.json
```

`save()` 会先读取现有 JSON 并比较 dict 内容，内容完全一致时不会重写文件，避免无意义刷新配置文件修改时间。

### `ThumbnailWorker`

继承 `QThread`，负责后台扫描 HDR 文件并生成缩略图，避免阻塞 UI。

扫描规则是有意设计为：

- 扫描 HDR 根目录中的文件。
- 扫描一级子目录中的文件。
- 不递归扫描更深层级目录。

不要把 `_collect_hdr_files()` 改成深度递归，除非明确收到需求。

### `HDRThumbnailWidget`

单个 HDR 缩略图控件。

主要能力：

- 懒加载缩略图。
- 滚动出较远范围后卸载 pixmap，减少内存占用。
- 双击触发加载 HDR 到 Houdini 节点。
- 右键菜单支持收藏/取消收藏。
- 收藏状态下文件名前会显示 `[Fav]`。

### `HDRLibraryPanel`

主面板，负责：

- 设置 HDR 库路径和缩略图缓存路径。
- 扫描 HDR 文件。
- 刷新缩略图。
- 调整缩略图尺寸。
- 下拉过滤：`ALL`、收藏、`⭐ Recent`、`Root Only`、一级子目录。
- 保存最近使用和收藏列表。
- 将 HDR 路径写入 Houdini 选中节点参数。

## 支持的 HDR 文件扩展名

定义在 `HDR_EXTENSIONS`：

```python
['.hdr', '.exr', '.hdri', '.tif', '.tiff', '.png', '.jpg', '.jpeg', '.tga', '.bmp']
```

## Houdini 参数写入

双击缩略图后，会遍历当前选中的 Houdini 节点，并尝试写入 `HDR_PARAMETER_NAMES` 中定义的参数：

```python
HDR_PARAMETER_NAMES = (
    "env_map",
    "xn__inputstexturefile_r3ah",
)
```

如果要支持更多灯光、渲染器或节点类型，优先扩展这个常量，而不是把参数名散落到业务逻辑里。

## 配置字段

配置文件中常见字段：

- `hdr_directory`：HDR 资产库路径。
- `cache_directory`：缩略图缓存路径。
- `print_path`：双击应用 HDR 时是否在控制台打印路径。
- `recent_hdrs`：最近使用 HDR 列表。
- `favorite_hdrs`：收藏 HDR 列表。
- `current_filter`：当前下拉过滤项。
- `thumbnail_size`：缩略图控件大小。
- `window_width`、`window_height`、`window_x`、`window_y`：窗口几何信息。
- `thumbnails`：缩略图缓存索引。
- `subfolders`：一级子目录列表。
- `hdr_dir_mtime`、`subfolders_mtime`：用于判断缓存是否仍然有效。

## 过滤逻辑约定

- `ALL`：显示全部 HDR。
- 收藏：显示 `favorite_hdrs` 中仍存在于当前库里的 HDR。
- `⭐ Recent`：显示 `recent_hdrs` 中仍存在于当前库里的 HDR。
- `Root Only`：只显示 HDR 根目录本身的文件。
- 一级子目录：只显示该子目录里的文件。

`Root Only` 只有在根目录本身存在 HDR 文件时才显示。

注意：过滤项的显示文本和 `_apply_filter()` 中的判断文本必须保持一致。修改下拉菜单文本时，要同步更新过滤判断逻辑。

## 设置保存和 dirty-state

项目里有意避免“打开面板什么都不做，关闭时仍重写配置文件”。

相关机制：

- `SettingsManager.save()` 内容相同时不写文件。
- `_loading_settings`：加载配置期间屏蔽控件信号导致的保存。
- `_settings_dirty`：只有用户修改设置、过滤、缩略图大小等状态时才认为普通设置需要保存。
- `_thumbnail_cache_dirty`：只有扫描生成新缩略图索引后才更新缩略图缓存字段。
- `SavedSizeDialog` 中的 `_geometry_dirty`：只有窗口在显示后真的发生移动或缩放事件，才保存窗口几何。

维护时应避免在 `closeEvent()` 中无条件重写配置字段。

## 缩略图缓存

缩略图文件名规则：

```text
原始相对路径去扩展名 + _Thumbnail.jpg
```

例如：

```text
B/example.exr -> B/example_Thumbnail.jpg
```

如果 ffmpeg 生成失败，会创建一个最小 JPEG placeholder，保证 UI 仍可加载。

## 已知维护注意事项

- 当前代码中有部分历史中文注释在终端里可能显示为乱码，但文件可被 Python 正常编译。
- 菜单中带星标或中文文本时，注意终端编码显示可能不稳定；代码内部应以 UTF-8 文件内容为准。
- 收藏过滤项当前应保持为同一个文本值，避免出现菜单显示和 `_apply_filter()` 判断不一致。
- 这个工具主要面向 Windows + Houdini 使用，但 ffmpeg 调用已经避免在非 Windows 环境无条件使用 `CREATE_NO_WINDOW`。

## 验证方式

修改后至少运行：

```powershell
python -m py_compile HDR_LibraryPanel.py
```

如果涉及 Houdini 行为，还需要在 Houdini 中手动验证：

- 能打开 `Panel()`。
- 能加载已有配置。
- 能扫描 HDR。
- 能右键收藏/取消收藏。
- 下拉过滤项显示正确。
- 双击缩略图能写入选中节点参数。
