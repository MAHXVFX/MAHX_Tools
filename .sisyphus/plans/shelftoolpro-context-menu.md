# MAShelfToolPro 右键菜单与自定义缩略图功能

## TL;DR

> **Quick Summary**: 为 MAShelfToolPro 面板的缩略图添加右键菜单（改名、设置自定义图片）、GIF 悬停动画播放、以及设置面板管理缩略图存放路径。
> 
> **Deliverables**: 
> - 右键菜单：改名（显示名称）+ 设置图片（.jpg/.png/.gif）
> - GIF 悬停 500ms 后自动播放动画
> - 设置按钮：可配置自定义缩略图存放路径
> - 缓存持久化：自定义名称和图片路径在面板重启后保留
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: NO - 单文件修改，顺序执行
> **Critical Path**: 缓存结构 → ThumbnailWidget 增强 → 设置面板 → 集成测试

---

## Context

### Original Request
给 MAShelfToolPro 新增功能：
- 增加右键点击缩略图可改名的功能
- 增加右键点击缩略图可给缩略图设置图片的功能（图片格式包括.jpg .png .gif，注意 gif 只有在鼠标悬停在缩略图上一定时间后才会播放）

### Interview Summary
**Key Discussions**:
- 改名只改显示名称，不改底层 shelf tool name
- 自定义图片需要复制到用户可配置的目录，而非记录原始路径
- 面板需要添加设置按钮，参考 HDR 面板风格
- GIF 悬停延迟设为 500ms

### 当前代码结构
- `python_panels/MAShelfToolPro.pypanel` - 主面板文件（296 行）
  - `ThumbnailWidget` - 单个缩略图控件（左键点击/拖拽）
  - `MAShelfToolProPanel` - 主面板容器（滑块 + 缩略图网格）
- `python3.11libs/MA/common/settings.py` - 缓存管理器
  - `ShelfToolsSettingsManager` - 小数据实时写入（已有 thumb_size）
  - `ShelfToolsCacheManager` - 大数据预留（未使用）
- `MA_ShelfTools_Pro_Settings.json` - 设置文件
- `MA_ShelfTools_Pro_Cache.json` - 缓存文件

---

## Work Objectives

### Core Objective
为 MAShelfToolPro 面板添加右键菜单功能（改名、设置自定义图片）、GIF 悬停动画、设置面板管理缩略图目录。

### Concrete Deliverables
- `ThumbnailWidget` 右键菜单（QMenu）
- `QInputDialog` 改名对话框
- `QFileDialog` 图片选择对话框
- `QMovie` GIF 动画支持（悬停 500ms 延迟）
- 设置按钮 + 设置对话框（路径配置）
- 缓存结构扩展（custom_images, custom_names）

### Definition of Done
- [ ] 右键缩略图弹出菜单，包含"改名"和"设置图片"选项
- [ ] 改名后 name_label 立即更新，面板重启后保留
- [ ] 选择图片后缩略图立即更新，面板重启后保留
- [ ] GIF 图片默认显示第一帧，悬停 500ms 后播放动画，离开后停止
- [ ] 设置按钮可打开设置对话框，配置缩略图存放路径
- [ ] 自定义图片自动复制到配置的目录

### Must Have
- 右键菜单：改名 + 设置图片
- GIF 悬停延迟播放（500ms）
- 设置面板：缩略图存放路径配置
- 缓存持久化：重启面板后自定义设置不丢失
- 图片格式：.jpg, .png, .gif

### Must NOT Have (Guardrails)
- 不修改底层 shelf 文件中的 tool name
- 不修改现有左键点击/拖拽功能
- 不修改滑块大小调整功能
- 不引入新的外部依赖（仅使用 PySide6 内置组件）
- 不记录原始图片绝对路径（必须复制到配置目录）

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: NO (Houdini 运行时依赖，无法外部测试)
- **Automated tests**: None
- **Agent-Executed QA**: ALWAYS (mandatory)

### QA Policy
- **Frontend/UI**: Playwright 不适用（Houdini 内嵌面板）
- **验证方式**: 代码审查 + 静态分析 + 逻辑验证
- 每个任务通过读取修改后的代码，验证：
  - 语法正确性（Python 3.11 兼容）
  - PySide6 API 使用正确
  - 缓存读写逻辑完整
  - 无遗漏的 import

---

## Execution Strategy

### Sequential Tasks (单文件修改，无法并行)

```
Wave 1 (Start Immediately - 全部顺序执行):
├── Task 1: 常量与缓存结构扩展 [quick]
├── Task 2: ThumbnailWidget 右键菜单 + 改名 [deep]
├── Task 3: ThumbnailWidget 自定义图片 + GIF 动画 [deep]
├── Task 4: 设置按钮 + 设置对话框 [unspecified-high]
└── Task 5: 面板初始化集成 + 缓存恢复 [quick]

Critical Path: Task 1 → Task 2 → Task 3 → Task 4 → Task 5
Parallel Speedup: N/A (single file)
```

### Dependency Matrix
- **1**: - → 2, 3, 4, 5
- **2**: 1 → 3, 5
- **3**: 1, 2 → 5
- **4**: 1 → 5
- **5**: 2, 3, 4 → -

---

## TODOs

- [x] 1. 常量与缓存结构扩展

  **What to do**:
  - 在 `constants.py` 添加 `DEFAULT_SHELFTOOLS_THUMBNAIL_DIR` 常量
  - 在 `ShelfToolsSettingsManager` 添加获取/设置缩略图目录的方法
  - 在 `ShelfToolsCacheManager` 添加 custom_images 和 custom_names 的读写方法
  - 确保 `MA_ShelfTools_Pro_Cache.json` 结构支持新字段

  **Must NOT do**:
  - 不修改 HDR 相关的常量或管理器
  - 不改变现有 SettingsManager 的行为

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的常量添加和方法扩展，逻辑清晰
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `customize-opencode`: 不涉及 opencode 配置

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Wave 1, Task 1)
  - **Blocks**: Tasks 2, 3, 4, 5
  - **Blocked By**: None

  **References**:
  - `python3.11libs/MA/common/constants.py` - 添加默认缩略图目录常量
  - `python3.11libs/MA/common/settings.py:69-74` - ShelfToolsSettingsManager 和 ShelfToolsCacheManager 类定义
  - `python3.11libs/MA/common/settings.py:47-53` - BaseJsonManager.update() 方法模式

  **Acceptance Criteria**:
  - [ ] `constants.py` 包含 `DEFAULT_SHELFTOOLS_THUMBNAIL_DIR` 常量
  - [ ] `ShelfToolsSettingsManager` 有 `get_thumbnail_directory()` 和 `set_thumbnail_directory(path)` 方法
  - [ ] `ShelfToolsCacheManager` 有 `get_custom_image(tool_name)` 和 `set_custom_image(tool_name, path, is_gif)` 方法
  - [ ] `ShelfToolsCacheManager` 有 `get_custom_name(tool_name)` 和 `set_custom_name(tool_name, name)` 方法

  **Commit**: YES
  - Message: `feat(shelftools): 扩展缓存结构支持自定义名称和图片`
  - Files: `python3.11libs/MA/common/constants.py`, `python3.11libs/MA/common/settings.py`

---

- [x] 2. ThumbnailWidget 右键菜单 + 改名功能

  **What to do**:
  - 在 `ThumbnailWidget` 中添加 `contextMenuEvent()` 方法
  - 创建 QMenu 包含"改名"和"设置图片"两个 QAction
  - 实现 `_on_rename()` 方法：
    - 使用 `QInputDialog.getText()` 弹出输入框
    - 默认值为当前显示名称
    - 验证输入非空后更新 `name_label`
    - 调用 `ShelfToolsCacheManager.set_custom_name()` 保存
  - 添加必要的 import：`QtWidgets` 已导入，需确认 `QMenu`, `QInputDialog` 可用

  **Must NOT do**:
  - 不修改 `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`
  - 不改变左键点击和拖拽行为
  - 不修改底层 tool name

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要理解现有鼠标事件处理逻辑，确保右键菜单不干扰现有功能
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Wave 1, Task 2)
  - **Blocks**: Tasks 3, 5
  - **Blocked By**: Task 1

  **References**:
  - `python_panels/MAShelfToolPro.pypanel:92-198` - ThumbnailWidget 类完整实现
  - `python_panels/MAShelfToolPro.pypanel:148-175` - 现有鼠标事件处理（不可修改）
  - `python_panels/MAShelfToolPro.pypanel:109-113` - name_label 定义和样式

  **Acceptance Criteria**:
  - [ ] 右键点击缩略图弹出 QMenu，包含"改名"和"设置图片"选项
  - [ ] 点击"改名"弹出 QInputDialog，输入新名称后 name_label 立即更新
  - [ ] 空名称输入被拒绝（保持原名称）
  - [ ] 自定义名称通过 ShelfToolsCacheManager 持久化

  **QA Scenarios**:
  ```
  Scenario: 右键菜单弹出
    Tool: 代码审查
    Steps:
      1. 检查 ThumbnailWidget 是否有 contextMenuEvent 方法
      2. 检查 QMenu 是否正确创建并添加两个 QAction
      3. 检查 QAction 的 triggered 信号是否连接到对应槽函数
    Expected Result: 代码结构完整，信号连接正确

  Scenario: 改名功能
    Tool: 代码审查
    Steps:
      1. 检查 _on_rename 方法是否调用 QInputDialog.getText()
      2. 检查返回值是否用于更新 name_label.setText()
      3. 检查是否调用 ShelfToolsCacheManager.set_custom_name()
      4. 检查空输入处理（result 为 False 或 text 为空时不更新）
    Expected Result: 改名逻辑完整，包含空输入校验
  ```

  **Commit**: YES (与 Task 1 合并)

---

- [x] 3. ThumbnailWidget 自定义图片 + GIF 动画

  **What to do**:
  - 实现 `_on_set_image()` 方法：
    - 使用 `QFileDialog.getOpenFileName()` 选择图片，过滤器 `"Images (*.jpg *.png *.gif)"`
    - 获取配置的缩略图目录（从 SettingsManager）
    - 使用 `shutil.copy2()` 复制图片到缩略图目录，文件名格式 `{tool_name}_custom.{ext}`
    - 调用 `ShelfToolsCacheManager.set_custom_image()` 保存路径和 is_gif 标记
    - 调用 `_load_custom_image()` 更新显示
  - 实现 `_load_custom_image()` 方法：
    - 从缓存读取自定义图片路径
    - 如果是 GIF：创建 QMovie 但不启动，显示第一帧
    - 如果是 JPG/PNG：使用 QPixmap 加载并缩放
    - 应用圆角遮罩（参考现有 `_make_rounded_pixmap`）
  - 实现 GIF 悬停动画：
    - 添加 `enterEvent()` 和 `leaveEvent()` 方法
    - `enterEvent()`: 启动 `QTimer.singleShot(500, self._start_gif_animation)`
    - `leaveEvent()`: 停止定时器，停止 QMovie
    - `_start_gif_animation()`: 检查是否有 GIF 且是自定义图片，启动 QMovie
    - `_stop_gif_animation()`: 停止 QMovie，恢复显示第一帧
  - 添加必要的成员变量：`_gif_timer`, `_movie`, `_is_gif_hovering`

  **Must NOT do**:
  - 不修改现有 `updateSize()` 的核心逻辑
  - 不影响非自定义图片的缩略图显示
  - 不在非 GIF 图片上启动定时器

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: GIF 动画和悬停事件处理逻辑复杂，需要 careful 状态管理
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Wave 1, Task 3)
  - **Blocks**: Task 5
  - **Blocked By**: Tasks 1, 2

  **References**:
  - `python_panels/MAShelfToolPro.pypanel:104-107` - image_label 定义
  - `python_panels/MAShelfToolPro.pypanel:119-145` - _make_rounded_pixmap 和 updateSize 方法
  - `python_panels/MAShelfToolPro.pypanel:147-175` - 现有鼠标事件（参考但不修改）

  **Acceptance Criteria**:
  - [ ] 点击"设置图片"弹出文件选择对话框，支持 .jpg/.png/.gif
  - [ ] 选择的图片复制到配置的缩略图目录
  - [ ] 自定义图片立即显示在缩略图上（带圆角）
  - [ ] GIF 图片默认显示第一帧（静态）
  - [ ] 鼠标悬停 GIF 500ms 后开始播放动画
  - [ ] 鼠标离开 GIF 后停止动画，恢复第一帧
  - [ ] 非 GIF 图片不受悬停事件影响

  **QA Scenarios**:
  ```
  Scenario: 设置 JPG 图片
    Tool: 代码审查
    Steps:
      1. 检查 _on_set_image 是否调用 QFileDialog.getOpenFileName 带正确过滤器
      2. 检查是否使用 shutil.copy2 复制到配置目录
      3. 检查文件名格式是否为 {tool_name}_custom.{ext}
      4. 检查 _load_custom_image 对非 GIF 使用 QPixmap 加载
      5. 检查圆角处理是否正确
    Expected Result: JPG/PNG 图片加载和显示逻辑完整

  Scenario: GIF 悬停动画
    Tool: 代码审查
    Steps:
      1. 检查 enterEvent 是否启动 QTimer.singleShot(500, ...)
      2. 检查 leaveEvent 是否停止定时器和 QMovie
      3. 检查 _start_gif_animation 是否验证 is_gif 标记
      4. 检查 QMovie 是否正确绑定到 image_label
      5. 检查 _stop_gif_animation 是否恢复第一帧
    Expected Result: GIF 悬停动画逻辑完整，无内存泄漏
  ```

  **Commit**: YES (与 Task 1, 2 合并)

---

- [x] 4. 设置按钮 + 设置对话框

  **What to do**:
  - 在 `MAShelfToolProPanel` 的滑块行添加设置按钮（⚙️ 图标或文字"Settings"）
  - 创建设置对话框类 `ShelfToolsSettingsDialog`：
    - 包含缩略图存放路径的 QLineEdit + 浏览按钮
    - 浏览按钮调用 `QFileDialog.getExistingDirectory()`
    - 保存按钮调用 `ShelfToolsSettingsManager.set_thumbnail_directory()`
    - 参考 HDR 面板的设置对话框风格
  - 设置按钮点击事件打开设置对话框
  - 对话框关闭时自动保存设置

  **Must NOT do**:
  - 不修改滑块行的现有布局逻辑
  - 不改变滑块大小调整功能
  - 不引入新的样式定义（复用现有 ACCENT_* 常量）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 对话框设计和布局需要一定的 UI 工作
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Wave 1, Task 4)
  - **Blocks**: Task 5
  - **Blocked By**: Task 1

  **References**:
  - `python_panels/MAShelfToolPro.pypanel:200-288` - MAShelfToolProPanel 类
  - `python_panels/MAShelfToolPro.pypanel:213-239` - 滑块行布局（设置按钮添加位置）
  - `python_panels/MAShelfToolPro.pypanel:13-20` - 颜色常量（样式复用）

  **Acceptance Criteria**:
  - [ ] 滑块行右侧添加设置按钮（⚙️ 或 "Settings"）
  - [ ] 点击设置按钮弹出设置对话框
  - [ ] 对话框包含路径输入框和浏览按钮
  - [ ] 浏览按钮打开目录选择对话框
  - [ ] 保存后路径通过 ShelfToolsSettingsManager 持久化
  - [ ] 对话框样式与 Houdini 暗色主题一致

  **QA Scenarios**:
  ```
  Scenario: 设置对话框打开
    Tool: 代码审查
    Steps:
      1. 检查滑块行是否添加设置按钮
      2. 检查按钮 clicked 信号是否连接到对话框打开方法
      3. 检查 ShelfToolsSettingsDialog 类是否完整定义
      4. 检查对话框是否包含 QLineEdit 和 QPushButton（浏览）
      5. 检查浏览按钮是否调用 QFileDialog.getExistingDirectory
    Expected Result: 设置对话框结构完整

  Scenario: 设置保存
    Tool: 代码审查
    Steps:
      1. 检查保存按钮是否调用 ShelfToolsSettingsManager.set_thumbnail_directory
      2. 检查路径是否通过 SettingsManager 持久化
      3. 检查对话框关闭后设置是否生效
    Expected Result: 设置保存逻辑完整
  ```

  **Commit**: YES (与 Task 1-3 合并)

---

- [x] 5. 面板初始化集成 + 缓存恢复

  **What to do**:
  - 在 `MAShelfToolProPanel.__init__()` 中：
    - 加载自定义名称缓存，应用到对应的 ThumbnailWidget
    - 加载自定义图片缓存，应用到对应的 ThumbnailWidget
    - 确保 ThumbnailWidget 初始化时接收缓存数据
  - 修改 `ThumbnailWidget.__init__()` 接受可选参数 `custom_name` 和 `custom_image_path`
  - 在面板初始化时从缓存读取并传递这些参数
  - 验证所有功能集成后无冲突

  **Must NOT do**:
  - 不改变面板的基本布局
  - 不修改工具架加载逻辑
  - 不引入新的全局变量

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 集成工作主要是参数传递和初始化逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Wave 1, Task 5)
  - **Blocks**: None
  - **Blocked By**: Tasks 2, 3, 4

  **References**:
  - `python_panels/MAShelfToolPro.pypanel:200-210` - MAShelfToolProPanel.__init__
  - `python_panels/MAShelfToolPro.pypanel:262-268` - ThumbnailWidget 创建循环
  - `python_panels/MAShelfToolPro.pypanel:92-117` - ThumbnailWidget.__init__

  **Acceptance Criteria**:
  - [ ] 面板打开时自动恢复自定义名称
  - [ ] 面板打开时自动恢复自定义图片
  - [ ] GIF 悬停动画在面板重启后正常工作
  - [ ] 所有功能（左键点击、拖拽、右键菜单、设置）无冲突

  **QA Scenarios**:
  ```
  Scenario: 缓存恢复
    Tool: 代码审查
    Steps:
      1. 检查 MAShelfToolProPanel.__init__ 是否加载自定义名称缓存
      2. 检查是否加载自定义图片缓存
      3. 检查 ThumbnailWidget 初始化是否接收 custom_name 和 custom_image_path
      4. 检查缓存数据是否正确应用到 UI 元素
    Expected Result: 缓存恢复逻辑完整

  Scenario: 功能无冲突
    Tool: 代码审查
    Steps:
      1. 检查所有鼠标事件处理是否互不干扰
      2. 检查右键菜单不阻止左键事件传播
      3. 检查 GIF 定时器不影响其他功能
      4. 检查设置对话框不阻塞主线程
    Expected Result: 所有功能独立工作，无冲突
  ```

  **Commit**: YES (与 Task 1-4 合并)

---

## Final Verification Wave (MANDATORY)

> 4 review agents run in PARALLEL. ALL must APPROVE.

- [x] F1. **Plan Compliance Audit** — `oracle`
  检查所有 Must Have 是否实现，Must NOT Have 是否遵守

- [x] F2. **Code Quality Review** — `unspecified-high`
  检查 Python 3.11 兼容性，PySide6 API 正确使用，无内存泄漏

- [x] F3. **Real Manual QA** — `unspecified-high`
  在 Houdini 中实际测试所有功能

- [x] F4. **Scope Fidelity Check** — `deep`
  验证无超出范围的功能添加

---

## Commit Strategy

- **Single Commit**: `feat(shelftools): 添加右键菜单、自定义图片、GIF 动画和设置面板`
  - Files: `python_panels/MAShelfToolPro.pypanel`, `python3.11libs/MA/common/constants.py`, `python3.11libs/MA/common/settings.py`

---

## Success Criteria

### Final Checklist
- [ ] 右键菜单：改名 + 设置图片
- [ ] 改名持久化，重启面板保留
- [ ] 自定义图片持久化，重启面板保留
- [ ] GIF 悬停 500ms 后播放动画
- [ ] 设置面板可配置缩略图存放路径
- [ ] 现有功能（左键点击、拖拽、滑块）不受影响
- [ ] 无新增外部依赖
