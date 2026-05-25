from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass


# ==========================================================
# 1. 空间结构状态（Space Structure State）
# ==========================================================

class SpaceStructureState(Enum):
    """
    描述空间在 Tree 结构中的状态
    """
    FREE = auto()       # 未使用，可放置
    SPLIT = auto()      # 已被切分（有 children）
    OCCUPIED = auto()   # 被板件占用
    INVALID = auto()     # 无效空间（被压缩/超界）


# ==========================================================
# 2. 放置状态（Placement Decision State）
# ==========================================================

class PlacementState(Enum):
    """
    描述“能不能放板件”的决策结果
    """
    ALLOWED = auto()    # 可以放（唯一正确状态）
    BLOCKED = auto()    # 不允许放
    UNKNOWN = auto()    # 未计算


# ==========================================================
# 3. UI 显示状态（视觉状态）
# ==========================================================

class VisualState(Enum):
    """
    只用于 UI，不参与业务逻辑
    """
    NORMAL = auto()     # 普通显示
    HOVER = auto()      # 鼠标悬停
    SUGGESTED = auto()  # 推荐（绿色高亮）
    WARNING = auto()    # 警告（黄色）
    ERROR = auto()      # 错误（红色）


# ==========================================================
# 4. 空间完整状态对象（核心🔥）
# ==========================================================

@dataclass
class SpaceState:
    """
    一个空间的统一状态容器

    ⚠️ 核心原则：
    - StructureState → 空间结构
    - PlacementState → 是否可放
    - VisualState → UI颜色
    """

    structure: SpaceStructureState = SpaceStructureState.FREE
    placement: PlacementState = PlacementState.UNKNOWN
    visual: VisualState = VisualState.NORMAL

    # 可选：是否需要重新计算
    dirty: bool = False


# ==========================================================
# 5. 状态判断工具（核心逻辑🔥）
# ==========================================================

def can_place(state: SpaceState) -> bool:
    """
    唯一标准：是否允许放板件
    """

    return (
        state.structure == SpaceStructureState.FREE
        and state.placement == PlacementState.ALLOWED
    )


def is_free(state: SpaceState) -> bool:
    """
    是否为空闲空间
    """
    return state.structure == SpaceStructureState.FREE


def to_visual_state(state: SpaceState) -> VisualState:
    """
    根据业务状态推导 UI 状态（非常重要🔥）
    """

    if state.placement == PlacementState.BLOCKED:
        return VisualState.ERROR

    if state.placement == PlacementState.ALLOWED:
        return VisualState.SUGGESTED

    if state.structure == SpaceStructureState.SPLIT:
        return VisualState.NORMAL

    return VisualState.NORMAL


# ==========================================================
# 6. 状态更新工具（避免 UI 乱改逻辑）
# ==========================================================

def mark_allowed(state: SpaceState) -> None:
    state.placement = PlacementState.ALLOWED
    state.visual = VisualState.SUGGESTED


def mark_blocked(state: SpaceState) -> None:
    state.placement = PlacementState.BLOCKED
    state.visual = VisualState.ERROR


def mark_split(state: SpaceState) -> None:
    state.structure = SpaceStructureState.SPLIT
    state.visual = VisualState.NORMAL


# ==========================================================
# 7. 拾取语义：``enums.SpaceState``（与本模块 ``SpaceState`` 数据类区分）
# ==========================================================

from .enums import SpaceState as PickSemanticSpaceState
from .space_models import Space

# --- UI 展示用：叶节点放置决策缓存（由业务层写入，``space_visual_mapper`` 只读）---

UI_METADATA_PLACEMENT_KEY = "ui_placement_decision"


def read_ui_placement_for_space_display(space: Space) -> PlacementState:
    """读取 ``metadata[UI_METADATA_PLACEMENT_KEY]``；缺省为 ``UNKNOWN``。"""
    md = getattr(space, "metadata", None)
    if not isinstance(md, dict):
        return PlacementState.UNKNOWN
    raw = md.get(UI_METADATA_PLACEMENT_KEY)
    if raw is None:
        return PlacementState.UNKNOWN
    if isinstance(raw, PlacementState):
        return raw
    s = str(raw).strip().upper()
    for p in PlacementState:
        if p.name.upper() == s:
            return p
    return PlacementState.UNKNOWN


def write_ui_placement_for_space_display(space: Space, p: PlacementState) -> None:
    """
    将 ``ConstraintEngine.validate`` 等业务结果写入 ``Space.metadata``。

    ``UNKNOWN`` 时移除键，避免陈旧状态。
    """
    md = getattr(space, "metadata", None)
    if not isinstance(md, dict):
        md = {}
        setattr(space, "metadata", md)
    if p is PlacementState.UNKNOWN:
        md.pop(UI_METADATA_PLACEMENT_KEY, None)
    else:
        md[UI_METADATA_PLACEMENT_KEY] = p.name


def infer_space_state(space: Space) -> PickSemanticSpaceState:
    """
    从 ``Space`` 推断 ``core.space.enums.SpaceState``（FREE / OCCUPIED / SPLIT）。

    供 ``space_picker``、``calculator`` 等使用；综合子节点、``is_occupied`` 与板件挂载。
    """
    children = getattr(space, "children", None) or []
    if len(children) > 0:
        return PickSemanticSpaceState.SPLIT

    occupied = bool(getattr(space, "is_occupied", False))
    panels = getattr(space, "panels", None) or []
    groups = getattr(space, "panel_groups", None) or []
    if occupied or len(panels) > 0 or len(groups) > 0:
        return PickSemanticSpaceState.OCCUPIED

    return PickSemanticSpaceState.FREE