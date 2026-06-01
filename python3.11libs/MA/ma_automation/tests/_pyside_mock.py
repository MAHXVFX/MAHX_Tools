"""
PySide6 Mock — 在所有导入 ma_automation 的测试文件中共享使用。

由于 PySide6 仅在 Houdini 环境中可用，测试需要在导入
ma_automation 前 mock PySide6.QtCore（Signal / QThread）。
此模块封装了 mock 逻辑，各测试文件只需在顶部 import 即可。
"""

import sys
from unittest.mock import MagicMock


class _MockSignalInstance:
    """绑定的 Signal 实例，支持 connect/emit。"""

    def __init__(self):
        self._callbacks = []

    def connect(self, cb):
        self._callbacks.append(cb)

    def emit(self, *args):
        for cb in self._callbacks:
            cb(*args)


class _MockSignalDescriptor:
    """类级别的 Signal 描述符，模拟 PySide6 Signal。"""

    def __init__(self, *types):
        self._types = types

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        try:
            return obj.__dict__[self._name]
        except KeyError:
            inst = _MockSignalInstance()
            obj.__dict__[self._name] = inst
            return inst


class _MockQThread:
    """QThread 最简 Mock，支持被子类化及 msleep。"""

    def __init__(self, parent=None):
        pass

    def msleep(self, ms):
        pass


def install_pyside_mock():
    """将 PySide6 / PySide6.QtCore / PySide6.QtWidgets 注入 sys.modules。

    如果已经存在则不重复注入。
    """
    if "PySide6" in sys.modules:
        return

    pyside_mod = type(sys)("PySide6")
    pyside_mod.__path__ = []

    qtcore_mod = type(sys)("PySide6.QtCore")
    qtcore_mod.Signal = _MockSignalDescriptor
    qtcore_mod.QThread = _MockQThread
    # QTimer & friends
    for _cls in ["QTimer", "QRect", "QPoint", "QSize", "QPropertyAnimation",
                 "QEasingCurve", "QAbstractAnimation"]:
        setattr(qtcore_mod, _cls, MagicMock())
    qtcore_mod.Qt = MagicMock()
    qtcore_mod.Qt.ScrollBarAlwaysOff = 2
    qtcore_mod.Qt.AlignCenter = 4

    sys.modules["PySide6"] = pyside_mod
    sys.modules["PySide6.QtCore"] = qtcore_mod

    # ── PySide6.QtWidgets mock（用于导入所有 UI 模块） ──
    qt_widgets_mod = type(sys)("PySide6.QtWidgets")

    # 用真实类（而非 MagicMock）作基类，避免 class 定义变成 MagicMock
    class _MockQWidget:
        """QWidget 最简桩，支持被子类化。"""
        def __init__(self, *args, **kwargs):
            self._children = {}
            self._object_name = None
            self._stylesheets = {}
        def setObjectName(self, name):
            self._object_name = name
        def objectName(self):
            return self._object_name
        def findChild(self, cls, name=None):
            return None
        def findChildren(self, cls, name=None):
            return []
        def setStyleSheet(self, ss):
            self._stylesheets = ss
        def setFixedWidth(self, w):
            pass
        def setMinimumSize(self, w, h):
            pass
        def setWindowTitle(self, t):
            pass
        def setWindowFlags(self, f):
            pass
        def winId(self):
            return 0
        def setLayout(self, layout):
            pass
        def layout(self):
            return None
        def parent(self):
            return None
        def deleteLater(self):
            pass
        def show(self):
            pass
        def hide(self):
            pass
        def close(self):
            pass
        def raise_(self):
            pass
        def activateWindow(self):
            pass
        # ── 事件桩 ──
        # mousePressEvent 是 AutomationWindow.mousePressEvent 末尾
        # ``super().mousePressEvent(event)`` 调用所需的 no-op 桩
        # (MRO 找不到 → AttributeError)。其他事件方法不需要桩,因为
        # 生产代码不再 override 它们(第二轮清理:eventFilter 已移除)。
        def mousePressEvent(self, event):
            pass

    class _MockQDialog(_MockQWidget):
        """QDialog 最简桩。"""
        def exec_(self):
            return 0
        def accept(self):
            pass
        def reject(self):
            pass
        def closeEvent(self, event):
            pass
        def result(self):
            return 0

    class _MockQHBoxLayout:
        def __init__(self, parent=None): pass
        def addWidget(self, w, *args): pass
        def addLayout(self, layout): pass
        def addStretch(self, n=0): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, s): pass
        def insertWidget(self, idx, w): pass
        def removeWidget(self, w): pass
        def count(self): return 0

    class _MockQVBoxLayout:
        def __init__(self, parent=None): pass
        def addWidget(self, w, *args): pass
        def addLayout(self, layout): pass
        def addStretch(self, n=0): pass
        def setContentsMargins(self, *args): pass
        def setSpacing(self, s): pass
        def insertWidget(self, idx, w): pass
        def removeWidget(self, w): pass
        def count(self): return 0

    class _MockQScrollArea:
        def __init__(self, parent=None): pass
        def setWidget(self, w): pass
        def setWidgetResizable(self, b): pass
        def setHorizontalScrollBarPolicy(self, p): pass
        def widget(self): return None

    setattr(qt_widgets_mod, 'QDialog', _MockQDialog)
    setattr(qt_widgets_mod, 'QWidget', _MockQWidget)
    setattr(qt_widgets_mod, 'QVBoxLayout', _MockQVBoxLayout)
    setattr(qt_widgets_mod, 'QHBoxLayout', _MockQHBoxLayout)
    setattr(qt_widgets_mod, 'QScrollArea', _MockQScrollArea)

    # 其余 QtWidgets 类用 MagicMock 即可（不会被用作基类）
    _OTHER_WIDGET_CLASSES = [
        "QPushButton", "QComboBox", "QLineEdit",
        "QCheckBox", "QLabel", "QStackedWidget",
        "QFileDialog", "QMessageBox", "QSizePolicy",
        "QGridLayout", "QFrame", "QToolButton", "QMenu",
        "QSlider", "QSpinBox", "QGroupBox", "QListWidget",
        "QListWidgetItem", "QProgressBar", "QApplication",
        "QSplitter", "QTabWidget", "QTextEdit", "QPlainTextEdit",
        "QGraphicsDropShadowEffect",  # 拖动抬起阴影
    ]
    for cls_name in _OTHER_WIDGET_CLASSES:
        setattr(qt_widgets_mod, cls_name, MagicMock())
    sys.modules["PySide6.QtWidgets"] = qt_widgets_mod

    # ── PySide6.QtGui mock（部分模块需要） ──
    qtgui_mod = type(sys)("PySide6.QtGui")
    for _cls in ["QFont", "QIcon", "QColor", "QPalette", "QFontMetrics",
                 "QPainter", "QPen", "QBrush", "QPixmap", "QImage",
                 "QCursor", "QAction", "QMovie", "QFontDatabase",
                 "QPainterPath"]:
        setattr(qtgui_mod, _cls, MagicMock())
    sys.modules["PySide6.QtGui"] = qtgui_mod


# 模块加载时自动安装
install_pyside_mock()
