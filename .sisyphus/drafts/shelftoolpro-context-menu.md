# Draft: MAShelfToolPro 右键菜单功能

## 用户需求（confirmed）
- **右键改名**: 右键点击缩略图弹出菜单，选择"改名"后可修改工具名称显示（不改底层 tool name）
- **右键设置图片**: 右键点击缩略图弹出菜单，选择"设置图片"后可选择本地图片文件作为缩略图
- **图片格式支持**: .jpg, .png, .gif
- **GIF 特殊处理**: 鼠标悬停 500ms 后才播放动画
- **设置面板**: 面板中添加设置按钮，弹出设置对话框，可配置缩略图存放路径，自定义图片复制到此路径

## 技术决策
- **右键菜单**: `contextMenuEvent` + `QMenu`
- **改名对话框**: `QInputDialog.getText()`
- **图片选择**: `QFileDialog.getOpenFileName()` 过滤 .jpg/.png/.gif
- **GIF 动画**: `QMovie` + `QTimer.singleShot(500ms)` 延迟播放
- **图片存储**: 复制到用户配置的缩略图目录
- **缓存**: 扩展 `MA_ShelfTools_Pro_Cache.json` 存储 custom_images 和 custom_names 映射
- **设置持久化**: `ShelfToolsSettingsManager` 存储 thumbnail_directory 配置

## 缓存结构扩展
```json
{
  "custom_images": {
    "tool_name": {"path": "custom_shelf_thumbnails/tool_name.jpg", "is_gif": false}
  },
  "custom_names": {
    "tool_name": "自定义显示名称"
  }
}
```

## 需要修改的文件
1. `python_panels/MAShelfToolPro.pypanel` - 主要修改
2. `python3.11libs/MA/common/constants.py` - 添加默认缩略图目录常量
