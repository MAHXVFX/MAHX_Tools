BG_PRIMARY = "#18181b"
BG_SECONDARY = "#1D1D20"
BG_INPUT = "#2d2d2d"
BG_HOVER = "#3d3d3d"
BG_WIDGET_HOVER = "#3a3a3a"
BORDER_COLOR = "#3d3d3d"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#cccccc"
TEXT_STATUS = "#888888"
ACCENT_BLUE = "#0d6399"
ACCENT_BLUE_HOVER = "#0a4d7a"
ACCENT_BLUE_PRESSED = "#083a5f"
ACCENT_BLUE_LIGHT = "#4da6d1"
ACCENT_BLUE_LIGHTER = "#1a7bb8"
ACCENT_PURPLE = "#8a5cf5"
ACCENT_YELLOW = "#e0cb56"
STATUS_SUCCESS = "#87cc8e"
STATUS_WARNING = "#d1283e"
VERSION_COLOR = "#735ECA"

BTN_PADDING = "6px 16px"
BTN_BORDER_RADIUS = "10px"
BTN_MIN_WIDTH_COLLAPSED = "100px"
BTN_MIN_WIDTH_EXPANDED = "130px"

STYLE_SHEET = f"""
    QWidget {{
        background-color: {BG_PRIMARY};
        color: {TEXT_PRIMARY};
        font-family: "Segoe UI", Arial, sans-serif;
    }}
    QPushButton {{
        background-color: {ACCENT_BLUE};
        color: white;
        border: none;
        padding: 12px 24px;
        border-radius: {BTN_BORDER_RADIUS};
        min-width: 120px;
        cursor: pointer;
    }}
    QPushButton:hover {{
        background-color: {ACCENT_BLUE_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {ACCENT_BLUE_PRESSED};
    }}
    QPushButton#settingsButton {{
        padding: {BTN_PADDING};
        border-radius: {BTN_BORDER_RADIUS};
    }}
    QPushButton#settingsButton:hover {{
        background-color: {ACCENT_BLUE_LIGHTER};
    }}
    QLineEdit {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_COLOR};
        padding: 6px;
        border-radius: 8px;
    }}
    QLabel {{
        background-color: transparent;
        border: none;
        color: {TEXT_SECONDARY};
    }}
    QScrollArea {{
        background-color: {BG_SECONDARY};
        border: 1px solid {BORDER_COLOR};
        border-radius: 5px;
    }}
    QProgressBar {{
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        text-align: center;
        background-color: {BG_INPUT};
    }}
    QProgressBar::chunk {{
        background-color: {ACCENT_BLUE};
    }}
    QSlider {{
        background-color: transparent;
        border: none;
    }}
    QSlider::groove:horizontal {{
        border: none;
        height: 6px;
        background-color: #000000;
        border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{
        background-color: {ACCENT_PURPLE};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background-color: {TEXT_PRIMARY};
        border: 1px solid {ACCENT_PURPLE};
        width: 14px;
        height: 14px;
        margin: -4px 0;
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{
        background-color: {TEXT_PRIMARY};
    }}
"""

SETTINGS_BUTTON_STYLE = (
    f"QPushButton#settingsButton {{ background-color: {ACCENT_BLUE}; color: white; "
    f"padding: 6px 8px; border-radius: {BTN_BORDER_RADIUS}; min-width: 50px; }}"
)

THUMB_SLIDER_STYLE = f"""
    QSlider#thumbSizeSlider {{
        background-color: transparent;
        border: none;
    }}
    QSlider#thumbSizeSlider::groove:horizontal {{
        border: none;
        height: 6px;
        background-color: #000000;
        border-radius: 3px;
    }}
    QSlider#thumbSizeSlider::sub-page:horizontal {{
        background-color: {ACCENT_PURPLE};
        border-radius: 3px;
    }}
    QSlider#thumbSizeSlider::handle:horizontal {{
        background-color: {TEXT_PRIMARY};
        border: 1px solid {ACCENT_PURPLE};
        width: 14px;
        height: 14px;
        margin: -4px 0;
        border-radius: 7px;
    }}
"""

THUMB_SIZE_LABEL_STYLE = f"""
    QLineEdit {{
        background-color: {BG_INPUT};
        color: white;
        border: 1px solid {BORDER_COLOR};
        border-radius: 4px;
        padding: 2px 4px;
    }}
"""

BROWSE_BUTTON_STYLE = (
    f"background-color: {ACCENT_YELLOW}; color: black; "
    f"border-radius: {BTN_BORDER_RADIUS}; padding: 4px 6px; min-height: 12px; min-width: 50px;"
)

ACTION_BUTTON_STYLE = (
    f"background-color: {ACCENT_BLUE}; color: white; "
    f"min-height: 28px; padding: 0px 16px; border-radius: {BTN_BORDER_RADIUS};"
)

COMBO_BOX_STYLE = f"""
    QComboBox {{
        background-color: {BG_INPUT};
        color: white;
        border: 1px solid {BORDER_COLOR};
        border-radius: 6px;
        padding: 4px 12px;
        min-width: 100px;
    }}
    QComboBox:hover {{
        background-color: {BG_HOVER};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border: none;
    }}
"""

FILTER_LABEL_STYLE = f"background-color: transparent; border: none; color: {TEXT_SECONDARY}; font-weight: bold;"
THUMB_SIZE_TITLE_STYLE = "background-color: transparent; border: none; font-weight: bold; font-size: 14px;"
STATUS_STYLE = "font-size: 12px; font-weight: bold;"
VERSION_STYLE = f"color: {VERSION_COLOR}; font-size: 12px;"
THUMBNAIL_NAME_STYLE = f"color: {TEXT_SECONDARY}; font-size: 10px;"
THUMBNAIL_BG_STYLE = f"background-color: {BG_INPUT}; border-radius: 5px;"
NO_FILES_STYLE = f"color: {TEXT_STATUS}; font-size: 14px;"
DIALOG_BG_STYLE = f"QDialog {{ background-color: {BG_PRIMARY}; }}"
THUMBNAIL_WIDGET_STYLE = f"background-color: {BG_SECONDARY};"
