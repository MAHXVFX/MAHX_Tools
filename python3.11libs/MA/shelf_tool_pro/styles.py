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
    f"QPushButton#settingsButton {{ background-color: #6b4c9c; color: white; "
    f"padding: 6px 8px; border-radius: 10px; min-width: 50px; font-weight: bold; "
    f"text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }}"
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

# ── 对话框通用样式 ──────────────────────────────

GROUPBOX_STYLE = (
    f"QGroupBox {{"
    f"  color: {TEXT_SECONDARY};"
    f"  font-size: 12px;"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  border-radius: 6px;"
    f"  margin-top: 12px;"
    f"  padding: 16px 12px 12px 12px;"
    f"}}"
    f"QGroupBox::title {{"
    f"  subcontrol-origin: margin;"
    f"  left: 12px;"
    f"  padding: 0 4px;"
    f"}}"
)

INPUT_STYLE = (
    f"QLineEdit {{"
    f"  background-color: {BG_INPUT};"
    f"  color: {TEXT_PRIMARY};"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  border-radius: 4px;"
    f"  padding: 6px;"
    f"}}"
    f"QLineEdit:focus {{ border-color: {ACCENT_BLUE}; }}"
)

INPUT_INVALID_STYLE = (
    f"QLineEdit {{"
    f"  background-color: {BG_INPUT};"
    f"  color: {TEXT_PRIMARY};"
    f"  border: 1px solid #ef4444;"
    f"  border-radius: 4px;"
    f"  padding: 6px;"
    f"}}"
)

INPUT_READONLY_STYLE = (
    f"QLineEdit {{"
    f"  background-color: {BG_INPUT};"
    f"  color: {TEXT_SECONDARY};"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  border-radius: 4px;"
    f"  padding: 6px;"
    f"}}"
)

DROPDOWN_BTN_STYLE = (
    f"background: transparent; border: none;"
    f"color: {ACCENT_BLUE}; font-size: 14px; padding: 0 8px;"
)

INPUT_CONTAINER_STYLE = (
    f"background-color: {BG_INPUT};"
    f"border: 1px solid {BORDER_COLOR}; border-radius: 4px;"
)

SUFFIX_STYLE = "color: #666666; background: transparent; padding: 0 4px; font-size: 12px;"

SAVE_BUTTON_STYLE = (
    f"QPushButton {{"
    f"  background-color: {ACCENT_BLUE};"
    f"  color: white;"
    f"  border-radius: 6px;"
    f"  padding: 8px 20px;"
    f"}}"
    f"QPushButton:hover {{ background-color: #0e77b8; }}"
    f"QPushButton:disabled {{"
    f"  background-color: #3a3a3a;"
    f"  color: #666666;"
    f"}}"
)

CANCEL_BUTTON_STYLE = (
    f"QPushButton {{"
    f"  background-color: {BG_INPUT};"
    f"  color: {TEXT_SECONDARY};"
    f"  border: 1px solid {BORDER_COLOR};"
    f"  border-radius: 6px;"
    f"  padding: 8px 20px;"
    f"}}"
    f"QPushButton:hover {{"
    f"  background-color: {BG_HOVER};"
    f"  color: {TEXT_PRIMARY};"
    f"}}"
)

THUMB_BG = "#2d2d2d"
