"""Markdown 渲染器：将 Markdown 文本渲染为带代码高亮的 HTML。

使用 vendored markdown + pygments 库，输出完整 HTML（含 <style> 块），
可直接用于 QTextBrowser.setHtml()。
"""

import sys
import os

# 确保 vendored 库在 sys.path 中（仅在需要时插入）
_vendored_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if _vendored_dir not in sys.path:
    sys.path.insert(0, _vendored_dir)

import markdown
from pygments.formatters import HtmlFormatter


# ── VS Code Dark+ 主题色 ─────────────────────────────
_VSCODE_DARK = {
    'keyword': '#569cd6',      # k, kc, kr
    'string': '#ce9178',       # s, s1, s2, sb, sc, sd
    'comment': '#6a9955',      # c, c1, cm, ch, cp
    'function': '#dcdcaa',     # nf, na
    'number': '#b5cea8',       # m, mf, mi
    'operator': '#d4d4d4',     # o, ow
    'type': '#4ec9b0',         # kt, nc
    'variable': '#9cdcfe',     # n, nv, nx
    'constant': '#4fc1ff',     # no, vc
    'decorator': '#dcdcaa',    # nd
    'error': '#f44747',        # err
}

# ── 基础排版样式 ─────────────────────────────────────
_BASE_STYLES = {
    'h1': {'color': '#BC5662', 'size': '22px'},
    'h2': {'color': '#C4733D', 'size': '20px'},
    'h3': {'color': '#D09926', 'size': '18px'},
    'h4': {'color': '#4DA66C', 'size': '16px'},
    'h5': {'color': '#4F86CD', 'size': '15px'},
    'h6': {'color': '#8D6BA9', 'size': '14px'},
    'em': {'color': '#BDE9B8'},
    'strong': {'color': '#FF5858'},
}


def _build_css() -> str:
    """构建完整的 CSS 样式表。"""
    parts = []

    # 基础排版
    parts.append("""
body {
    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
    font-size: 13px;
    color: #d4d4d4;
    background-color: #1e1e1e;
    margin: 8px;
    line-height: 1.5;
}
""")

    # 标题样式
    for tag, style in _BASE_STYLES.items():
        if tag.startswith('h'):
            parts.append(f"""
{tag} {{
    color: {style['color']};
    font-size: {style['size']};
    margin: 12px 0 6px 0;
    font-weight: bold;
}}
""")

    # 粗体/斜体
    parts.append(f"""
strong {{ color: {_BASE_STYLES['strong']['color']}; font-weight: bold; }}
em {{ color: {_BASE_STYLES['em']['color']}; font-style: italic; }}
""")

    # 代码块容器
    parts.append("""
div.codehilite {
    background-color: #1e1e1e;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 12px;
    margin: 8px 0;
    overflow-x: auto;
}
div.codehilite pre {
    margin: 0;
    padding: 0;
    background-color: transparent;
    border: none;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.5;
    color: #d4d4d4;
}
""")

    # VS Code Dark+ 语法高亮（覆盖 Pygments monokai 默认色）
    parts.append(f"""
/* 关键字 */
div.codehilite .k,
div.codehilite .kc,
div.codehilite .kr {{ color: {_VSCODE_DARK['keyword']}; }}

/* 字符串 */
div.codehilite .s,
div.codehilite .s1,
div.codehilite .s2,
div.codehilite .sb,
div.codehilite .sc,
div.codehilite .sd,
div.codehilite .sh,
div.codehilite .si,
div.codehilite .sx {{ color: {_VSCODE_DARK['string']}; }}

/* 注释 */
div.codehilite .c,
div.codehilite .c1,
div.codehilite .cm,
div.codehilite .ch,
div.codehilite .cp,
div.codehilite .cpf {{ color: {_VSCODE_DARK['comment']}; font-style: italic; }}

/* 函数名 */
div.codehilite .nf,
div.codehilite .na {{ color: {_VSCODE_DARK['function']}; }}

/* 数字 */
div.codehilite .m,
div.codehilite .mf,
div.codehilite .mi,
div.codehilite .mo {{ color: {_VSCODE_DARK['number']}; }}

/* 类型 */
div.codehilite .kt,
div.codehilite .nc {{ color: {_VSCODE_DARK['type']}; }}

/* 变量 */
div.codehilite .n,
div.codehilite .nv,
div.codehilite .nx {{ color: {_VSCODE_DARK['variable']}; }}

/* 常量 */
div.codehilite .no,
div.codehilite .vc {{ color: {_VSCODE_DARK['constant']}; }}

/* 装饰器 */
div.codehilite .nd {{ color: {_VSCODE_DARK['decorator']}; }}

/* 错误 */
div.codehilite .err {{ color: {_VSCODE_DARK['error']}; }}
""")

    # 行内代码
    parts.append("""
code {
    background-color: #2d2d2d;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #d4d4d4;
}
""")

    # 表格
    parts.append("""
table {
    border-collapse: collapse;
    margin: 8px 0;
    width: 100%;
}
th, td {
    border: 1px solid #3d3d3d;
    padding: 6px 10px;
    text-align: left;
}
th {
    background-color: #2d2d2d;
    font-weight: bold;
}
""")

    # 链接
    parts.append("""
a {
    color: #6cb6ff;
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}
""")

    # 引用
    parts.append("""
blockquote {
    border-left: 3px solid #3d3d3d;
    margin: 8px 0;
    padding: 4px 12px;
    color: #999999;
}
""")

    # 列表
    parts.append("""
ul, ol {
    padding-left: 24px;
    margin: 4px 0;
}
li {
    margin: 2px 0;
}
""")

    # 水平线
    parts.append("""
hr {
    border: none;
    border-top: 1px solid #3d3d3d;
    margin: 12px 0;
}
""")

    return '\n'.join(parts)


def render_markdown(text: str) -> str:
    """将 Markdown 文本渲染为带代码高亮的完整 HTML。

    Args:
        text: Markdown 格式文本

    Returns:
        完整 HTML 字符串，可直接用于 QTextBrowser.setHtml()
    """
    # 使用 vendored markdown 库渲染
    extensions = [
        'markdown.extensions.extra',    # fenced_code, tables, attr_list, etc.
        'markdown.extensions.codehilite',  # 代码高亮（通过 Pygments）
    ]

    extension_configs = {
        'markdown.extensions.codehilite': {
            'pygments_style': 'monokai',
            'noclasses': False,       # 使用 CSS 类（便于我们覆盖颜色）
            'linenums': False,
            'css_class': 'codehilite',
            'guess_lang': True,
        },
    }

    html_body = markdown.markdown(
        text,
        extensions=extensions,
        extension_configs=extension_configs,
        output_format='html',
    )

    # 构建完整 HTML
    css = _build_css()

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style type="text/css">
{css}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

    return full_html
