# Markdown 渲染增强 + Vendoring 依赖计划

## TL;DR

> **Quick Summary**: 将 `python-markdown` 和 `Pygments` 库 vendoring 到项目中，替换现有的 `QTextBrowser.setMarkdown()` 渲染管线，实现完整的 Markdown 渲染（含代码块语法高亮），确保 MAHX_Tools 文件夹可拷贝到其他 Windows 电脑直接使用。
> 
> **Deliverables**: 
> - Vendored `markdown` 库 (~300KB) 置于 `python3.11libs/markdown/`
> - Vendored `Pygments` 库 (~1MB) 置于 `python3.11libs/pygments/`
> - 重构 `thumbnail_widget.py` 的 Markdown 渲染管线
> - 更新所有 Notes 面板（悬停/中键/右键）使用新渲染器
> - 暗色主题代码高亮样式匹配 Houdini 风格
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Vendoring → 渲染管线重构 → 面板更新 → 测试验证

---

## Context

### Original Request
用户需要为 MA ShelfTools Pro 面板的 Notes 功能添加代码块语法高亮支持。由于 MAHX_Tools 需拷贝到其他 Windows 电脑直接使用，不能依赖外部安装的 Python 包，必须将依赖库 vendoring 到项目内部。

### Interview Summary
**Key Discussions**:
- 需要代码块语法高亮 → 决定 vendoring `Pygments`
- 不能安装到外部环境 → 决定 vendoring 到 `python3.11libs/`
- Houdini 21.0 使用 Python 3.11 → 确认兼容性

**Research Findings**:
- `python-markdown` 3.5.2：纯 Python，无 C 扩展，BSD 3-Clause 许可证，~108KB wheel，支持 Python 3.8+
- `Pygments` 2.17.2：纯 Python，无 C 扩展，BSD 2-Clause 许可证，~1.2MB wheel，支持 Python 3.8+
- 两者均兼容 Python 3.11，无需编译
- `markdown` 的 `codehilite` 扩展依赖 Pygments
- Pygments 的 `plugin.py` 使用 `importlib.metadata` 发现外部插件，vendoring 后需调整
- 入口点 (entry points) 用于扩展发现，vendoring 后需手动注册扩展

### Metis Review
**Identified Gaps** (addressed):
- Vendoring 体积控制：Pygments 包含 500+ 语言词法，完整版 ~1.2MB 可接受 → 保留完整版
- 许可证合规：需在项目中保留原始 LICENSE 文件 → 计划中包含此步骤
- Houdini sys.path 加载机制：确认 `python3.11libs/` 自动加入路径 → 无需额外配置
- Entry points 问题：vendoring 后 `markdown` 的扩展发现可能失效 → 需在代码中手动注册扩展
- Pygments `plugin.py`：vendoring 后需禁用外部插件发现 → 修改 `plugin.py` 或捕获异常

---

## Work Objectives

### Core Objective
为 Notes 功能提供完整的 Markdown 渲染能力（含代码高亮），通过 vendoring 实现零外部依赖部署。

### Concrete Deliverables
- `python3.11libs/markdown/` - Vendored markdown 库 (~300KB)
- `python3.11libs/pygments/` - Vendored Pygments 精简版 (~300KB)
- `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py` - 重构后的渲染管线
- `python3.11libs/MA/shelf_tool_pro/markdown_renderer.py` - 新增渲染器模块
- `python3.11libs/MA/shelf_tool_pro/note_editor.py` - 新增实时预览编辑器

### Definition of Done
- [ ] 悬停备注面板正确渲染 Markdown + 代码高亮
- [ ] 中键备注窗口正确渲染 Markdown + 代码高亮
- [ ] 右键编辑器保存的 Markdown 在其他电脑正确渲染
- [ ] 拷贝整个 MAHX_Tools 到新电脑后无需安装任何依赖

### Must Have
- 完整的 GFM 支持（表格、任务列表、删除线等）
- 代码块语法高亮（至少支持 Python、C++、Hscript、Python）
- 暗色主题匹配 Houdini 风格
- 保留现有标题颜色/粗体/斜体样式

### Must NOT Have (Guardrails)
- 不修改 Houdini 系统 Python 环境
- 不引入 C 扩展或需要编译的依赖
- 不改变 Notes 功能的三种交互方式（悬停/中键/右键）
- 不破坏现有的 `_clamp_to_screen` 定位逻辑

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (Houdini 运行时依赖，无法外部测试)
- **Automated tests**: None
- **Framework**: None
- **Agent-Executed QA**: ALWAYS (mandatory for all tasks)

### QA Policy
- **Houdini 内测试**: 用户需在 Houdini 中手动验证渲染效果
- **代码验证**: LSP 检查 + 语法验证
- **Vendoring 验证**: 确认库文件完整且可导入

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - Vendoring 依赖):
├── Task 1: 下载并 vendoring `markdown` 库 [quick]
├── Task 2: 下载并 vendoring `Pygments` 精简版 [quick]
└── Task 3: 验证 vendored 库可导入 [quick]

Wave 2 (After Wave 1 - 渲染管线重构):
├── Task 4: 创建 `markdown_renderer.py` 渲染器模块 [unspecified-high]
├── Task 5: 重构 `_apply_styles_to_document` 适配新 HTML [unspecified-high]
└── Task 6: 实现暗色主题代码高亮样式 [quick]

Wave 3 (After Wave 2 - 面板更新):
├── Task 7: 更新悬停备注面板使用新渲染器 [quick]
├── Task 8: 更新中键备注窗口使用新渲染器 [quick]
└── Task 9: 实现右键编辑器实时预览功能 [unspecified-high]

Wave 4 (After Wave 3 - 集成验证):
└── Task 10: 端到端验证 + 许可证合规检查 [unspecified-high]

Critical Path: Task 1/2 → Task 3 → Task 4/5 → Task 7/8/9 → Task 10
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 3 (Wave 1 & 2 & 3)
```

### Dependency Matrix

- **1-3**: - → 4-6, 1
- **4**: 3 → 7-9, 2
- **5**: 3 → 7-9, 2
- **6**: 4 → 7-9, 2
- **7-9**: 4,5,6 → 10, 3
- **10**: 7,8,9 → -

### Agent Dispatch Summary

- **Wave 1**: **3** - T1-T3 → `quick`
- **Wave 2**: **3** - T4 → `unspecified-high`, T5 → `unspecified-high`, T6 → `quick`
- **Wave 3**: **3** - T7 → `quick`, T8 → `quick`, T9 → `unspecified-high`
- **Wave 4**: **1** - T10 → `unspecified-high`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

- [x] 1. Vendoring `python-markdown` 库

  **What to do**:
  - 使用 `pip download markdown==3.5.2 --no-deps -d temp/` 下载 wheel/sdist
  - 解压到 `python3.11libs/markdown/`
  - 保留 `LICENSE` 和 `LICENSE_OFL` 文件
  - 创建 `python3.11libs/markdown/__init__.py` 确保可导入

  **Must NOT do**:
  - 不修改 markdown 库源码
  - 不安装到系统 Python 环境

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 3, 4, 5
  - **Blocked By**: None

  **References**:
  - PyPI: `https://pypi.org/project/Markdown/3.5.2/#files`
  - 官方文档: `https://python-markdown.github.io/install/`

  **Acceptance Criteria**:
  - [ ] `python3.11libs/markdown/` 目录存在且包含 `__init__.py`
  - [ ] `python3.11libs/markdown/LICENSE` 文件存在
  - [ ] 目录大小约 300KB

  **Commit**: YES (groups with 2, 3)
  - Message: `feat(deps): vendor python-markdown 3.5.2`
  - Files: `python3.11libs/markdown/`

- [x] 2. Vendoring `Pygments` 精简版

  **What to do**:
  - 使用 `pip download Pygments==2.17.2 --no-deps -d temp/` 下载
  - 解压并裁剪 `pygments/lexers/` 目录，仅保留：
    - `python.py`, `python3.py`, `_python_builtins.py`
    - `c_cpp.py`, `_c_like_builtins.py`
    - `shells.py`, `_bash_builtins.py`
    - `haxe.py` (Hscript 近似)
    - `_mapping.py` (需重新生成或手动编辑)
    - `__init__.py`, `_mapping.py`
  - 保留 `pygments/formatters/html.py` (HTML 输出必需)
  - 保留 `pygments/styles/` 中暗色主题相关文件
  - 保留 `LICENSE` 文件
  - 创建 `python3.11libs/pygments/__init__.py` 确保可导入

  **Must NOT do**:
  - 不破坏 `lexers/__init__.py` 的导入逻辑
  - 不删除 `_mapping.py` 中的已保留语言条目

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Tasks 3, 4, 6
  - **Blocked By**: None

  **References**:
  - PyPI: `https://pypi.org/project/Pygments/2.17.2/#files`
  - 官方文档: `https://pygments.org/docs/`

  **Acceptance Criteria**:
  - [ ] `python3.11libs/pygments/` 目录存在且包含 `__init__.py`
  - [ ] `python3.11libs/pygments/LICENSE` 文件存在
  - [ ] 目录大小约 300KB（精简后）
  - [ ] `from pygments.lexers import PythonLexer, CLexer, BashLexer` 可正常导入

  **Commit**: YES (groups with 1, 3)
  - Message: `feat(deps): vendor Pygments 2.17.2 (trimmed)`
  - Files: `python3.11libs/pygments/`

- [x] 3. 验证 vendored 库可导入

  **What to do**:
  - 创建测试脚本验证 `import markdown` 和 `import pygments` 成功
  - 验证 `markdown.markdown("# Test")` 返回正确 HTML
  - 验证 `pygments.highlight()` 可正常工作

  **Must NOT do**:
  - 不依赖系统已安装的库

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on 1, 2)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: Tasks 1, 2

  **Acceptance Criteria**:
  - [ ] `python -c "import sys; sys.path.insert(0, 'python3.11libs'); import markdown; print(markdown.markdown('# Test'))"` 输出 `<h1>Test</h1>`
  - [ ] `python -c "import sys; sys.path.insert(0, 'python3.11libs'); from pygments import highlight; print('OK')"` 输出 `OK`

  **Commit**: YES (groups with 1, 2)
  - Message: `test(deps): verify vendored libraries importable`

- [x] 4. 创建 `markdown_renderer.py` 渲染器模块

  **What to do**:
  - 创建 `python3.11libs/MA/shelf_tool_pro/markdown_renderer.py`
  - 实现 `render_markdown(text: str, theme: str = "dark") -> str` 函数
  - 集成 `markdown.markdown()` 与 `Pygments` 代码高亮
  - 配置扩展：`extra`, `codehilite`, `tables`, `toc`, `fenced_code`
  - 实现暗色主题 CSS 注入

  **Must NOT do**:
  - 不复制现有 `_apply_styles_to_document` 逻辑（需重新设计）
  - 不使用 `QTextBrowser.setMarkdown()`（改用 `setHtml()`）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6)
  - **Blocks**: Tasks 7, 8, 9
  - **Blocked By**: Task 3

  **References**:
  - `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py:112-163` - 现有 `_apply_styles_to_document` 实现
  - `python3.11libs/MA/shelf_tool_pro/styles.py` - 现有样式常量
  - 官方文档: `https://python-markdown.github.io/extensions/code_hilite/`

  **Acceptance Criteria**:
  - [ ] `render_markdown("# Heading\n```python\nprint('hello')\n```")` 返回包含 `<h1>` 和语法高亮代码块的 HTML
  - [ ] 暗色主题 CSS 包含代码块背景色 `#1e1e1e`、文本色 `#d4d4d4`
  - [ ] 标题颜色与现有 `_MARKDOWN_STYLES` 一致

  **Commit**: YES
  - Message: `feat(notes): add markdown_renderer module with code highlighting`
  - Files: `python3.11libs/MA/shelf_tool_pro/markdown_renderer.py`

- [x] 5. 重构 `_apply_styles_to_document` 适配新 HTML

  **What to do**:
  - 废弃现有 `_apply_styles_to_document` 方法
  - 新实现接收 `markdown_renderer.render_markdown()` 输出的 HTML
  - 应用标题颜色、粗体颜色、斜体颜色（保持现有 `_MARKDOWN_STYLES` 配置）
  - 通过 CSS 注入而非 `QTextCursor` 遍历实现样式

  **Must NOT do**:
  - 不保留旧的 `QTextCursor` 遍历逻辑
  - 不修改 `_MARKDOWN_STYLES` 常量定义

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 6)
  - **Blocks**: Tasks 7, 8, 9
  - **Blocked By**: Task 3

  **References**:
  - `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py:112-163` - 待废弃的方法
  - `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py:24-33` - `_MARKDOWN_STYLES` 常量

  **Acceptance Criteria**:
  - [ ] 新 `_apply_styles_to_document` 方法接收 HTML 字符串并返回带样式的 HTML
  - [ ] 标题颜色与 `_MARKDOWN_STYLES` 一致
  - [ ] 代码块样式与 `markdown_renderer` 输出兼容

  **Commit**: YES
  - Message: `refactor(notes): replace QTextCursor styling with CSS injection`
  - Files: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`

- [x] 6. 实现暗色主题代码高亮样式

  **What to do**:
  - 设计 Houdini 风格暗色主题代码高亮 CSS
  - 背景色 `#1e1e1e`，文本色 `#d4d4d4`
  - 关键字 `#569cd6`，字符串 `#ce9178`，注释 `#6a9955`，函数 `#dcdcaa`
  - 集成到 `markdown_renderer.py` 的 CSS 注入逻辑

  **Must NOT do**:
  - 不使用 Pygments 默认亮色主题
  - 不修改 Pygments 库源码

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5)
  - **Blocks**: Tasks 7, 8, 9
  - **Blocked By**: Task 4

  **References**:
  - VS Code Dark+ 主题色板
  - `python3.11libs/MA/shelf_tool_pro/styles.py` - 现有样式常量

  **Acceptance Criteria**:
  - [ ] 代码块背景色 `#1e1e1e`
  - [ ] Python 关键字显示为 `#569cd6`
  - [ ] 字符串显示为 `#ce9178`
  - [ ] 注释显示为 `#6a9955`

  **Commit**: YES
  - Message: `style(notes): add dark theme code highlighting CSS`
  - Files: `python3.11libs/MA/shelf_tool_pro/markdown_renderer.py`

- [x] 7. 更新悬停备注面板使用新渲染器

  **What to do**:
  - 修改 `_show_notes_panel()` 使用 `markdown_renderer.render_markdown()`
  - 替换 `setMarkdown()` 为 `setHtml()` + 样式注入
  - 验证悬停定位逻辑不受影响

  **Must NOT do**:
  - 不改变悬停面板的定位逻辑
  - 不修改 `_clamp_to_screen` 方法

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 9)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 4, 5, 6

  **References**:
  - `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py:543-586` - `_show_notes_panel` 方法

  **Acceptance Criteria**:
  - [ ] 悬停备注正确渲染 Markdown + 代码高亮
  - [ ] 悬停定位逻辑正常工作
  - [ ] 鼠标移向备注面板时保持显示

  **Commit**: YES (groups with 8, 9)
  - Message: `feat(notes): update hover panel to use new markdown renderer`
  - Files: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`

- [x] 8. 更新中键备注窗口使用新渲染器

  **What to do**:
  - 修改 `_open_notes_window()` 使用 `markdown_renderer.render_markdown()`
  - 替换 `setMarkdown()` 为 `setHtml()` + 样式注入
  - 验证窗口定位逻辑不受影响

  **Must NOT do**:
  - 不改变中键窗口的定位逻辑
  - 不修改 `_clamp_to_screen` 方法

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 9)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 4, 5, 6

  **References**:
  - `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py:333-385` - `_open_notes_window` 方法

  **Acceptance Criteria**:
  - [ ] 中键窗口正确渲染 Markdown + 代码高亮
  - [ ] 窗口定位逻辑正常工作
  - [ ] 无备注时无事发生

  **Commit**: YES (groups with 7, 9)
  - Message: `feat(notes): update middle-click window to use new markdown renderer`
  - Files: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`

- [x] 9. 实现右键编辑器实时预览功能

  **What to do**:
  - 修改 `_on_edit_notes()` 对话框为分屏布局（左编辑/右预览）
  - 左侧：`QTextEdit` 用于编辑 Markdown 文本
  - 右侧：`QTextBrowser` 用于实时渲染预览
  - 连接 `textChanged` 信号，延迟 300ms 触发预览更新（防抖）
  - 预览使用 `markdown_renderer.render_markdown()` + 样式注入
  - 保留 OK/Cancel 按钮，保存逻辑不变

  **Must NOT do**:
  - 不改变 `ShelfToolsCacheManager.set_note()` 调用
  - 不修改窗口定位逻辑
  - 不使用 `QWebEngineView`（Houdini 不包含）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 7, 8)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 4, 5, 6

  **References**:
  - `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py:261-331` - `_on_edit_notes` 方法
  - `python3.11libs/MA/shelf_tool_pro/markdown_renderer.py` - 渲染器模块

  **Acceptance Criteria**:
  - [ ] 右键编辑器显示分屏布局（左编辑/右预览）
  - [ ] 编辑时预览实时更新（300ms 防抖）
  - [ ] 代码块在预览中正确高亮
  - [ ] OK 按钮保存后，悬停/中键面板渲染正确
  - [ ] 窗口定位逻辑正常工作

  **Commit**: YES (groups with 7, 8)
  - Message: `feat(notes): add live preview to right-click editor`
  - Files: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`

- [x] 10. 端到端验证 + 许可证合规检查

  **What to do**:
  - 验证所有 Notes 面板渲染效果
  - 确认 `markdown/LICENSE` 和 `pygments/LICENSE` 文件存在
  - 检查 vendored 库完整性
  - 更新 `AGENTS.md` 文档

  **Must NOT do**:
  - 不遗漏任何许可证文件
  - 不修改 vendored 库源码

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (final verification)
  - **Blocks**: -
  - **Blocked By**: Tasks 7, 8, 9

  **References**:
  - `AGENTS.md` - 架构文档
  - `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py` - 主文件

  **Acceptance Criteria**:
  - [ ] 所有 Notes 面板正确渲染 Markdown + 代码高亮
  - [ ] `markdown/LICENSE` 文件存在
  - [ ] `pygments/LICENSE` 文件存在
  - [ ] `AGENTS.md` 更新包含 vendored 依赖说明

  **Commit**: YES
  - Message: `docs: update AGENTS.md with vendored dependencies note`
  - Files: `AGENTS.md`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE.

- [x] F1. **Plan Compliance Audit** — `oracle`
- [x] F2. **Code Quality Review** — `unspecified-high`
- [x] F3. **Real Manual QA** — `unspecified-high`
- [x] F4. **Scope Fidelity Check** — `deep`

---

## Commit Strategy

- **Wave 1**: `feat(deps): vendor markdown 3.5.2 and Pygments 2.17.2 (trimmed)`
- **Wave 2**: `feat(notes): add markdown renderer with code highlighting`
- **Wave 3**: `feat(notes): update all notes panels + add live preview editor`
- **Wave 4**: `docs: update AGENTS.md with vendored dependencies note`

---

## Success Criteria

### Verification Commands
```bash
python -c "import sys; sys.path.insert(0, 'python3.11libs'); import markdown; print(markdown.markdown('# Test'))"
# Expected: <h1>Test</h1>

python -c "import sys; sys.path.insert(0, 'python3.11libs'); from pygments import highlight; print('OK')"
# Expected: OK
```

### Final Checklist
- [ ] Vendored 库完整且可导入
- [ ] 所有 Notes 面板正确渲染 Markdown + 代码高亮
- [ ] 许可证文件齐全
- [ ] AGENTS.md 更新
