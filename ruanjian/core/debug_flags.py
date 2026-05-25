# -*- coding: utf-8 -*-
"""运行时调试开关（无 Qt，供 ``core`` / ``commands`` / ``ui`` 共用）。

为 ``True`` 时打印 View3D / Core / Command 管线中的高频诊断 ``print``。

以下在 ``False`` 时仍会输出（核心生命周期与错误，便于正常排障）：

- ``[SOLVER] solve cabinet`` 等求解器核心行
- ``[View3D] rebuild panels = …``（仅全量重建路径；加板为 ``add panel visual``）
- 命令 ``FAILED``、handler 异常与 ``traceback``（见各 handler）
"""

DEBUG_VIEW3D = False

__all__ = ["DEBUG_VIEW3D"]
