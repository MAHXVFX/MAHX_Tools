# ============================================================
# common - 公共模块（所有功能共享）
# ============================================================
from MAHX.common import HDR_EXTENSIONS, HDR_PARAMETER_NAMES, SettingsManager, FilterManager

# HDR_EXTENSIONS       - HDR 文件扩展名列表
# HDR_PARAMETER_NAMES  - Houdini 环境光参数名
# SettingsManager      - 设置管理器（带缓存的 JSON 读写）
# FilterManager        - 筛选/收藏/最近列表管理

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
    'FilterManager',
    'HDRLibraryPanel',
    'Panel',
]
