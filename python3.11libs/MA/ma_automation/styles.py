"""MA Automation 样式常量。

集中管理主窗口 `STYLE_SHEET`，与项目其他模块 (`hdr_library/`、
`shelf_tool_pro/`) 拆分 styles.py 的约定保持一致。

设计意图:
- 颜色用字面量写死（不抽常量），因为这套配色只服务本面板，跨模块共享的
  颜色统一在 `MA/common/styles.py` 维护（待未来真需要时再抽）
- 关键 objectName (`startBtn` / `addBtn` / `removeBtn` / `taskSlot`)
  在样式表中通过 ``#name`` 选择器特化样式
"""

# 暗色主题基色
STYLE_SHEET = """
QDialog { background-color: #18181b; }
QPushButton { background-color: #2d2d2d; color: #e0e0e0; border: none;
              padding: 6px 16px; border-radius: 4px; font-size: 13px; }
QPushButton:hover { background-color: #3d3d3d; }
QPushButton:pressed { background-color: #0d6399; }
QPushButton#startBtn { background-color: #0d6399; color: white; font-weight: bold; }
QPushButton#startBtn:hover { background-color: #0e7bc9; }
QPushButton#addBtn, QPushButton#removeBtn {
    padding: 6px 8px; font-size: 16px; font-weight: bold; min-width: 28px;
}
QComboBox { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d;
            padding: 4px 8px; border-radius: 4px; }
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView { background-color: #2d2d2d; color: #e0e0e0;
                               selection-background-color: #0d6399; }
QLineEdit { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d;
            padding: 4px 8px; border-radius: 4px; }
QCheckBox { color: #e0e0e0; spacing: 6px; }
QScrollArea { border: none; background-color: transparent; }
QLabel { background-color: transparent; color: #e0e0e0; border: none; }
QWidget#taskSlot { background-color: #252528; }
QWidget#taskSlot[selected="true"],
QWidget#taskSlot[dragging="true"] { background-color: #2d2d32; }
QWidget#taskSlot[selected="true"] QLabel#taskSlotHandle { color: #0d6399; }
QWidget#taskSlot[dragging="true"] { border: 1px solid #0d6399; }
QLabel#taskSlotHandle { background-color: transparent; padding: 2px 4px; }
QLabel#taskSlotHandle:hover { background-color: #2d2d32; }
"""
