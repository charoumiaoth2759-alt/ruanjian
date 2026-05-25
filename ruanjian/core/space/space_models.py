from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

if TYPE_CHECKING:
    from ..panel.panel_models import Panel, PanelGroup

from .constraints import SpaceConstraint
from .enums import SpaceType, SplitDirection
from ..dirty.dirty_flags import DirtyFlag


@dataclass
class Space:
    """
    空间递归节点 —— 整个柜体系统的根数据结构。

    职责边界：
      - 只持有数据，不执行计算
      - 树结构操作（add/remove）保持 parent 双向引用同步
      - dirty_flag 由 dirty_tracker 负责写入，此处只声明字段
      - 不持有任何宿主 UI / 图形上下文引用
    """

    # ----------------------------------------------------------------
    # 基础信息
    # ----------------------------------------------------------------
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    space_type: SpaceType = SpaceType.NORMAL

    # ----------------------------------------------------------------
    # 位置（相对父节点原点，单位 mm）
    # ----------------------------------------------------------------
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    # ----------------------------------------------------------------
    # 尺寸（单位 mm）
    # ----------------------------------------------------------------
    width: float = 0.0    # X 轴
    height: float = 0.0   # Y 轴
    depth: float = 0.0    # Z 轴

    # ----------------------------------------------------------------
    # 树结构
    # ----------------------------------------------------------------
    parent: Optional["Space"] = field(default=None, repr=False)
    children: list["Space"] = field(default_factory=list, repr=False)

    # ----------------------------------------------------------------
    # 挂载板件（逻辑宿主；不在此 import Panel 避免循环依赖）
    # ----------------------------------------------------------------
    panels: list["Panel"] = field(default_factory=list, repr=False)
    panel_groups: list["PanelGroup"] = field(default_factory=list, repr=False)

    # ----------------------------------------------------------------
    # 分割信息
    # ----------------------------------------------------------------
    split_direction: SplitDirection = SplitDirection.NONE

    # ----------------------------------------------------------------
    # 约束
    # ----------------------------------------------------------------
    constraints: SpaceConstraint = field(default_factory=SpaceConstraint)

    # ----------------------------------------------------------------
    # Dirty 标记
    # ⚑ 由 dirty_tracker.mark_dirty() / mark_clean() 写入，勿手动修改
    # ----------------------------------------------------------------
    dirty_flag: DirtyFlag = field(default=DirtyFlag.CLEAN, compare=False)

    # ----------------------------------------------------------------
    # 功能扩展
    # ----------------------------------------------------------------
    metadata: dict = field(default_factory=dict, repr=False)

    # ================================================================
    # 树操作
    # ================================================================

    def add_child(self, child: "Space") -> None:
        """挂载子节点，维护双向引用，并将本节点标为 DIRTY。"""
        child.parent = self
        self.children.append(child)
        # 结构变化 → 本节点需要重算，由 dirty_tracker 负责向下游传播
        self.dirty_flag = DirtyFlag.DIRTY

    def remove_child(self, child: "Space") -> None:
        """移除子节点，解除双向引用，并将本节点标为 DIRTY。"""
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            self.dirty_flag = DirtyFlag.DIRTY

    def detach(self) -> None:
        """将自身从父节点摘除。"""
        if self.parent is not None:
            self.parent.remove_child(self)

    # ================================================================
    # 查询
    # ================================================================

    @property
    def is_leaf(self) -> bool:
        """没有子节点 → 叶节点，通常对应实际的柜格/抽屉空间。"""
        return len(self.children) == 0

    @property
    def is_root(self) -> bool:
        """没有父节点 → 根节点，通常对应整个柜体。"""
        return self.parent is None

    @property
    def is_dirty(self) -> bool:
        """快捷判断：此节点是否需要重算。"""
        return self.dirty_flag != DirtyFlag.CLEAN

    @property
    def depth_in_tree(self) -> int:
        """节点在树中的深度，根节点为 0。"""
        depth = 0
        node = self
        while node.parent is not None:
            depth += 1
            node = node.parent
        return depth

    @property
    def root(self) -> "Space":
        """沿 parent 链向上，返回根节点。"""
        node = self
        while node.parent is not None:
            node = node.parent
        return node

    # ----------------------------------------------------------------
    # 尺寸 / 位置快捷访问
    # ----------------------------------------------------------------

    @property
    def size(self) -> tuple[float, float, float]:
        """(width, height, depth) 三元组。"""
        return self.width, self.height, self.depth

    @property
    def position(self) -> tuple[float, float, float]:
        """(x, y, z) 相对父节点原点的位置三元组。"""
        return self.x, self.y, self.z

    @property
    def volume(self) -> float:
        """体积（mm³），可用于异常检测（volume == 0 说明尺寸未初始化）。"""
        return self.width * self.height * self.depth

    def half_size(self) -> tuple[float, float, float]:
        """半宽/半高/半深，供渲染层居中绘制使用。"""
        return self.width / 2, self.height / 2, self.depth / 2

    # ================================================================
    # 调试
    # ================================================================

    def print_tree(self, level: int = 0) -> None:
        """递归打印树结构，附带脏标记状态，便于调试。"""
        indent = "    " * level
        dirty_mark = " ✦" if self.is_dirty else ""
        print(
            f"{indent}"
            f"{self.name or self.space_type.value}"
            f"  [{self.width:.1f} × {self.height:.1f} × {self.depth:.1f}]"
            f"  id={self.id[:8]}"
            f"{dirty_mark}"
        )
        for child in self.children:
            child.print_tree(level + 1)

    def __repr__(self) -> str:
        return (
            f"Space(id={self.id[:8]}, name={self.name!r}, "
            f"type={self.space_type.value}, "
            f"size={self.width:.1f}×{self.height:.1f}×{self.depth:.1f}, "
            f"dirty={self.dirty_flag.name})"
        )