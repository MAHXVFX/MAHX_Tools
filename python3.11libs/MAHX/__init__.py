# ============================================================
# common - 公共模块（所有功能共享）
# ============================================================
# ============================================================
# common - 公共模块（所有功能共享）
# ============================================================
from MAHX.common import (
    HDR_EXTENSIONS, HDR_PARAMETER_NAMES,
    SettingsManager, CacheManager,
    ShelfToolsSettingsManager, ShelfToolsCacheManager,
    FilterManager,
)

# HDR_EXTENSIONS              - HDR 文件扩展名列表
# HDR_PARAMETER_NAMES         - Houdini 环境光参数名
# SettingsManager             - HDR 设置管理器（小数据，实时写）
# CacheManager                - HDR 缩略图缓存管理器（大数据，关闭时写）
# ShelfToolsSettingsManager   - ShelfTools 设置管理器（小数据，实时写）
# ShelfToolsCacheManager      - ShelfTools 缓存管理器（大数据，关闭时写）
# FilterManager               - 筛选/收藏/最近列表管理

# ============================================================
# hdr_library - HDR 材质库面板
# ============================================================
from MAHX.hdr_library import HDRLibraryPanel, Panel

# HDRLibraryPanel - HDR 面板主类
# Panel           - 打开 HDR 面板的入口函数

__all__ = [
    'HDR_EXTENSIONS',
    'HDR_PARAMETER_NAMES',
    'SettingsManager',
    'CacheManager',
    'ShelfToolsSettingsManager',
    'ShelfToolsCacheManager',
    'FilterManager',
    'HDRLibraryPanel',
    'Panel',
]
