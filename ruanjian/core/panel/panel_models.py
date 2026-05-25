# -*- coding: utf-8 -*-
"""
柜体板件领域**数据模型**（``dataclass``）。

本模块不依赖宿主 UI / 图形框架；尺寸与封边的变更方法供 ``core.panel`` 内
计算器 / 放置 / 生成器写入领域状态，**不**承担视图或交互职责。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from ..space.space_models import Space
    from ..material.models import MaterialRef

from ..constants.enums import AnchorType, PanelRole, EdgeBandFace, PanelOrientation, PlacementMode
from ..dirty.dirty_flags import DirtyFlag


# ================================================================
# 封边规格
# ================================================================

@dataclass
class EdgeBandSpec:
    """
    单条棱边的封边规格。

    width     : 封边条宽度（mm），应 >= 板件厚度
    thickness : 封边条厚度（mm），典型值 0.4 / 1.0 / 2.0
    material  : 封边材料引用（颜色/材质，与板面饰面匹配）
    """
    width:     float = 0.0
    thickness: float = 0.5
    material:  Optional[str] = None       # 封边材料 id，指向 edge_band_materials

    def is_valid(self) -> bool:
        return self.width > 0 and self.thickness > 0


# ================================================================
# Panel 核心数据对象
# ================================================================

@dataclass
class Panel:
    """
    板件逻辑对象。

    职责边界：
      - 持有板件的完整逻辑描述（尺寸、角色、材料、封边、位置）
      - 不执行任何计算，计算由 calculator.py / placement.py 写入
      - dirty_flag 由 dirty_tracker 写入，此处只声明字段
      - 不持有任何宿主 UI / 图形上下文引用

    坐标系：
      世界坐标系，原点在柜体左下角前方。
      x → 右，y → 上，z → 前。
      (x, y, z) 为板件包围盒的最小角点。

    尺寸语义：
      width / height / thickness：板件本体坐标系下的外观尺寸（含封边含义见各计算器）；
      orientation 决定上述三量如何映射到世界轴（见 ``panel_bounds.panel_extents_world_xyz``）。
      size_x / size_y / size_z：若三者均 > 0，则表示 **世界轴** 上包围盒的 Δx/Δy/Δz（mm），
      与 ``(x,y,z)`` 最小角直接构成 AABB，**优先于** width/height/thickness 映射（用于 View3D 等真 3D 盒绘制）。
    """

    # ----------------------------------------------------------------
    # 基础信息
    # ----------------------------------------------------------------
    id:          str      = field(default_factory=lambda: str(uuid4()))
    name:        str      = ""
    role:        PanelRole = PanelRole.UNKNOWN
    orientation: PanelOrientation = PanelOrientation.VERTICAL_X

    # ----------------------------------------------------------------
    # 尺寸（单位 mm，由 calculator.py 写入）
    # ----------------------------------------------------------------
    width:     float = 0.0    # X 方向可见尺寸
    height:    float = 0.0    # Y 方向可见尺寸
    thickness: float = 18.0   # 板件厚度（默认 18mm 颗粒板）

    # 世界轴对齐包围盒尺寸（mm）：与 ``(x,y,z)`` 最小角配合，直接得到 Δx/Δy/Δz。
    # 三者均 > 0 时，``panel_bounds.panel_extents_world_xyz`` 优先用此三元组，不再按 orientation 映射 width/height/thickness。
    size_x: float = 0.0
    size_y: float = 0.0
    size_z: float = 0.0

    # ----------------------------------------------------------------
    # 世界坐标位置（由 placement.py 写入）
    # ----------------------------------------------------------------
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    # ----------------------------------------------------------------
    # 材料引用
    # ----------------------------------------------------------------
    material_id:      Optional[str] = None   # 指向 board_materials
    surface_id:       Optional[str] = None   # 指向 surface_materials（饰面）

    # ----------------------------------------------------------------
    # 封边
    # 只有"暴露面"才需要封边；背板四面嵌槽通常不封边
    # exposed_faces 由 panel_edge_band_rules.py 写入
    # edge_bands    由 panel_edge_band_rules.py 写入
    # ----------------------------------------------------------------
    exposed_faces: set[EdgeBandFace] = field(default_factory=set)
    edge_bands:    dict[EdgeBandFace, EdgeBandSpec] = field(default_factory=dict)

    # ----------------------------------------------------------------
    # 关联 Space
    # space_id      : 此板件归属的 Space 节点 id
    # space_bounds  : 所属 Space 的世界坐标边界，供 validators 使用
    #                 格式：(x0, y0, z0, x1, y1, z1)
    # ----------------------------------------------------------------
    space_id:     Optional[str]                         = None
    space_bounds: Optional[tuple[float, float, float,
                                 float, float, float]]  = None

    # ----------------------------------------------------------------
    # 放置策略（锚点贴边 vs 自动布局；None = 由 ``anchor_placement`` 按 role 推断）
    # ----------------------------------------------------------------
    placement_mode: Optional[PlacementMode] = None
    anchor_type:    Optional[AnchorType]    = None

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
    # 计算属性
    # ================================================================

    @property
    def is_dirty(self) -> bool:
        return self.dirty_flag != DirtyFlag.CLEAN

    @property
    def volume(self) -> float:
        """体积（mm³），为 0 说明尺寸未初始化。"""
        if self.size_x > 1e-9 and self.size_y > 1e-9 and self.size_z > 1e-9:
            return self.size_x * self.size_y * self.size_z
        return self.width * self.height * self.thickness

    @property
    def face_area(self) -> float:
        """板面面积（mm²），用于材料用量统计。"""
        return self.width * self.height

    @property
    def size(self) -> tuple[float, float, float]:
        """(width, height, thickness) 三元组。"""
        return self.width, self.height, self.thickness

    @property
    def position(self) -> tuple[float, float, float]:
        """(x, y, z) 世界坐标位置。"""
        return self.x, self.y, self.z

    # ----------------------------------------------------------------
    # 净尺寸（扣除封边后的基材尺寸）
    # 净尺寸用于 CNC 开料，封边尺寸用于外观展示
    # ----------------------------------------------------------------

    @property
    def net_width(self) -> float:
        """扣除左右封边厚度后的基材宽度（开料尺寸）。"""
        left  = self._band_thickness(EdgeBandFace.LEFT)
        right = self._band_thickness(EdgeBandFace.RIGHT)
        return self.width - left - right

    @property
    def net_height(self) -> float:
        """扣除上下封边厚度后的基材高度（开料尺寸）。"""
        top    = self._band_thickness(EdgeBandFace.TOP)
        bottom = self._band_thickness(EdgeBandFace.BOTTOM)
        return self.height - top - bottom

    def _band_thickness(self, face: EdgeBandFace) -> float:
        """返回指定面的封边条厚度，未封边返回 0。"""
        spec = self.edge_bands.get(face)
        if spec is None:
            return 0.0
        return spec.thickness

    # ----------------------------------------------------------------
    # 封边工具
    # ----------------------------------------------------------------

    def set_edge_band(
        self,
        face: EdgeBandFace,
        width: float,
        thickness: float = 0.5,
        material: Optional[str] = None,
    ) -> None:
        """
        设置指定面的封边规格，同时将该面加入 exposed_faces。

        示例：
            panel.set_edge_band(EdgeBandFace.TOP, width=18.0, thickness=1.0)
        """
        self.edge_bands[face] = EdgeBandSpec(
            width=width,
            thickness=thickness,
            material=material,
        )
        self.exposed_faces.add(face)
        self.dirty_flag = DirtyFlag.DIRTY

    def clear_edge_band(self, face: EdgeBandFace) -> None:
        """移除指定面的封边配置。"""
        self.edge_bands.pop(face, None)
        self.exposed_faces.discard(face)
        self.dirty_flag = DirtyFlag.DIRTY

    def edge_band_length(self) -> float:
        """
        所有封边条的总线米数（mm），用于 BOM 统计。
        TOP/BOTTOM 封边长度 = width；LEFT/RIGHT 封边长度 = height。
        """
        total = 0.0
        length_map = {
            EdgeBandFace.TOP:    self.width,
            EdgeBandFace.BOTTOM: self.width,
            EdgeBandFace.LEFT:   self.height,
            EdgeBandFace.RIGHT:  self.height,
        }
        for face in self.edge_bands:
            total += length_map.get(face, 0.0)
        return total

    # ----------------------------------------------------------------
    # 尺寸修改（自动标脏）
    # ----------------------------------------------------------------

    def set_size(
        self,
        width: Optional[float] = None,
        height: Optional[float] = None,
        thickness: Optional[float] = None,
    ) -> None:
        """
        批量修改尺寸，自动触发 dirty 标记。
        供 calculator.py 调用，不应由 UI 层直接修改字段。
        """
        changed = False
        if width is not None and abs(width - self.width) > 1e-6:
            self.width = width;       changed = True
        if height is not None and abs(height - self.height) > 1e-6:
            self.height = height;     changed = True
        if thickness is not None and abs(thickness - self.thickness) > 1e-6:
            self.thickness = thickness; changed = True
        if changed:
            self.size_x = self.size_y = self.size_z = 0.0
            self.dirty_flag = DirtyFlag.DIRTY

    def set_position(self, x: float, y: float, z: float) -> None:
        """
        设置世界坐标位置，自动触发 dirty 标记。
        供 placement.py 调用。
        """
        if (abs(x - self.x) > 1e-6 or
                abs(y - self.y) > 1e-6 or
                abs(z - self.z) > 1e-6):
            self.x, self.y, self.z = x, y, z
            self.dirty_flag = DirtyFlag.DIRTY

    def __repr__(self) -> str:
        return (
            f"Panel(id={self.id[:8]}, role={self.role.value}, "
            f"size={self.width:.1f}×{self.height:.1f}×{self.thickness:.1f}, "
            f"dirty={self.dirty_flag.name})"
        )


# ================================================================
# 板件组（同一 Space 下生成的所有板件）
# ================================================================

@dataclass
class PanelGroup:
    """
    一个 Space 节点对应的板件集合。

    generator.py 生成的板件按 Space id 分组存储，
    方便按柜格查询、增量重算与 BOM 分区统计。
    """
    space_id: str
    panels:   list[Panel] = field(default_factory=list)

    def by_role(self, role: PanelRole) -> list[Panel]:
        """按角色过滤，如 group.by_role(PanelRole.SHELF) 获取所有层板。"""
        return [p for p in self.panels if p.role == role]

    def add(self, panel: Panel) -> None:
        panel.space_id = self.space_id
        self.panels.append(panel)

    def total_face_area(self) -> float:
        """组内所有板件的板面面积之和（mm²），用于材料用量估算。"""
        return sum(p.face_area for p in self.panels)

    def dirty_panels(self) -> list[Panel]:
        """返回组内所有脏板件，供 incremental_solver 使用。"""
        return [p for p in self.panels if p.is_dirty]

    def __repr__(self) -> str:
        return (
            f"PanelGroup(space={self.space_id[:8]}, "
            f"count={len(self.panels)}, "
            f"dirty={len(self.dirty_panels())})"
        )
