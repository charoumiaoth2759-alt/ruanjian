# -*- coding: utf-8 -*-
"""柜体设计模式 —— 属性面板（柜体 / 板件 / 审图 三Tab）

主窗口中叠在画布最右侧，左侧与 `CabinetAssembler` 紧挨。
"""

from __future__ import annotations
import os, sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QStackedWidget,
    QVBoxLayout, QWidget, QGraphicsDropShadowEffect,
)

# ─── 路径 ───────────────────────────────────────────────────────────────────

def _project_root() -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return base
    here = os.path.dirname(os.path.abspath(__file__))
    cur = here
    for _ in range(12):
        if os.path.isfile(os.path.join(cur, "main.py")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(os.path.join(here, "..", "..", ".."))

# ─── 颜色 / 尺寸 ────────────────────────────────────────────────────────────

_BG    = "#f5f7fa"
_WHITE = "#ffffff"
_BORD  = "#dcdfe6"
_BLUE  = "#1a6fc4"
_BLH   = "#1560ad"
_BLL   = "#eaf2fd"
_TEXT  = "#303133"
_GRAY  = "#606266"
_ODD   = "#f8f9fb"
_GRP   = "#e8edf5"
_RED_L = "#fff0f0"
_RED_B = "#f0b4b4"
_RED   = "#e74c3c"
_LOCK  = "#f39c12"

_TAB_H   = 30
PANEL_W  = 240
_ROW_H   = 24
# 柜体 Tab 内容区左右留白（与底部按钮区对齐）
_SIDE_GUTTER = 10
# 前缩等 3×2 网格相对内容区再向右，避免贴左过紧
_SHRINK_GRID_LEFT_PAD = _SIDE_GUTTER + 20

# ─── 通用小部件 ─────────────────────────────────────────────────────────────

class _HLine(QFrame):
    def __init__(self, p=None):
        super().__init__(p)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet(f"color:{_BORD};")

def _mk_scroll():
    s = QScrollArea(); s.setWidgetResizable(True)
    s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    s.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    s.setStyleSheet("""QScrollArea{border:none;background:transparent;}
        QScrollBar:vertical{background:#f0f2f5;width:5px;border-radius:2px;}
        QScrollBar::handle:vertical{background:#c0c4cc;border-radius:2px;min-height:16px;}
        QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}""")
    return s

def _row_text(label, value, even):
    row = QWidget(); row.setFixedHeight(_ROW_H)
    row.setStyleSheet(f"background:{'#fff' if even else _ODD};")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(_SIDE_GUTTER, 0, _SIDE_GUTTER, 0)
    lay.setSpacing(3)
    lbl = QLabel(label); lbl.setFixedWidth(54)
    lbl.setStyleSheet(f"color:{_GRAY};font-size:11px;"); lay.addWidget(lbl)
    val = QLabel(value); val.setStyleSheet(f"color:{_TEXT};font-size:11px;")
    lay.addWidget(val,1); return row

def _row_spin(label, spin, even):
    row = QWidget(); row.setFixedHeight(_ROW_H)
    row.setStyleSheet(f"background:{'#fff' if even else _ODD};")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(_SIDE_GUTTER, 1, _SIDE_GUTTER, 1)
    lay.setSpacing(3)
    lbl = QLabel(label); lbl.setFixedWidth(54)
    lbl.setStyleSheet(f"color:{_GRAY};font-size:11px;"); lay.addWidget(lbl)
    lay.addWidget(spin,1); return row

# ─── 通用全局变量折叠区 ──────────────────────────────────────────────────────

_GLOBAL_VARS = [
    ("S",  18.0, "柜板厚度"),
    ("F",   5.0, "背板厚度"),
    ("M",   1.0, "厚封边"),
    ("N",   0.9, "薄封边"),
    ("G",   1.2, "门封边"),
    ("FW",  3.0, "宽度收缩"),
    ("FL",  3.5, "长度收缩"),
    ("C",   6.0, "入槽深度"),
    ("K",  18.0, "门板厚度"),
]

class _GlobalVarRow(QWidget):
    def __init__(self, var, value, desc, even=True, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setStyleSheet(f"background:{'#ffffff' if even else _ODD};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(_SIDE_GUTTER, 2, _SIDE_GUTTER, 2)
        lay.setSpacing(4)

        lbl = QLabel(var); lbl.setFixedWidth(22)
        lbl.setStyleSheet(f"color:{_TEXT};font-size:11px;font-weight:bold;background:transparent;")
        lay.addWidget(lbl)

        spin = QDoubleSpinBox()
        spin.setDecimals(1); spin.setRange(0.0, 9999.0); spin.setValue(value)
        spin.setFixedWidth(54)
        spin.setStyleSheet(f"""QDoubleSpinBox{{background:{_WHITE};border:1px solid {_BORD};
            border-radius:2px;color:{_TEXT};font-size:11px;padding:1px 2px;min-height:19px;}}
            QDoubleSpinBox:focus{{border-color:{_BLUE};}}
            QDoubleSpinBox::up-button,QDoubleSpinBox::down-button{{width:13px;}}""")
        lay.addWidget(spin)
        self._spin = spin

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(f"color:{_GRAY};font-size:11px;background:transparent;")
        lay.addWidget(desc_lbl, 1)

    def value(self): return self._spin.value()


class _GlobalVarsSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        self._hdr = QPushButton("+ 通用全局变量")
        self._hdr.setStyleSheet(f"""QPushButton{{background:{_BLL};border:none;
            border-bottom:1px solid {_BORD};color:{_BLUE};font-size:11px;
            text-align:left;padding:3px {_SIDE_GUTTER}px;min-height:22px;}}
            QPushButton:hover{{background:#d0e8ff;}}""")
        self._hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hdr.clicked.connect(self._toggle)
        lay.addWidget(self._hdr)

        self._body = QWidget()
        self._body.setStyleSheet(f"background:{_BG};")
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(0, 0, 0, 0); body_lay.setSpacing(0)

        self._var_rows: list[_GlobalVarRow] = []
        for i, (var, val, desc) in enumerate(_GLOBAL_VARS):
            row = _GlobalVarRow(var, val, desc, even=(i % 2 == 0))
            body_lay.addWidget(row)
            self._var_rows.append(row)

        body_lay.addWidget(_HLine())

        btn_w = QWidget(); btn_w.setStyleSheet(f"background:{_BG};")
        btn_lay = QHBoxLayout(btn_w)
        btn_lay.setContentsMargins(_SIDE_GUTTER, 5, _SIDE_GUTTER, 6)
        btn_lay.setSpacing(4)

        b_apply = QPushButton("应用到当前产品")
        b_apply.setStyleSheet(f"""QPushButton{{background:#f0f4fa;border:1px solid {_BORD};
            border-radius:3px;color:{_TEXT};font-size:11px;min-height:26px;}}
            QPushButton:hover{{background:#dce7f8;border-color:{_BLUE};}}""")
        btn_lay.addWidget(b_apply, 1)

        b_save = QPushButton("应用并存为默认")
        b_save.setStyleSheet(f"""QPushButton{{background:#f0f4fa;border:1px solid {_BORD};
            border-radius:3px;color:{_TEXT};font-size:11px;min-height:26px;}}
            QPushButton:hover{{background:#dce7f8;border-color:{_BLUE};}}""")
        btn_lay.addWidget(b_save, 1)
        body_lay.addWidget(btn_w)

        lay.addWidget(self._body)
        self._body.setVisible(self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        """外部设置折叠状态（进入柜体模式时默认折叠）。"""
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._body.setVisible(self._expanded)
        self._hdr.setText(
            ("- " if self._expanded else "+ ") + "通用全局变量")

    def _toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._hdr.setText(("- " if self._expanded else "+ ") + "通用全局变量")

    def get_values(self):
        return {_GLOBAL_VARS[i][0]: row.value() for i, row in enumerate(self._var_rows)}

# ─── 数值输入框 ──────────────────────────────────────────────────────────────

class _PropSpin(QDoubleSpinBox):
    def __init__(self, value=0.0, mn=0.0, mx=99999.0, parent=None):
        super().__init__(parent)
        self.setDecimals(1); self.setRange(mn,mx); self.setValue(value)
        self.setGroupSeparatorShown(True)
        self.setStyleSheet(f"""QDoubleSpinBox{{background:{_WHITE};border:1px solid {_BORD};
            border-radius:2px;color:{_TEXT};font-size:11px;padding:1px 2px;min-height:19px;}}
            QDoubleSpinBox:focus{{border-color:{_BLUE};}}
            QDoubleSpinBox::up-button,QDoubleSpinBox::down-button{{width:13px;}}""")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

class _ShrinkSpin(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(-999,999); self.setValue(0); self.setFixedWidth(42)
        self.setStyleSheet(f"""QSpinBox{{background:{_WHITE};border:1px solid {_BORD};
            border-radius:2px;color:{_TEXT};font-size:10px;min-height:17px;}}
            QSpinBox:focus{{border-color:{_BLUE};}}
            QSpinBox::up-button,QSpinBox::down-button{{width:11px;}}""")

# ─── 板件属性行 ──────────────────────────────────────────────────────────────

class _PanelPropRow(QWidget):
    def __init__(self, prop_name: str, locked: bool = True,
                 value: str = "", even: bool = True, parent=None):
        super().__init__(parent)
        self.setFixedHeight(_ROW_H)
        self.setStyleSheet(f"background:{'#fff' if even else _ODD};")
        self._name = prop_name

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4,1,4,1); lay.setSpacing(3)

        name_lbl = QLabel(prop_name)
        name_lbl.setFixedWidth(72)
        name_lbl.setStyleSheet(f"color:{_TEXT};font-size:11px;")
        lay.addWidget(name_lbl)

        self._locked = locked
        self._lock_btn = QPushButton("🔒" if locked else "🔓")
        self._lock_btn.setFixedSize(20, 20)
        self._lock_btn.setStyleSheet(f"""QPushButton{{
            background:transparent;border:none;font-size:11px;
            color:{'#f39c12' if locked else _GRAY};padding:0;}}
            QPushButton:hover{{background:#f0f0f0;border-radius:3px;}}""")
        self._lock_btn.setToolTip("点击切换锁定")
        self._lock_btn.clicked.connect(self._toggle_lock)
        lay.addWidget(self._lock_btn)

        self._edit = QLineEdit(value)
        self._edit.setStyleSheet(f"""QLineEdit{{
            background:{_WHITE};border:1px solid {_BORD};border-radius:2px;
            color:{_TEXT};font-size:11px;padding:1px 3px;min-height:18px;}}
            QLineEdit:focus{{border-color:{_BLUE};}}""")
        self._edit.setEnabled(not locked)
        lay.addWidget(self._edit, 1)

    def _toggle_lock(self):
        self._locked = not self._locked
        self._lock_btn.setText("🔒" if self._locked else "🔓")
        self._lock_btn.setStyleSheet(f"""QPushButton{{
            background:transparent;border:none;font-size:11px;
            color:{'#f39c12' if self._locked else _GRAY};padding:0;}}
            QPushButton:hover{{background:#f0f0f0;border-radius:3px;}}""")
        self._edit.setEnabled(not self._locked)

    def get_value(self): return self._edit.text()
    def is_locked(self): return self._locked

# ─── 延伸量输入行 ─────────────────────────────────────────────────────────────

class _ExtendRow(QWidget):
    def __init__(self, left_label, right_label, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        lay = QHBoxLayout(self); lay.setContentsMargins(4,2,4,2); lay.setSpacing(4)

        _LS = f"color:{_GRAY};font-size:11px;"
        _ES = f"""QLineEdit{{background:{_WHITE};border:1px solid {_BORD};
            border-radius:2px;color:{_TEXT};font-size:11px;
            padding:1px 3px;min-height:18px;}}
            QLineEdit:focus{{border-color:{_BLUE};}}"""

        ll = QLabel(left_label); ll.setFixedWidth(36); ll.setStyleSheet(_LS)
        lay.addWidget(ll)
        self._left = QLineEdit(""); self._left.setStyleSheet(_ES)
        lay.addWidget(self._left, 1)

        rl = QLabel(right_label); rl.setFixedWidth(36); rl.setStyleSheet(_LS)
        lay.addWidget(rl)
        self._right = QLineEdit(""); self._right.setStyleSheet(_ES)
        lay.addWidget(self._right, 1)

    def values(self): return self._left.text(), self._right.text()

# ─── 主面板：CabinetPropertyPanel ────────────────────────────────────────────

class CabinetPropertyPanel(QWidget):
    """属性面板：柜体 / 板件 / 审图 三 Tab；画布右缘与组件库并排。"""
    PANEL_WIDTH = PANEL_W

    sig_finish_design    = Signal()
    sig_save_to_library  = Signal()
    sig_add_or_modify    = Signal()
    sig_tab_changed      = Signal(int)
    # --- 结构解耦：属性面板按钮除保留原信号外，可发 command_name 供 CommandDispatcher ---
    sig_command_requested = Signal(str, object)

    _TABS = ["柜体","板件","审图"]

    _SHRINK_FIELDS = [
        ("Q","前缩"),("X","后缩"),
        ("Z","左缩"),("Y","右缩"),
        ("S","上缩"),("X","下缩"),
    ]

    _PANEL_PROPS = [
        ("组件名称", True,  ""),
        ("组件材料", True,  ""),
        ("组件纹理", True,  ""),
        ("规格",     True,  ""),
        ("R",        True,  ""),
        ("轴向R",    True,  ""),
        ("封边扣减", True,  ""),
        ("孔位模板", True,  ""),
        ("孔槽连接", True,  ""),
        ("孔位方向", True,  ""),
        ("图元模块", True,  ""),
        ("图元变换", True,  ""),
        ("引用模型", True,  ""),
        ("宽度留缝", True,  ""),
        ("长度留缝", True,  ""),
        ("屏蔽切角", True,  ""),
        ("备注说明", True,  ""),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(self.PANEL_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"CabinetPropertyPanel{{background:{_BG};border-right:1px solid {_BORD};}}")
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(12)
        sh.setOffset(0, 3)
        sh.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(sh)
        self._build_ui()
        self._wire_dimension_event_emit_for_solver_coalesce()

    def _build_ui(self):
        # ── 总布局 ───────────────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_tab_bar())
        root.addWidget(_HLine())

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        self._stack.addWidget(self._build_guiti())  # 0 柜体
        self._stack.addWidget(self._build_banjian())  # 1 板件
        self._stack.addWidget(self._build_shenjian())  # 2 审图
        root.addWidget(self._stack, 1)

    def _wire_dimension_event_emit_for_solver_coalesce(self) -> None:
        """
        W/H/D 连续拖动时会高频触发；通过 `PANEL_CHANGED` + 与命令链相同的合并键，
        由事件总线合并为单次去抖后的求解，避免 60fps 重复 ``solver.solve(Space)``。
        """
        from commands.cabinet_event_bridge import emit_dimension_spins_panel_changed

        def bump() -> None:
            emit_dimension_spins_panel_changed()

        self._spin_w.valueChanged.connect(lambda *_: bump())
        self._spin_h.valueChanged.connect(lambda *_: bump())
        self._spin_d.valueChanged.connect(lambda *_: bump())

    def apply_selection_from_event(self, event) -> None:
        """
        订阅 `SelectionChanged` 时的回调入口（由 `register_cabinet_mode_event_subscribers` 调用）。

        当前实现：在面板工具提示中展示选中来源，后续可扩展为加载板件属性行等。
        """
        pl = getattr(event, "payload", None) or {}
        kind = pl.get("kind", "?")
        idx = pl.get("index", "")
        path = pl.get("path", "")
        self.setToolTip(f"当前选中：{kind}  idx={idx}  path={path}")

    # ── Tab 栏 ───────────────────────────────────────────────────────────────

    def _build_tab_bar(self):
        bar = QWidget(); bar.setFixedHeight(_TAB_H)
        bar.setStyleSheet(f"background:{_BG};")
        lay = QHBoxLayout(bar); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        self._tab_btns: list[QPushButton] = []
        for i, name in enumerate(self._TABS):
            btn = QPushButton(name); btn.setCheckable(True); btn.setChecked(i==0)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._tab_style(btn, i==0)
            btn.clicked.connect(lambda _=False,idx=i: self._on_tab(idx))
            self._tab_btns.append(btn); lay.addWidget(btn)
            if i < len(self._TABS)-1:
                vl = QFrame(); vl.setFrameShape(QFrame.Shape.VLine)
                vl.setFixedWidth(1); vl.setStyleSheet(f"color:{_BORD};")
                lay.addWidget(vl)
        return bar

    @staticmethod
    def _tab_style(btn, active):
        if active:
            btn.setStyleSheet(f"""QPushButton{{background:transparent;border:none;
                border-bottom:2px solid {_BLUE};color:{_BLUE};
                font-size:12px;font-weight:bold;}}""")
        else:
            btn.setStyleSheet(f"""QPushButton{{background:transparent;border:none;
                border-bottom:2px solid transparent;color:{_GRAY};font-size:12px;}}
                QPushButton:hover{{color:{_BLUE};}}""")

    def _on_tab(self, idx):
        for i, btn in enumerate(self._tab_btns):
            btn.setChecked(i==idx); self._tab_style(btn, i==idx)
        self._stack.setCurrentIndex(idx)
        self.sig_tab_changed.emit(idx)

    def _toggle_module_section(self):
        """模块产品参数折叠区：进入柜体模式时默认展开。"""
        self._module_expanded = not self._module_expanded
        self._module_body.setVisible(self._module_expanded)
        self._module_hdr.setText(
            ("- " if self._module_expanded else "+ ") + "模块产品参数")

    # ── 柜体 Tab ─────────────────────────────────────────────────────────────

    def _build_guiti(self):
        w = QWidget(); w.setStyleSheet(f"background:{_BG};")
        outer = QVBoxLayout(w); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)

        scroll = _mk_scroll()
        inner = QWidget(); inner.setStyleSheet(f"background:{_BG};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(_SIDE_GUTTER, 0, _SIDE_GUTTER, 0)
        lay.setSpacing(0)

        # 通用全局变量：进入模式默认折叠
        self._global_vars_sec = _GlobalVarsSection()
        lay.addWidget(self._global_vars_sec)

        # 模块产品参数：默认展开，可折叠
        self._module_expanded = True
        self._module_hdr = QPushButton("- 模块产品参数")
        self._module_hdr.setStyleSheet(f"""QPushButton{{background:{_BLL};border:none;
            border-bottom:1px solid {_BORD};color:{_BLUE};font-size:11px;
            text-align:left;padding:3px {_SIDE_GUTTER}px;min-height:22px;}}
            QPushButton:hover{{background:#d0e8ff;}}""")
        self._module_hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._module_hdr.clicked.connect(self._toggle_module_section)
        lay.addWidget(self._module_hdr)

        self._module_body = QWidget()
        self._module_body.setStyleSheet(f"background:{_BG};")
        mbl = QVBoxLayout(self._module_body)
        mbl.setContentsMargins(0, 0, 0, 0)
        mbl.setSpacing(0)
        mbl.addWidget(_HLine())

        mbl.addWidget(_row_text("产品名称", "空框架", True))
        mbl.addWidget(_row_text("型号", "", False))
        self._spin_w = _PropSpin(2400.0)
        self._spin_h = _PropSpin(2200.0)
        self._spin_d = _PropSpin(600.0)
        self._spin_qty = _PropSpin(1.0, mn=1.0, mx=9999.0)
        for i, (lbl, spin) in enumerate([
            ("W", self._spin_w), ("H", self._spin_h),
            ("D", self._spin_d), ("批量", self._spin_qty),
        ]):
            mbl.addWidget(_row_spin(lbl, spin, i % 2 == 0))
        mbl.addWidget(_row_text("附加属性", "", True))
        mbl.addWidget(_HLine())
        mbl.addStretch(1)
        lay.addWidget(self._module_body)

        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # 前缩等：固定在「添加or修改」上方，不随表格区中间留白滚动
        shrink_w = QWidget()
        shrink_w.setStyleSheet(f"background:{_BG};")
        g = QGridLayout(shrink_w)
        g.setContentsMargins(_SHRINK_GRID_LEFT_PAD, 6, _SIDE_GUTTER, 10)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(6)
        self._shrink_spins: dict[str, _ShrinkSpin] = {}
        for idx, (prefix, name) in enumerate(self._SHRINK_FIELDS):
            row, cp = divmod(idx, 2)
            lbl = QLabel(f"{prefix}. {name}")
            lbl.setStyleSheet(f"color:{_GRAY};font-size:10px;")
            lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            g.addWidget(lbl, row, cp * 2)
            spin = _ShrinkSpin()
            g.addWidget(spin, row, cp * 2 + 1)
            self._shrink_spins[name] = spin
        outer.addWidget(shrink_w)

        outer.addWidget(_HLine())
        outer.addWidget(self._build_action_row())
        outer.addWidget(self._build_save_row())
        outer.addWidget(self._build_finish())
        return w

    # ── 板件 Tab ─────────────────────────────────────────────────────────────

    def _build_banjian(self):
        w = QWidget(); w.setStyleSheet(f"background:{_BG};")
        outer = QVBoxLayout(w); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)

        scroll = _mk_scroll()
        inner = QWidget(); inner.setStyleSheet(f"background:{_BG};")
        lay = QVBoxLayout(inner); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        # 表头
        hdr = QWidget(); hdr.setFixedHeight(22)
        hdr.setStyleSheet(f"background:{_GRP};border-bottom:1px solid {_BORD};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(4,0,4,0); hl.setSpacing(3)
        for txt, w_ in [("属性名",72),("锁定",24),("属性值",-1)]:
            lbl = QLabel(txt); lbl.setStyleSheet(f"color:{_GRAY};font-size:11px;font-weight:bold;")
            if w_>0: lbl.setFixedWidth(w_)
            hl.addWidget(lbl, 0 if w_>0 else 1)
        lay.addWidget(hdr)

        self._panel_prop_rows: list[_PanelPropRow] = []
        for i,(pname,locked,val) in enumerate(self._PANEL_PROPS):
            row = _PanelPropRow(pname, locked, val, even=(i%2==0))
            lay.addWidget(row)
            self._panel_prop_rows.append(row)

        lay.addWidget(_HLine())

        ext_fields = [
            ("Q.前延","X.后延"),
            ("Z.左延","Y.右延"),
            ("S.上延","X.下延"),
            ("P.偏移",""),
        ]
        self._ext_rows: list[_ExtendRow] = []
        for ll, rl in ext_fields:
            er = _ExtendRow(ll, rl)
            lay.addWidget(er); self._ext_rows.append(er)

        lay.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        outer.addWidget(_HLine())

        apply_w = QWidget(); apply_w.setStyleSheet(f"background:{_BG};")
        alay = QHBoxLayout(apply_w); alay.setContentsMargins(4,3,4,2); alay.setSpacing(4)
        b_apply = QPushButton("√ 修改应用属性!")
        b_apply.setStyleSheet(f"""QPushButton{{background:#f0f4fa;border:1px solid {_BORD};
            border-radius:3px;color:{_TEXT};font-size:11px;min-height:26px;}}
            QPushButton:hover{{background:#dce7f8;border-color:{_BLUE};}}""")
        alay.addWidget(b_apply, 1)
        b_cancel = QPushButton("✕"); b_cancel.setFixedSize(26,26)
        b_cancel.setStyleSheet(f"""QPushButton{{background:transparent;border:1px solid {_RED_B};
            border-radius:3px;color:{_RED};font-size:13px;font-weight:bold;}}
            QPushButton:hover{{background:#ffe0e0;}}""")
        alay.addWidget(b_cancel)
        outer.addWidget(apply_w)

        grp_w = QWidget(); grp_w.setStyleSheet(f"background:{_BG};")
        glay = QHBoxLayout(grp_w); glay.setContentsMargins(4,2,4,2); glay.setSpacing(0)
        b_grp = QPushButton("修改到同组板件")
        b_grp.setStyleSheet(f"""QPushButton{{background:#f5f7fa;border:1px solid {_BORD};
            border-radius:3px;color:{_GRAY};font-size:11px;min-height:26px;}}
            QPushButton:hover{{background:#e8edf5;color:{_TEXT};}}""")
        glay.addWidget(b_grp)
        outer.addWidget(grp_w)

        btn3_w = QWidget(); btn3_w.setStyleSheet(f"background:{_BG};")
        b3lay = QHBoxLayout(btn3_w); b3lay.setContentsMargins(4,2,4,4); b3lay.setSpacing(4)
        for label in ["🖌 刷异形","🖌 刷孔槽","材料"]:
            b = QPushButton(label)
            b.setStyleSheet(f"""QPushButton{{background:{_WHITE};border:1px solid {_BORD};
                border-radius:3px;color:{_TEXT};font-size:11px;min-height:26px;}}
                QPushButton:hover{{background:#e8f4ff;border-color:{_BLUE};}}""")
            b3lay.addWidget(b, 1)
        outer.addWidget(btn3_w)
        outer.addWidget(self._build_finish())
        return w

    # ── 审图 Tab ─────────────────────────────────────────────────────────────

    def _build_shenjian(self):
        w = QWidget(); w.setStyleSheet(f"background:{_BG};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        tip = QLabel("审图功能开发中…")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet(f"color:{_GRAY};font-size:12px;")
        lay.addStretch(1); lay.addWidget(tip); lay.addStretch(1)
        lay.addWidget(self._build_finish())
        return w

    # ── 公共操作按钮 ─────────────────────────────────────────────────────────

    def _build_action_row(self):
        w = QWidget(); w.setStyleSheet(f"background:{_BG};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(_SIDE_GUTTER, 4, _SIDE_GUTTER, 2)
        lay.setSpacing(6)
        b1 = QPushButton("添加or修改")
        b1.setStyleSheet(f"""QPushButton{{background:#f0f4fa;border:1px solid {_BORD};
            border-radius:3px;color:{_TEXT};font-size:11px;min-height:25px;}}
            QPushButton:hover{{background:#dce7f8;border-color:{_BLUE};}}""")
        b1.clicked.connect(self._emit_add_or_modify_command)
        lay.addWidget(b1)
        b2 = QPushButton("↩")
        b2.setToolTip("撤销（最多 5 步）")
        b2.setFixedSize(26, 25)
        b2.setStyleSheet(f"""QPushButton{{background:transparent;border:1px solid {_BORD};
            border-radius:3px;color:{_GRAY};font-size:12px;}}
            QPushButton:hover{{background:#f5e6e6;border-color:{_RED};color:{_RED};}}""")
        b2.clicked.connect(
            lambda: self.sig_command_requested.emit("cabinet_undo", None)
        )
        lay.addWidget(b2)
        return w

    def _build_save_row(self):
        w = QWidget(); w.setStyleSheet(f"background:{_BG};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(_SIDE_GUTTER, 2, _SIDE_GUTTER, 4)
        lay.setSpacing(6)
        b1 = QPushButton("存为产品库")
        b1.setStyleSheet(f"""QPushButton{{background:{_RED_L};border:1px solid {_RED_B};
            border-radius:3px;color:#c0392b;font-size:11px;min-height:25px;}}
            QPushButton:hover{{background:#ffe0e0;border-color:{_RED};}}""")
        b1.clicked.connect(self._emit_save_to_library_command)
        b2 = QPushButton("✕"); b2.setToolTip("删除"); b2.setFixedSize(26,25)
        b2.setStyleSheet(f"""QPushButton{{background:transparent;border:1px solid {_RED_B};
            border-radius:3px;color:{_RED};font-size:12px;font-weight:bold;}}
            QPushButton:hover{{background:#ffe0e0;}}""")
        lay.addWidget(b2); return w

    def _build_finish(self):
        w = QWidget()
        w.setStyleSheet(f"background:{_BG};border-top:1px solid {_BORD};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(_SIDE_GUTTER, 6, _SIDE_GUTTER, 8)
        btn = QPushButton("完成柜子设计")
        btn.setStyleSheet(f"""QPushButton{{background:{_BLUE};border:none;
            border-radius:5px;color:#ffffff;font-size:14px;font-weight:bold;
            min-height:40px;}}
            QPushButton:hover{{background:{_BLH};}}
            QPushButton:pressed{{background:#0e4f9a;}}""")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._emit_finish_design_command)
        lay.addWidget(btn); return w

    # ── 公开 API ──────────────────────────────────────────────────────────────

    def prepare_for_cabinet_mode(self) -> None:
        """进入柜体设计模式时：通用全局变量折叠、模块产品参数展开、回到柜体 Tab。"""
        self._global_vars_sec.set_expanded(False)
        self._module_expanded = True
        self._module_body.setVisible(True)
        self._module_hdr.setText("- 模块产品参数")
        self._on_tab(0)

    def set_dimensions(self, w, h, d):
        self._spin_w.setValue(w); self._spin_h.setValue(h); self._spin_d.setValue(d)

    def get_dimensions(self):
        return self._spin_w.value(), self._spin_h.value(), self._spin_d.value()

    def set_quantity(self, qty): self._spin_qty.setValue(qty)
    def get_quantity(self):      return self._spin_qty.value()

    def get_shrink_values(self):
        return {k: s.value() for k, s in self._shrink_spins.items()}

    def get_panel_props(self):
        return {row._name: (row.get_value(), row.is_locked())
                for row in self._panel_prop_rows}

    # --- 命令链兼容：双发旧信号 + sig_command_requested（由 CabinetDesignView 接 dispatcher）---

    def _emit_add_or_modify_command(self) -> None:
        """添加 or 修改：保留主窗口既有连接，同时走命令名。"""
        self.sig_add_or_modify.emit()
        self.sig_command_requested.emit("apply_add_or_modify", None)

    def _emit_save_to_library_command(self) -> None:
        """存为产品库：双发。"""
        self.sig_save_to_library.emit()
        self.sig_command_requested.emit("save_to_library", None)

    def _emit_finish_design_command(self) -> None:
        """完成柜子设计：先发命令链占位，再保持原退出信号顺序。"""
        self.sig_command_requested.emit("finish_cabinet_design", None)
        self.sig_finish_design.emit()


# ─── 独立预览 ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMainWindow, QHBoxLayout
    app = QApplication(sys.argv); app.setStyle("Fusion")
    win = QMainWindow(); win.setWindowTitle("CabinetPropertyPanel 预览"); win.resize(340, 780)
    central = QWidget(); hl = QHBoxLayout(central)
    hl.setContentsMargins(0,0,0,0); hl.setSpacing(0)
    canvas = QWidget(); canvas.setStyleSheet("background:#2c3e50;")
    hl.addWidget(canvas, 1)
    panel = CabinetPropertyPanel()
    panel.sig_finish_design.connect(lambda: print("[完成]"))
    panel.sig_add_or_modify.connect(lambda: print("[添加/修改]"))
    hl.addWidget(panel)
    win.setCentralWidget(central); win.show()
    import sys; sys.exit(app.exec())
