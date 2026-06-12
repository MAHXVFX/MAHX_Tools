"""About MATools panel - 显示插件信息的关于面板。

使用 QTextBrowser 渲染 HTML 内容，展示项目信息、功能特性、技术栈等。
轻量级原生渲染，无延迟显示。
"""

import logging

from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from MA.common.styles import DIALOG_BG_STYLE

logger = logging.getLogger("MA")

_panel_window = None

# 关于信息的 HTML 内容（QTextBrowser 兼容子集）
ABOUT_HTML = """
<style>
body {
    background-color: #1F1F24;
    color: #d4d4d4;
    font-size: 14px;
    line-height: 1.6;
    padding: 12px 24px;
}
h1 { color: #BC5662; font-size: 26px; font-weight: 600; margin-top: 8px; margin-bottom: 4px; }
h2 { color: #D47440; font-size: 20px; font-weight: 600; margin-top: 20px; margin-bottom: 6px;
     border-bottom: 1px solid #3d3d3d; padding-bottom: 4px; }
h3 { color: #ECBC47; font-size: 16px; font-weight: 600; margin-top: 14px; margin-bottom: 4px; }
strong { color: #FF5858; }
a { color: #58a6ff; text-decoration: none; }
code { background-color: #2d2d2d; color: #e06c75; padding: 1px 4px;
       font-family: Consolas, monospace; font-size: 13px; }
hr { border: none; border-top: 1px solid #3d3d3d; margin: 16px 0; }
ul { padding-left: 24px; margin: 6px 0; }
li { margin: 3px 0; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th { background-color: #2d2d2d; color: #e0e0e0; font-weight: 600;
     border: 1px solid #3d3d3d; padding: 8px 12px; }
td { border: 1px solid #3d3d3d; padding: 8px 12px; color: #d4d4d4; }
</style>

<center>
<h1>MATools</h1>
<p><strong style="color: #d4d4d4;">Houdini 21.0 PySide6 工具集</strong></p>
<hr>
<p>一套为 Houdini 21.0 打造的 PySide6 图形化工具集，<br>
提供 <strong>HDR 环境光库管理</strong>、<strong>加强版工具架</strong>、<strong>自动化批处理</strong> 和 <strong>视频转序列图</strong> 四大核心功能。</p>
<p><strong>作者：MAHX</strong></p>
<p><a href="https://github.com/MAHXVFX/MAHX_Tools">GitHub: MAHXVFX/MAHX_Tools</a></p>
</center>
<h2>✨ 核心功能</h2>
<h3>🖼️ HDR 环境光库面板</h3>
<p>HDR 环境光库面板是一个专业的 HDR/EXR 环境光管理工具，帮助艺术家快速浏览、筛选和加载环境光贴图。</p>
<p><strong>主要特性：</strong></p>
<ul>
<li><strong>自动扫描与缩略图生成</strong>
    <ul>
    <li>支持 HDR、EXR、HDRI、TIFF、PNG、JPG、TGA、BMP 等格式</li>
    <li>使用 ffmpeg 自动生成缩略图网格</li>
    <li>三级缓存机制：内存缓存 → 磁盘缓存 → 重新生成，确保高效加载</li>
    </ul>
</li>
<li><strong>一键加载到场景</strong>
    <ul>
    <li>点击缩略图直接加载到 Houdini 环境光节点</li>
    <li>支持双模式打开：菜单栏弹窗模式与 Pane Tab 内嵌模式</li>
    </ul>
</li>
<li><strong>智能筛选与管理</strong>
    <ul>
    <li>文件夹分类：按子文件夹快速筛选</li>
    <li>收藏列表：标记常用 HDR，快速访问</li>
    <li>最近使用记录：自动记录最近加载的 HDR</li>
    <li>占位图过滤：自动隐藏生成失败的灰色占位图</li>
    </ul>
</li>
<li><strong>用户界面</strong>
    <ul>
    <li>缩略图大小实时调节（70~250px）</li>
    <li>窗口位置、大小、筛选状态自动保存</li>
    <li>暗色主题，与 Houdini 界面风格统一</li>
    </ul>
</li>
</ul>

<h3>🛠️ MA ShelfTools Pro</h3>
<p>MA ShelfTools Pro 是一个工具架可视化管理面板，将传统的工具架工具以缩略图形式展示，提供更直观的操作体验。</p>
<p><strong>主要特性：</strong></p>
<ul>
<li><strong>缩略图展示</strong>
    <ul>
    <li>将工具架工具以可视化缩略图呈现</li>
    <li>支持自定义缩略图（JPG/PNG/GIF）</li>
    <li>支持自定义工具显示名称</li>
    <li>缩略图大小实时调节（70~250px）</li>
    <li>SVG 矢量收藏图标，带阴影效果</li>
    </ul>
</li>
<li><strong>精准放置</strong>
    <ul>
    <li>点击：自动放置到当前 NetworkEditor</li>
    <li>拖拽：拖拽到 NetworkEditor 精确定位放置</li>
    </ul>
</li>
<li><strong>GIF 动画支持</strong>
    <ul>
    <li>自定义 GIF 缩略图，悬停自动播放（可配置延迟）</li>
    <li>每帧手动缩放、居中、应用圆角遮罩</li>
    <li>离开停止，节省资源</li>
    </ul>
</li>
<li><strong>Markdown 备注系统</strong>
    <ul>
    <li>悬停预览：鼠标悬停显示浮动备注面板（可配置延迟）</li>
    <li>中键查看：中键点击打开独立查看窗口</li>
    <li>右键编辑：分屏编辑器，实时 Markdown 渲染</li>
    <li>支持 VitePress 风格代码高亮（VEX、Python 等）</li>
    <li>支持 Callout 提示块（Note/Tip/Warning/Caution/Quote）</li>
    <li>支持 GIF、图片、视频链接实时渲染</li>
    </ul>
</li>
<li><strong>内置工具与用户工具</strong>
    <ul>
    <li>内置工具：随项目提交，只读，数据由 <code>builtin_tools.json</code> 管理</li>
    <li>用户工具：存储在 <code>MAtoolbar/</code> 目录，支持创建、编辑、删除</li>
    <li>额外目录支持：可添加额外 shelf 文件夹路径，自动扫描工具</li>
    <li>收藏功能：标记常用工具，快速访问</li>
    <li>标签管理：为工具添加标签，便于分类和筛选</li>
    <li>Shelf 颜色映射：不同来源的工具使用彩虹背景色区分</li>
    <li>中文编码修复：自动修复 .shelf 文件中的中文乱码</li>
    </ul>
</li>
</ul>

<h3>🤖 自动化批处理工具</h3>
<p>自动化批处理工具是一个可配置的任务执行器，支持按顺序执行多种 Houdini 操作。</p>
<p><strong>主要特性：</strong></p>
<ul>
<li><strong>三种任务类型</strong>
    <ul>
    <li>按钮点击：自动点击节点参数面板的按钮（如渲染提交），支持 <code>dl_Submit</code> 特殊处理</li>
    <li>Flipbook 拍屏：自动执行视口拍屏，支持自定义帧范围和输出路径</li>
    <li>HomeAssistant Webhook：发送 POST 请求到 HomeAssistant，触发智能家居操作</li>
    </ul>
</li>
<li><strong>任务管理</strong>
    <ul>
    <li>可视化任务槽：拖拽重排、选中删除</li>
    <li>自动填充：一键从当前场景填充任务参数</li>
    <li>多配置支持：可保存/加载多套任务配置</li>
    <li>配置下拉菜单：可编辑配置名，支持选择/键入新配置</li>
    </ul>
</li>
<li><strong>执行控制</strong>
    <ul>
    <li>顺序执行：按任务槽顺序依次执行</li>
    <li>可随时取消：执行过程中可中断</li>
    <li>日志输出：可选将执行日志保存到磁盘</li>
    <li>参数路径支持：支持从 Houdini 参数面板拖入参数路径</li>
    <li>多配置管理：可编辑配置下拉菜单，支持保存/加载多套任务配置</li>
    <li>设置面板：可配置日志输出选项</li>
    </ul>
</li>
</ul>

<h3>🎬 MA 视频转序列图</h3>
<p>MA 视频转序列图是一个专业的视频帧提取工具，将 mov、mp4、avi 等视频格式转换为 JPG 序列图。</p>
<p><strong>主要特性：</strong></p>
<ul>
<li><strong>视频格式支持</strong>
    <ul>
    <li>支持 mov、mp4、avi、mkv、wmv、flv、webm、m4v、mpg、mpeg、3gp、ts 等格式</li>
    <li>ffprobe 优先获取元数据，ffmpeg 作为回退方案</li>
    </ul>
</li>
<li><strong>输出设置</strong>
    <ul>
    <li>可自定义 JPG 图片质量（1%-100%）</li>
    <li>可设置起始帧号（默认从 $RFSTART 获取）</li>
    <li>可自定义帧号位数（默认 4 位）</li>
    <li>可自定义文件名前缀（默认 cam）</li>
    </ul>
</li>
<li><strong>相机集成</strong>
    <ul>
    <li>自动检测场景中的相机节点</li>
    <li>转换完成后自动设置相机 Background Image 参数</li>
    <li>自动禁用 vm_bgenable（设为 0）</li>
    </ul>
</li>
<li><strong>性能优化</strong>
    <ul>
    <li>ffmpeg 单进程直接批量输出 JPEG 序列</li>
    <li>-progress pipe:1 实时帧级进度报告</li>
    <li>QThread 后台线程，支持取消操作</li>
    </ul>
</li>
</ul>

<h2>📦 项目信息</h2>

<table cellpadding="8">
<tr><th>项目</th><th>信息</th></tr>
<tr><td><strong>版本</strong></td><td>1.0.0</td></tr>
<tr style="background-color: #252526;"><td><strong>作者</strong></td><td>MAHX</td></tr>
<tr><td><strong>许可证</strong></td><td>MIT License</td></tr>
<tr style="background-color: #252526;"><td><strong>项目路径</strong></td><td><code>Documents/houdini21.0/MAHX_Tools</code></td></tr>
<tr><td><strong>技术栈</strong></td><td>PySide6 + QWebEngineView + ffmpeg + marked.js + highlight.js</td></tr>
</table>

<hr>

<center>
<p><strong style="color: #d4d4d4;">Built with ❤️ for Houdini Artists</strong></p>
</center>
"""


class _AboutDialog(QtWidgets.QDialog):
    """关于面板对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About MATools")
        self.setMinimumSize(500, 400)
        self.resize(828, 500)
        self.setWindowFlags(
            Qt.Window | Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint
        )
        self.setStyleSheet(DIALOG_BG_STYLE)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        browser = QtWidgets.QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("QTextBrowser { border: none; }")
        browser.setHtml(ABOUT_HTML)
        layout.addWidget(browser)

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
