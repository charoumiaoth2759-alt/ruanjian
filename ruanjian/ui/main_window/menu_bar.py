# -*- coding: utf-8 -*-
"""菜单栏模块

封装主窗口顶部菜单栏。所有 QAction 都作为属性挂在 MenuBar 上，
便于外部（主窗口、工具栏、快捷键）连接信号或复用。
"""
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenuBar


class MenuBar(QMenuBar):
    """主窗口菜单栏。

    设计原则：
    - 菜单栏只负责"提供动作"，不实现业务逻辑。
    - 所有 QAction 作为属性暴露，由主窗口或 controller 连接 triggered 信号。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._create_actions()
        self._build_menus()

    # ---------------------------------------------------------------- 动作创建
    def _create_actions(self):
        """集中创建所有 QAction，便于统一管理快捷键与图标。"""
        # 文件
        self.action_new = QAction("新建(&N)", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_exit = QAction("退出(&X)", self)
        self.action_exit.setShortcut("Ctrl+Q")

        # 打开 / 保存（独立顶级项，模拟参考图）
        self.action_open = QAction("打开(&O)", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_save = QAction("保存(&S)", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save_as = QAction("另存为...", self)
        self.action_save_as.setShortcut("Ctrl+Shift+S")

        # 订单
        self.action_order_manage = QAction("订单管理", self)
        self.action_order_new = QAction("新建订单", self)

        # ---------------- 设置 ----------------
        self.action_user_basic_settings  = QAction("用户基础设置", self)
        self.action_software_settings    = QAction("软件系统设置", self)
        self.action_shortcut_settings    = QAction("快捷命令设置", self)
        self.action_product_material     = QAction("产品系列材料", self)
        # 系统工艺设置（带子菜单）
        self.action_craft_general        = QAction("常规工艺", self)
        self.action_craft_board          = QAction("板件工艺", self)
        self.action_craft_door           = QAction("门板工艺", self)
        self.action_craft_hardware       = QAction("五金工艺", self)
        # 系统工艺设置 → 孔位规则/五金设置（新增）
        self.action_hole_rule            = QAction("孔位规则/五金设置", self)
        self.action_product_structure    = QAction("产品结构设置", self)
        self.action_irregular_element    = QAction("异形图元设置", self)
        self.action_clear_authorization  = QAction("批量清除授权", self)
        self.action_space_database       = QAction("智柜空间数据库", self)
        self.action_web_account_apply    = QAction("网页账号申请", self)
        self.action_password_modify      = QAction("登录密码修改", self)
        self.action_super_user_tool      = QAction("超级用户工具", self)
        self.action_about_zhigui_space   = QAction("关于智柜空间", self)
        self.action_check_update         = QAction("检查最新版本", self)

        # 渲染
        self.action_render_realtime = QAction("实时渲染", self)
        self.action_render_high = QAction("高质量渲染", self)

        # 结算
        self.action_quote = QAction("报价单", self)
        self.action_settle = QAction("订单结算", self)

        # 算料（直接打开物料解析页面，无子菜单）
        self.action_split_bom = QAction("算料", self)
        self.action_split_bom.setShortcut("F9")

        # 优化（排版/套料）
        self.action_nesting = QAction("板材优化排版", self)
        self.action_nesting.setShortcut("F10")

        # 产品图
        self.action_product_drawing = QAction("生成产品图", self)
        self.action_export_drawing = QAction("导出加工图", self)

        # 门操作
        self.action_door_add = QAction("添加门板", self)
        self.action_door_split = QAction("门板分割", self)
        self.action_door_style = QAction("门型款式...", self)

        # 测量
        self.action_measure_distance = QAction("测距", self)
        self.action_measure_area = QAction("测面积", self)

        # 标记
        self.action_mark_add = QAction("添加标注", self)
        self.action_mark_clear = QAction("清除标注", self)

        # 工具
        self.action_undo = QAction("撤销", self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_redo = QAction("重做", self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.action_calculator = QAction("计算器", self)
        self.action_about = QAction("关于智柜...", self)

    # ---------------------------------------------------------------- 菜单组装
    def _build_menus(self):
        """按参考图顺序组装顶级菜单。"""
        # 文件菜单
        menu_file = self.addMenu("文件(&F)")
        menu_file.addAction(self.action_new)
        menu_file.addSeparator()
        menu_file.addAction(self.action_exit)

        # 打开 / 保存（顶级项形式，与参考图一致）
        menu_open = self.addMenu("打开(&O)")
        menu_open.addAction(self.action_open)

        menu_save = self.addMenu("保存(&S)")
        menu_save.addAction(self.action_save)
        menu_save.addAction(self.action_save_as)

        # 订单
        menu_order = self.addMenu("订单")
        menu_order.addAction(self.action_order_new)
        menu_order.addAction(self.action_order_manage)

        # 设置（严格按截图顺序）
        menu_settings = self.addMenu("设置")
        menu_settings.addAction(self.action_user_basic_settings)
        menu_settings.addAction(self.action_software_settings)
        menu_settings.addAction(self.action_shortcut_settings)
        menu_settings.addAction(self.action_product_material)

        # 系统工艺设置 —— 子菜单
        self.menu_craft_settings = menu_settings.addMenu("系统工艺设置")
        self.menu_craft_settings.addAction(self.action_craft_general)
        self.menu_craft_settings.addAction(self.action_craft_board)
        self.menu_craft_settings.addAction(self.action_craft_door)
        self.menu_craft_settings.addAction(self.action_craft_hardware)
        self.menu_craft_settings.addSeparator()
        self.menu_craft_settings.addAction(self.action_hole_rule)

        menu_settings.addAction(self.action_product_structure)
        menu_settings.addAction(self.action_irregular_element)
        menu_settings.addAction(self.action_clear_authorization)
        menu_settings.addAction(self.action_space_database)
        menu_settings.addAction(self.action_web_account_apply)
        menu_settings.addAction(self.action_password_modify)
        menu_settings.addAction(self.action_super_user_tool)
        menu_settings.addAction(self.action_about_zhigui_space)
        menu_settings.addAction(self.action_check_update)

        # 渲染
        menu_render = self.addMenu("渲染")
        menu_render.addAction(self.action_render_realtime)
        menu_render.addAction(self.action_render_high)

        # 结算
        menu_settle = self.addMenu("结算")
        menu_settle.addAction(self.action_quote)
        menu_settle.addAction(self.action_settle)

        # 算料（直接触发，无子菜单）
        self.addAction(self.action_split_bom)

        # 优化
        menu_nesting = self.addMenu("优化")
        menu_nesting.addAction(self.action_nesting)

        # 产品图
        menu_drawing = self.addMenu("产品图")
        menu_drawing.addAction(self.action_product_drawing)
        menu_drawing.addAction(self.action_export_drawing)

        # 门操作
        menu_door = self.addMenu("门操作")
        menu_door.addAction(self.action_door_add)
        menu_door.addAction(self.action_door_split)
        menu_door.addSeparator()
        menu_door.addAction(self.action_door_style)

        # 测量
        menu_measure = self.addMenu("测量")
        menu_measure.addAction(self.action_measure_distance)
        menu_measure.addAction(self.action_measure_area)

        # 标记
        menu_mark = self.addMenu("标记")
        menu_mark.addAction(self.action_mark_add)
        menu_mark.addAction(self.action_mark_clear)

        # 工具
        menu_tools = self.addMenu("工具")
        menu_tools.addAction(self.action_undo)
        menu_tools.addAction(self.action_redo)
        menu_tools.addSeparator()
        menu_tools.addAction(self.action_calculator)
        menu_tools.addSeparator()
        menu_tools.addAction(self.action_about)