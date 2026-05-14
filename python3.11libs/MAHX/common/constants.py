import os

_MAHX_TOOLS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

HDR_SETTINGS_FILE = os.path.join(_MAHX_TOOLS_DIR, "MAHX_HDR_Library_Settings.json")
HDR_CACHE_FILE = os.path.join(_MAHX_TOOLS_DIR, "MAHX_HDR_Library_Cache.json")
SHELFTOOLS_SETTINGS_FILE = os.path.join(_MAHX_TOOLS_DIR, "MAHX_ShelfTools_Pro_Settings.json")
SHELFTOOLS_CACHE_FILE = os.path.join(_MAHX_TOOLS_DIR, "MAHX_ShelfTools_Pro_Cache.json")

HDR_EXTENSIONS = ['.hdr', '.exr', '.hdri', '.tif', '.tiff', '.png', '.jpg', '.jpeg', '.tga', '.bmp']

HDR_PARAMETER_NAMES = (
    "env_map",
    "xn__inputstexturefile_r3ah",
)

MAX_RECENT_HDRS = 20
FAVORITE_NOT_FOUND = -1
MIN_VALID_THUMBNAIL_SIZE = 1000
DEFAULT_THUMBNAIL_SIZE = 130
DEFAULT_THUMBNAIL_IMAGE_SIZE = 120
DEFAULT_WINDOW_WIDTH = 500
DEFAULT_WINDOW_HEIGHT = 757
THUMBNAIL_GRID_SPACING = 15
LAYOUT_MARGIN = 20
RESIZE_DELAY_MS = 50
ANIMATION_DURATION_MS = 200
ANIMATION_STEPS = 30
