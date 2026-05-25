# -*- coding: utf-8 -*-
"""主窗口模块

负责把所有 UI 子组件装配起来。
本文件只做"装配 + 信号连接"，不实现任何业务逻辑。
业务逻辑（拆单、排版、文件读写等）由 core/ 层处理，通过 controller 连接。
"""
import os
import sys

from PySide6.QtCore import Qt, QSize, Signal as _Signal, QRectF, QPointF
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import (
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QFrame,
    QButtonGroup,
    QGraphicsDropShadowEffect,
)

from .menu_bar import MenuBar
from .status_bar import StatusBar
from .tool_bar import SideTabBar
from ..dialogs.basic_config_dialog import BasicConfigDialog
from ..dialogs.system_param_dialog import SystemParamDialog
from ..dialogs.shortcut_command_dialog import ShortcutCommandDialog
from ..dialogs.irregular_element_dialog import IrregularElementDialog
from ..dialogs.order_manager_dialog import OrderManagerDialog
from ..dialogs.hole_rule_dialog import HoleRuleDialog
from ..dialogs.product_structure_dialog import ProductStructureDialog  # 产品结构设计器
from .view_2d import View2D, FloorPlanScene  # FloorPlanScene 负责 drawBackground 参考网格
from .view_3d import View3D   # OpenGL 3D 画柜子视图
from .new_cabinet_dialog import NewCabinetDialog  # 新建柜子对话框
from space_engine.room import Room, StraightWall

from ui.qt_lifecycle import safe_set_font_size


def _resolve_icon_dir() -> str:
    """定位 icons 目录。

    优先顺序：
        1. 已打包（PyInstaller）：sys._MEIPASS / icons
        2. 源码运行：项目根目录 / icons（main_window.py 向上两级）
        3. 兜底：当前工作目录 / icons
    """
    # 1. PyInstaller 单文件运行
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, "icons")
        if os.path.isdir(p):
            return p

    # 2. 源码：ui/main_window/main_window.py → 项目根
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(here, "..", ".."))
    p = os.path.join(project_root, "icons")
    if os.path.isdir(p):
        return p

    # 3. cwd 兜底
    return os.path.abspath("icons")


class MainWindow(QMainWindow):
    """智柜 V2026 主窗口。

    布局结构：
        ┌─────────────────────────────────────────────────┐
        │  菜单栏 (MenuBar)                                │
        ├──┬───────────┬──────────────────────────────────┤
        │侧│           │                                  │
        │栏│ 资源面板  │       中央画布 (Canvas)          │
        │  │  (Stack)  │                                  │
        │  │           │                                  │
        ├──┴───────────┴──────────────────────────────────┤
        │  状态栏 (StatusBar)                              │
        └─────────────────────────────────────────────────┘
    """

    APP_TITLE = "智柜 V2026"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.APP_TITLE)
        self.resize(1400, 860)

        # 资源目录
        self._icon_dir = _resolve_icon_dir()

        # 内存中暂存的设置数据（未来由 core/config 持久化）
        self._basic_config: dict = {}
        self._system_param: dict = {}
        self._shortcut_command: dict = {}
        self._irregular_element: dict = {}
        self._hole_rule_config: dict = {}

        # 订单管理对话框单例（避免重复打开）
        self._order_dialog: OrderManagerDialog | None = None

        self._build_menu()
        self._build_central()
        self._build_status_bar()
        self._connect_signals()

    # ---------------------------------------------------------------- 菜单
    def _build_menu(self):
        """创建菜单栏。"""
        self.menu_bar = MenuBar(self)
        self.setMenuBar(self.menu_bar)

    # ---------------------------------------------------------------- 中央区域
    def _build_central(self):
        """构建中央区域:左侧 Tab + 资源面板 + 画布。"""
        central = QWidget(self)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. 最左侧 —— 垂直 Tab 切换栏
        self.side_tab = SideTabBar(central)
        root.addWidget(self.side_tab)

        # 2. 左侧资源面板（用 QStackedWidget 配合 SideTabBar 切换）
        self.resource_stack = self._build_resource_stack()
        root.addWidget(self.resource_stack)

        # 3. 中央画布占位
        self.canvas = self._build_canvas()
        root.addWidget(self.canvas, stretch=1)

        self.setCentralWidget(central)

        # 柜体设计模式全屏覆盖层（默认隐藏）
        from view.cabinet_view.cabinet_design_view import CabinetDesignView
        self._cabinet_design_view = CabinetDesignView(self)
        self._cabinet_design_view.hide()
        self._cabinet_design_view.sig_finish.connect(self._on_cabinet_finish)

        # 柜体设计左侧组件面板 + 右侧属性面板（进入柜体模式时懒创建，退出时隐藏）
        self._assembler_panel = None
        self._prop_panel = None

    def _on_cabinet_finish(self):
        """CabinetDesignView.exit() 发射 sig_finish 后执行：恢复侧栏 Tab 文字 + 隐藏属性面板。"""
        btns = self.side_tab._buttons
        for i, (orig_name, _) in enumerate(self.side_tab.TABS):
            if i < len(btns):
                btns[i].setText(self.side_tab._to_vertical_text(orig_name))
                btns[i].show()
        self.side_tab.set_current_index(1)

        # 隐藏两侧面板
        if self._assembler_panel is not None:
            self._assembler_panel.hide()
        if self._prop_panel is not None:
            self._prop_panel.hide()

    # ---------------------------------------------------------------- 柜体模式进入/退出
    def _enter_cabinet_mode(self, project):
        """进入柜体设计模式：委托 CabinetDesignView；根 Space 仅经 ``SET_ROOT_SPACE`` 命令写入。"""
        self._cabinet_design_view.enter(
            canvas         = self.canvas,
            menu_bar       = self.menu_bar,
            side_tab       = self.side_tab,
            resource_stack = self.resource_stack,
            status_bar     = self.status_bar,
            project        = project,
        )

        # ── 左侧组件面板（CabinetAssembler）────────────────────────────
        from view.cabinet_view.cabinet_assembler import (
            CabinetAssembler,
            assembler_icon_status_label,
        )
        if self._assembler_panel is None:
            self._assembler_panel = CabinetAssembler(
                icon_dir = self._icon_dir,
                parent   = self.canvas,   # 叠加在 canvas 上
            )
            self._assembler_panel.sig_icon_clicked.connect(
                lambda idx, path: self.status_bar.set_hint(
                    f"选中：{assembler_icon_status_label(idx, path)}"
                    + (f"  ({path})" if path else ""),
                    1500,
                )
            )
            self._assembler_panel.sig_template_clicked.connect(
                lambda name, path: self.status_bar.set_hint(
                    f"载入模板：{name}", 1500
                )
            )

        # ── 右侧属性面板 ──────────────────────────────────────────────
        # 懒创建：首次进入时才实例化，后续复用（仅重置数据）
        from view.cabinet_view.cabinet_property_panel import CabinetPropertyPanel
        if self._prop_panel is None:
            self._prop_panel = CabinetPropertyPanel(
                parent = self.canvas,     # 叠加在 canvas 上
            )
            # 信号连接
            self._prop_panel.sig_finish_design.connect(
                self._cabinet_design_view.exit
            )
            self._prop_panel.sig_save_to_library.connect(
                lambda: self.status_bar.set_hint("已存为产品库", 2000)
            )
            self._prop_panel.sig_add_or_modify.connect(
                lambda: self.status_bar.set_hint("添加/修改完成", 2000)
            )
            self._prop_panel.sig_tab_changed.connect(
                lambda i: self.status_bar.set_hint(
                    ["柜体", "板件", "审图"][i] + " 面板", 1500
                )
            )

        # 同步产品参数到面板
        w = float(getattr(project, "cabinet_width",  2400))
        h = float(getattr(project, "cabinet_height", 2200))
        d = float(getattr(project, "cabinet_depth",   600))
        self._prop_panel.set_dimensions(w, h, d)
        self._prop_panel.prepare_for_cabinet_mode()

        # 柜体命令链：UI 信号 → CommandDispatcher（结构解耦，不改变原有面板信号语义）
        self._cabinet_design_view.bind_cabinet_command_ui(
            self._assembler_panel,
            self._prop_panel,
        )
        self._cabinet_design_view.dispatch_set_root_space()

        # 定位并显示（两面板叠在 canvas 右侧、彼此紧挨；parent 均为 canvas）
        self._layout_prop_panel()
        self._assembler_panel.show()
        self._assembler_panel.raise_()
        self._prop_panel.show()
        self._prop_panel.raise_()

    def _exit_cabinet_mode(self):
        """退出柜体设计模式：恢复左侧 Tab 文字（其余由 CabinetDesignView.exit() 完成）。"""
        btns = self.side_tab._buttons
        for i, (orig_name, _) in enumerate(self.side_tab.TABS):
            if i < len(btns):
                btns[i].setText(self.side_tab._to_vertical_text(orig_name))
                btns[i].show()
        self.side_tab.set_current_index(1)

    def _layout_prop_panel(self):
        """将两面板叠在 canvas 右缘：属性面板贴右，组件面板紧挨其左侧（无中间缝隙）。"""
        cw = self.canvas.width()
        ch = self.canvas.height()

        pw = self._prop_panel.PANEL_WIDTH if self._prop_panel is not None else 0
        aw = self._assembler_panel.PANEL_WIDTH if self._assembler_panel is not None else 0

        if self._prop_panel is not None:
            self._prop_panel.setGeometry(cw - pw, 0, pw, ch)

        if self._assembler_panel is not None:
            self._assembler_panel.setGeometry(cw - pw - aw, 0, aw, ch)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cw = self.centralWidget()
        if cw and hasattr(self, "_cabinet_design_view"):
            self._cabinet_design_view.setGeometry(cw.geometry())
        # 通知导航方块更新位置
        if hasattr(self, "_cabinet_design_view"):
            self._cabinet_design_view.on_canvas_resize(self.canvas.width())
        # 两侧面板跟随 canvas 大小调整
        if getattr(self, "_prop_panel", None) and self._prop_panel.isVisible():
            self._layout_prop_panel()

    def _build_resource_stack(self) -> QStackedWidget:
        """创建资源面板堆栈。

        每个 Tab 对应一个面板。当前为占位实现，
        未来会被 ui/panels/ 下的真实组件替换。
        """
        stack = QStackedWidget()
        stack.setFixedWidth(250)
        stack.setStyleSheet(
            "QStackedWidget { background-color: #f5f7fa; border-right: 1px solid #dcdfe6; }"
        )

        # index 0：画户型面板（定制：带"新建房间"/"删除房间"按钮）
        stack.addWidget(self._build_floor_plan_panel())

        # index 1：画柜子面板（定制：预制柜体模型库）
        stack.addWidget(self._build_cabinet_panel())

        # index 2：材质面板（图片浏览器）
        stack.addWidget(self._build_material_panel())

        # index 3-4：其余面板（占位）
        for title in ["模型面板", "场景树面板"]:
            stack.addWidget(self._make_placeholder_panel(title))

        return stack

    def _build_floor_plan_panel(self) -> QWidget:
        """构建"画户型"专属资源面板。

        布局：
            ┌─────────────────────────────┐
            │ [+ 新建一个房间]            │
            │ [🗑 删除当前房间]           │
            │─────────────────────────────│
            │ [搜索户型] [导入图纸]       │
            │ ▼ 画房间                    │
            │   [直墙B][矩形墙F][弧墙H]  │
            │   [外部区域]               │
            │ ▼ 放门窗                    │
            │   [门][窗][飘窗][门窗洞]   │
            │ ▼加结构                     │
            │   [柱子][梁][楼梯]         │
            │   [烟道][洞口][包管]       │
            │   [飘窗台][壁龛]           │
            └─────────────────────────────┘

        图标命名规则（放在 icons/ 目录下）：
            fp_search.png         搜索户型
            fp_import_cad.png     导入图纸
            fp_wall_straight.png  直墙
            fp_wall_rect.png      矩形墙
            fp_wall_arc.png       弧墙
            fp_exterior.png       外部区域
            fp_door.png           门
            fp_window.png         窗
            fp_bay_window.png     飘窗
            fp_opening.png        门窗洞
            fp_column.png         柱子
            fp_beam.png           梁
            fp_stair.png          楼梯
            fp_flue.png           烟道
            fp_hole.png           洞口
            fp_pipe.png           包管
            fp_bay_sill.png       飘窗台
            fp_niche.png          壁龛
        """
        # ── 图标目录 ─────────────────────────────────────────────
        icon_dir = self._icon_dir

        # ── 样式常量 ─────────────────────────────────────────────
        _BTN_NORMAL = """
            QPushButton {
                background: #ffffff;
                border: 1px solid #d0d5dd;
                border-radius: 4px;
                color: #303133;
                font-size: 13px;
                text-align: left;
                padding: 0 12px;
                height: 32px;
            }
            QPushButton:hover  { background: #f0f4ff; border-color: #aab4c8; }
            QPushButton:pressed { background: #e0eaff; }
        """
        _BTN_DELETE = """
            QPushButton {
                background: #ffffff;
                border: 1px solid #d0d5dd;
                border-radius: 4px;
                color: #303133;
                font-size: 13px;
                text-align: left;
                padding: 0 12px;
                height: 32px;
            }
            QPushButton:hover  { background: #fff0f0; border-color: #e0a0a0; color: #c0392b; }
            QPushButton:pressed { background: #ffe0e0; }
        """
        _BTN_ACTION = """
            QPushButton {
                background: #f4f6f8;
                border: 1px solid #d0d5dd;
                border-radius: 4px;
                color: #303133;
                font-size: 12px;
                padding: 0 8px;
                height: 30px;
            }
            QPushButton:hover  { background: #e8f0fe; border-color: #7aadee; }
            QPushButton:pressed { background: #d6e8ff; }
        """
        _TOOL_BTN = """
            QToolButton {
                background: #f9fafb;
                border: 1px solid #e4e7ed;
                border-radius: 5px;
                color: #303133;
                font-size: 11px;
            }
            QToolButton:checked { background: #94dfef; border-color: #5bbfd4; color: #1a5fa8; }
            QToolButton:pressed { background: #7dd4e8; }
        """
        _GROUP_HDR = """
            QPushButton {
                background: transparent;
                border: none;
                border-top: 1px solid #e4e7ed;
                color: #303133;
                font-size: 12px;
                font-weight: bold;
                text-align: left;
                padding: 2px 2px;
            }
            QPushButton:hover { color: #4a90d9; }
        """

        def make_icon_btn(icon_file: str, label: str, tip: str = "") -> QToolButton:
            """创建图标在上、文字在下的方形工具按钮（72×68）。"""
            btn = QToolButton()
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setText(label)
            btn.setToolTip("")          # 不显示悬停提示
            btn.setCheckable(True)
            btn.setFixedSize(72, 68)
            btn.setIconSize(QSize(30, 30))
            btn.setStyleSheet(_TOOL_BTN)
            icon_path = os.path.join(icon_dir, icon_file)
            if os.path.isfile(icon_path):
                btn.setIcon(QIcon(icon_path))
            return btn

        def make_group_header(text: str) -> QPushButton:
            """分组标题行，带折叠箭头（▲/▼），点击切换子内容显隐。"""
            btn = QPushButton(f"∨  {text}")
            btn.setStyleSheet(_GROUP_HDR)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            return btn

        # 画户型图标工具 id（与 groups 展平顺序一致）
        FP_TOOL_IDS = (
            "wall_straight", "wall_rect", "arc_wall", "exterior",
            "door", "window", "bay_window", "opening",
            "column", "beam", "stair", "flue", "hole", "pipe", "bay_sill", "niche",
        )

        def make_grid(btns: list) -> QWidget:
            """将按钮列表排成每行3列的网格容器（互斥与再次点击关闭由主窗口 _connect_draw_tools 处理）。"""
            container = QWidget()
            grid = QGridLayout(container)
            grid.setContentsMargins(0, 2, 0, 2)
            grid.setSpacing(4)
            for i, btn in enumerate(btns):
                grid.addWidget(btn, i // 3, i % 3)
            return container

        # ════════════════════════════════════════════════════════════
        # 外层面板
        # ════════════════════════════════════════════════════════════
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(8, 6, 8, 4)
        outer.setSpacing(4)

        # ── ① 新建 / 删除房间 ─────────────────────────────────────
        btn_add = QPushButton("＋  新建一个房间")
        btn_add.setStyleSheet(_BTN_NORMAL)
        btn_add.setFixedHeight(34)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        outer.addWidget(btn_add)

        btn_del = QPushButton("🗑  删除当前房间")
        btn_del.setStyleSheet(_BTN_DELETE)
        btn_del.setFixedHeight(34)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        outer.addWidget(btn_del)

        # ── ② 内容区（搜索/导入 + 三分组，直接铺开不滚动）─────────
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(inner)
        vbox.setContentsMargins(0, 4, 0, 2)
        vbox.setSpacing(1)

        # ── 搜索户型 / 导入图纸 ───────────────────────────────────
        row_top = QHBoxLayout()
        row_top.setSpacing(6)
        for icon_f, lbl in [("fp_search.png", "搜索户型"),
                             ("fp_import_cad.png", "导入图纸")]:
            b = QPushButton(lbl)
            b.setStyleSheet(_BTN_ACTION)
            b.setFixedHeight(30)
            icon_path = os.path.join(icon_dir, icon_f)
            if os.path.isfile(icon_path):
                b.setIcon(QIcon(icon_path))
                b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            row_top.addWidget(b)
        vbox.addLayout(row_top)

        # ── 分组数据 ──────────────────────────────────────────────
        groups = [
            ("画房间", [
                ("fp_wall_straight.png", "直墙",   "直墙 (B)"),
                ("fp_wall_rect.png",     "矩形墙", "矩形墙 (F)"),
                ("fp_wall_arc.png",      "弧墙",   "弧墙 (H)"),
                ("fp_exterior.png",      "外部区域", "外部区域"),
            ]),
            ("放门窗", [
                ("fp_door.png",    "门",    "门"),
                ("fp_window.png",  "窗",    "窗"),
                ("fp_bay_window.png", "飘窗", "飘窗"),
                ("fp_opening.png", "门窗洞", "门窗洞"),
            ]),
            ("加结构", [
                ("fp_column.png",   "柱子",  "柱子"),
                ("fp_beam.png",     "梁",    "梁"),
                ("fp_stair.png",    "楼梯",  "楼梯"),
                ("fp_flue.png",     "烟道",  "烟道"),
                ("fp_hole.png",     "洞口",  "洞口"),
                ("fp_pipe.png",     "包管",  "包管"),
                ("fp_bay_sill.png", "飘窗台", "飘窗台"),
                ("fp_niche.png",    "壁龛",  "壁龛"),
            ]),
        ]

        panel._fp_tool_buttons = []
        panel._fp_btn_wall = None
        panel._fp_btn_rect_wall = None
        panel._fp_tool_group = None
        _fp_idx = 0
        for grp_name, items in groups:
            hdr = make_group_header(grp_name)
            vbox.addWidget(hdr)

            btns = [make_icon_btn(f, lbl, tip) for f, lbl, tip in items]
            if grp_name == "画房间":
                if btns:
                    panel._fp_btn_wall = btns[0]
                if len(btns) >= 2:
                    panel._fp_btn_rect_wall = btns[1]
            for b in btns:
                if _fp_idx < len(FP_TOOL_IDS):
                    b.setProperty("fp_tool_id", FP_TOOL_IDS[_fp_idx])
                _fp_idx += 1
                panel._fp_tool_buttons.append(b)
            grid_w = make_grid(btns)
            vbox.addWidget(grid_w)

            # 折叠/展开
            def _toggle(checked, gw=grid_w, hb=hdr):
                gw.setVisible(checked)
                hb.setText(("∨  " if checked else "∧  ") + hb.text()[3:])
            hdr.toggled.connect(_toggle)

        outer.addWidget(inner)

        return panel

    def _build_cabinet_panel(self) -> QWidget:
        """构建"画柜子"专属资源面板。

        本地 Tab：
            - 根目录 = 主程序同级的 templates/ 目录
            - 支持进入子文件夹（双击/单击文件夹按钮）
            - 支持返回上级（← 按钮）
            - 路径栏显示当前相对路径
            - JSON 文件显示为模型卡片（读取 thumbnail 字段或用默认图标）
        在线 Tab：预留，显示占位提示。
        """
        import json as _json

        icon_dir     = self._icon_dir

        # templates 根目录：与主程序 main.py 同级
        here         = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(here, "..", ".."))
        templates_root = os.path.join(project_root, "templates")

        # ── 样式 ──────────────────────────────────────────────────
        _TAB_BAR = """
            QWidget#cabinetTabBar {
                background: #ffffff;
                border-bottom: 1px solid #e4e7ed;
            }
        """
        _TAB_BTN = """
            QPushButton {
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                color: #606266;
                font-size: 13px;
                padding: 6px 14px;
                min-width: 48px;
            }
            QPushButton:checked {
                color: #4a90d9;
                border-bottom: 2px solid #4a90d9;
                font-weight: bold;
            }
            QPushButton:hover { color: #4a90d9; }
        """
        _NAV_BTN = """
            QPushButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                color: #606266;
                font-size: 13px;
                padding: 2px 5px;
                min-width: 24px;
                height: 22px;
            }
            QPushButton:hover  { background: #e8edf5; border-color: #c0c8d8; }
            QPushButton:pressed { background: #d8e2f0; }
            QPushButton:disabled { color: #c0c4cc; }
        """
        _PATH_INPUT = """
            QLineEdit {
                background: #ffffff;
                border: 1px solid #d0d5dd;
                border-radius: 3px;
                font-size: 12px;
                color: #303133;
                padding: 0 6px;
                height: 22px;
            }
        """
        _ITEM_BTN = """
            QToolButton {
                background: #ffffff;
                border: 1px solid #e4e7ed;
                border-radius: 5px;
                color: #303133;
                font-size: 11px;
            }
            QToolButton:hover  { background: #e8f4ff; border-color: #94dfef; }
            QToolButton:pressed { background: #d0ecf8; }
        """

        # ── 绘制默认文件夹图标 ────────────────────────────────────
        def _make_folder_pixmap() -> QPixmap:
            from PySide6.QtGui import QPainterPath
            from PySide6.QtCore import QRectF
            pix = QPixmap(52, 44)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            # 背面
            p.setBrush(QBrush(QColor("#e8a020")))
            pb = QPainterPath()
            pb.addRoundedRect(QRectF(0, 8, 52, 34), 3, 3)
            p.drawPath(pb)
            # 标签
            pt = QPainterPath()
            pt.addRoundedRect(QRectF(0, 4, 20, 8), 2, 2)
            p.drawPath(pt)
            # 前面
            p.setBrush(QBrush(QColor("#f5a623")))
            pf = QPainterPath()
            pf.addRoundedRect(QRectF(0, 12, 52, 28), 3, 3)
            p.drawPath(pf)
            # 暗条
            p.setBrush(QBrush(QColor(44, 62, 80, 80)))
            p.drawRect(QRectF(0, 12, 52, 3))
            p.end()
            return pix

        # ── 绘制默认 JSON 模型图标 ────────────────────────────────
        def _make_model_pixmap() -> QPixmap:
            from PySide6.QtCore import QRectF
            pix = QPixmap(52, 52)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#e8f4ff")))
            from PySide6.QtGui import QPainterPath
            pp = QPainterPath()
            pp.addRoundedRect(QRectF(2, 2, 48, 48), 5, 5)
            p.drawPath(pp)
            # 简单柜体示意线框
            pen = QPen(QColor("#5bbfd4"))
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(10, 10, 32, 32)          # 外框
            p.drawLine(26, 10, 26, 42)           # 竖中线
            p.drawLine(10, 26, 42, 26)           # 横中线
            # 小把手
            p.drawEllipse(22, 23, 4, 4)
            p.drawEllipse(28, 23, 4, 4)
            p.end()
            return pix

        # ── 从 JSON 读取缩略图 ────────────────────────────────────
        def _thumb_from_json(json_path: str) -> QPixmap | None:
            """尝试读取 JSON 内 thumbnail / preview / image 字段（base64）。"""
            try:
                with open(json_path, "r", encoding="utf-8") as jf:
                    data = _json.load(jf)
                for key in ("thumbnail", "preview", "image", "thumb"):
                    val = data.get(key, "")
                    if val and isinstance(val, str):
                        import base64
                        raw = base64.b64decode(val)
                        pix = QPixmap()
                        pix.loadFromData(raw)
                        if not pix.isNull():
                            return pix.scaled(
                                52, 52,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
            except Exception:
                pass
            return None

        # ── 构建内容网格（文件夹 + JSON 文件）─────────────────────
        def _build_grid(dir_path: str, on_enter) -> QWidget:
            """扫描 dir_path，文件夹和 .json 文件各做一个 QToolButton，2列网格。"""
            container = QWidget()
            container.setStyleSheet("background: #ffffff;")
            grid = QGridLayout(container)
            grid.setContentsMargins(8, 8, 8, 8)
            grid.setSpacing(8)
            grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

            entries = []
            if os.path.isdir(dir_path):
                try:
                    for name in sorted(os.listdir(dir_path)):
                        full = os.path.join(dir_path, name)
                        if os.path.isdir(full):
                            entries.append(("dir", name, full))
                        elif name.lower().endswith(".json"):
                            entries.append(("json", name[:-5], full))
                except PermissionError:
                    pass

            for idx, (kind, display, full_path) in enumerate(entries):
                btn = QToolButton()
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                btn.setToolTip("")
                btn.setFixedSize(96, 90)
                btn.setStyleSheet(_ITEM_BTN)

                if kind == "dir":
                    btn.setText(display)
                    btn.setIconSize(QSize(52, 44))
                    btn.setIcon(QIcon(_make_folder_pixmap()))
                    btn.clicked.connect(lambda _, p=full_path: on_enter(p))
                else:
                    # JSON 模型
                    short = display if len(display) <= 6 else display[:5] + "…"
                    btn.setText(short)
                    btn.setIconSize(QSize(52, 52))
                    thumb = _thumb_from_json(full_path)
                    btn.setIcon(QIcon(thumb if thumb else _make_model_pixmap()))
                    # 单击选中（不导航）
                    btn.setCheckable(True)

                grid.addWidget(btn, idx // 2, idx % 2)

            # 空目录提示
            if not entries:
                lbl = QLabel("（空目录）")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("color: #c0c4cc; font-size: 12px;")
                grid.addWidget(lbl, 0, 0, 1, 2)

            return container

        # ════════════════════════════════════════════════════════════
        # 面板主体
        # ════════════════════════════════════════════════════════════
        panel = QWidget()
        panel.setStyleSheet("background: #f5f7fa;")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Tab 栏：本地 / 在线 ───────────────────────────────────
        tab_bar = QWidget()
        tab_bar.setObjectName("cabinetTabBar")
        tab_bar.setStyleSheet(_TAB_BAR)
        tab_bar.setFixedHeight(34)
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)
        tab_group = QButtonGroup(tab_bar)
        tab_group.setExclusive(True)
        for i, name in enumerate(["本地", "在线"]):
            tb = QPushButton(name)
            tb.setCheckable(True)
            tb.setChecked(i == 0)
            tb.setStyleSheet(_TAB_BTN)
            tab_group.addButton(tb, i)
            tab_layout.addWidget(tb)
        tab_layout.addStretch(1)
        outer.addWidget(tab_bar)

        # ── 导航栏 ────────────────────────────────────────────────
        nav_bar   = QWidget()
        nav_bar.setObjectName("cabinetNavBar")
        nav_bar.setFixedHeight(30)
        nav_bar.setStyleSheet(
            "QWidget#cabinetNavBar { background:#f5f7fa; border-bottom:1px solid #e4e7ed; }"
        )
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(4, 3, 4, 3)
        nav_layout.setSpacing(3)

        btn_back = QPushButton("←")
        btn_back.setStyleSheet(_NAV_BTN)
        btn_back.setFixedSize(24, 22)
        btn_back.setEnabled(False)
        nav_layout.addWidget(btn_back)

        btn_filter = QPushButton("▽")
        btn_filter.setStyleSheet(_NAV_BTN)
        btn_filter.setFixedSize(24, 22)
        nav_layout.addWidget(btn_filter)

        path_edit = QLineEdit("/")
        path_edit.setStyleSheet(_PATH_INPUT)
        path_edit.setReadOnly(True)
        nav_layout.addWidget(path_edit, stretch=1)
        outer.addWidget(nav_bar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e4e7ed;")
        outer.addWidget(sep)

        # ── 内容 QStackedWidget（本地 / 在线）─────────────────────
        content_stack = QStackedWidget()
        content_stack.setStyleSheet("background: #ffffff;")

        # ── 本地页：可导航的滚动区域 ──────────────────────────────
        local_scroll = QScrollArea()
        local_scroll.setWidgetResizable(True)
        local_scroll.setFrameShape(QFrame.Shape.NoFrame)
        local_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        local_scroll.setStyleSheet("QScrollArea { background: #ffffff; }")
        content_stack.addWidget(local_scroll)   # index 0

        # ── 在线页：占位 ──────────────────────────────────────────
        online_ph = QWidget()
        online_ph.setStyleSheet("background: #ffffff;")
        ph_layout = QVBoxLayout(online_ph)
        ph_lbl = QLabel("在线模型库\n（敬请期待）")
        ph_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_lbl.setStyleSheet("color: #c0c4cc; font-size: 13px;")
        ph_layout.addWidget(ph_lbl)
        content_stack.addWidget(online_ph)      # index 1

        outer.addWidget(content_stack, stretch=1)

        # ── 导航状态 ──────────────────────────────────────────────
        # 用列表模拟导航历史栈
        _nav_stack: list[str] = []

        def _navigate_to(dir_path: str):
            """进入指定目录，刷新内容区。"""
            _nav_stack.append(dir_path)
            _refresh()

        def _refresh():
            cur = _nav_stack[-1] if _nav_stack else templates_root
            # 更新路径栏
            try:
                rel = os.path.relpath(cur, templates_root)
                path_edit.setText("/" if rel == "." else "/" + rel.replace(os.sep, "/"))
            except ValueError:
                path_edit.setText(cur)
            # 返回按钮：根目录时禁用
            btn_back.setEnabled(len(_nav_stack) > 1)
            # 重建网格
            grid_w = _build_grid(cur, _navigate_to)
            old_w = local_scroll.widget()
            local_scroll.setWidget(grid_w)
            if old_w:
                old_w.deleteLater()

        def _go_back():
            if len(_nav_stack) > 1:
                _nav_stack.pop()
                _refresh()

        btn_back.clicked.connect(_go_back)

        # ── Tab 切换 ──────────────────────────────────────────────
        tab_group.idClicked.connect(content_stack.setCurrentIndex)

        # ── 初始化：加载 templates 根目录 ────────────────────────
        os.makedirs(templates_root, exist_ok=True)
        _navigate_to(templates_root)

        return panel


    @staticmethod
    def _make_placeholder_panel(title: str, desc: str = "") -> QWidget:
        """生成占位面板，后续由实际面板替换。"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #303133;")
        layout.addWidget(lbl_title)

        layout.addStretch(1)
        return panel

    def _build_material_panel(self) -> QWidget:
        """构建"材质"专属资源面板。

        根目录 = 主程序同级的 material/ 目录。
        支持：
            - 进入子文件夹（单击文件夹按钮）
            - 返回上级（← 按钮）
            - 路径栏显示当前相对路径
            - 预览 jpg / png 图片（缩略图显示）
        """
        icon_dir     = self._icon_dir
        here         = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(here, "..", ".."))
        material_root = os.path.join(project_root, "material")

        # ── 样式 ──────────────────────────────────────────────────
        _TAB_BAR = """
            QWidget#materialTabBar {
                background: #ffffff;
                border-bottom: 1px solid #e4e7ed;
            }
        """
        _TAB_BTN = """
            QPushButton {
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                color: #606266;
                font-size: 13px;
                padding: 6px 14px;
                min-width: 48px;
            }
            QPushButton:checked {
                color: #4a90d9;
                border-bottom: 2px solid #4a90d9;
                font-weight: bold;
            }
            QPushButton:hover { color: #4a90d9; }
        """
        _NAV_BTN = """
            QPushButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                color: #606266;
                font-size: 13px;
                padding: 2px 5px;
                min-width: 24px;
                height: 22px;
            }
            QPushButton:hover  { background: #e8edf5; border-color: #c0c8d8; }
            QPushButton:pressed { background: #d8e2f0; }
            QPushButton:disabled { color: #c0c4cc; }
        """
        _PATH_INPUT = """
            QLineEdit {
                background: #ffffff;
                border: 1px solid #d0d5dd;
                border-radius: 3px;
                font-size: 12px;
                color: #303133;
                padding: 0 6px;
                height: 22px;
            }
        """
        _ITEM_BTN = """
            QToolButton {
                background: #ffffff;
                border: 1px solid #e4e7ed;
                border-radius: 5px;
                color: #303133;
                font-size: 11px;
            }
            QToolButton:hover  { background: #e8f4ff; border-color: #94dfef; }
            QToolButton:pressed { background: #d0ecf8; }
        """

        # ── 默认文件夹图标 ────────────────────────────────────────
        def _make_folder_pixmap() -> QPixmap:
            from PySide6.QtGui import QPainterPath
            pix = QPixmap(52, 44)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#e8a020")))
            pb = QPainterPath()
            pb.addRoundedRect(QRectF(0, 8, 52, 34), 3, 3)
            p.drawPath(pb)
            pt = QPainterPath()
            pt.addRoundedRect(QRectF(0, 4, 20, 8), 2, 2)
            p.drawPath(pt)
            p.setBrush(QBrush(QColor("#f5a623")))
            pf = QPainterPath()
            pf.addRoundedRect(QRectF(0, 12, 52, 28), 3, 3)
            p.drawPath(pf)
            p.setBrush(QBrush(QColor(44, 62, 80, 80)))
            p.drawRect(QRectF(0, 12, 52, 3))
            p.end()
            return pix

        # ── 默认材质图标（纯色块）────────────────────────────────
        def _make_material_pixmap() -> QPixmap:
            pix = QPixmap(52, 52)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            from PySide6.QtGui import QPainterPath
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#e0e0e0")))
            pp = QPainterPath()
            pp.addRoundedRect(QRectF(2, 2, 48, 48), 5, 5)
            p.drawPath(pp)
            pen = QPen(QColor("#b0b0b0"))
            pen.setWidthF(1.0)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(2, 26, 50, 26)
            p.drawLine(26, 2, 26, 50)
            p.end()
            return pix

        # ── 从图片文件加载缩略图 ──────────────────────────────────
        def _thumb_from_image(img_path: str) -> QPixmap | None:
            try:
                pix = QPixmap(img_path)
                if not pix.isNull():
                    return pix.scaled(
                        52, 52,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
            except Exception:
                pass
            return None

        # ── 构建内容网格（文件夹 + 图片文件）─────────────────────
        def _build_grid(dir_path: str, on_enter) -> QWidget:
            """扫描 dir_path，文件夹和 jpg/png 图片各做一个 QToolButton，2列网格。"""
            container = QWidget()
            container.setStyleSheet("background: #ffffff;")
            grid = QGridLayout(container)
            grid.setContentsMargins(8, 8, 8, 8)
            grid.setSpacing(8)
            grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

            entries = []
            if os.path.isdir(dir_path):
                try:
                    for name in sorted(os.listdir(dir_path)):
                        full = os.path.join(dir_path, name)
                        if os.path.isdir(full):
                            entries.append(("dir", name, full))
                        elif name.lower().endswith((".jpg", ".jpeg", ".png")):
                            entries.append(("img", os.path.splitext(name)[0], full))
                except PermissionError:
                    pass

            for idx, (kind, display, full_path) in enumerate(entries):
                btn = QToolButton()
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                btn.setToolTip(display)
                btn.setFixedSize(96, 90)
                btn.setStyleSheet(_ITEM_BTN)

                if kind == "dir":
                    btn.setText(display)
                    btn.setIconSize(QSize(52, 44))
                    btn.setIcon(QIcon(_make_folder_pixmap()))
                    btn.clicked.connect(lambda _, p=full_path: on_enter(p))
                else:
                    # 图片材质
                    short = display if len(display) <= 6 else display[:5] + "…"
                    btn.setText(short)
                    btn.setIconSize(QSize(52, 52))
                    thumb = _thumb_from_image(full_path)
                    btn.setIcon(QIcon(thumb if thumb else _make_material_pixmap()))
                    btn.setCheckable(True)

                grid.addWidget(btn, idx // 2, idx % 2)

            if not entries:
                lbl = QLabel("（空目录）")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("color: #c0c4cc; font-size: 12px;")
                grid.addWidget(lbl, 0, 0, 1, 2)

            return container

        # ════════════════════════════════════════════════════════════
        # 面板主体
        # ════════════════════════════════════════════════════════════
        panel = QWidget()
        panel.setStyleSheet("background: #f5f7fa;")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Tab 栏：本地 / 在线 ───────────────────────────────────
        tab_bar = QWidget()
        tab_bar.setObjectName("materialTabBar")
        tab_bar.setStyleSheet(_TAB_BAR)
        tab_bar.setFixedHeight(34)
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)
        tab_group = QButtonGroup(tab_bar)
        tab_group.setExclusive(True)
        for i, name in enumerate(["本地", "在线"]):
            tb = QPushButton(name)
            tb.setCheckable(True)
            tb.setChecked(i == 0)
            tb.setStyleSheet(_TAB_BTN)
            tab_group.addButton(tb, i)
            tab_layout.addWidget(tb)
        tab_layout.addStretch(1)
        outer.addWidget(tab_bar)

        # ── 导航栏 ────────────────────────────────────────────────
        nav_bar = QWidget()
        nav_bar.setObjectName("materialNavBar")
        nav_bar.setFixedHeight(30)
        nav_bar.setStyleSheet(
            "QWidget#materialNavBar { background:#f5f7fa; border-bottom:1px solid #e4e7ed; }"
        )
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(4, 3, 4, 3)
        nav_layout.setSpacing(3)

        btn_back = QPushButton("←")
        btn_back.setStyleSheet(_NAV_BTN)
        btn_back.setFixedSize(24, 22)
        btn_back.setEnabled(False)
        nav_layout.addWidget(btn_back)

        path_edit = QLineEdit("/")
        path_edit.setStyleSheet(_PATH_INPUT)
        path_edit.setReadOnly(True)
        nav_layout.addWidget(path_edit, stretch=1)
        outer.addWidget(nav_bar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e4e7ed;")
        outer.addWidget(sep)

        # ── 内容 QStackedWidget（本地 / 在线）─────────────────────
        content_stack = QStackedWidget()
        content_stack.setStyleSheet("background: #ffffff;")

        # 本地页
        local_scroll = QScrollArea()
        local_scroll.setWidgetResizable(True)
        local_scroll.setFrameShape(QFrame.Shape.NoFrame)
        local_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        local_scroll.setStyleSheet("QScrollArea { background: #ffffff; }")
        content_stack.addWidget(local_scroll)   # index 0

        # 在线页：占位
        online_ph = QWidget()
        online_ph.setStyleSheet("background: #ffffff;")
        ph_layout = QVBoxLayout(online_ph)
        ph_lbl = QLabel("在线材质库\n（敬请期待）")
        ph_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_lbl.setStyleSheet("color: #c0c4cc; font-size: 13px;")
        ph_layout.addWidget(ph_lbl)
        content_stack.addWidget(online_ph)      # index 1

        outer.addWidget(content_stack, stretch=1)

        # ── 导航状态 ──────────────────────────────────────────────
        _nav_stack: list[str] = []

        def _navigate_to(dir_path: str):
            _nav_stack.append(dir_path)
            _refresh()

        def _refresh():
            cur = _nav_stack[-1] if _nav_stack else material_root
            try:
                rel = os.path.relpath(cur, material_root)
                path_edit.setText("/" if rel == "." else "/" + rel.replace(os.sep, "/"))
            except ValueError:
                path_edit.setText(cur)
            btn_back.setEnabled(len(_nav_stack) > 1)
            grid_w = _build_grid(cur, _navigate_to)
            old_w = local_scroll.widget()
            local_scroll.setWidget(grid_w)
            if old_w:
                old_w.deleteLater()

        def _go_back():
            if len(_nav_stack) > 1:
                _nav_stack.pop()
                _refresh()

        btn_back.clicked.connect(_go_back)
        tab_group.idClicked.connect(content_stack.setCurrentIndex)

        os.makedirs(material_root, exist_ok=True)
        _navigate_to(material_root)

        return panel

    def _build_canvas(self) -> QWidget:
        """构建中央 2D 工作区。

        结构：
            Canvas2DWorkspace（QWidget，相对布局）
            ├── _GridGraphicsView          —— 网格画布（填满）
            ├── _CanvasFloatToolBar        —— 顶部悬浮工具栏（绝对定位）
            └── _CanvasBottomBar           —— 底部状态工具栏（绝对定位）
        """
        workspace = _Canvas2DWorkspace()
        return workspace

    # ---------------------------------------------------------------- 状态栏
    def _build_status_bar(self):
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

    # ---------------------------------------------------------------- 信号连接
    def _connect_signals(self):
        """连接组件间的信号。"""
        # 侧栏 Tab 切换 → 资源面板切换
        self.side_tab.tab_changed.connect(self.resource_stack.setCurrentIndex)
        self.side_tab.tab_changed.connect(
            lambda i: self.status_bar.set_hint(
                f"已切换到：{self.side_tab.TABS[i][0]}", 2000
            )
        )
        # 侧栏 Tab 切换 → 工作区 2D/3D 视图切换（画柜子 → 3D，其余 → 2D）
        self.side_tab.tab_changed.connect(self.canvas.set_sidebar_tab_index)
        self.side_tab.tab_changed.connect(self.canvas.switch_view_by_tab)

        # 订单 → 订单管理 / 新建订单（均打开订单管理对话框）
        self.menu_bar.action_order_manage.triggered.connect(self._open_order_manager_dialog)
        self.menu_bar.action_order_new.triggered.connect(self._open_order_manager_dialog)

        # 设置 → 用户基础设置
        self.menu_bar.action_user_basic_settings.triggered.connect(
            self._open_basic_config_dialog
        )
        # 设置 → 软件系统设置
        self.menu_bar.action_software_settings.triggered.connect(
            self._open_system_param_dialog
        )
        # 设置 → 快捷命令设置
        self.menu_bar.action_shortcut_settings.triggered.connect(
            self._open_shortcut_command_dialog
        )
        # 设置 → 异形图元设置
        self.menu_bar.action_irregular_element.triggered.connect(
            self._open_irregular_element_dialog
        )
        # 设置 → 系统工艺设置 → 孔位规则/五金设置
        self.menu_bar.action_hole_rule.triggered.connect(
            self._open_hole_rule_dialog
        )

        # 产品图 → 产品结构设计
        self.menu_bar.action_product_structure.triggered.connect(
            self._open_product_structure_dialog
        )

        # 算料 → 直接弹出物料解析页面
        self.menu_bar.action_split_bom.triggered.connect(self._open_bom_parse_dialog)

        # 退出
        self.menu_bar.action_exit.triggered.connect(self.close)

        # 画户型工具按钮（在 canvas 存在之后绑定）
        self._connect_draw_tools()

        # 画柜子竖排工具栏 → 新建柜子按钮（index=0）
        self._connect_cabinet_tools()

        # 同步侧栏索引到画布（启动时 tab_changed 可能未发射）
        self.canvas.set_sidebar_tab_index(self.side_tab.current_index())

    # ---------------------------------------------------------------- 画柜子工具栏绑定
    def _connect_cabinet_tools(self):
        """绑定画柜子竖排工具栏按钮信号。index=0 → 新建柜子。"""
        cab_bar   = getattr(self.canvas, "_cabinet_bar", None)
        if cab_bar is None:
            return
        btn_group = getattr(cab_bar, "_btn_group", None)
        if btn_group is None:
            return

        def _on_cabinet_btn(btn):
            idx = btn_group.id(btn)
            if idx == 0:
                self._open_new_cabinet_dialog()

        btn_group.buttonClicked.connect(_on_cabinet_btn)

    def _open_new_cabinet_dialog(self):
        """弹出新建柜子对话框，确认后进入柜体设计模式。"""
        try:
            from cabinet.cabinet_project import CabinetProject, CabinetBody
            from cabinet.cabinet_builder import CabinetBuilder
            _has_cabinet = True
        except ImportError:
            _has_cabinet = False

        dlg = NewCabinetDialog(parent=self)
        dlg.adjustSize()
        geo  = self.geometry()
        hint = dlg.sizeHint()
        dlg.move(
            geo.x() + (geo.width()  - hint.width())  // 2,
            geo.y() + (geo.height() - hint.height()) // 2,
        )
        if dlg.exec() != NewCabinetDialog.DialogCode.Accepted:
            return

        if _has_cabinet:
            project = CabinetProject(
                name           = dlg.product_name,
                cabinet_width  = dlg.cabinet_width,
                cabinet_height = dlg.cabinet_height,
                cabinet_depth  = dlg.cabinet_depth,
            )
            body = CabinetBody(
                name           = dlg.product_name,
                cabinet_width  = float(dlg.cabinet_width),
                cabinet_height = float(dlg.cabinet_height),
                cabinet_depth  = float(dlg.cabinet_depth),
            )
            CabinetBuilder.build_frame(body)
            project.add_body(body)
        else:
            from types import SimpleNamespace
            project = SimpleNamespace(
                name           = dlg.product_name,
                cabinet_width  = dlg.cabinet_width,
                cabinet_height = dlg.cabinet_height,
                cabinet_depth  = dlg.cabinet_depth,
            )
        self._enter_cabinet_mode(project)

    # ---------------------------------------------------------------- 画户型工具按钮绑定
    def _connect_draw_tools(self):
        """画户型面板图标工具：与直墙相同——点选激活、再点取消；同时只保留一个高亮。"""
        fp = self.resource_stack.widget(0)   # index 0 = 画户型面板
        btns = getattr(fp, "_fp_tool_buttons", None)
        if not btns:
            return

        gv = self.canvas._grid_view

        def _fp_tool_toggled(btn, checked: bool):
            tid = btn.property("fp_tool_id")
            if not isinstance(tid, str):
                tid = ""
            if checked:
                for ob in btns:
                    if ob is not btn:
                        ob.blockSignals(True)
                        ob.setChecked(False)
                        ob.blockSignals(False)
                self.canvas.switch_view("2d")
                if tid == "wall_straight":
                    gv.set_tool("wall_straight")
                elif tid == "wall_rect":
                    gv.on_rect_wall_clicked()
                    gv.set_tool("wall_rect")
                else:
                    gv.set_tool("none")
                gv.setFocus()
                return
            if tid == "wall_straight" and gv._tool == "wall_straight":
                gv.set_tool("none")
            elif tid == "wall_rect" and gv._tool == "wall_rect":
                gv.set_tool("none")

        for b in btns:
            b.toggled.connect(lambda c, btn=b: _fp_tool_toggled(btn, c))

    # ---------------------------------------------------------------- 对话框入口
    def _open_basic_config_dialog(self):
        """打开『用户基础设置』对话框。"""
        dialog = BasicConfigDialog(self)
        if self._basic_config:
            dialog.set_config(self._basic_config)

        if dialog.exec() == BasicConfigDialog.DialogCode.Accepted:
            self._basic_config = dialog.get_config()
            self.status_bar.set_hint("已保存基础配置", 2000)

    def _open_system_param_dialog(self):
        """打开『软件系统设置』对话框。"""
        dialog = SystemParamDialog(self)
        if self._system_param:
            dialog.set_config(self._system_param)

        if dialog.exec() == SystemParamDialog.DialogCode.Accepted:
            self._system_param = dialog.get_config()
            self.status_bar.set_hint("已保存系统参数", 2000)

    def _open_shortcut_command_dialog(self):
        """打开『快捷命令设置』对话框。"""
        dialog = ShortcutCommandDialog(self)
        if self._shortcut_command:
            dialog.set_config(self._shortcut_command)

        if dialog.exec() == ShortcutCommandDialog.DialogCode.Accepted:
            self._shortcut_command = dialog.get_config()
            self.status_bar.set_hint("已保存快捷命令", 2000)

    def _open_irregular_element_dialog(self):
        """打开『异形图元设置』对话框（图元参数化编辑器）。"""
        dialog = IrregularElementDialog(self)
        dialog.exec()
        self.status_bar.set_hint("图元参数化编辑器已关闭", 2000)

    def _open_order_manager_dialog(self):
        """打开『订单文件管理』对话框。"""
        if self._order_dialog is None:
            self._order_dialog = OrderManagerDialog(self)
            # 业务信号 → 状态栏提示（后续由 controller 接管真实业务）
            self._order_dialog.search_requested.connect(
                lambda f: self.status_bar.set_hint(
                    f"查找订单：关键字='{f.get('keyword','')}' 状态={f.get('status','')}", 3000
                )
            )
            self._order_dialog.open_requested.connect(
                lambda ids: self.status_bar.set_hint(f"打开订单：{', '.join(ids)}", 3000)
            )
            self._order_dialog.submit_requested.connect(
                lambda ids: self.status_bar.set_hint(f"提交订单：{', '.join(ids)}", 3000)
            )
            self._order_dialog.delete_requested.connect(
                lambda ids: self.status_bar.set_hint(f"删除订单：{', '.join(ids)}", 3000)
            )
        self._order_dialog.show()
        self._order_dialog.raise_()
        self._order_dialog.activateWindow()

    def _open_product_structure_dialog(self):
        """打开『产品结构设计器』（单例，重复点击直接激活已有窗口）。"""
        if not hasattr(self, '_product_structure_dlg') \
                or self._product_structure_dlg is None:
            self._product_structure_dlg = ProductStructureDialog(self)
        self._product_structure_dlg.show()
        self._product_structure_dlg.raise_()
        self._product_structure_dlg.activateWindow()

    def _open_hole_rule_dialog(self):
        """打开『孔位规则/五金设置』对话框。"""
        dialog = HoleRuleDialog(icon_dir=self._icon_dir, parent=self)
        if self._hole_rule_config:
            dialog.set_config(self._hole_rule_config)

        # 保存按钮按下 → 暂存到内存，状态栏提示
        dialog.property_saved.connect(
            lambda name, props: self.status_bar.set_hint(f"已保存：{name}", 2000)
        )

        dialog.exec()
        # 关闭时把对话框内的最新数据回收到内存
        self._hole_rule_config = dialog.get_config()


    def _open_bom_parse_dialog(self):
        """打开『订单物料解析』对话框。"""
        from calculator.cabinet_calculator import BomParseDialog

        project    = getattr(self, "_current_project", None)
        order_data = None

        if project is not None:
            try:
                from calculator.cabinet_calculator import CabinetCalculator
                calc       = CabinetCalculator(project)
                bom        = calc.calculate()
                order_data = bom.to_order_data(
                    order_id=getattr(project, "order_id", ""),
                )
            except Exception:
                order_data = None

        dlg = BomParseDialog(order_data=order_data, parent=self)
        dlg.sig_save.connect(lambda: self.status_bar.set_hint("物料已保存", 2000))
        dlg.exec()


# ============================================================ 内部工具类

class _GridGraphicsView(QGraphicsView):
    """带两级参考网格的 2D 画布视图。

    - 白色背景
    - 小格 20px（浅灰 #dde1e6），大格每5小格（稍深 #c2c7d0）
    - 原点轴线（#a8b0be）
    - 滚轮缩放，空格/中键拖拽
    - 缩放时网格密度自适应
    """

    MINOR_SIZE   = 20
    MAJOR_FACTOR = 5
    MAJOR_SIZE   = MINOR_SIZE * MAJOR_FACTOR   # 100

    BG_COLOR     = QColor("#ffffff")
    MINOR_COLOR  = QColor("#dde1e6")
    MAJOR_COLOR  = QColor("#c2c7d0")
    AXIS_COLOR   = QColor("#a8b0be")
    LABEL_COLOR  = QColor("#9099aa")

    ZOOM_MIN     = 0.012
    ZOOM_MAX     = 1500.0
    ZOOM_STEP    = 1.15

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setBackgroundBrush(QBrush(self.BG_COLOR))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)
        self._zoom   = 1.0
        self._space  = False
        self._label_font = QFont("Consolas")
        safe_set_font_size(self._label_font, 8)

    # ── 背景绘制 ──────────────────────────────────────────────────
    def drawBackground(self, painter: QPainter, rect):
        # 强制白底
        painter.fillRect(rect, self.BG_COLOR)

        scale  = self.transform().m11()
        minor, major = self._adaptive(scale)

        l = int(rect.left())   - (int(rect.left())   % minor) - minor
        t = int(rect.top())    - (int(rect.top())    % minor) - minor
        r = int(rect.right())  + minor
        b = int(rect.bottom()) + minor

        # 小格线
        pen = QPen(self.MINOR_COLOR)
        pen.setCosmetic(True)
        painter.setPen(pen)
        x = l
        while x <= r:
            if x % major != 0:
                painter.drawLine(x, t, x, b)
            x += minor
        y = t
        while y <= b:
            if y % major != 0:
                painter.drawLine(l, y, r, y)
            y += minor

        # 大格线
        pen.setColor(self.MAJOR_COLOR)
        painter.setPen(pen)
        x = l - (l % major)
        while x <= r:
            painter.drawLine(x, t, x, b)
            x += major
        y = t - (t % major)
        while y <= b:
            painter.drawLine(l, y, r, y)
            y += major

        # 原点轴线
        pen.setColor(self.AXIS_COLOR)
        painter.setPen(pen)
        painter.drawLine(0, t, 0, b)
        painter.drawLine(l, 0, r, 0)

        # 刻度标注
        painter.setFont(self._label_font)
        pen.setColor(self.LABEL_COLOR)
        painter.setPen(pen)
        step = major * 5
        ox = int(rect.left()) - (int(rect.left()) % step)
        while ox <= rect.right():
            if ox != 0:
                painter.drawText(QPointF(ox + 3, -3), str(ox))
            ox += step
        oy = int(rect.top()) - (int(rect.top()) % step)
        while oy <= rect.bottom():
            if oy != 0:
                painter.drawText(QPointF(3, oy - 3), str(oy))
            oy += step

    def _adaptive(self, scale: float):
        minor, major = self.MINOR_SIZE, self.MAJOR_SIZE
        while minor * scale < 12 and minor < 100000:
            minor *= self.MAJOR_FACTOR
            major *= self.MAJOR_FACTOR
        while minor * scale > 40 and minor > self.MINOR_SIZE:
            minor //= self.MAJOR_FACTOR
            major //= self.MAJOR_FACTOR
        return int(minor), int(major)

    # ── 滚轮缩放 ─────────────────────────────────────────────────
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        f = self.ZOOM_STEP if delta > 0 else 1.0 / self.ZOOM_STEP
        new_zoom = self._zoom * f
        if self.ZOOM_MIN <= new_zoom <= self.ZOOM_MAX:
            self.scale(f, f)
            self._zoom = new_zoom

    # ── 键盘拖拽 ─────────────────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space = False
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            super().keyReleaseEvent(event)

    # ── 中键拖拽 ─────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            from PySide6.QtGui import QMouseEvent
            fake = QMouseEvent(
                event.type(), event.position(), event.globalPosition(),
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                event.modifiers()
            )
            super().mousePressEvent(fake)
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            if not self._space:
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            super().mouseReleaseEvent(event)


# ──────────────────────────────────────────────────────────────
class _CanvasFloatToolBar(QWidget):
    """悬浮在画布顶部中央的三按钮工具栏。

    参考图：✏️绘图模式  |  3D 视图  |  ❓帮助
    使用绝对定位，由 _Canvas2DWorkspace.resizeEvent 居中。

    Signals:
        view_mode_changed(str)  —— "2d" 或 "3d"
    """

    view_mode_changed = _Signal(str)   # "2d" | "3d"

    _BTN_STYLE = """
        QPushButton {{
            background: #ffffff;
            border: 1px solid #c8cdd6;
            border-radius: 0;
            color: #303133;
            font-size: 13px;
            padding: 0 14px;
            min-width: 44px;
            height: 32px;
        }}
        QPushButton:hover {{
            background: #ecf5ff;
            border-color: #409eff;
            color: #409eff;
        }}
        QPushButton:checked {{
            background: #ecf5ff;
            border-color: #409eff;
            color: #409eff;
            font-weight: bold;
        }}
        QPushButton:first-child {{
            border-top-left-radius: 4px;
            border-bottom-left-radius: 4px;
        }}
        QPushButton:last-child {{
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
        }}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.Widget)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        buttons = [
            ("✏", "绘图模式（2D）", True),
            ("3D",  "切换到 3D 视图",  False),
            ("?",   "帮助 / 操作指引", False),
        ]
        for idx, (label, tip, checked) in enumerate(buttons):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(checked)
            btn.setToolTip(tip)
            btn.setStyleSheet(self._BTN_STYLE)
            # 首尾按钮单独加圆角（stylesheet :first-child/:last-child 在自定义 layout 中不可靠）
            if idx == 0:
                btn.setStyleSheet(self._BTN_STYLE + """
                    QPushButton { border-top-left-radius: 4px; border-bottom-left-radius: 4px; }
                """)
            elif idx == len(buttons) - 1:
                btn.setStyleSheet(self._BTN_STYLE + """
                    QPushButton { border-top-right-radius: 4px; border-bottom-right-radius: 4px;
                                  border-left: none; }
                """)
            else:
                btn.setStyleSheet(self._BTN_STYLE + "QPushButton { border-left: none; }")
            self._group.addButton(btn, idx)
            layout.addWidget(btn)

        self.adjustSize()

        # 按钮切换 → 发出视图模式信号
        self._group.idClicked.connect(self._on_btn_clicked)

        # 投影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    # ---------------------------------------------------------------- 对外接口
    def _on_btn_clicked(self, idx: int):
        self.view_mode_changed.emit("3d" if idx == 1 else "2d")

    def set_mode(self, mode: str):
        """外部切换模式（"2d"/"3d"），同步按钮选中状态。"""
        self._group.blockSignals(True)
        try:
            target_id = 1 if mode == "3d" else 0
            btn = self._group.button(target_id)
            if btn:
                btn.setChecked(True)
        finally:
            self._group.blockSignals(False)


# ──────────────────────────────────────────────────────────────
class _CanvasBottomBar(QWidget):
    """悬浮在画布底部的状态/工具栏。

    参考图：
        [箭头] [矩形] [多边形] [文字]  快捷命令: [________]   [未命名▼]
    使用绝对定位，紧贴画布底边。
    """

    _BAR_H  = 34
    _BTN_W  = 32

    _BAR_STYLE = """
        QWidget#canvasBottomBar {
            background: #f0f2f5;
            border-top: 1px solid #c8cdd6;
        }
    """
    _TOOL_BTN = """
        QPushButton {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 3px;
            color: #303133;
            font-size: 14px;
            padding: 0;
        }
        QPushButton:hover  { background: #dde1e8; border-color: #bcc2cb; }
        QPushButton:checked { background: #d0e8ff; border-color: #409eff; color: #409eff; }
    """
    _INPUT_STYLE = """
        QLineEdit {
            background: #ffffff;
            border: 1px solid #c8cdd6;
            border-radius: 3px;
            font-size: 12px;
            padding: 0 6px;
            color: #303133;
        }
        QLineEdit:focus { border-color: #409eff; }
    """
    _NAME_BTN = """
        QPushButton {
            background: #4dc9e4;
            border: none;
            border-radius: 3px;
            color: #ffffff;
            font-size: 12px;
            padding: 0 10px;
            font-weight: bold;
        }
        QPushButton:hover { background: #36b8d4; }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("canvasBottomBar")
        self.setFixedHeight(self._BAR_H)
        self.setStyleSheet(self._BAR_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        # ── 工具按钮组 ──────────────────────────────
        group = QButtonGroup(self)
        group.setExclusive(True)

        # 图标与截图对应：斜向箭头选择 / 矩形 / 菱形多边形 / T文字
        tool_defs = [
            ("⬋", "选择 / 移动",   False),   # ↖ 箭头
            ("□",  "绘制矩形",      False),   # □ 矩形
            ("◇",  "绘制多边形",    False),   # ◇ 多边形
            ("T",  "插入文字",      True),    # T  文字（截图中高亮选中）
        ]
        for idx, (icon, tip, checked) in enumerate(tool_defs):
            btn = QPushButton(icon)
            btn.setCheckable(True)
            btn.setChecked(checked)
            btn.setFixedSize(self._BTN_W, 26)
            btn.setToolTip(tip)
            btn.setStyleSheet(self._TOOL_BTN)
            group.addButton(btn, idx)
            layout.addWidget(btn)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #c8cdd6;")
        layout.addWidget(sep)

        # ── 快捷命令输入 ─────────────────────────────
        lbl = QLabel("快捷命令:")
        lbl.setStyleSheet("font-size: 12px; color: #606266;")
        layout.addWidget(lbl)

        self.cmd_input = QLineEdit()
        self.cmd_input.setFixedSize(160, 26)
        self.cmd_input.setPlaceholderText("")
        self.cmd_input.setStyleSheet(self._INPUT_STYLE)
        layout.addWidget(self.cmd_input)

        layout.addStretch(1)

        # ── 项目名按钮 ───────────────────────────────
        self.project_btn = QPushButton("未命名")
        self.project_btn.setFixedSize(72, 26)
        self.project_btn.setStyleSheet(self._NAME_BTN)
        self.project_btn.setToolTip("点击重命名当前项目")
        layout.addWidget(self.project_btn)


# ──────────────────────────────────────────────────────────────
class _Canvas3DPlaceholder(QWidget):
    """3D 视图占位页面。

    后续由真实 3D 渲染引擎（OpenGL / VTK 等）替换。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1a2332;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("⬡")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            "font-size: 72px; color: #4dc9e4; background: transparent;"
        )
        layout.addWidget(icon_lbl)

        tip_lbl = QLabel("3D 视图")
        tip_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip_lbl.setStyleSheet(
            "font-size: 20px; color: #a0aec0; background: transparent; margin-top: 12px;"
        )
        layout.addWidget(tip_lbl)

        sub_lbl = QLabel("（3D 渲染引擎接入后显示实际内容）")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setStyleSheet(
            "font-size: 12px; color: #4a5568; background: transparent; margin-top: 6px;"
        )
        layout.addWidget(sub_lbl)


# ──────────────────────────────────────────────────────────────
class _Canvas2DWorkspace(QWidget):
    """主工作区容器，内含 2D 网格画布和 3D 画柜子视图，通过 QStackedWidget 切换。

    布局（绝对定位）：
        ├── _view_stack          —— QStackedWidget（index 0=2D 画布，index 1=View3D，铺满）
        ├── _float_bar           —— 顶部悬浮工具栏（居中）
        └── _bottom_bar          —— 底部工具状态栏（全宽贴底）

    对外接口：
        switch_view(mode)        —— "2d" | "3d"
    """

    _FLOAT_TOP = 12

    # 与 SideTabBar.TABS 对应：index=1 为"画柜子"，2=材质，3=模型，4=场景树 → 3D
    _3D_TAB_INDICES = {1, 2, 3, 4}
    # 只有"画柜子"Tab 才显示左侧竖排工具栏
    _CABINET_BAR_TAB = 1

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── 视图堆栈 ──────────────────────────────────
        self._view_stack = QStackedWidget(self)

        # 页面 0：2D 网格画布（必须用 self 持有 scene，否则 __init__ 结束后局部变量被回收，
        # PySide 可能释放场景，view.scene() 变为 None，网格与墙体都不会显示。）
        self._floor_plan_scene = FloorPlanScene()
        self._room = Room("默认房间")
        self._floor_plan_scene.setProperty("room", self._room)
        self._grid_view = View2D(self._floor_plan_scene, self._view_stack)
        self._view_stack.addWidget(self._grid_view)       # index 0

        # 页面 1：3D 画柜子视图（View3D，OpenGL / 软渲染自适应）
        self._3d_view = View3D(self._view_stack)
        self._view_stack.addWidget(self._3d_view)         # index 1

        self._view_stack.setCurrentIndex(0)

        # 当前侧栏 Tab（0=画户型）；画户型下禁止悬浮条切到 3D，避免误看 3D 导致无网格/直墙无效
        self._sidebar_tab_index = 0

        # ── 顶部悬浮工具栏 ───────────────────────────
        self._float_bar = _CanvasFloatToolBar(self)
        self._float_bar.adjustSize()
        self._float_bar.raise_()

        # 悬浮栏按钮 → 视图切换（经守卫：画户型 Tab 下忽略 3D）
        self._float_bar.view_mode_changed.connect(self._on_float_view_mode)

        # ── 底部工具状态栏 ───────────────────────────
        self._bottom_bar = _CanvasBottomBar(self)
        self._bottom_bar.raise_()

        # ── 画柜子竖排工具栏（仅 3D 模式可见）────────
        self._cabinet_bar = _Cabinet3DToolBar(self)
        self._cabinet_bar.raise_()
        self._cabinet_bar.setVisible(False)   # 默认隐藏，画户型模式


    def set_sidebar_tab_index(self, tab_index: int):
        """由主窗口侧栏 Tab 更新；用于画户型下拦截悬浮条切 3D。"""
        self._sidebar_tab_index = int(tab_index)
        # 切回画户型时若误留在 3D 页，强制回到 2D
        if self._sidebar_tab_index == 0 and self._view_stack.currentIndex() != 0:
            self.switch_view("2d")

    def _on_float_view_mode(self, mode: str):
        """画户型（侧栏 index 0）下不允许通过悬浮条进入 3D。"""
        if self._sidebar_tab_index == 0 and mode == "3d":
            self._float_bar.set_mode("2d")
            return
        self.switch_view(mode)

    # ---------------------------------------------------------------- 公开接口
    def switch_view(self, mode: str):
        """切换 2D / 3D 视图，并同步顶部按钮状态。

        注意：画柜子工具栏的显隐由 switch_view_by_tab 单独控制。

        Args:
            mode: "2d" 或 "3d"
        """
        is_3d = (mode == "3d")
        idx = 1 if is_3d else 0
        self._view_stack.setCurrentIndex(idx)
        self._float_bar.set_mode(mode)
        if is_3d:
            # 同步 2D 户型数据：墙体在 3D 中沿 Y 挤出 DEFAULT_EXTRUDE_HEIGHT（见 View3D）
            self._3d_view.set_room(self._room)
            self._cabinet_bar.raise_()

    def refresh_3d_room_display(self) -> None:
        """2D 已修改 Room（如删除墙体）后刷新 3D 挤出线框。"""
        self._3d_view.set_room(self._room)

    def switch_view_by_tab(self, tab_index: int):
        """根据侧栏 Tab 索引切换 2D/3D 视图，并控制画柜子工具栏显隐。

        3D Tab：画柜子(1)、材质(2)、模型(3)、场景树(4)
        画柜子竖排工具栏：仅 index=1（画柜子）时显示。
        """
        is_3d = tab_index in self._3D_TAB_INDICES
        self.switch_view("3d" if is_3d else "2d")
        show_cabinet_bar = (tab_index == self._CABINET_BAR_TAB)
        self._cabinet_bar.setVisible(show_cabinet_bar)
        if show_cabinet_bar:
            self._cabinet_bar.raise_()

    def clear_cabinet_param_space(self) -> None:
        """退出柜体设计：取消主 3D 视图中的逻辑空间盒。"""
        self._3d_view.set_cabinet_space(None)

    def refresh_cabinet_view(self) -> None:
        """柜体命令执行后刷新主 3D 视图（委托 View3D.refresh，供 CommandDispatcher 上下文使用）。"""
        self._3d_view.refresh()

    # ---------------------------------------------------------------- 布局
    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()

        # 视图堆栈铺满
        self._view_stack.setGeometry(0, 0, w, h)

        # 悬浮工具栏：水平居中，距顶 _FLOAT_TOP px
        fb_w = self._float_bar.sizeHint().width()
        fb_h = self._float_bar.sizeHint().height()
        self._float_bar.setGeometry(
            (w - fb_w) // 2, self._FLOAT_TOP, fb_w, fb_h
        )

        # 底部工具栏：紧贴底边，全宽
        bb_h = self._bottom_bar.height()
        self._bottom_bar.setGeometry(0, h - bb_h, w, bb_h)

        # 画柜子工具栏：左侧居中垂直，距左 12px，距顶 _FLOAT_TOP+46px
        cb_w = self._cabinet_bar.sizeHint().width()
        cb_h = self._cabinet_bar.sizeHint().height()
        top_offset = self._FLOAT_TOP + 46
        self._cabinet_bar.setGeometry(12, top_offset, cb_w, cb_h)



# ──────────────────────────────────────────────────────────────
class _Cabinet3DToolBar(QWidget):
    """3D 画柜子模式专属竖排工具栏。

    仅在"画柜子"Tab（3D 视图）激活时显示，其他 Tab 隐藏。

    按钮（从上到下，对照参考图）：
        开始        —— 顶部标题区（蓝色背景，不可点击）
        新建柜子    —— cabinet.png
        设计推门    —— sliding_door.png
        客户信息    —— customer.png
        订单材料    —— order_material.png
        附件配件    —— fittings.png
        完整显示    —— full_display.png
    """

    _BAR_W   = 64          # 工具栏宽度
    _BTN_H   = 56          # 每个按钮高度（图标+文字）
    _ICON_SZ = 28          # 图标尺寸

    _BAR_STYLE = """
        QWidget#cabinet3DBar {
            background: #ffffff;
            border: 1px solid #d0d5dd;
            border-radius: 6px;
        }
    """
    _HEADER_STYLE = """
        QLabel {
            background: #4a90d9;
            border-radius: 5px 5px 0 0;
            color: #ffffff;
            font-size: 12px;
            font-weight: bold;
            padding: 4px 0;
        }
    """
    _BTN_STYLE = """
        QPushButton {
            background: transparent;
            border: none;
            border-radius: 4px;
            color: #303133;
            font-size: 11px;
            padding: 2px 0 4px 0;
        }
        QPushButton:hover {
            background: #e8f4ff;
            color: #1a6fc4;
        }
        QPushButton:checked {
            background: #d0e8ff;
            color: #1a6fc4;
            font-weight: bold;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cabinet3DBar")
        self.setFixedWidth(self._BAR_W)
        self.setStyleSheet(self._BAR_STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # 阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setOffset(2, 2)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(0)

        # ── 顶部标题 ──────────────────────────────────
        header = QLabel("开始")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFixedHeight(28)
        header.setStyleSheet(self._HEADER_STYLE)
        layout.addWidget(header)

        # ── 工具按钮定义 ──────────────────────────────
        # (icon文件名不含路径, 显示文字, tooltip)
        btn_defs = [
            ("cabinet.png",        "新建柜子", "新建柜子"),
            ("sliding_door.png",   "设计推门", "设计推门"),
            ("customer.png",       "客户信息", "客户信息"),
            ("order_material.png", "订单材料", "订单材料"),
            ("fittings.png",       "附件配件", "附件配件"),
            ("full_display.png",   "完整显示", "完整显示"),
        ]

        # 解析 icon 目录（与主窗口同一 _resolve_icon_dir 逻辑）
        import sys, os
        base = getattr(sys, "_MEIPASS", None)
        if base:
            icon_dir = os.path.join(base, "icons")
        else:
            here = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(here, "..", ".."))
            icon_dir = os.path.join(project_root, "icons")
            if not os.path.isdir(icon_dir):
                icon_dir = os.path.abspath("icons")

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        for idx, (icon_file, label, tip) in enumerate(btn_defs):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setFixedSize(self._BAR_W - 2, self._BTN_H)
            btn.setStyleSheet(self._BTN_STYLE)

            # 图标
            icon_path = os.path.join(icon_dir, icon_file)
            if os.path.isfile(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(self._ICON_SZ, self._ICON_SZ))

            # 文字在图标下方：用换行实现（图标+文字竖排布局）
            btn.setText(label)
            btn.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            # 强制图标在上、文字在下
            from PySide6.QtCore import QSize as _QSize
            btn.setStyleSheet(
                self._BTN_STYLE +
                "QPushButton { text-align: center; }"
            )
            # 使用 QToolButton 风格：图标在上文字在下
            # QPushButton 本身不支持，改用 setFixedHeight + 自绘，
            # 这里用简单方案：将图标放入 QLabel，文字单独 QLabel，外套 QWidget
            btn.setParent(None)   # 释放刚创建的 btn，改用复合 widget

            cell = QWidget()
            cell.setFixedSize(self._BAR_W - 2, self._BTN_H)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 4, 0, 2)
            cell_layout.setSpacing(1)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

            icon_lbl = QLabel()
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setFixedSize(self._ICON_SZ + 4, self._ICON_SZ + 4)
            if os.path.isfile(icon_path):
                pix = QPixmap(icon_path).scaled(
                    self._ICON_SZ, self._ICON_SZ,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                icon_lbl.setPixmap(pix)
            else:
                icon_lbl.setText("□")
                icon_lbl.setStyleSheet("font-size:18px; color:#606266;")

            text_lbl = QLabel(label)
            text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text_lbl.setStyleSheet("font-size:11px; color:#303133;")

            cell_layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignHCenter)
            cell_layout.addWidget(text_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

            # 整个 cell 做成可点击：用 QPushButton 包裹（透明覆盖）
            overlay = QPushButton(cell)
            overlay.setCheckable(True)
            overlay.setFlat(True)
            overlay.setFixedSize(self._BAR_W - 2, self._BTN_H)
            overlay.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover  { background: rgba(26,111,196,0.10); }
                QPushButton:checked { background: rgba(26,111,196,0.18); }
            """)
            overlay.setToolTip(tip)
            overlay.move(0, 0)
            overlay.raise_()
            self._btn_group.addButton(overlay, idx)

            layout.addWidget(cell)

        layout.addStretch(1)

# ══════════════════════════════════════════════════════════════════════════════