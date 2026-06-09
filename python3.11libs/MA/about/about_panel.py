"""About MATools panel - 显示插件信息的关于面板。

复用 WebRenderer 渲染 Markdown 内容，展示项目信息、功能特性、技术栈等。
"""

import logging

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

from MA.shelf_tool_pro.web_renderer import WebRenderer
from MA.common.styles import DIALOG_BG_STYLE

logger = logging.getLogger("MA")

_panel_window = None

# 关于信息的 Markdown 内容
ABOUT_MARKDOWN = """
<div align="center">

# MATools

**Houdini 21.0 PySide6 工具集**

---

一套为 Houdini 21.0 打造的 PySide6 图形化工具集，
提供 **HDR 环境光库管理**、**加强版工具架** 和 **自动化批处理** 三大核心功能。

**作者：MAHX**

</div>

## ✨ 核心功能

### 🖼️ HDR 环境光库面板

HDR 环境光库面板是一个专业的 HDR/EXR 环境光管理工具，帮助艺术家快速浏览、筛选和加载环境光贴图。

**主要特性：**

- **自动扫描与缩略图生成**
  - 支持 HDR、EXR、HDRI、TIFF、PNG、JPG、TGA、BMP 等格式
  - 使用 ffmpeg 自动生成缩略图网格
  - 三级缓存机制：内存缓存 → 磁盘缓存 → 重新生成，确保高效加载

- **一键加载到场景**
  - 点击缩略图直接加载到 Houdini 环境光节点
  - 支持双模式打开：菜单栏弹窗模式与 Pane Tab 内嵌模式

- **智能筛选与管理**
  - 文件夹分类：按子文件夹快速筛选
  - 收藏列表：标记常用 HDR，快速访问
  - 最近使用记录：自动记录最近加载的 HDR
  - 占位图过滤：自动隐藏生成失败的灰色占位图

- **用户界面**
  - 缩略图大小实时调节（70~250px）
  - 窗口位置、大小、筛选状态自动保存
  - 暗色主题，与 Houdini 界面风格统一

### 🛠️ MA ShelfTools Pro

MA ShelfTools Pro 是一个工具架可视化管理面板，将传统的工具架工具以缩略图形式展示，提供更直观的操作体验。

**主要特性：**

- **缩略图展示**
  - 将工具架工具以可视化缩略图呈现
  - 支持自定义缩略图（JPG/PNG/GIF）
  - 支持自定义工具显示名称
  - 缩略图大小实时调节（70~250px）
  - SVG 矢量收藏图标，带阴影效果

- **精准放置**
  - 点击：自动放置到当前 NetworkEditor
  - 拖拽：拖拽到 NetworkEditor 精确定位放置

- **GIF 动画支持**
  - 自定义 GIF 缩略图，悬停自动播放（可配置延迟）
  - 每帧手动缩放、居中、应用圆角遮罩
  - 离开停止，节省资源

- **Markdown 备注系统**
  - 悬停预览：鼠标悬停显示浮动备注面板（可配置延迟）
  - 中键查看：中键点击打开独立查看窗口
  - 右键编辑：分屏编辑器，实时 Markdown 渲染
  - 支持 VitePress 风格代码高亮（VEX、Python 等）
  - 支持 Callout 提示块（Note/Tip/Warning/Caution/Quote）
  - 支持 GIF、图片、视频链接实时渲染

- **内置工具与用户工具**
  - 内置工具：随项目提交，只读，数据由 `builtin_tools.json` 管理
  - 用户工具：存储在 `MAtoolbar/` 目录，支持创建、编辑、删除
  - 额外目录支持：可添加额外 shelf 文件夹路径，自动扫描工具
  - 收藏功能：标记常用工具，快速访问
  - 标签管理：为工具添加标签，便于分类和筛选
  - Shelf 颜色映射：不同来源的工具使用彩虹背景色区分
  - 中文编码修复：自动修复 .shelf 文件中的中文乱码

### 🤖 自动化批处理工具

自动化批处理工具是一个可配置的任务执行器，支持按顺序执行多种 Houdini 操作。

**主要特性：**

- **三种任务类型**
  - 按钮点击：自动点击节点参数面板的按钮（如渲染提交），支持 `dl_Submit` 特殊处理
  - Flipbook 拍屏：自动执行视口拍屏，支持自定义帧范围和输出路径
  - HomeAssistant Webhook：发送 POST 请求到 HomeAssistant，触发智能家居操作

- **任务管理**
  - 可视化任务槽：拖拽重排、选中删除
  - 自动填充：一键从当前场景填充任务参数
  - 多配置支持：可保存/加载多套任务配置
  - 配置下拉菜单：可编辑配置名，支持选择/键入新配置

- **执行控制**
  - 顺序执行：按任务槽顺序依次执行
  - 可随时取消：执行过程中可中断
  - 日志输出：可选将执行日志保存到磁盘
  - 参数路径支持：支持从 Houdini 参数面板拖入参数路径
  - 多配置管理：可编辑配置下拉菜单，支持保存/加载多套任务配置
  - 设置面板：可配置日志输出选项

## 📦 项目信息

| 项目 | 信息 |
|------|------|
| **版本** | 1.0.0 |
| **作者** | MAHX |
| **许可证** | MIT License |
| **项目路径** | `Documents/houdini21.0/MAHX_Tools` |
| **技术栈** | PySide6 + QWebEngineView + ffmpeg + marked.js + highlight.js |

---

<div align="center">

**Built with ❤️ for Houdini Artists**

</div>
"""


class _AboutDialog(QtWidgets.QDialog):
    """关于面板对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About MATools")
        self.setMinimumSize(500, 400)
        self.resize(744, 500)
        self.setWindowFlags(
            Qt.Window | Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint
        )
        self.setStyleSheet(DIALOG_BG_STYLE)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # 创建布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建 WebRenderer
        self._renderer = WebRenderer()
        self._view = self._renderer.get_widget()
        layout.addWidget(self._view)
        # 渲染前隐藏，避免首次显示模糊
        self._view.hide()

    def showEvent(self, event):
        """窗口显示后渲染内容。"""
        super().showEvent(event)
        self._renderer.render(ABOUT_MARKDOWN, callback=self._on_render_done)

    def _on_render_done(self, _=None):
        """渲染完成后显示 QWebEngineView。"""
        self._view.show()

    def closeEvent(self, event):
        """窗口关闭时清理资源。"""
        global _panel_window
        _panel_window = None
        super().closeEvent(event)


def _apply_window_flags(window):
    """设置窗口样式，使其在任务栏显示独立图标。"""
    try:
        from ctypes import windll
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        hwnd = int(window.winId())
        SetWindowLong = windll.user32.SetWindowLongW
        GetWindowLong = windll.user32.GetWindowLongW
        style = GetWindowLong(hwnd, GWL_EXSTYLE)
        style |= WS_EX_APPWINDOW
        SetWindowLong(hwnd, GWL_EXSTYLE, style)
        windll.shell32.SetCurrentProcessExplicitAppUserModelID('MA.MATools.About.1')
    except Exception as e:
        logger.debug("Failed to apply window flags: %s", e)


def Panel():
    """打开关于面板的入口函数。

    如果面板已打开，则激活现有窗口；否则创建新窗口。
    """
    global _panel_window

    # 检查是否已有打开的面板
    if _panel_window is not None:
        try:
            if _panel_window.isVisible():
                _panel_window.raise_()
                _panel_window.activateWindow()
                return
        except (RuntimeError, AttributeError):
            _panel_window = None

    # 创建新面板
    import hou
    parent_window = hou.qt.mainWindow()

    _panel_window = _AboutDialog(parent_window)
    _apply_window_flags(_panel_window)
    _panel_window.show()
