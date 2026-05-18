"""Web-based Markdown renderer using QWebEngineView.

Uses vendored marked.js + highlight.js via an HTML template to render
Markdown with proper syntax highlighting and VitePress-style code blocks.
"""

import json
import logging
import os

from PySide6.QtCore import QTimer, QUrl, QObject, Qt
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView

logger = logging.getLogger(__name__)

# File extensions that should be opened in the system player
_MEDIA_EXTENSIONS = {
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a",
}


class _MediaNavigationHandler(QWebEnginePage):
    """Intercepts navigation to file:// media URLs and opens them externally."""

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if url.scheme() == "file":
            path = url.toLocalFile().lower()
            ext = os.path.splitext(path)[1]
            if ext in _MEDIA_EXTENSIONS:
                logger.debug("MediaNavigationHandler: opening %s in system player", url.toDisplayString())
                QDesktopServices.openUrl(url)
                return False  # Block navigation in the web view
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)


class WebRendererPool:
    """Global singleton pool for the shared hover notes WebRenderer."""
    _NOTES_PANEL_WIDTH = 450
    _NOTES_PANEL_HEIGHT = 600
    _FADE_OUT_MS = 180
    _renderer: "WebRenderer | None" = None
    _mouse_in_notes: bool = False
    _show_generation: int = 0

    @classmethod
    def has_renderer(cls) -> bool:
        return cls._renderer is not None

    @classmethod
    def get_renderer(cls) -> "WebRenderer":
        if cls._renderer is None:
            cls._renderer = WebRenderer()
            panel = cls._renderer.get_widget()
            panel.setWindowFlags(
                Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            )
            panel.setAttribute(Qt.WA_TranslucentBackground, False)
            panel.resize(cls._NOTES_PANEL_WIDTH, cls._NOTES_PANEL_HEIGHT)
        return cls._renderer  # type: ignore[return-value]

    @classmethod
    def show_notes(cls, note_text: str, panel_pos) -> None:
        renderer = cls.get_renderer()
        panel = renderer.get_widget()
        cls._show_generation += 1
        generation = cls._show_generation
        panel.hide()

        def _show_after_render(_=None) -> None:
            if generation != cls._show_generation:
                return
            panel.move(panel_pos)
            panel.show()
            panel.raise_()
            panel.activateWindow()

        renderer.render(note_text, _show_after_render, fade=True)

    @classmethod
    def hide_notes(cls) -> None:
        cls._show_generation += 1
        generation = cls._show_generation
        if cls._renderer is not None:
            cls._renderer.hide_content()
            panel = cls._renderer.get_widget()
            QTimer.singleShot(
                cls._FADE_OUT_MS,
                lambda: panel.hide() if generation == cls._show_generation else None,
            )
        cls._mouse_in_notes = False

    @classmethod
    def is_notes_panel(cls, obj) -> bool:
        if cls._renderer and obj is cls._renderer.get_widget():
            return True
        return False


class WebRenderer(QObject):
    """Renders Markdown text via QWebEngineView + marked.js.

    Handles async timing: the HTML template is loaded once via setHtml(),
    and render() calls are queued until loadFinished fires.

    Usage:
        renderer = WebRenderer()
        widget = renderer.get_widget()        # embed this in your UI
        renderer.render("# Hello\\nWorld")     # queues or executes immediately
    """

    def __init__(self):
        super().__init__()
        self._page = _MediaNavigationHandler()
        self._page.setBackgroundColor(QColor("#1F1F24"))
        self._view = QWebEngineView()
        self._view.setPage(self._page)
        self._view.setStyleSheet("QWebEngineView { background-color: #1F1F24; }")
        self._ready = False
        self._pending_render: "tuple[str, object, bool] | None" = None

        # Vendor directory for template and JS libraries
        vendor_dir = os.path.join(os.path.dirname(__file__), "vendor")

        # Load HTML template
        template_path = os.path.join(vendor_dir, "template.html")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                self._html_template = f.read()
            logger.debug("WebRenderer: loaded template from %s", template_path)
        except (OSError, IOError) as e:
            logger.error("WebRenderer: failed to load template: %s", e)
            self._html_template = "<html><body><p>Template not found</p></body></html>"

        # Connect loadFinished signal
        self._view.loadFinished.connect(self._on_load_finished)

        # Load the HTML template into the view with baseUrl for relative script paths
        self._view.setHtml(
            self._html_template,
            baseUrl=QUrl.fromLocalFile(vendor_dir + "/"),
        )

    def render(self, markdown_text: str, callback=None, fade: bool = False) -> None:
        """Render markdown text in the web view.

        Args:
            markdown_text: Raw Markdown text (not pre-escaped).
            callback: Optional callable invoked after JS injection completes.
            fade: Fade in the rendered content inside the web page.
        """
        if self._ready:
            self._inject_markdown(markdown_text, callback, fade=fade)
        else:
            logger.debug("WebRenderer: page not ready, queuing render")
            self._pending_render = (markdown_text, callback, fade)

    def get_widget(self) -> QWebEngineView:
        """Return the QWebEngineView instance for embedding in UI."""
        return self._view

    def _on_load_finished(self, ok: bool) -> None:
        """Handle loadFinished signal from QWebEngineView.

        Args:
            ok: True if page loaded successfully.
        """
        if ok:
            logger.debug("WebRenderer: page loaded successfully")
            self._ready = True
            # Process the last queued render (earlier ones are obsolete)
            if self._pending_render is not None:
                text, callback, fade = self._pending_render
                self._pending_render = None
                self._inject_markdown(text, callback, fade=fade)
        else:
            # If page was already loaded, this is just a navigation cancellation
            # (e.g., media link intercepted), not a real failure.
            if not self._ready:
                logger.error("WebRenderer: page failed to load")
                self._ready = False

    def _inject_markdown(self, text: str, callback=None, fade: bool = False) -> None:
        """Inject markdown text into the page via runJavaScript.

        Args:
            text: Raw Markdown text.
            callback: Optional callable invoked after JS execution completes.
        """
        js_safe_text = json.dumps(text)
        if fade:
            js_code = f"window.renderMarkdown({js_safe_text}, {{fade: true}});"
        else:
            js_code = f"window.renderMarkdown({js_safe_text});"

        try:
            if callback:
                self._view.page().runJavaScript(js_code, 0, callback)
            else:
                self._view.page().runJavaScript(js_code)
        except Exception as e:
            logger.error("WebRenderer: JS injection failed: %s", e)

    def hide_content(self) -> None:
        """Hide current page content without destroying the loaded template."""
        if not self._ready:
            return
        try:
            self._view.page().runJavaScript("window.hideMarkdownContent && window.hideMarkdownContent();")
        except Exception as e:
            logger.error("WebRenderer: JS hide content failed: %s", e)
