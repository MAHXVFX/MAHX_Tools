# Learnings - Markdown Rendering Upgrade

## Wave 1: Vendor JS Libraries (2026-05-16)

### Files Created
- `python3.11libs/MA/shelf_tool_pro/vendor/__init__.py` - Empty init file
- `python3.11libs/MA/shelf_tool_pro/vendor/marked.min.js` - v15.0.12, 38.97KB
- `python3.11libs/MA/shelf_tool_pro/vendor/highlight.min.js` - v11.11.1, 124.51KB

### Key Findings

#### highlight.js Size Constraint
- **Target**: < 100KB
- **Actual**: 124.51KB (standard UMD build from CDN)
- **Reason**: The CDN `@highlightjs/cdn-assets/highlight.min.js` is a pre-built bundle with ~40 common languages
- **Attempted alternatives**:
  - `highlight.js/lib/core.min.js` (22KB) + individual language files = 60KB, but uses CommonJS (`module.exports`) - not browser-compatible
  - No `highlight.core.min.js` exists in CDN assets
  - Individual language files from CDN require the core UMD build to be loaded first
- **Decision**: Use standard 124KB UMD build - it's the only browser-compatible option from CDN, and 124KB is acceptable for a syntax highlighting library

#### marked.js
- v15.0.12, 38.97KB - well under 100KB target
- UMD build, works in browser context
- MIT License

#### CDN Sources
- marked: `https://cdn.jsdelivr.net/npm/marked/marked.min.js`
- highlight.js: `https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets/highlight.min.js`

### Reference Paths for web_renderer.py
- marked: `vendor/marked.min.js`
- highlight.js: `vendor/highlight.min.js`

## Wave 2: T4 - Replace Hover Panel QTextBrowser → QWebEngineView (2026-05-16)

### Changes Made
- **File**: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`
- **Import added**: `from MA.shelf_tool_pro.web_renderer import WebRenderer`
- **`__init__`**: Added `self._web_renderer = None` instance variable
- **`_init_notes_panel()`**: Replaced `QtWidgets.QTextBrowser()` with `WebRenderer()` + `get_widget()`
  - Removed QTextBrowser-specific settings: `setReadOnly()`, `setStyleSheet()`, `setMaximumHeight()`, `setOpenExternalLinks()`
  - Kept: window flags (`FramelessWindowHint`), `WA_TranslucentBackground`, `installEventFilter()`, `setVisible(False)`
- **`_show_notes_panel()`**: Replaced `render_markdown()` + `setHtml()` with `self._web_renderer.render(note_text)`
- **`render_markdown` import preserved**: Still needed for edit-notes dialog (T7 fallback path)

### LSP Notes
- PySide6 import error expected (not available outside Houdini)
- Type checker warning on `self._web_renderer.render()` - `_web_renderer` typed as `None` in `__init__` but always initialized in `_init_notes_panel()` called from `__init__`
- Both are false positives, no runtime impact

## Wave 3: T6 - Replace Middle-Click Notes Window QTextBrowser → QWebEngineView (2026-05-16)

### Changes Made
- **File**: `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`
- **Method**: `_open_notes_window()` (lines 314-359)
- **Replaced**: `QtWidgets.QTextBrowser()` + `render_markdown()` + `setHtml()` → `WebRenderer()` + `get_widget()` + `render()`
- **`notes_renderer` is local variable**: Not stored as instance variable (method-scoped, window is standalone)
- **Window flags unchanged**: `Dialog | WindowCloseButtonHint | WindowMaximizeButtonHint | WindowStaysOnTopHint`
- **Window size unchanged**: 450x600
- **Positioning logic unchanged**: `_clamp_to_screen()`
- **`render_markdown` import preserved**: Still needed for fallback paths

### Key Difference from Hover Panel (T4)
- Hover panel uses **instance-level** `self._web_renderer` (reused across show/hide cycles)
- Middle-click window uses **local** `notes_renderer` (window is standalone, created/destroyed per invocation)
- This is correct: middle-click window is a one-shot QDialog, not a persistent panel

## Wave 4: T8 - Final Integration Test + Cleanup (2026-05-16)

### Import Audit
- All 9 imports in thumbnail_widget.py are actively used
- No unused imports found
- render_markdown import preserved for fallback paths (3 methods)
- WebRenderer import used in primary paths (3 methods)

### QWebEngineView Instance Lifecycle
- **Hover panel** (self._web_renderer): Instance variable, created once in _init_notes_panel(), reused across show/hide cycles. No leak.
- **Edit dialog** (preview_renderer): Local variable in _on_edit_notes(), garbage collected when dialog closes. No leak.
- **Middle-click window** (notes_renderer): Local variable in _open_notes_window(), garbage collected when window closes. No leak.

### __init__.py Exports
- No change needed. WebRenderer is internal to thumbnail_widget.py, not part of public API.
- Current export: MAShelfToolProPanel only.

### Code Quality
- Zero TODO/FIXME/HACK comments found
- Zero print() statements (only logger.debug() calls)
- All three rendering paths have proper if/else fallback branches
- Fallback path uses render_markdown() + QTextBrowser consistently

### Final Line Count
- thumbnail_widget.py: 626 lines (up from ~574 original)
- web_renderer.py: 120 lines (new file)
- Total addition: ~172 lines for full QWebEngineView integration with fallback
