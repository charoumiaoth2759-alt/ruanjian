# -*- coding: utf-8 -*-
"""空间与板件尺寸边界常量（单位 mm）。"""

# 空间整体合法范围
MIN_SPACE_WIDTH: float = 1.0
MIN_SPACE_HEIGHT: float = 1.0
MIN_SPACE_DEPTH: float = 1.0
MAX_SPACE_WIDTH: float = 200_000.0
MAX_SPACE_HEIGHT: float = 200_000.0
MAX_SPACE_DEPTH: float = 200_000.0

# 树深度
MAX_TREE_DEPTH: int = 256

# 板件外观最小尺寸（用于 calculator 合法性提示）
MIN_PANEL_WIDTH: float = 1.0
MIN_PANEL_HEIGHT: float = 1.0

# 叶节点「可用性」宽松阈值（validators.check_leaf_usability）
MIN_USABLE_WIDTH: float = 1.0
MIN_USABLE_HEIGHT: float = 1.0
MIN_USABLE_DEPTH: float = 1.0
