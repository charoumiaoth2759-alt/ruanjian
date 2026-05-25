# -*- coding: utf-8 -*-
"""柜体参数化空间 —— 3D 可视化（与 `core.space.space_models.Space` 解耦）。

UI → Space（逻辑数据）→ SpaceVisual → GLView（pyqtgraph.opengl）

根 ``Space`` 的创建请走 ``commands`` / ``CommandDispatcher``（如 ``SET_ROOT_SPACE``），
勿在 UI 中直接 ``make_root_cabinet_space`` 写 ``project``；此处仍再导出工厂函数供脚本或测试使用。
"""

from core.space.root_factory import make_root_cabinet_space

from .param_space_gl_view import ParamSpaceGLView
from .panel_visual import build_panel_mesh, rebuild_panels
from .scene_manager import SceneManager
from .tool_modes import ToolMode

__all__ = [
    "SceneManager",
    "ParamSpaceGLView",
    "ToolMode",
    "make_root_cabinet_space",
    "build_panel_mesh",
    "rebuild_panels",
]
