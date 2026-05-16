# AGENTS.md

## 概述

Houdini PySide6 工具包，主要功能：
- **HDR 环境光库面板**：管理 HDR 环境光缩略图，一键加载到场景环境光节点
- **MA ShelfTools Pro**：自定义工具架面板，以缩略图展示工具架上的工具，支持点击自动放置和拖拽到 NetworkEditor 定位放置

### 面板入口

| 面板 | 打开方式 |
|---|---|
| HDR 环境光库 | 菜单栏 `MainMenuCommon.xml` → `MA.Panel()`；内嵌面板 `MAHDR.pypanel` |
| MA ShelfTools Pro | 内嵌面板 `MAShelfToolPro.pypanel`（Pane Tab 菜单 → MA ShelfTools Pro） |

## 架构

```
MATools/
├── MainMenuCommon.xml             # 菜单栏入口（MA HDR Asset Library 菜单项）
├── toolbar/
│   ├── mahx.shelf                 # 工具架定义文件
│   └── Houdini_Shelf_Tool_Trigger_Guide.md
├── python_panels/
│   ├── MAHDR.pypanel              # HDR 环境光库面板
│   └── MAShelfToolPro.pypanel     # 工具架缩略图面板（薄层入口，仅 12 行）
└── python3.11libs/
    └── MA/
        ├── __init__.py                # 导出所有公共接口
        ├── common/
        │   ├── __init__.py            # 公共模块导出（SettingsManager, CacheManager 等）
        │   ├── constants.py           # 路径常量、HDR_EXTENSIONS、UI 常量、DEFAULT_SHELFTOOLS_THUMBNAIL_DIR
        │   ├── settings.py            # BaseJsonManager + 4 个子类（详见下方）
        │   ├── filter_manager.py      # FilterManager（筛选/收藏/最近/占位图过滤）
        │   ├── styles.py              # Qt 样式表
        │   ├── animation_helper.py    # UI 动画（elastic_resize 等）
        │   └── utils.py               # find_ffmpeg(), _collect_hdr_files()
        ├── hdr_library/
        │   ├── main.py                # Panel() 入口, SavedSizeDialog（弹窗模式下 closeEvent 保存）
        │   ├── library_panel.py       # HDRLibraryPanel 主 UI 类
        │   ├── thumbnail_worker.py    # ThumbnailWorker QThread（ffmpeg 生成缩略图）
        │   ├── thumbnail_manager.py   # ThumbnailManager（网格布局/懒加载/虚拟滚动）
        │   └── thumbnail_widget.py    # HDRThumbnailWidget 单个缩略图控件
        └── shelf_tool_pro/            # MA ShelfTools Pro 业务模块（拆分架构）
            ├── __init__.py            # 导出 MAShelfToolProPanel
            ├── panel.py               # MAShelfToolProPanel（UI 组装：工具栏/设置面板/工具区）
            ├── thumbnail_widget.py    # ThumbnailWidget（缩略图控件：点击/拖拽/右键/GIF/Notes）
            ├── web_renderer.py        # Markdown 渲染器（QWebEngineView + marked.js + highlight.js）
            ├── vendor/                # Vendored 前端库
            │   ├── marked.min.js      # marked.js v15.0.12（MIT）
            │   ├── highlight.min.js   # highlight.js v11.11.1（BSD 3-Clause）
            │   └── template.html      # HTML 模板（VitePress 风格 CSS + renderMarkdown 函数）
            ├── shelf_loader.py        # shelf 加载与执行（scan_tool_names, ensure_shelves, execute_tool, drop_at_cursor）
            └── styles.py              # 样式常量（颜色、QSS）
```

## 配置文件架构

所有 JSON 配置文件在项目根目录，已 `.gitignore`：

| 文件 | 管理类 | 内容 | 保存时机 |
|---|---|---|---|
| `MA_HDR_Library_Settings.json` | `SettingsManager` | hdr_directory, cache_directory, thumbnail_size, current_filter, recent_hdrs, favorite_hdrs, print_path, hide_gray, window_* | **实时**（改即写） |
| `MA_HDR_Library_Cache.json` | `CacheManager` | thumbnails 路径字典, subfolders, mtime 快照 | **关闭时**（closeEvent） |
| `MA_ShelfTools_Pro_Settings.json` | `ShelfToolsSettingsManager` | thumb_size, thumbnail_directory | **实时**（滑块拖动/设置保存） |
| `MA_ShelfTools_Pro_Cache.json` | `ShelfToolsCacheManager` | custom_images, custom_names | **实时**（改名/设置图片时写） |

### 类层次

```
BaseJsonManager              ← 通用 JSON 读写 + 类级缓存 + diff 跳过写入
  ├── SettingsManager         → HDR 设置（小，实时写）
  ├── CacheManager            → HDR 缓存（大，关闭时写）
  ├── ShelfToolsSettingsManager → ShelfTools 设置（小，实时写）
  └── ShelfToolsCacheManager    → ShelfTools 缓存（大，预留）
```

### 设计原则

- **设置与缓存分离**：小数据（用户偏好）实时写入，大数据（缩略图路径、元数据）只在关闭时写入
- **类级单例**：`load()` 返回同一 dict 引用，修改即改缓存
- **diff 跳过**：`save()` 与 `_saved_state` 比较，无变化则跳过磁盘写入
- **Qt6 滚动条**：`_vscroll` 用 `@property` 实时获取，不能缓存——Qt6 可能重建滚动条

## HDR Library 设计

### 关键数据流

1. **菜单流**：`MainMenuCommon.xml` → `Panel()` → `SavedSizeDialog` → `HDRLibraryPanel` → `_load_settings()`
2. **内嵌面板流**：Pane Tab 菜单 → `MAHDR.pypanel` → `HDRLibraryPanel` → `_load_settings()`
3. **缩略图加载优先级**：缓存(`_try_load_cached_thumbnails`，读 CacheManager) → 文件系统扫描(`_load_existing_thumbnails`) → 用户手动扫描(`_scan_hdr_files`)
4. **关闭保存**：弹窗模式由 `SavedSizeDialog.closeEvent()` 保存（settings + cache 分两次写）；嵌入模式由 `HDRLibraryPanel.closeEvent()` → `_save_on_close()` 保存

### 关键陷阱

#### 关闭保存：两种模式对应不同路径
- **弹窗模式**（`Panel()`）：`SavedSizeDialog.closeEvent()` 保存窗口几何 + 设置 + 缓存
- **嵌入模式**（`MAHDR.pypanel`）：`HDRLibraryPanel.closeEvent()` → `_save_on_close()` 保存设置 + 缓存
- 两者互不干扰：Qt 子控件不会随父对话框触发 `closeEvent`
- `_save_on_close()` 有 `_saved_on_close` 守卫防止重复保存
- 只要 `_filter_mgr.thumbnails` 非空就保存缓存，不依赖 `_thumbnail_cache_dirty`
- 这确保 `is_placeholder` 标记在面板关闭时持久化

#### 占位图机制
- `ThumbnailWorker._generate_thumbnail()` 失败时返回共享占位图 `_placeholder_gray.jpg`
- 所有失败的 HDR 共享同一张占位图文件
- `is_placeholder=True` 标记在扫描时写入，通过缓存持久化
- "Hide gray thumbnails" 按 `is_placeholder` 过滤，不检查文件是否存在

#### hide_gray 信号处理
- 使用 `toggled` 信号（非 `stateChanged`），专用处理器 `_on_hide_gray_toggled`
- `_update_folder_combo` 和 `_apply_filter` 都接受可选参数，默认回退到 `isChecked()`
- 加载设置期间 `_loading_settings=True` 阻止信号处理器执行保存

## MA ShelfTools Pro 设计

### 架构（已拆分）

```
python_panels/MAShelfToolPro.pypanel  ← 薄层入口（from MA.shelf_tool_pro import MAShelfToolProPanel）
    ↓
python3.11libs/MA/shelf_tool_pro/
    ├── panel.py                ← MAShelfToolProPanel（UI 组装）
    ├── thumbnail_widget.py     ← ThumbnailWidget（缩略图控件）
    ├── web_renderer.py         ← WebRenderer（QWebEngineView + marked.js + highlight.js）
    ├── vendor/                 ← Vendored 前端库（marked.min.js, highlight.min.js, template.html）
    ├── shelf_loader.py         ← shelf 加载与执行逻辑
    └── styles.py               ← 样式常量
```

### 核心流程

```
toolbar/*.shelf
    ↓ hou.shelves.loadFile()     （启动时加载一次，替换需重启 Houdini）
Houdini Shelf 系统（内存注册）
    ↓ hou.shelves.tool(name)     按工具名称查找
Tool 对象
    ↓ exec(tool.script(), {"kwargs": kwargs, "hou": hou, "__builtins__": __builtins__})
创建节点 → 定位到 NetworkEditor
```

### 关键数据流

1. **工具名称加载流**：模块加载时 `scan_tool_names()` → 正则解析 `toolbar/*.shelf` 中的 `<tool name="...">`，提取 shelf 文件名作为前缀，生成 `{shelf_stem}_{tool_name}` 唯一标识（纯文件操作，不调 Houdini API）
2. **点击触发流**：`mouseReleaseEvent` → `execute_tool(unique_id)` → 从 `_TOOL_REGISTRY` 解析原始 `tool_name` → 自动查找当前 NetworkEditor → 注入 `pane` 到 kwargs → 执行脚本
3. **拖拽触发流**：`mouseMoveEvent` → `QDrag.exec_()` → `drop_at_cursor(unique_id)` → `ne.cursorPosition()` → `execute_tool()` 带精确坐标
4. **shelf 加载流**：`ensure_shelves()` → 扫描 `toolbar/*.shelf` → 逐个 `hou.shelves.loadFile()`
5. **缩略图大小设置流**：滑块拖动 → `_on_size_changed()` → `ShelfToolsSettingsManager.update("thumb_size", value)` 实时保存
6. **右键改名流**：`contextMenuEvent` → `QInputDialog.getText()` → 更新 `name_label` → `ShelfToolsCacheManager.set_custom_name(unique_id)`
7. **右键设置图片流**：`QFileDialog.getOpenFileName()` → `shutil.copy2()` 到配置目录 → `ShelfToolsCacheManager.set_custom_image(unique_id)` → `_load_custom_image()`
8. **GIF 悬停动画流**：`enterEvent` → `startTimer(500)` → `timerEvent` → `_start_gif_animation()` → `leaveEvent` → `killTimer()` + `_stop_gif_animation()`
9. **设置面板流**：Settings 按钮 → `elastic_resize()` 展开/收起 → 路径输入框 + Browse 按钮 → `ShelfToolsSettingsManager.set_thumbnail_directory()`
10. **右键编辑备注流**：`contextMenuEvent` → `_on_edit_notes()` → 自定义 QDialog (900x700) → `ShelfToolsCacheManager.set_note(unique_id)`
11. **中键查看备注流**：`mouseReleaseEvent(MiddleButton)` → `_open_notes_window()` → QWebEngineView 渲染 markdown → 无备注则无事发生
12. **悬停显示备注流**：`enterEvent` → 500ms 延迟 → `_show_notes_panel()` → 无边框 QWebEngineView 显示在缩略图上方/下方 → 鼠标移向备注时通过 `eventFilter` 保持显示

### 缩略图显示
- 正方形 1:1，圆角 `size // 8`，默认灰色占位图
- **圆角通过代码绘制**：使用 `_apply_rounded_mask` / `_apply_rounded_mask_with_bg` 方法，不依赖样式表 `border-radius`
- 支持自定义图片（.jpg/.png/.gif），通过右键菜单设置
- GIF 默认显示第一帧，鼠标悬停 500ms 后播放动画，离开后停止
- **GIF 动画实现**：连接 `QMovie.frameChanged` 信号，每帧手动缩放、居中、应用圆角遮罩，避免 `QLabel.setMovie()` 的拉伸填充
- 滑块可调大小（70~250px），实时保存到 `ShelfToolsSettingsManager`
- 名称在缩略图下方，字号随大小缩放
- `updateSize()` 时检查 `_custom_image_path`，有则重新加载自定义图片，无则显示默认占位图
- **工具区使用 `QScrollArea` 包裹**：缩略图大小调整不影响面板大小，仅改变滚动区域内布局（参考 HDR 面板架构）
- **布局细节**：`image_label` 大小为 `size + 2`（右边缘缓冲防裁剪），缩略图间距 `12px`
- **HDR 面板同步**：`hdr_library/thumbnail_widget.py` 同样使用代码绘制圆角，保持视觉一致

### Notes 备注功能

#### 三种交互方式
| 触发方式 | 行为 | 面板类型 |
|---|---|---|
| 悬停 500ms | 显示小型浮动备注（只读，markdown 渲染） | 无边框 QWebEngineView，固定 450x600 |
| 中键点击 | 打开独立备注窗口（只读，markdown 渲染） | 带标题栏 QDialog (450x600)，无备注则无事发生 |
| 右键 → Notes | 打开备注编辑窗口（分屏实时预览） | 自定义 QDialog (900x700)，QTextEdit + QWebEngineView 分屏 |

#### Markdown 渲染管线
- **渲染器**：`web_renderer.py` 使用 vendored `marked.js` + `highlight.js` 通过 QWebEngineView 渲染
- **模板**：`vendor/template.html` 包含 VitePress 风格 CSS 和 `window.renderMarkdown()` 函数
- **代码高亮**：VitePress 风格（`#2E2E32` 背景、圆角容器、语言标签、语法高亮）
- **JS 注入**：`json.dumps()` 安全转义 → `runJavaScript()` 调用 `window.renderMarkdown()`
- **异步处理**：`setHtml()` → `loadFinished` → 队列渲染 → `runJavaScript()`
- **关键陷阱**：`setHtml()` 必须传 `baseUrl` 参数，否则相对路径 JS 脚本无法加载
- **GC 防护**：中键窗口和编辑对话框中的 `WebRenderer` 实例必须绑定到窗口对象，防止被 GC 回收

#### 悬停备注智能定位
- **优先上方显示**：若超出屏幕上边缘 → 改为下方显示
- **鼠标移入保持**：鼠标从缩略图移向备注时，通过 150ms 延迟 + `eventFilter` 保持显示
- **鼠标离开隐藏**：鼠标离开备注面板后 100ms 自动隐藏

#### 窗口面板智能定位（中键/右键）
- 使用 `_clamp_to_screen()` 统一处理，避免被屏幕边缘或任务栏裁剪
- **水平**：优先右侧打开 → 超出右边缘 → 改为左侧打开
- **垂直**：底部超出 → 上移（留 20px 间距）；顶部超出 → 下移贴顶边
- 使用 `screen.availableGeometry()` 排除 Windows 任务栏区域

#### 关键实现细节
- **悬停备注**：`_init_notes_panel()` 创建独立窗口，`installEventFilter(self)` 检测鼠标进出
- **`_mouse_in_notes` 标志**：跟踪鼠标是否在备注面板上，决定延迟隐藏行为
- **`_delayed_hide_notes()`**：150ms 延迟检查，给鼠标移动到备注面板的时间窗口
- **中键窗口**：无备注时直接 return，不显示任何内容
- **编辑窗口**：分屏布局（左编辑/右预览），300ms 防抖实时更新，闭包避免实例引用泄漏

### 缓存结构扩展

```json
{
  "custom_images": {
    "unique_id": {"path": "custom_shelf_thumbnails/unique_id.jpg", "is_gif": false}
  },
  "custom_names": {
    "unique_id": "自定义显示名称"
  },
  "notes": {
    "unique_id": "备注内容（markdown 格式）"
  }
}
```

**唯一标识规则**：`{shelf_stem}_{tool_name}`（例如 `mahxA_cam`、`mahxB_cam`）
- 解决多 shelf 同名 tool 导致缓存冲突的问题
- `unique_id` 用于缓存键、MIME 数据、内部查找
- 显示名称保持原始 `tool_name`，避免 UI 混乱
- `hou.shelves.tool()` 仍使用原始 `tool_name` 查找

### 关键陷阱（Shelf Tool 触发）

详见 `toolbar/Houdini_Shelf_Tool_Trigger_Guide.md`

- `hou.shelves` **是模块不是函数**：正确调用 `hou.shelves.shelfSets()`、`hou.shelves.tool(name)`
- **Tool 没有 run()**：只能用 `exec(tool.script(), globals_dict)`
- **必须注入 kwargs 到 exec 上下文**：`exec(tool.script(), {"kwargs": kwargs, "hou": hou, "__builtins__": __builtins__})`
  - 否则脚本无法获取 `kwargs["pane"]`，节点会错误放置到 `/obj` 层级并跳转视窗
- **必须传 `"pane": ne` 到 kwargs**：否则脚本走错分支，不处理坐标
- **必须传 `"outputnodename": ""` 让 `num_args=6`**：默认 `num_args=1` → hscript 里 `$argc < 2` 会重置 `$arg2/$arg3` 为 0
- **`cursorPosition()` 直接获取网络坐标**：不要自己算 `visibleBounds` + `screenPosition` 映射
- **`sys.exit()` 捕获 `SystemExit`**：脚本中的 `sys.exit()` 抛出 `SystemExit`，不被 `except Exception` 捕获，需单独处理
- **点击触发时必须查找当前 NetworkEditor**：`pane.isCurrentTab()` 优先，回退到任意 NetworkEditor

### 关键陷阱（UI 渲染）

#### 圆角绘制
- **不使用样式表 `border-radius`**：Qt 样式表圆角在某些 DPI 设置下会出现不对称裁剪
- **使用 `QPainterPath` + `setClipPath`**：确保圆角精确对称
- **`image_label` 尺寸 `size + 2`**：右边缘 1px 缓冲防止圆角被相邻控件遮挡
- **缩略图间距 `12px`**：确保圆角有足够空间不被裁剪

#### GIF 动画
- **不使用 `QLabel.setMovie()`**：会导致图片拉伸填充，失去圆角和居中效果
- **使用 `frameChanged` 信号**：每帧手动获取 `QPixmap`，经过缩放、居中、圆角遮罩后显示
- **旧 `QMovie` 清理**：重新加载时调用 `deleteLater()` 防止内存泄漏
- **PySide6 API**：使用 `movie.state()` 和 `movie.paused()` 检查状态，`isPlaying()` 不存在

#### API 兼容性
- **`QDrag.exec()` / `QMenu.exec()`**：PySide6 推荐使用 `exec()` 替代过时的 `exec_()`

#### Notes 备注
- **`_clamp_to_screen()` 统一处理定位**：所有弹出面板（编辑/查看）都调用此方法，避免重复代码
- **`availableGeometry()` 排除任务栏**：不要用 `geometry()`，否则面板会被任务栏遮挡
- **`_BOTTOM_MARGIN = 20`**：面板与屏幕底部保持 20px 间距，避免紧贴任务栏
- **eventFilter 必须安装**：`_notes_panel.installEventFilter(self)` 是检测鼠标进出备注面板的关键
- **延迟隐藏机制**：`leaveEvent` 不直接隐藏，而是 `QTimer.singleShot(150, _delayed_hide_notes)`，给鼠标移动到备注面板的时间窗口
- **GC 防护**：中键窗口和编辑对话框中的 `WebRenderer` 实例必须绑定到窗口对象（如 `notes_window._notes_renderer = renderer`），防止被 GC 回收
- **`setHtml()` 必须传 `baseUrl`**：否则 `./marked.min.js` 等相对路径脚本无法加载

#### Vendored 依赖
- **`python3.11libs/MA/shelf_tool_pro/vendor/`**：前端渲染库
  - `marked.min.js` — marked.js v15.0.12（MIT）
  - `highlight.min.js` — highlight.js v11.11.1（BSD 3-Clause）
  - `template.html` — HTML 模板（VitePress 风格 CSS + `renderMarkdown` 函数）
- **许可证合规**：`marked/LICENSE.md` 和 `highlight.js/LICENSE` 必须保留在项目根目录
- **Houdini 自动加载**：`python3.11libs/` 自动加入 `sys.path`，无需额外配置

## 开发约束

- **无独立测试**：依赖 Houdini 运行时（`import hou`），无法在外部运行
- **Python 3.11**：Houdini 21.0 内置
- **PySide6**：Qt 绑定，信号/槽机制
- **PySide6-Addons**：QWebEngineView 属于 PySide6-Addons，需确认 Houdini 21.0 是否包含
- **ffmpeg**：缩略图生成依赖 ffmpeg，优先级：打包的 `ffmpeg.exe` → Houdini 的 `hffmpeg` → PATH
- **配置文件均已 `.gitignore`**：4 个 JSON（settings × 2 + cache × 2），不要手动提交
- **`_collect_hdr_files`** 只扫描两层（根目录 + 一级子目录）
- **ShelfToolPro 模块拆分**：业务逻辑在 `python3.11libs/MA/shelf_tool_pro/`，`.pypanel` 仅为薄层入口
- **`updateSize()` 必须保留自定义图片**：调整大小时检查 `_custom_image_path`，有则重新加载，无则显示默认占位图
- **Vendored 依赖**：`marked.min.js` 和 `highlight.min.js` vendored 到 `python3.11libs/MA/shelf_tool_pro/vendor/`，确保零外部网络依赖部署
- **许可证合规**：`marked/LICENSE.md` 和 `highlight.js/LICENSE` 必须保留在项目根目录
