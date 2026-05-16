"""Web-based Markdown renderer using QWebEngineView.

Uses vendored marked.js + highlight.js via an HTML template to render
Markdown with proper syntax highlighting and VitePress-style code blocks.
"""

import json
import logging
import os

from PySide6.QtCore import QUrl, QObject
from PySide6.QtWebEngineWidgets import QWebEngineView

logger = logging.getLogger(__name__)


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
        self._view = QWebEngineView()
        self._ready = False
        self._pending_render: list[str] = []

        # Load HTML template
        template_path = os.path.join(os.path.dirname(__file__), "vendor", "template.html")
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
        vendor_dir = os.path.join(os.path.dirname(__file__), "vendor")
        self._view.setHtml(
            self._html_template,
            baseUrl=QUrl.fromLocalFile(vendor_dir + os.sep),
        )

    def render(self, markdown_text: str) -> None:
        """Render markdown text in the web view.

        If the page is ready, inject immediately. Otherwise, queue for
        later processing after loadFinished fires.

        Args:
            markdown_text: Raw Markdown text (not pre-escaped).
        """
        if self._ready:
            self._inject_markdown(markdown_text)
        else:
            logger.debug("WebRenderer: page not ready, queuing render")
            self._pending_render.append(markdown_text)

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
            # Process any queued render calls
            pending = self._pending_render[:]
            self._pending_render.clear()
            for text in pending:
                self._inject_markdown(text)
        else:
            logger.error("WebRenderer: page failed to load")
            self._ready = False

    def _inject_markdown(self, text: str) -> None:
        """Inject markdown text into the page via runJavaScript.

        Escapes the text for safe JS string literal injection, then calls
        window.renderMarkdown() defined in the HTML template.

        Args:
            text: Raw Markdown text.
        """
        # Use json.dumps to safely escape for JS string literal context
        # (handles quotes, backslashes, newlines, unicode, etc.)
        js_safe_text = json.dumps(text)

        js_code = f"window.renderMarkdown({js_safe_text});"

        try:
            self._view.page().runJavaScript(js_code, 0, self._on_js_result)
        except Exception as e:
            logger.error("WebRenderer: JS injection failed: %s", e)

    def _on_js_result(self, result) -> None:
        """Callback for runJavaScript execution."""
        logger.debug("WebRenderer: JS execution result: %s", result)
