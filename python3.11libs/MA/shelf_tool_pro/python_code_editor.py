"""Python 代码编辑器，支持语法高亮。"""

import re

from PySide6 import QtWidgets, QtGui, QtCore


# ── Python 语法高亮颜色方案 ──────────────────────────────

_KEYWORD_COLOR = "#c678dd"      # 关键字：紫色
_BUILTIN_COLOR = "#e5c07b"     # 内置函数：黄色
_STRING_COLOR = "#98c379"      # 字符串：绿色
_COMMENT_COLOR = "#5c6370"     # 注释：灰色
_NUMBER_COLOR = "#d19a66"      # 数字：橙色
_DECORATOR_COLOR = "#61afef"   # 装饰器：蓝色
_FUNCTION_COLOR = "#61afef"    # 函数定义：蓝色
_SELF_COLOR = "#e06c75"        # self：红色
_OPERATOR_COLOR = "#56b6c2"    # 运算符：青色


class PythonSyntaxHighlighter(QtGui.QSyntaxHighlighter):
    """Python 语法高亮器。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []
        self._setup_rules()

    def _setup_rules(self):
        """设置语法规则。"""
        # 关键字
        keywords = [
            'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
            'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from',
            'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not',
            'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
            'True', 'False', 'None',
        ]
        keyword_pattern = r'\b(?:' + '|'.join(keywords) + r')\b'
        self._rules.append((
            re.compile(keyword_pattern),
            self._make_format(_KEYWORD_COLOR, bold=True),
        ))

        # 内置函数
        builtins = [
            'print', 'len', 'range', 'int', 'float', 'str', 'list', 'dict',
            'set', 'tuple', 'type', 'isinstance', 'issubclass', 'hasattr',
            'getattr', 'setattr', 'delattr', 'callable', 'repr', 'hash',
            'id', 'abs', 'all', 'any', 'bin', 'hex', 'oct', 'chr', 'ord',
            'min', 'max', 'sum', 'round', 'sorted', 'reversed', 'enumerate',
            'zip', 'map', 'filter', 'input', 'open', 'super', 'property',
            'staticmethod', 'classmethod', 'format', 'vars', 'dir', 'help',
        ]
        builtin_pattern = r'\b(?:' + '|'.join(builtins) + r')(?=\s*\()'
        self._rules.append((
            re.compile(builtin_pattern),
            self._make_format(_BUILTIN_COLOR),
        ))

        # self 关键字
        self._rules.append((
            re.compile(r'\bself\b'),
            self._make_format(_SELF_COLOR),
        ))

        # 函数定义
        self._rules.append((
            re.compile(r'\bdef\s+(\w+)'),
            self._make_format(_FUNCTION_COLOR, bold=True),
        ))

        # 类定义
        self._rules.append((
            re.compile(r'\bclass\s+(\w+)'),
            self._make_format(_FUNCTION_COLOR, bold=True),
        ))

        # 装饰器
        self._rules.append((
            re.compile(r'@\w+'),
            self._make_format(_DECORATOR_COLOR),
        ))

        # 数字
        self._rules.append((
            re.compile(r'\b\d+\.?\d*\b'),
            self._make_format(_NUMBER_COLOR),
        ))

        # 运算符
        self._rules.append((
            re.compile(r'[+\-*/%=<>!&|^~]+'),
            self._make_format(_OPERATOR_COLOR),
        ))

        # 字符串（单引号和双引号）
        self._rules.append((
            re.compile(r'"[^"]*"'),
            self._make_format(_STRING_COLOR),
        ))
        self._rules.append((
            re.compile(r"'[^']*'"),
            self._make_format(_STRING_COLOR),
        ))

        # 三引号字符串
        self._triple_quote_format = self._make_format(_STRING_COLOR)
        self._triple_single_quote_re = re.compile(r"'''")
        self._triple_double_quote_re = re.compile(r'"""')

        # 注释（必须放在最后，优先级最高）
        self._comment_format = self._make_format(_COMMENT_COLOR, italic=True)
        self._comment_re = re.compile(r'#[^\n]*')

    @staticmethod
    def _make_format(color: str, bold: bool = False, italic: bool = False) -> QtGui.QTextCharFormat:
        """创建文本格式。"""
        fmt = QtGui.QTextCharFormat()
        fmt.setForeground(QtGui.QColor(color))
        if bold:
            fmt.setFontWeight(QtGui.QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def highlightBlock(self, text: str) -> None:
        """高亮单行文本。"""
        # 应用普通规则
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, fmt)

        # 处理注释（但不在字符串内的注释）
        for match in self._comment_re.finditer(text):
            start = match.start()
            # 检查是否在引号内
            before = text[:start]
            single_quotes = before.count("'") - before.count("\\'")
            double_quotes = before.count('"') - before.count('\\"')
            if single_quotes % 2 == 0 and double_quotes % 2 == 0:
                length = match.end() - start
                self.setFormat(start, length, self._comment_format)

        # 处理多行字符串（简化版：只处理当前行内的三引号）
        self.setCurrentBlockState(0)

        # 检查三引号字符串
        text_for_triple = text
        in_triple = False
        triple_start = 0
        triple_re = self._triple_double_quote_re if '"""' in text_for_triple else self._triple_single_quote_re
        
        for match in triple_re.finditer(text_for_triple):
            if not in_triple:
                triple_start = match.start()
                in_triple = True
            else:
                end = match.end()
                self.setFormat(triple_start, end - triple_start, self._triple_quote_format)
                in_triple = False


class PythonCodeEdit(QtWidgets.QPlainTextEdit):
    """Python 代码编辑器，支持行号和语法高亮。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._highlighter = PythonSyntaxHighlighter(self.document())
        self._setup_style()
        self._line_number_area = _LineNumberArea(self)
        self._setup_connections()

    def _setup_style(self):
        """设置编辑器样式。"""
        font = QtGui.QFont("Consolas", 11)
        font.setFixedPitch(True)
        self.setFont(font)

        self.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #1E1E1E;"
            "  color: #D4D4D4;"
            "  border: 1px solid #3D3D3D;"
            "  border-radius: 4px;"
            "  padding: 8px;"
            "  selection-background-color: #264F78;"
            "}"
            "QPlainTextEdit:focus {"
            "  border-color: #0D6399;"
            "}"
        )

        # 设置 Tab 宽度
        metrics = QtGui.QFontMetrics(font)
        self.setTabStopDistance(4 * metrics.horizontalAdvance(' '))

    def _setup_connections(self):
        """设置信号连接。"""
        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        
        # 初始化
        self._update_line_number_width()
        self._highlight_current_line()

    def line_number_area_width(self) -> int:
        """计算行号区域宽度。"""
        digits = len(str(max(1, self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def _update_line_number_width(self):
        """更新行号区域边距。"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        """滚动时更新行号区域。"""
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width()

    def resizeEvent(self, event):
        """窗口大小变化时调整行号区域。"""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QtCore.QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def _highlight_current_line(self):
        """高亮当前行。"""
        selections = []
        if not self.isReadOnly():
            selection = QtWidgets.QTextEdit.ExtraSelection()
            selection.format.setBackground(QtGui.QColor("#2A2D2E"))
            selection.format.setProperty(QtGui.QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            selections.append(selection)
        self.setExtraSelections(selections)

    def line_number_area_paint_event(self, event):
        """绘制行号。"""
        painter = QtGui.QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QtGui.QColor("#1E1E1E"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QtGui.QColor("#858585"))
                painter.drawText(
                    0, top, self._line_number_area.width() - 5,
                    self.fontMetrics().height(),
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

        painter.end()


class _LineNumberArea(QtWidgets.QWidget):
    """行号区域控件。"""

    def __init__(self, editor: PythonCodeEdit):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)
