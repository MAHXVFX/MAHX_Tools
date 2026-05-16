# MAShelfToolsPro Markdown 渲染升级：QWebEngineView 方案

## TL;DR

> **Quick Summary**: 将 MAShelfToolsPro 备注面板的 Markdown 渲染从 QTextBrowser 升级为 QWebEngineView + 轻量前端渲染（marked.js + highlight.js），解决代码块背景色断裂问题，实现 VitePress 风格的渲染质量。
> 
> **Deliverables**:
> - `web_renderer.py` - 新 Markdown 渲染模块（HTML 模板 + JS 注入）
> - `vendor/` 目录 - vendored 前端库（marked.min.js, highlight.min.js）
> - `thumbnail_widget.py` - 三个渲染场景替换为 QWebEngineView
> - 回退机制 - QWebEngineView 不可用时降级到 QTextBrowser
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: T1+T2+T3 → T4+T5+T6 → T7 → T8 → F1-F4

---

## Context

### Original Request
用户反馈代码块背景色在 QTextBrowser 中显示为每行分离，不是连贯的容器。希望达到 Markdown 笔记软件（如 VitePress）的渲染效果。

### Interview Summary
**Key Discussions**:
- QTextBrowser 只支持 HTML/CSS 子集，无法正确处理 Pygments 生成的嵌套 `<span>` + 内联样式
- 用户同意使用 QWebEngineView + 轻量前端渲染方案
- 要求 VitePress 风格的代码块样式（圆角容器、语法高亮、连贯背景）

**Research Findings**:
- QWebEngineView 属于 PySide6-Addons，需要验证 Houdini 21.0 是否包含
- 当前代码在 3 个地方使用 QTextBrowser：悬停面板、编辑对话框预览、中键备注窗口
- 备注已迁移到独立 .md 文件存储（MA_ShelfTools_Pro_Notes/）

### Metis Review
**Identified Gaps** (addressed):
- **QWebEngineView 可用性**: 添加启动时检测，不可用时回退到 QTextBrowser
- **异步时序**: 使用 `loadFinished` 信号确保模板加载完成后再注入内容
- **实例复用**: QWebEngineView 在 `_init_notes_panel` 时创建一次，复用显示/隐藏
- **特殊字符转义**: 通过 JS 全局变量传递 markdown 文本，而非直接拼接 HTML
- **性能边界**: 悬停面板显示延迟不超过现有方案（500ms timer + 渲染）

---

## Work Objectives

### Core Objective
替换 3 个 QTextBrowser 实例为 QWebEngineView，使用 marked.js + highlight.js 实现完美的 Markdown 渲染，特别是代码块的连贯背景和语法高亮。

### Concrete Deliverables
- `python3.11libs/MA/shelf_tool_pro/web_renderer.py` - 新渲染模块
- `python3.11libs/MA/shelf_tool_pro/vendor/marked.min.js` - Markdown 解析器
- `python3.11libs/MA/shelf_tool_pro/vendor/highlight.min.js` - 语法高亮库
- `python3.11libs/MA/shelf_tool_pro/vendor/template.html` - HTML 模板
- `thumbnail_widget.py` - 三处渲染逻辑替换

### Definition of Done
- [ ] 悬停备注面板代码块显示为连贯的圆角容器（截图验证）
- [ ] 编辑对话框预览实时更新，代码高亮正确
- [ ] 中键备注窗口支持所有 Markdown 元素正确渲染
- [ ] QWebEngineView 不可用时功能正常降级

### Must Have
- VitePress 风格代码块（圆角容器 `#2E2E32` 背景、语法高亮、语言标签）
- 暗色主题与现有 UI 一致（`#1e1e1e` 背景，`#d4d4d4` 文字）
- QWebEngineView 实例复用（不每次创建）
- 回退机制（import 失败时降级到 QTextBrowser）
- 零外部网络依赖（所有 JS 库 vendored 到项目目录）

### Must NOT Have (Guardrails)
- 不引入 Vue/React/完整 Markdown 编辑器
- 不复制 VitePress 的侧边栏/导航/搜索功能
- 不添加代码复制按钮（增加 JS 复杂度）
- 不添加行号显示（需要额外插件）
- 不支持 KaTeX/Mermaid（大幅增加复杂度）
- 不修改备注存储结构（保持 .md 文件方案）

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (Houdini runtime dependency)
- **Automated tests**: None
- **Framework**: None
- **Agent-Executed QA**: ALWAYS (mandatory for all tasks)

### QA Policy
Every task MUST include agent-executed QA scenarios.
- **Frontend/UI**: Use Playwright (playwright skill) - Navigate, interact, assert DOM, screenshot
- **TUI/CLI**: Use interactive_bash (tmux) - Run command, send keystrokes, validate output
- **API/Backend**: Use Bash (curl) - Send requests, assert status + response fields
- **Library/Module**: Use Bash (bun/node REPL) - Import, call functions, compare output

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - foundation + vendoring):
├── Task 1: Download and vendor frontend libraries [quick]
├── Task 2: Create HTML template with VitePress-style CSS [quick]
└── Task 3: Create web_renderer.py module [unspecified-high]

Wave 2 (After Wave 1 - replace rendering in thumbnail_widget.py):
├── Task 4: Replace hover preview panel (QTextBrowser → QWebEngineView) [deep]
├── Task 5: Replace edit dialog preview pane [unspecified-high]
└── Task 6: Replace middle-click notes window [unspecified-high]

Wave 3 (After Wave 2 - sequential integration):
├── Task 7: Add QWebEngineView availability check + fallback [quick]
└── Task 8: Final integration test + cleanup [quick] (after T7)

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay
```

### Dependency Matrix

- **1-3**: - → 4-6
- **4-6**: 1, 2, 3 → 7
- **7**: 4, 5, 6 → 8
- **8**: 7 → F1-F4

### Agent Dispatch Summary

- **1**: **3** - T1 → `quick`, T2 → `quick`, T3 → `unspecified-high`
- **2**: **3** - T4 → `deep`, T5 → `unspecified-high`, T6 → `unspecified-high`
- **3**: **2** - T7 → `quick` → T8 → `quick` (sequential)
- **FINAL**: **4** - F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Download and vendor frontend libraries

  **What to do**:
  - Download `marked.min.js` (v12+) to `python3.11libs/MA/shelf_tool_pro/vendor/`
  - Download `highlight.min.js` (v11+) with common languages to same directory
  - Create `vendor/__init__.py` (empty)
  - Verify file sizes are reasonable (< 100KB each)

  **Must NOT do**:
  - Do NOT use CDN references
  - Do NOT download full highlight.js with all languages
  - Do NOT modify the downloaded JS files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file download task, no complex logic
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: None

  **References**:
  - `python3.11libs/MA/shelf_tool_pro/` - Target directory for vendor folder
  - https://marked.js.org/ - marked.js official site
  - https://highlightjs.org/ - highlight.js official site

  **Acceptance Criteria**:
  - [ ] `vendor/marked.min.js` exists and is valid JS (can be parsed)
  - [ ] `vendor/highlight.min.js` exists and is valid JS
  - [ ] Both files < 100KB

  **QA Scenarios**:
  ```
  Scenario: Verify vendored files exist and are valid
    Tool: Bash
    Steps:
      1. Check file existence: test -f vendor/marked.min.js && echo "OK" || echo "FAIL"
      2. Check file existence: test -f vendor/highlight.min.js && echo "OK" || echo "FAIL"
      3. Check file sizes: wc -c vendor/marked.min.js vendor/highlight.min.js
    Expected Result: Both files exist and are < 100KB
    Evidence: .sisyphus/evidence/task-1-vendor-check.txt
  ```

  **Commit**: YES (groups with 2, 3)
  - Message: `feat(shelf_tool_pro): vendor marked.js and highlight.js`
  - Files: `python3.11libs/MA/shelf_tool_pro/vendor/`
  - Pre-commit: None

- [x] 2. Create HTML template with VitePress-style CSS

  **What to do**:
  - Create `vendor/template.html` with:
    - `<meta charset="utf-8">` declaration
    - Inline `<script>` tags for marked.js and highlight.js
    - VitePress-style CSS for code blocks (round corners, `#2E2E32` background, language label)
    - Dark theme matching existing UI (`#1e1e1e` bg, `#d4d4d4` text)
    - `window.renderMarkdown(text)` JS function that parses markdown and updates DOM
    - HTML escaping for injected content (prevent XSS)
  - Template should be self-contained (no external dependencies)

  **Must NOT do**:
  - Do NOT use external CSS/JS references
  - Do NOT include Vue/React frameworks
  - Do NOT add copy buttons or line numbers

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: HTML/CSS template creation, straightforward
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: None

  **References**:
  - `python3.11libs/MA/shelf_tool_pro/vendor/` - Output directory
  - `python3.11libs/MA/shelf_tool_pro/styles.py` - Existing color constants for reference
  - VitePress documentation for code block styling reference

  **Acceptance Criteria**:
  - [ ] Template is valid HTML5
  - [ ] Contains inline script tags for both libraries
  - [ ] Has `window.renderMarkdown(text)` function
  - [ ] Code block CSS matches VitePress style (round corners, dark bg, language label)

  **QA Scenarios**:
  ```
  Scenario: Verify template structure
    Tool: Bash
    Steps:
      1. Check template exists: test -f vendor/template.html
      2. Verify meta charset: grep -c 'meta charset' vendor/template.html
      3. Verify marked.js reference: grep -c 'marked.min.js' vendor/template.html
      4. Verify highlight.js reference: grep -c 'highlight.min.js' vendor/template.html
      5. Verify renderMarkdown function: grep -c 'renderMarkdown' vendor/template.html
    Expected Result: All checks pass (count > 0)
    Evidence: .sisyphus/evidence/task-2-template-check.txt
  ```

  **Commit**: YES (groups with 1, 3)
  - Message: `feat(shelf_tool_pro): add HTML template with VitePress-style CSS`
  - Files: `python3.11libs/MA/shelf_tool_pro/vendor/template.html`
  - Pre-commit: None

- [x] 3. Create web_renderer.py module

  **What to do**:
  - Create `python3.11libs/MA/shelf_tool_pro/web_renderer.py`
  - Implement `WebRenderer` class:
    - `__init__`: Load HTML template, create QWebEngineView instance
    - `render(markdown_text)`: Inject markdown via `runJavaScript()`, wait for completion
    - `_on_load_finished`: Handle template load completion
    - `get_widget()`: Return the QWebEngineView instance
  - Handle async timing: `setHtml()` → `loadFinished` → `runJavaScript()`
  - HTML escape markdown text before passing to JS
  - Add error handling for JS injection failures

  **Must NOT do**:
  - Do NOT create new QWebEngineView per render call
  - Do NOT use synchronous blocking for async operations
  - Do NOT modify the HTML template at runtime

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Complex async timing, requires understanding of QWebEngineView lifecycle
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: None (module structure can be created independently; vendor files referenced by path, not imported)

  **References**:
  - `thumbnail_widget.py:502-562` - Current _init_notes_panel and _show_notes_panel implementation
  - `thumbnail_widget.py:201-270` - Current _on_edit_notes implementation
  - `thumbnail_widget.py:317-368` - Current _open_notes_window implementation
  - PySide6 QWebEngineView documentation for async patterns

  **Acceptance Criteria**:
  - [ ] WebRenderer class can be instantiated
  - [ ] render() method accepts markdown text and triggers JS injection
  - [ ] loadFinished signal is properly handled
  - [ ] HTML escaping prevents XSS from script tags in markdown

  **QA Scenarios**:
  ```
  Scenario: Verify WebRenderer basic functionality
    Tool: Bash (Python REPL)
    Steps:
      1. Import WebRenderer class
      2. Instantiate with mock QWebEngineView
      3. Call render() with simple markdown text
      4. Verify no exceptions raised
    Expected Result: Import succeeds, instantiation succeeds, render() completes without error
    Evidence: .sisyphus/evidence/task-3-webrenderer-basic.txt
  
  Scenario: Verify HTML escaping
    Tool: Bash (Python REPL)
    Steps:
      1. Call WebRenderer._escape_html('<script>alert("xss")</script>')
      2. Verify output is '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
    Expected Result: HTML entities are properly escaped
    Evidence: .sisyphus/evidence/task-3-escape-check.txt
  ```

  **Commit**: YES (groups with 1, 2)
  - Message: `feat(shelf_tool_pro): add WebRenderer module`
  - Files: `python3.11libs/MA/shelf_tool_pro/web_renderer.py`
  - Pre-commit: None

- [x] 4. Replace hover preview panel (QTextBrowser → QWebEngineView)

  **What to do**:
  - Modify `_init_notes_panel()` in `thumbnail_widget.py`:
    - Replace `QTextBrowser` with `WebRenderer.get_widget()`
    - Keep window flags, event filter, visibility logic
  - Modify `_show_notes_panel()`:
    - Replace `render_markdown()` + `setHtml()` with `web_renderer.render(note_text)`
    - Handle async timing (panel may need to show after render completes)
    - Keep resize, positioning, show/raise/activateWindow logic
  - Keep `_hide_notes_panel()`, `_delayed_hide_notes()`, `eventFilter()` unchanged

  **Must NOT do**:
  - Do NOT change the hover timing (500ms timer)
  - Do NOT change the panel positioning logic
  - Do NOT remove the mouse-in-notes detection

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex async timing, must preserve existing behavior while changing rendering engine
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Wave 1 completion)
  - **Parallel Group**: Wave 2 (with Tasks 5, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `thumbnail_widget.py:502-562` - Current _init_notes_panel and _show_notes_panel
  - `thumbnail_widget.py:564-584` - Hide and event filter logic (keep unchanged)
  - `web_renderer.py` - New WebRenderer class

  **Acceptance Criteria**:
  - [ ] Hover preview shows markdown rendered with VitePress-style code blocks
  - [ ] Panel appears within 500ms of hover (same as before)
  - [ ] Mouse-in-notes detection still works (panel stays visible when mouse moves to it)
  - [ ] Panel hides correctly when mouse leaves

  **QA Scenarios**:
  ```
  Scenario: Verify hover preview renders code blocks correctly
    Tool: Playwright (or manual screenshot in Houdini)
    Steps:
      1. Create a tool with markdown note containing code block
      2. Hover over thumbnail for 500ms
      3. Screenshot the preview panel
      4. Verify code block has round corners, dark background, syntax highlighting
    Expected Result: Code block renders as continuous container with VitePress style
    Evidence: .sisyphus/evidence/task-4-hover-codeblock.png
  
  Scenario: Verify hover timing unchanged
    Tool: Bash (timing measurement)
    Steps:
      1. Record timestamp before hover
      2. Hover over thumbnail
      3. Record timestamp when panel appears
      4. Calculate delta
    Expected Result: Delta <= 600ms (allowing 100ms tolerance)
    Evidence: .sisyphus/evidence/task-4-hover-timing.txt
  ```

  **Commit**: YES
  - Message: `refactor(shelf_tool_pro): replace hover preview with QWebEngineView`
  - Files: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`
  - Pre-commit: None

- [x] 5. Replace edit dialog preview pane

  **What to do**:
  - Modify `_on_edit_notes()` in `thumbnail_widget.py`:
    - Replace `preview_browser = QtWidgets.QTextBrowser()` with `web_renderer.get_widget()`
    - Replace `preview_browser.setHtml(render_markdown(text))` with `web_renderer.render(text)`
    - Keep the 300ms debounce timer
    - Keep splitter layout, dialog sizing, button logic
  - Handle async update: debounce timer → `web_renderer.render()` → preview updates

  **Must NOT do**:
  - Do NOT change the 300ms debounce timing
  - Do NOT change the dialog layout or sizing
  - Do NOT modify the text editor (left side)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Straightforward replacement, but must handle async timing with debounce
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `thumbnail_widget.py:201-315` - Current _on_edit_notes implementation
  - `web_renderer.py` - New WebRenderer class

  **Acceptance Criteria**:
  - [ ] Edit dialog shows live preview with VitePress-style rendering
  - [ ] Preview updates within 300ms of typing (debounce)
  - [ ] Code blocks in preview render correctly
  - [ ] Dialog layout unchanged (50:50 split, 900x700 size)

  **QA Scenarios**:
  ```
  Scenario: Verify edit dialog preview updates correctly
    Tool: Playwright (or manual screenshot in Houdini)
    Steps:
      1. Open edit dialog for a tool
      2. Type markdown with code block in left editor
      3. Wait 300ms
      4. Screenshot right preview pane
      5. Verify code block renders correctly
    Expected Result: Preview updates with correct rendering after debounce
    Evidence: .sisyphus/evidence/task-5-edit-preview.png
  ```

  **Commit**: YES (groups with 6)
  - Message: `refactor(shelf_tool_pro): replace edit dialog preview with QWebEngineView`
  - Files: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`
  - Pre-commit: None

- [x] 6. Replace middle-click notes window

  **What to do**:
  - Modify `_open_notes_window()` in `thumbnail_widget.py`:
    - Replace `notes_display = QtWidgets.QTextBrowser()` with `web_renderer.get_widget()`
    - Replace `notes_display.setHtml(render_markdown(current_note))` with `web_renderer.render(current_note)`
    - Keep window flags, sizing, positioning, show/raise/activateWindow logic
  - Create separate WebRenderer instance for this window (not shared with hover panel)

  **Must NOT do**:
  - Do NOT change the window size (450x600)
  - Do NOT change the window flags (close button, maximize button, stays on top)
  - Do NOT change the positioning logic

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Similar to Task 4, but simpler (no async timing concerns)
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5)
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 1, 2, 3

  **References**:
  - `thumbnail_widget.py:317-368` - Current _open_notes_window implementation
  - `web_renderer.py` - New WebRenderer class

  **Acceptance Criteria**:
  - [ ] Middle-click opens notes window with VitePress-style rendering
  - [ ] Window size is 450x600
  - [ ] Window has close and maximize buttons
  - [ ] Code blocks render correctly

  **QA Scenarios**:
  ```
  Scenario: Verify middle-click notes window renders correctly
    Tool: Playwright (or manual screenshot in Houdini)
    Steps:
      1. Middle-click a tool with markdown notes
      2. Screenshot the notes window
      3. Verify all markdown elements render correctly (headings, code blocks, lists, tables)
    Expected Result: Window shows properly rendered markdown
    Evidence: .sisyphus/evidence/task-6-middle-click-notes.png
  ```

  **Commit**: YES (groups with 5)
  - Message: `refactor(shelf_tool_pro): replace middle-click notes window with QWebEngineView`
  - Files: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`
  - Pre-commit: None

- [x] 7. Add QWebEngineView availability check + fallback

  **What to do**:
  - Add import check at top of `thumbnail_widget.py`:
    ```python
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView
        _WEB_ENGINE_AVAILABLE = True
    except ImportError:
        _WEB_ENGINE_AVAILABLE = False
        logger.warning("QWebEngineView not available, falling back to QTextBrowser")
    ```
  - Modify `_init_notes_panel()` to check `_WEB_ENGINE_AVAILABLE`:
    - If True: use WebRenderer
    - If False: use existing QTextBrowser + render_markdown()
  - Keep `render_markdown` import for fallback path
  - Add similar checks for edit dialog and middle-click window

  **Must NOT do**:
  - Do NOT crash if QWebEngineView is unavailable
  - Do NOT remove the existing render_markdown fallback
  - Do NOT log errors (only warnings)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple conditional logic, straightforward
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Wave 2 completion)
  - **Parallel Group**: Wave 3 (with Task 8)
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 4, 5, 6

  **References**:
  - `thumbnail_widget.py:1-15` - Current imports
  - `thumbnail_widget.py:502-562` - _init_notes_panel
  - `thumbnail_widget.py:201-315` - _on_edit_notes
  - `thumbnail_widget.py:317-368` - _open_notes_window

  **Acceptance Criteria**:
  - [ ] Import check correctly detects QWebEngineView availability
  - [ ] Fallback path uses QTextBrowser + render_markdown()
  - [ ] No crashes when QWebEngineView is unavailable
  - [ ] Warning logged when falling back

  **QA Scenarios**:
  ```
  Scenario: Verify fallback when QWebEngineView unavailable
    Tool: Bash (Python REPL with mocked import)
    Steps:
      1. Mock ImportError for QtWebEngineWidgets
      2. Import thumbnail_widget module
      3. Verify _WEB_ENGINE_AVAILABLE is False
      4. Verify warning is logged
      5. Verify notes panel can still be created (QTextBrowser path)
    Expected Result: Fallback works, no crashes, warning logged
    Evidence: .sisyphus/evidence/task-7-fallback-check.txt
  ```

  **Commit**: YES
  - Message: `feat(shelf_tool_pro): add QWebEngineView availability check with fallback`
  - Files: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`
  - Pre-commit: None

- [x] 8. Final integration test + cleanup

  **What to do**:
  - Test all three rendering paths work correctly:
    1. Hover preview panel
    2. Edit dialog preview
    3. Middle-click notes window
  - Verify fallback path works (simulate QWebEngineView unavailable)
  - Remove unused imports from `thumbnail_widget.py`
  - Verify no memory leaks (QWebEngineView instances properly managed)
  - Update `__init__.py` exports if needed

  **Must NOT do**:
  - Do NOT add new features
  - Do NOT change existing behavior beyond rendering engine swap
  - Do NOT modify other modules

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Integration testing and cleanup
  - **Skills**: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Wave 3 completion)
  - **Parallel Group**: Wave 3 (with Task 7)
  - **Blocks**: Final verification wave
  - **Blocked By**: Task 7

  **References**:
  - `thumbnail_widget.py` - All modified sections
  - `web_renderer.py` - New module
  - `vendor/` - Vendored files

  **Acceptance Criteria**:
  - [ ] All three rendering paths work correctly
  - [ ] Fallback path works
  - [ ] No unused imports
  - [ ] No memory leaks (QWebEngineView instances reused)

  **QA Scenarios**:
  ```
  Scenario: Full integration test - all rendering paths
    Tool: Bash (Houdini Python Console simulation)
    Steps:
      1. Start Houdini (or simulate environment)
      2. Create tool with markdown notes containing code blocks, tables, lists
      3. Test hover preview
      4. Test edit dialog preview
      5. Test middle-click notes window
      6. Verify all render correctly
    Expected Result: All three paths work, markdown renders correctly
    Evidence: .sisyphus/evidence/task-8-integration.png
  
  Scenario: Verify no unused imports
    Tool: Bash
    Steps:
      1. Run pyflakes or similar on thumbnail_widget.py
      2. Check for unused imports
    Expected Result: No unused imports
    Evidence: .sisyphus/evidence/task-8-imports-check.txt
  ```

  **Commit**: YES
  - Message: `chore(shelf_tool_pro): final cleanup and integration verification`
  - Files: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`
  - Pre-commit: None

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Review all changed files for: unused imports, error handling, async timing correctness, memory management. Check AI slop: excessive comments, over-abstraction.
  Output: `Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill if UI)
  Execute EVERY QA scenario from EVERY task. Test cross-task integration. Test edge cases: empty notes, notes with special characters, notes with script tags. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **1**: `feat(shelf_tool_pro): vendor marked.js and highlight.js, add HTML template and WebRenderer` - vendor/, web_renderer.py
- **2**: `refactor(shelf_tool_pro): replace QTextBrowser with QWebEngineView in all rendering paths` - thumbnail_widget.py
- **3**: `feat(shelf_tool_pro): add QWebEngineView availability check with fallback` - thumbnail_widget.py
- **4**: `chore(shelf_tool_pro): final cleanup and integration verification` - thumbnail_widget.py

---

## Success Criteria

### Verification Commands
```bash
# In Houdini Python Console:
from PySide6.QtWebEngineWidgets import QWebEngineView  # Should succeed or fail gracefully
from MA.shelf_tool_pro.web_renderer import WebRenderer  # Should succeed
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] Code blocks render as continuous containers with VitePress style
- [ ] Fallback works when QWebEngineView unavailable
- [ ] No memory leaks (QWebEngineView instances reused)
- [ ] No unused imports
- [ ] All evidence files captured
