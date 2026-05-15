"""MAShelfToolPro 样式常量。"""

ACCENT_BLUE = "#0d6399"
ACCENT_PURPLE = "#8a5cf5"
BG_PRIMARY = "#18181b"
BG_SECONDARY = "#1D1D20"
BG_INPUT = "#2d2d2d"
BG_HOVER = "#3d3d3d"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#cccccc"
BORDER_COLOR = "#3d3d3d"

SETTINGS_BUTTON_STYLE = (
    f"QPushButton#settingsButton {{ background-color: {ACCENT_BLUE}; color: white; "
    f"padding: 6px 8px; border-radius: 10px; min-width: 50px; }}"
)

THUMB_SLIDER_STYLE = f"""
    QSlider#thumbSizeSlider {{
        background-color: transparent; border: none;
    }}
    QSlider#thumbSizeSlider::groove:horizontal {{
        border: none; height: 6px; background-color: #000000; border-radius: 3px;
    }}
    QSlider#thumbSizeSlider::sub-page:horizontal {{
        background-color: {ACCENT_PURPLE}; border-radius: 3px;
    }}
    QSlider#thumbSizeSlider::handle:horizontal {{
        background-color: {TEXT_PRIMARY}; border: 1px solid {ACCENT_PURPLE};
        width: 14px; height: 14px; margin: -4px 0; border-radius: 7px;
    }}
"""

CONTEXT_MENU_STYLE = (
    f"QMenu {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_COLOR}; "
    f"border-radius: 4px; padding: 4px; }}"
    f"QMenu::item {{ padding: 6px 20px; }}"
    f"QMenu::item:selected {{ background-color: {BG_HOVER}; }}"
)
