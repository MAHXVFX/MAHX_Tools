import math

from PySide6.QtWidgets import QGraphicsOpacityEffect
from PySide6.QtCore import QTimer

from .constants import ANIMATION_DURATION_MS, ANIMATION_STEPS


def animate_widget_height(widget, start_h, end_h, duration=ANIMATION_DURATION_MS,
                          visible=True, fade_in=True, on_complete=None):
    steps = ANIMATION_STEPS
    interval = duration // steps

    def _animate(step=0):
        if step >= steps:
            widget.setFixedHeight(end_h)
            if not visible:
                widget.setVisible(False)
                widget.setGraphicsEffect(None)
            else:
                _set_opacity(widget, 1.0)
            if on_complete:
                on_complete()
            return

        t = step / steps
        if end_h > start_h:
            current_h = start_h + (end_h - start_h) * (1 - math.pow(1 - t, 3))
            opacity = t
        else:
            current_h = start_h * (1 - math.pow(t, 2))
            opacity = 1.0 - t

        widget.setFixedHeight(int(current_h))
        if fade_in or (not fade_in and step > 0):
            _set_opacity(widget, opacity)
        QTimer.singleShot(interval, lambda: _animate(step + 1))

    widget.setVisible(True)
    if fade_in:
        _set_opacity(widget, 0.0)
    QTimer.singleShot(0, lambda: _animate())


def elastic_resize(widget, expanding):
    if expanding:
        widget.setFixedHeight(0)
        animate_widget_height(widget, 0, widget.sizeHint().height(),
                              visible=True, fade_in=True)
    else:
        current_height = widget.height()
        widget.setFixedHeight(current_height)
        animate_widget_height(widget, current_height, 0,
                              visible=False, fade_in=False)


def animate_button_width(button, expanding, start_w=100, end_w=130, duration=200):
    steps = 20
    interval = duration // steps

    def _animate(step=0):
        if step >= steps:
            button.setFixedWidth(end_w)
            return
        t = step / steps
        if expanding:
            current_w = start_w + (end_w - start_w) * (1 - math.pow(1 - t, 3))
        else:
            current_w = start_w * (1 - math.pow(t, 2)) + end_w * math.pow(t, 2)
        button.setFixedWidth(int(current_w))
        QTimer.singleShot(interval, lambda: _animate(step + 1))

    button.setFixedWidth(start_w)
    QTimer.singleShot(0, lambda: _animate())


def pulse_button(button, original_color, pulse_color, padding, border_radius, duration=150):
    steps = 6
    interval = duration // steps

    r1, g1, b1 = int(original_color[1:3], 16), int(original_color[3:5], 16), int(original_color[5:7], 16)
    r2, g2, b2 = int(pulse_color[1:3], 16), int(pulse_color[3:5], 16), int(pulse_color[5:7], 16)

    def _animate(step=0):
        if step >= steps:
            button.setStyleSheet(
                f"background-color: {original_color}; color: white; "
                f"padding: {padding}; border-radius: {border_radius};"
            )
            return
        ratio = math.sin(step / steps * math.pi)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        button.setStyleSheet(
            f"background-color: #{r:02x}{g:02x}{b:02x}; color: white; "
            f"padding: {padding}; border-radius: {border_radius};"
        )
        QTimer.singleShot(interval, lambda: _animate(step + 1))

    QTimer.singleShot(0, lambda: _animate())


def _set_opacity(widget, opacity):
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(opacity)
    widget.setGraphicsEffect(effect)
