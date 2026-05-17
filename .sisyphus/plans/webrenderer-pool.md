# 共享 WebRenderer 单例 - 减少 QtWebEngineProcess.exe 进程数

## TL;DR

> **问题**：每个 ThumbnailWidget 在 `__init__` 时创建独立 `WebRenderer`（QWebEngineView），100 个缩略图 = 100 个 QtWebEngineProcess.exe 进程。
>
> **方案**：全局只创建 1 个 `WebRenderer` 作为单例，所有缩略图共享悬停备注面板。
>
> **进程数**：100 → 1（仅悬停面板共享；编辑对话框/中键窗口按需创建，不膨胀）

---

## 改动文件

### 1. `python3.11libs/MA/shelf_tool_pro/web_renderer.py`

**新增 `WebRendererPool` 单例类**（放在 `_MediaNavigationHandler` 之后）：

```python
class WebRendererPool:
    """Global singleton pool for the shared hover notes WebRenderer."""
    _renderer: WebRenderer | None = None
    _mouse_in_notes: bool = False

    @classmethod
    def get_renderer(cls) -> "WebRenderer":
        if cls._renderer is None:
            cls._renderer = WebRenderer()
        return cls._renderer

    @classmethod
    def show_notes(cls, note_text: str, panel_widget) -> None:
        renderer = cls.get_renderer()
        renderer.render(note_text)
        panel = renderer.get_widget()
        panel.move(panel_widget)
        panel.show()
        panel.raise_()
        panel.activateWindow()

    @classmethod
    def hide_notes(cls) -> None:
        if cls._renderer is not None:
            cls._renderer.get_widget().hide()
        cls._mouse_in_notes = False
```

### 2. `python3.11libs/MA/shelf_tool_pro/thumbnail_widget.py`

**import 变更**：
```python
# 移除:
from MA.shelf_tool_pro.web_renderer import WebRenderer
# 改为:
from MA.shelf_tool_pro.web_renderer import WebRendererPool
```

**`__init__` 移除 `_init_notes_panel()` 调用**（第 67 行）：
```python
# 删除:
self._init_notes_panel()
# 同时删除实例变量:
self._notes_panel = None
self._web_renderer = None
```

**删除 `_init_notes_panel` 方法**（第 493-505 行）

**修改 `_show_notes_panel`**（第 507-536 行）：
```python
def _show_notes_panel(self):
    note_text = ShelfToolsCacheManager.get_note(self._unique_id)
    if not note_text or not note_text.strip():
        return

    # 智能定位
    panel_width = WebRendererPool._NOTES_PANEL_WIDTH   # 450
    panel_height = WebRendererPool._NOTES_PANEL_HEIGHT  # 600
    pos_above = self.mapToGlobal(QtCore.QPoint(0, -panel_height))
    available = self._get_available_geometry()

    if pos_above.y() < available.y():
        pos = self.mapToGlobal(QtCore.QPoint(0, self.height()))
    else:
        pos = pos_above

    pos = self._clamp_to_screen(pos, panel_width, panel_height)

    WebRendererPool.show_notes(note_text, pos)
```

**修改 `_hide_notes_panel`**（第 538-541 行）：
```python
def _hide_notes_panel(self):
    WebRendererPool.hide_notes()
```

**修改 `_delayed_hide_notes`**（第 543-547 行）：
```python
def _delayed_hide_notes(self):
    if not WebRendererPool._mouse_in_notes:
        WebRendererPool.hide_notes()
```

**修改 `eventFilter`**（第 549-558 行）：
```python
def eventFilter(self, obj, event):
    # 检查是否是全局 notes panel
    notes_panel = WebRendererPool.get_renderer().get_widget()
    if obj == notes_panel:
        if event.type() == QtCore.QEvent.Type.Enter:
            WebRendererPool._mouse_in_notes = True
        elif event.type() == QtCore.QEvent.Type.Leave:
            WebRendererPool._mouse_in_notes = False
            QtCore.QTimer.singleShot(self._NOTES_HIDE_DELAY, self._hide_notes_panel)
    return super().eventFilter(obj, event)
```

**在 `WebRendererPool` 添加常量**：
```python
class WebRendererPool:
    _NOTES_PANEL_WIDTH = 450
    _NOTES_PANEL_HEIGHT = 600
    # ... 其余代码
```

---

## 效果

| 指标 | 修改前 | 修改后 |
|---|---|---|
| 悬停面板进程数 | N（每个缩略图 1 个） | 1（全局共享） |
| 编辑对话框进程 | 按需创建，关闭释放 | 不变 |
| 中键窗口进程 | 按需创建，关闭释放 | 不变 |
| 100 个缩略图总进程 | ~100 | ~3（1 共享 + 最多 2 个按需） |

---

## 执行

```
task(category="quick", load_skills=[], description="实现 WebRendererPool 单例", prompt="按 .sisyphus/plans/webrenderer-pool.md 实现。修改 web_renderer.py 和 thumbnail_widget.py。", run_in_background=false)
```
