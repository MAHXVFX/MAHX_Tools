"""Markdown-aware text editor with smart input handling."""

import re

from PySide6 import QtWidgets, QtGui, QtCore


class MarkdownTextEdit(QtWidgets.QTextEdit):
    """QTextEdit with Markdown smart input handling.

    Features:
    - Auto-continue ordered/unordered/task lists on Enter
    - Ctrl+B for **bold**, Ctrl+I for *italic*, Ctrl+` for `code`
    - Ctrl+Shift+K for code block insertion
    - Tab for indentation
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)  # 纯文本模式

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+B: 粗体
        if key == QtCore.Qt.Key.Key_B and modifiers == QtCore.Qt.KeyboardModifier.ControlModifier:
            self._wrap_selection('**', '**')
            return

        # Ctrl+I: 斜体
        if key == QtCore.Qt.Key.Key_I and modifiers == QtCore.Qt.KeyboardModifier.ControlModifier:
            self._wrap_selection('*', '*')
            return

        # Ctrl+`: 行内代码
        if key == QtCore.Qt.Key.Key_QuoteLeft and modifiers == QtCore.Qt.KeyboardModifier.ControlModifier:
            self._wrap_selection('`', '`')
            return

        # Ctrl+Shift+K: 代码块
        if key == QtCore.Qt.Key.Key_K and modifiers == (QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.KeyboardModifier.ShiftModifier):
            self._insert_code_block()
            return

        # Tab: 缩进
        if key == QtCore.Qt.Key.Key_Tab and modifiers == QtCore.Qt.KeyboardModifier.NoModifier:
            self._insert_indent()
            return

        # Shift+Tab: 反缩进
        if key == QtCore.Qt.Key.Key_Backtab:
            self._remove_indent()
            return

        # Enter: 智能列表延续
        if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            if self._handle_list_continuation():
                return

        super().keyPressEvent(event)

    def _wrap_selection(self, prefix, suffix):
        """Wrap selected text with prefix and suffix, or insert at cursor."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
            cursor.insertText(f"{prefix}{text}{suffix}")
        else:
            pos = cursor.position()
            cursor.insertText(f"{prefix}{suffix}")
            cursor.setPosition(pos + len(prefix))
            self.setTextCursor(cursor)

    def _insert_code_block(self):
        """Insert a fenced code block with cursor inside."""
        cursor = self.textCursor()
        pos = cursor.position()
        # 确保前面有换行（文件开头时不需要）
        if pos > 0:
            cursor.setPosition(pos - 1)
            if cursor.selectedText() != '\n':
                cursor.setPosition(pos)
                cursor.insertText('\n')
                pos += 1
        else:
            # 文件开头直接插入，代码块后加一个空行避免粘连
            cursor.insertText('```\n\n```\n')
            cursor.setPosition(pos + 4)
            self.setTextCursor(cursor)
            return
        cursor.insertText('```\n\n```')
        cursor.setPosition(pos + 4)  # 光标放在代码块中间
        self.setTextCursor(cursor)

    def _insert_indent(self):
        """Insert 2-space indent at current line start."""
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText('  ')

    def _remove_indent(self):
        """Remove 2-space indent at current line start."""
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor, 2)
        if cursor.selectedText() == '  ':
            cursor.removeSelectedText()

    def _handle_list_continuation(self):
        """Auto-continue lists on Enter. Returns True if handled."""
        cursor = self.textCursor()
        block = cursor.block()
        text = block.text()

        # 有序列表：1. xxx → 2. 
        m = re.match(r'^(\s*)(\d+)\. (.*)$', text)
        if m:
            indent, num, content = m.groups()
            if content.strip():  # 当前行有内容才延续
                next_num = int(num) + 1
                self._insert_new_line_with_prefix(f"{indent}{next_num}. ")
                return True
            else:  # 当前行为空，退出列表
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfLine)
                prefix_len = len(indent) + len(num) + 2
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor, prefix_len)
                cursor.removeSelectedText()
                self._insert_new_line()
                return True

        # 任务列表：- [x] xxx → - [ ] 
        m = re.match(r'^(\s*)[-*] \[[ xX]\] (.*)$', text)
        if m:
            indent, content = m.groups()
            if content.strip():
                self._insert_new_line_with_prefix(f"{indent}- [ ] ")
                return True
            else:
                cursor = self.textCursor()
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfLine)
                prefix_len = len(indent) + 6
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor, prefix_len)
                cursor.removeSelectedText()
                self._insert_new_line()
                return True

        # 无序列表：- xxx → - 
        m = re.match(r'^(\s*)[-*] (.*)$', text)
        if m:
            indent, content = m.groups()
            if content.strip():
                self._insert_new_line_with_prefix(f"{indent}- ")
                return True
            else:
                cursor = self.textCursor()
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfLine)
                prefix_len = len(indent) + 2
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor, prefix_len)
                cursor.removeSelectedText()
                self._insert_new_line()
                return True

        # Blockquote: > xxx → > 
        m = re.match(r'^(\s*)> (.*)$', text)
        if m:
            indent, content = m.groups()
            if content.strip():
                self._insert_new_line_with_prefix(f"{indent}> ")
                return True
            else:
                # Empty blockquote: remove '> ' prefix and insert newline
                cursor = self.textCursor()
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfLine)
                prefix_len = len(indent) + 2
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right, QtGui.QTextCursor.MoveMode.KeepAnchor, prefix_len)
                cursor.removeSelectedText()
                self._insert_new_line()
                return True

        return False

    def _insert_new_line_with_prefix(self, prefix):
        """Insert newline with prefix at cursor position."""
        cursor = self.textCursor()
        cursor.insertText(f'\n{prefix}')
        self.setTextCursor(cursor)

    def _insert_new_line(self):
        """Insert plain newline."""
        cursor = self.textCursor()
        cursor.insertText('\n')
        self.setTextCursor(cursor)
