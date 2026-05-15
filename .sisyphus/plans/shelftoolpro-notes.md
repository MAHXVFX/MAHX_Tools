# MAShelfToolPro 缩略图备注功能

## TL;DR

> **Quick Summary**: 为 MAShelfToolPro 缩略图右键菜单添加"备注"选项，支持 markdown 格式输入，鼠标悬停 500ms 时在缩略图上方显示渲染后的备注内容。
> 
> **Deliverables**: 
> - `ShelfToolsCacheManager` 新增 `get_note()` / `set_note()` 方法
> - `thumbnail_widget.py` 右键菜单新增 "Notes" 项
> - 悬停显示 markdown 渲染的备注面板（QTextBrowser）
> - `MA_ShelfTools_Pro_Cache.json` 扩展 `notes` 字段
> 
> **Estimated Effort**: Short
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1 (缓存扩展) → Task 2 (UI 集成)

---

## Context

### Original Request
新增功能：
- MAShelfToolPro增加一个缩略图右键选项 备注，可以给tool添加备注，当鼠标悬停500ms时显示备注
- 备注输入支持markdown格式，显示时可以渲染出markdown备注

### Interview Summary
**Key Discussions**:
- 备注输入方式：简单多行文本框 (QInputDialog.getMultiLineText)
- 备注显示位置：固定在缩略图上方的面板
- 悬停触发策略：与 GIF 悬停共用 500ms 延迟

**Research Findings**:
- ShelfToolsCacheManager 使用 BaseJsonManager，实时写入 JSON
- 右键菜单在 contextMenuEvent 中，现有 Rename/Set Image 两项
- GIF 悬停使用 startTimer(500) 模式
- PySide6 QTextBrowser 原生支持 setMarkdown()，无需外部库

### Metis Review
**Identified Gaps** (addressed):
- Notes 面板定位问题：使用独立 QFrame + mapToGlobal 全局坐标，避免 QScrollArea 裁剪
- Timer 逻辑：共享 500ms timer，但 GIF 和 notes 逻辑独立判断
- 边界情况：超长文本设置最大高度 + 滚动条，快速进出缩略图时 killTimer 清理

---

## Work Objectives

### Core Objective
为 MAShelfToolPro 缩略图添加备注功能，支持 markdown 输入与悬停渲染。

### Concrete Deliverables
- `python3.11libs/MA/common/settings.py` - ShelfToolsCacheManager 扩展 get_note/set_note
- `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py` - 右键菜单 + 备注面板 + 悬停逻辑

### Definition of Done
- [x] 右键菜单包含 "Notes" 项，点击弹出多行文本输入对话框
- [x] 输入文本保存后，再次右键打开对话框显示已保存内容
- [x] 悬停缩略图 500ms 后，notes 面板在缩略图上方显示渲染后的 markdown
- [x] 鼠标离开缩略图，notes 面板立即隐藏
- [x] 无 notes 的工具悬停时不显示面板
- [x] MA_ShelfTools_Pro_Cache.json 包含 "notes" 字段

### Must Have
- 右键菜单新增 "Notes" 项
- 使用 QInputDialog.getMultiLineText() 输入备注
- ShelfToolsCacheManager 扩展 get_note/set_note 方法
- 使用 QTextBrowser.setMarkdown() 渲染 markdown
- Notes 面板使用独立 QFrame + mapToGlobal 全局坐标定位
- 共享 500ms timer，GIF 和 notes 逻辑独立判断
- 面板样式与现有 UI 一致（深色背景 #2d2d2d，白色文字，圆角 4px）
- 面板最大高度 200px + 垂直滚动条

### Must NOT Have (Guardrails)
- 不添加外部 markdown 渲染库（如 markdown2、mistune）
- 不修改 HDR 面板的任何代码
- 不改变现有 context menu 的样式或行为（仅添加 "Notes" 项）
- 不修改 GIF 动画的现有行为（notes 逻辑不能干扰 GIF 播放/停止）
- 不创建新的 JSON 配置文件（复用 MA_ShelfTools_Pro_Cache.json）
- 不改变 unique_id 的格式或缓存结构（仅扩展 notes 字段）
- 不添加 markdown 实时预览功能
- 不添加 notes 搜索/过滤功能
- 不添加面板动画效果（直接 show/hide）

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (依赖 Houdini 运行时，无法独立运行测试)
- **Automated tests**: None
- **Framework**: None
- **Agent-Executed QA**: 代码审查 + 静态分析 + Agent QA Scenarios

### QA Policy
每个任务包含 agent-executed QA scenarios：
- 代码审查：验证实现符合 acceptance criteria
- 静态分析：检查代码模式、API 使用正确性
- 证据保存：保存关键代码片段和验证结果

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - 缓存扩展):
├── Task 1: ShelfToolsCacheManager 扩展 get_note/set_note [quick]

Wave 2 (After Wave 1 - UI 集成):
└── Task 2: thumbnail_widget.py 右键菜单 + 备注面板 + 悬停逻辑 [deep]

Wave FINAL (After ALL tasks — 并行审查):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
└── Task F3: Scope fidelity check (deep)
-> Present results -> Get explicit user okay
```

### Dependency Matrix
- **1**: - → 2
- **2**: 1 → F1-F3

### Agent Dispatch Summary
- **Wave 1**: 1 task - T1 → `quick`
- **Wave 2**: 1 task - T2 → `deep`
- **FINAL**: 3 tasks - F1 → `oracle`, F2 → `unspecified-high`, F3 → `deep`

---

## TODOs

- [x] 1. ShelfToolsCacheManager 扩展 get_note/set_note 方法

  **What to do**:
  - 在 `python3.11libs/MA/common/settings.py` 的 `ShelfToolsCacheManager` 类中添加两个方法
  - `get_note(cls, tool_name)`: 返回 notes 字典中对应 tool_name 的值，或 None
  - `set_note(cls, tool_name, note)`: 设置 notes 字典中对应 tool_name 的值，调用 cls.save(data)
  - 复用现有 get_custom_name/set_custom_name 的代码模式
  - 缓存结构扩展: `"notes": {"unique_id": "markdown text"}`

  **Must NOT do**:
  - 不修改 BaseJsonManager 或其他 Manager 类
  - 不创建新的 JSON 配置文件
  - 不改变现有 custom_images/custom_names 的逻辑

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的方法添加，复用现有模式，代码量小
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - 无特殊技能需要

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Wave 1)
  - **Blocks**: Task 2
  - **Blocked By**: None (can start immediately)

  **References**:
  - `python3.11libs/MA/common/settings.py:85-114` - ShelfToolsCacheManager 类定义，get_custom_name/set_custom_name 模式
  - `python3.11libs/MA/common/settings.py:11-58` - BaseJsonManager 基类，load/save/update 方法

  **Acceptance Criteria**:
  - [ ] ShelfToolsCacheManager 有 get_note(tool_name) 方法，返回 str 或 None
  - [ ] ShelfToolsCacheManager 有 set_note(tool_name, note) 方法，实时保存 JSON
  - [ ] MA_ShelfTools_Pro_Cache.json 保存后包含 "notes" 字段

  **QA Scenarios**:
  ```
  Scenario: get_note 返回已保存的备注
    Tool: Bash (代码审查)
    Steps:
      1. 读取 settings.py，确认 get_note 方法存在
      2. 检查方法逻辑：data.get("notes", {}).get(tool_name)
    Expected Result: 方法返回 notes 字典中对应 tool_name 的值，无则返回 None
    Evidence: .sisyphus/evidence/task-1-get-note-method.txt

  Scenario: set_note 保存备注到 JSON
    Tool: Bash (代码审查)
    Steps:
      1. 读取 settings.py，确认 set_note 方法存在
      2. 检查方法逻辑：data.setdefault("notes", {})[tool_name] = note; cls.save(data)
    Expected Result: 方法正确设置 notes 值并调用 save
    Evidence: .sisyphus/evidence/task-1-set-note-method.txt
  ```

  **Commit**: YES (groups with 2)
  - Message: `feat(shelftoolpro): add get_note/set_note to ShelfToolsCacheManager`
  - Files: `python3.11libs/MA/common/settings.py`

---

- [x] 2. thumbnail_widget.py 右键菜单 + 备注面板 + 悬停逻辑

  **What to do**:
  
  ### 2.1 右键菜单扩展
  - 在 `contextMenuEvent` 方法中添加 "Notes" 菜单项
  - 连接 `_on_edit_notes` 方法
  
  ### 2.2 备注编辑对话框
  - 新增 `_on_edit_notes()` 方法
  - 使用 `QInputDialog.getMultiLineText()` 弹出多行文本输入对话框
  - 从 `ShelfToolsCacheManager.get_note(self._unique_id)` 读取当前备注作为默认值
  - 保存时调用 `ShelfToolsCacheManager.set_note(self._unique_id, note_text)`
  - 如果文本为空，保存空字符串（或删除该 key）
  
  ### 2.3 备注面板创建
  - 在 `__init__` 中创建 `_notes_panel` (QTextBrowser)
  - 设置属性：`setReadOnly(True)`, `setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)`
  - 设置样式：背景色 #2d2d2d, 文字颜色 #ffffff, 圆角 4px, 最大高度 200px
  - 初始状态：`hide()`
  
  ### 2.4 悬停显示逻辑
  - 修改 `enterEvent`: 在现有 GIF timer 逻辑后，无条件启动 500ms timer（或确保 timer 启动）
  - 修改 `timerEvent`: 在 GIF 逻辑后，添加 notes 显示逻辑：
    - 调用 `ShelfToolsCacheManager.get_note(self._unique_id)`
    - 如果有备注内容，调用 `_show_notes_panel()`
  - 修改 `leaveEvent`: 在现有 GIF 逻辑后，添加 `_hide_notes_panel()`
  
  ### 2.5 面板显示/隐藏方法
  - `_show_notes_panel()`: 
    - 获取备注文本，调用 `_notes_panel.setMarkdown(note_text)`
    - 计算位置：`pos = self.mapToGlobal(QPoint(0, -panel_height))`
    - 调用 `_notes_panel.move(pos)`
    - 调用 `_notes_panel.show()` 和 `_notes_panel.raise_()`
  - `_hide_notes_panel()`:
    - 调用 `_notes_panel.hide()`
  
  **Must NOT do**:
  - 不修改 GIF 动画的现有行为
  - 不修改 HDR 面板代码
  - 不改变 context menu 样式
  - 不使用外部 markdown 库

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 涉及多个方法修改，需要理解现有 timer 逻辑、坐标计算、QTextBrowser 使用
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - 无特殊技能需要

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (Wave 2, after Task 1)
  - **Blocks**: F1-F3
  - **Blocked By**: Task 1

  **References**:
  - `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py:116-123` - contextMenuEvent 实现
  - `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py:125-132` - _on_rename 模式参考
  - `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py:232-251` - enterEvent/leaveEvent/timerEvent 实现
  - `python3.11libs/MA/shelf_tool_pro/styles.py` - CONTEXT_MENU_STYLE 样式参考
  - `python3.11libs/MA/common/settings.py:85-114` - ShelfToolsCacheManager 方法

  **Acceptance Criteria**:
  - [ ] 右键菜单包含 "Notes" 项
  - [ ] 点击 "Notes" 弹出多行文本输入对话框
  - [ ] 对话框显示已保存的备注内容（如有）
  - [ ] 保存后再次右键，对话框显示更新后的内容
  - [ ] 悬停 500ms 后，notes 面板在缩略图上方显示
  - [ ] 面板使用 setMarkdown() 渲染 markdown
  - [ ] 鼠标离开缩略图，notes 面板隐藏
  - [ ] 无备注的工具悬停时不显示面板
  - [ ] GIF 动画行为不受影响

  **QA Scenarios**:
  ```
  Scenario: 右键菜单包含 Notes 项
    Tool: Bash (代码审查)
    Steps:
      1. 读取 thumbnail_widget.py contextMenuEvent 方法
      2. 确认有 menu.addAction("Notes") 或类似代码
    Expected Result: contextMenuEvent 包含 Notes 菜单项
    Evidence: .sisyphus/evidence/task-2-context-menu.txt

  Scenario: _on_edit_notes 方法正确实现
    Tool: Bash (代码审查)
    Steps:
      1. 读取 _on_edit_notes 方法
      2. 确认使用 QInputDialog.getMultiLineText()
      3. 确认调用 ShelfToolsCacheManager.get_note/set_note
    Expected Result: 方法逻辑正确，读写缓存
    Evidence: .sisyphus/evidence/task-2-edit-notes-method.txt

  Scenario: 备注面板创建和样式
    Tool: Bash (代码审查)
    Steps:
      1. 读取 __init__ 方法，确认 _notes_panel 创建
      2. 确认设置 setReadOnly(True), setWindowFlags, 样式
    Expected Result: 面板正确创建，样式与现有 UI 一致
    Evidence: .sisyphus/evidence/task-2-notes-panel-creation.txt

  Scenario: 悬停显示逻辑正确
    Tool: Bash (代码审查)
    Steps:
      1. 读取 enterEvent/leaveEvent/timerEvent
      2. 确认 timer 启动逻辑，notes 显示/隐藏逻辑
      3. 确认 GIF 逻辑不受影响
    Expected Result: 悬停 500ms 后显示 notes，离开后隐藏
    Evidence: .sisyphus/evidence/task-2-hover-logic.txt

  Scenario: 面板定位计算正确
    Tool: Bash (代码审查)
    Steps:
      1. 读取 _show_notes_panel 方法
      2. 确认使用 mapToGlobal 计算位置
      3. 确认面板在缩略图上方显示
    Expected Result: 位置计算正确，面板显示在缩略图上方
    Evidence: .sisyphus/evidence/task-2-panel-position.txt
  ```

  **Commit**: YES (groups with 1)
  - Message: `feat(shelftoolpro): add notes feature to thumbnail widget`
  - Files: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 3 review agents run in PARALLEL. ALL must APPROVE.

- [x] F1. **Plan Compliance Audit** — `oracle`
  检查 get_note/set_note 方法存在、右键菜单有 Notes 项、QTextBrowser 使用 setMarkdown()、缓存文件有 notes 字段。
  Output: `Must Have [8/8] | Must NOT Have [9/9] | Tasks [2/2] | VERDICT: APPROVE`

- [x] F2. **Code Quality Review** — `unspecified-high`
  检查代码质量：无 as any/@ts-ignore、无空 catch、无 console.log、无未使用导入。检查 AI slop 模式。
  Output: `Lint [PASS] | Files [2 clean/0 issues] | VERDICT: APPROVE`

- [x] F3. **Scope Fidelity Check** — `deep`
  验证每个任务的 "What to do" 与实际 diff 1:1 匹配。检查 "Must NOT do" 合规性。
  Output: `Tasks [2/2 compliant] | Contamination [CLEAN] | VERDICT: APPROVE`

---

## Commit Strategy

- **1**: `feat(shelftoolpro): add notes feature (cache manager + widget)` - settings.py, thumbnail_widget.py

---

## Success Criteria

### Final Checklist
- [x] 右键菜单包含 "Notes" 项
- [x] QInputDialog.getMultiLineText() 弹出输入对话框
- [x] ShelfToolsCacheManager.get_note/set_note 方法存在
- [x] MA_ShelfTools_Pro_Cache.json 包含 "notes" 字段
- [x] QTextBrowser.setMarkdown() 渲染 markdown
- [x] 悬停 500ms 后显示 notes 面板
- [x] 鼠标离开隐藏 notes 面板
- [x] 无 notes 时不显示面板
- [x] 面板样式与现有 UI 一致
- [x] GIF 动画行为不受影响
