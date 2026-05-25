from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from .panel_bounds import panel_world_aabb
from .panel_models import Panel
from ..constants.enums import PanelRole, PanelOrientation, EdgeBandFace
from ..constants.tolerance import DIMENSION_TOLERANCE


# ================================================================
# 基础类型
# ================================================================

class ContactType(Enum):
    """
    两块板件之间的接触类型。

    FACE_TO_FACE  板面对板面（两块板平行，面对面贴合，如背板贴旁板内侧）
    FACE_TO_EDGE  板面对端面（一块板的面贴另一块板的截面，如顶板面压旁板端面）
    EDGE_TO_EDGE  端面对端面（两块板截面相对，通常是 45° 拼角，柜体少见）
    """
    FACE_TO_FACE = "face_to_face"
    FACE_TO_EDGE = "face_to_edge"
    EDGE_TO_EDGE = "edge_to_edge"


class JointDirection(Enum):
    """接触发生的轴向。"""
    X = "X"
    Y = "Y"
    Z = "Z"


@dataclass(frozen=True)
class SharedEdge:
    """
    两块板件共享的棱边描述。
    棱边用起点 + 终点表示（世界坐标，单位 mm）。
    """
    x0: float; y0: float; z0: float
    x1: float; y1: float; z1: float

    @property
    def length(self) -> float:
        dx = self.x1 - self.x0
        dy = self.y1 - self.y0
        dz = self.z1 - self.z0
        return (dx*dx + dy*dy + dz*dz) ** 0.5

    def __repr__(self) -> str:
        return (
            f"Edge(({self.x0:.1f},{self.y0:.1f},{self.z0:.1f})"
            f"→({self.x1:.1f},{self.y1:.1f},{self.z1:.1f})"
            f" L={self.length:.1f})"
        )


@dataclass(frozen=True)
class ContactFace:
    """
    两块板件之间的接触面描述。
    接触面用矩形区域（x0/y0/z0 ~ x1/y1/z1）表示。
    area：接触面积（mm²）。
    """
    x0: float; y0: float; z0: float
    x1: float; y1: float; z1: float
    area: float

    def __repr__(self) -> str:
        return (
            f"ContactFace("
            f"({self.x0:.1f},{self.y0:.1f},{self.z0:.1f})"
            f"~({self.x1:.1f},{self.y1:.1f},{self.z1:.1f})"
            f" area={self.area:.1f}mm²)"
        )


@dataclass
class PanelContact:
    """
    两块板件之间的完整接触关系描述。

    panel_a / panel_b    : 接触的两块板
    contact_type         : 接触类型（面对面 / 面对端 / 端对端）
    joint_direction      : 接触轴向
    contact_face         : 接触面几何描述
    shared_edges         : 共享棱边列表（通常 1 条）
    needs_fastener       : 是否需要连接件（minifix / 木榫 / 螺丝）
    fastener_count_hint  : 建议连接件数量（由 hardware 规则最终决定）
    """
    panel_a:            Panel
    panel_b:            Panel
    contact_type:       ContactType
    joint_direction:    JointDirection
    contact_face:       ContactFace
    shared_edges:       list[SharedEdge]    = field(default_factory=list)
    needs_fastener:     bool                = True
    fastener_count_hint: int               = 0

    def involves(self, panel: Panel) -> bool:
        return panel is self.panel_a or panel is self.panel_b

    def other(self, panel: Panel) -> Panel:
        if panel is self.panel_a:
            return self.panel_b
        if panel is self.panel_b:
            return self.panel_a
        raise ValueError(f"{panel!r} 不在此接触关系中")

    def __repr__(self) -> str:
        a = self.panel_a.name or self.panel_a.id[:6]
        b = self.panel_b.name or self.panel_b.id[:6]
        return (
            f"Contact({a} ↔ {b}  "
            f"{self.contact_type.value}  "
            f"area={self.contact_face.area:.1f}mm²  "
            f"fastener×{self.fastener_count_hint})"
        )


# ================================================================
# 几何工具
# ================================================================

def _panel_bbox(panel: Panel) -> dict:
    """
    返回板件在世界坐标系中的包围盒。
    根据朝向确定三轴范围（厚度沿 X / Y / Z 见 ``panel_bounds.panel_extents_world_xyz``）。
    """
    x0, x1, y0, y1, z0, z1 = panel_world_aabb(panel)
    return dict(x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1)


def _interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    """两区间重叠长度，< 0 表示无交叉。"""
    return min(a1, b1) - max(a0, b0)


def _detect_contact(
    ba: dict, bb: dict, tol: float = DIMENSION_TOLERANCE
) -> Optional[tuple[JointDirection, ContactFace]]:
    """
    检测两个包围盒是否接触（共享一个面，另两轴有实质重叠）。
    返回 (JointDirection, ContactFace) 或 None。
    """
    # ── X 轴接触 ──────────────────────────────────────────────
    for x_a, x_b in ((ba["x1"], bb["x0"]), (bb["x1"], ba["x0"])):
        if abs(x_a - x_b) <= tol:
            oy = _interval_overlap(ba["y0"], ba["y1"], bb["y0"], bb["y1"])
            oz = _interval_overlap(ba["z0"], ba["z1"], bb["z0"], bb["z1"])
            if oy > tol and oz > tol:
                cy0 = max(ba["y0"], bb["y0"])
                cy1 = min(ba["y1"], bb["y1"])
                cz0 = max(ba["z0"], bb["z0"])
                cz1 = min(ba["z1"], bb["z1"])
                cx  = x_a
                return JointDirection.X, ContactFace(
                    x0=cx, y0=cy0, z0=cz0,
                    x1=cx, y1=cy1, z1=cz1,
                    area=oy * oz,
                )

    # ── Y 轴接触 ──────────────────────────────────────────────
    for y_a, y_b in ((ba["y1"], bb["y0"]), (bb["y1"], ba["y0"])):
        if abs(y_a - y_b) <= tol:
            ox = _interval_overlap(ba["x0"], ba["x1"], bb["x0"], bb["x1"])
            oz = _interval_overlap(ba["z0"], ba["z1"], bb["z0"], bb["z1"])
            if ox > tol and oz > tol:
                cx0 = max(ba["x0"], bb["x0"])
                cx1 = min(ba["x1"], bb["x1"])
                cz0 = max(ba["z0"], bb["z0"])
                cz1 = min(ba["z1"], bb["z1"])
                cy  = y_a
                return JointDirection.Y, ContactFace(
                    x0=cx0, y0=cy, z0=cz0,
                    x1=cx1, y1=cy, z1=cz1,
                    area=ox * oz,
                )

    # ── Z 轴接触 ──────────────────────────────────────────────
    for z_a, z_b in ((ba["z1"], bb["z0"]), (bb["z1"], ba["z0"])):
        if abs(z_a - z_b) <= tol:
            ox = _interval_overlap(ba["x0"], ba["x1"], bb["x0"], bb["x1"])
            oy = _interval_overlap(ba["y0"], ba["y1"], bb["y0"], bb["y1"])
            if ox > tol and oy > tol:
                cx0 = max(ba["x0"], bb["x0"])
                cx1 = min(ba["x1"], bb["x1"])
                cy0 = max(ba["y0"], bb["y0"])
                cy1 = min(ba["y1"], bb["y1"])
                cz  = z_a
                return JointDirection.Z, ContactFace(
                    x0=cx0, y0=cy0, z0=cz,
                    x1=cx1, y1=cy1, z1=cz,
                    area=ox * oy,
                )

    return None


def _classify_contact_type(
    pa: Panel, pb: Panel, direction: JointDirection
) -> ContactType:
    """
    根据两块板的朝向和接触轴向判断接触类型。

    判断逻辑：
      - 接触轴向与某块板的"厚度轴"一致 → 那块板是"面接触"方
      - 两块板厚度轴都与接触轴一致      → FACE_TO_FACE（背靠背，柜体很少）
      - 只有一块板厚度轴与接触轴一致    → FACE_TO_EDGE（最常见）
      - 两块板厚度轴都不与接触轴一致    → EDGE_TO_EDGE（拼角）
    """
    def _thickness_axis(p: Panel) -> JointDirection:
        if p.orientation == PanelOrientation.VERTICAL_X:
            return JointDirection.X
        if p.orientation == PanelOrientation.HORIZONTAL:
            return JointDirection.Y
        return JointDirection.Z   # VERTICAL_Z

    ta = _thickness_axis(pa)
    tb = _thickness_axis(pb)
    a_is_face = (ta == direction)
    b_is_face = (tb == direction)

    if a_is_face and b_is_face:
        return ContactType.FACE_TO_FACE
    if a_is_face or b_is_face:
        return ContactType.FACE_TO_EDGE
    return ContactType.EDGE_TO_EDGE


def _extract_shared_edges(cf: ContactFace) -> list[SharedEdge]:
    """
    从接触面提取共享棱边。
    接触面是一个退化矩形（某轴坐标相同），
    提取其四条棱中最长的两条作为共享棱边候选。
    通常只有 1 条主要棱边（最长的那条）有实际意义。
    """
    edges = []

    # 接触面退化在 X 轴（x0==x1）
    if abs(cf.x1 - cf.x0) < DIMENSION_TOLERANCE:
        x = cf.x0
        edges.append(SharedEdge(x, cf.y0, cf.z0, x, cf.y1, cf.z0))  # 底棱
        edges.append(SharedEdge(x, cf.y0, cf.z1, x, cf.y1, cf.z1))  # 顶棱（z方向）
        edges.append(SharedEdge(x, cf.y0, cf.z0, x, cf.y0, cf.z1))  # 左棱
        edges.append(SharedEdge(x, cf.y1, cf.z0, x, cf.y1, cf.z1))  # 右棱

    # 接触面退化在 Y 轴（y0==y1）
    elif abs(cf.y1 - cf.y0) < DIMENSION_TOLERANCE:
        y = cf.y0
        edges.append(SharedEdge(cf.x0, y, cf.z0, cf.x1, y, cf.z0))
        edges.append(SharedEdge(cf.x0, y, cf.z1, cf.x1, y, cf.z1))
        edges.append(SharedEdge(cf.x0, y, cf.z0, cf.x0, y, cf.z1))
        edges.append(SharedEdge(cf.x1, y, cf.z0, cf.x1, y, cf.z1))

    # 接触面退化在 Z 轴（z0==z1）
    elif abs(cf.z1 - cf.z0) < DIMENSION_TOLERANCE:
        z = cf.z0
        edges.append(SharedEdge(cf.x0, cf.y0, z, cf.x1, cf.y0, z))
        edges.append(SharedEdge(cf.x0, cf.y1, z, cf.x1, cf.y1, z))
        edges.append(SharedEdge(cf.x0, cf.y0, z, cf.x0, cf.y1, z))
        edges.append(SharedEdge(cf.x1, cf.y0, z, cf.x1, cf.y1, z))

    # 只返回有实际长度的棱边，按长度降序
    valid = [e for e in edges if e.length > DIMENSION_TOLERANCE]
    valid.sort(key=lambda e: e.length, reverse=True)
    return valid


def _estimate_fastener_count(contact_face: ContactFace, contact_type: ContactType) -> int:
    """
    根据接触面积和接触类型估算连接件数量。
    最终数量由 hardware/rules/ 精确计算，此处只给 hint。

    规则：
      FACE_TO_EDGE（最常见）：
        面积 < 20000 mm²（约 100×200）→ 2 个
        面积 < 60000 mm²（约 200×300）→ 4 个
        面积 >= 60000 mm²              → 每 20000 mm² 增加 2 个
      FACE_TO_FACE（背板贴面）：通常不需要连接件，靠槽固定
      EDGE_TO_EDGE：通常 2 个
    """
    if contact_type == ContactType.FACE_TO_FACE:
        return 0

    area = contact_face.area
    if contact_type == ContactType.EDGE_TO_EDGE:
        return 2

    # FACE_TO_EDGE
    if area < 20_000:
        return 2
    if area < 60_000:
        return 4
    return 4 + 2 * int((area - 60_000) / 20_000)


def _needs_fastener(pa: Panel, pb: Panel, ct: ContactType) -> bool:
    """
    判断两块板的接触是否需要连接件。
    背板通常嵌槽固定，不需要额外连接件。
    """
    back_roles = {PanelRole.BACK}
    if pa.role in back_roles or pb.role in back_roles:
        return False
    if ct == ContactType.FACE_TO_FACE:
        return False
    return True


# ================================================================
# 核心接口
# ================================================================

def get_contacts(
    panels: list[Panel],
    *,
    tol: float = DIMENSION_TOLERANCE,
) -> list[PanelContact]:
    """
    计算板件列表中所有两两接触关系。
    O(n²)，板件数通常 < 60，可接受。

    典型调用：
        contacts = get_contacts(panel_group.panels)
        for c in contacts:
            hardware_generator.process(c)

    Returns:
        PanelContact 列表，每对接触板件恰好出现一次
    """
    result: list[PanelContact] = []
    bboxes = [_panel_bbox(p) for p in panels]

    for i in range(len(panels)):
        for j in range(i + 1, len(panels)):
            hit = _detect_contact(bboxes[i], bboxes[j], tol)
            if hit is None:
                continue

            direction, contact_face = hit
            pa, pb = panels[i], panels[j]
            ct = _classify_contact_type(pa, pb, direction)
            edges = _extract_shared_edges(contact_face)
            count = _estimate_fastener_count(contact_face, ct)
            needs = _needs_fastener(pa, pb, ct)

            result.append(PanelContact(
                panel_a=pa,
                panel_b=pb,
                contact_type=ct,
                joint_direction=direction,
                contact_face=contact_face,
                shared_edges=edges,
                needs_fastener=needs,
                fastener_count_hint=count if needs else 0,
            ))

    return result


def get_contacts_for(
    panel: Panel,
    all_panels: list[Panel],
    *,
    tol: float = DIMENSION_TOLERANCE,
) -> list[PanelContact]:
    """
    查询单块板件的所有接触关系。

    典型调用：
        # 查左旁板的所有接触，决定在哪些位置打 minifix 孔
        contacts = get_contacts_for(left_panel, all_panels)
    """
    ba = _panel_bbox(panel)
    result = []

    for other in all_panels:
        if other is panel:
            continue
        bb = _panel_bbox(other)
        hit = _detect_contact(ba, bb, tol)
        if hit is None:
            continue
        direction, contact_face = hit
        ct = _classify_contact_type(panel, other, direction)
        edges = _extract_shared_edges(contact_face)
        count = _estimate_fastener_count(contact_face, ct)
        needs = _needs_fastener(panel, other, ct)
        result.append(PanelContact(
            panel_a=panel,
            panel_b=other,
            contact_type=ct,
            joint_direction=direction,
            contact_face=contact_face,
            shared_edges=edges,
            needs_fastener=needs,
            fastener_count_hint=count if needs else 0,
        ))

    return result


def contact_map(
    panels: list[Panel],
) -> dict[str, list[PanelContact]]:
    """
    返回以 panel_id 为 key 的接触字典，O(1) 查询。

    典型调用：
        cmap = contact_map(panels)
        left_contacts = cmap[left_panel.id]
    """
    contacts = get_contacts(panels)
    result: dict[str, list[PanelContact]] = {p.id: [] for p in panels}
    for c in contacts:
        result[c.panel_a.id].append(c)
        result[c.panel_b.id].append(c)
    return result


def get_face_to_edge_contacts(panels: list[Panel]) -> list[PanelContact]:
    """
    只返回 FACE_TO_EDGE 类型的接触（最常见，需要打 minifix）。
    供 hardware/generator.py 直接调用，不需要全量过滤。
    """
    return [c for c in get_contacts(panels)
            if c.contact_type == ContactType.FACE_TO_EDGE]


def total_fastener_hint(panels: list[Panel]) -> int:
    """
    返回所有接触关系的连接件数量估算总和。
    用于快速估料，BOM 粗算时使用。
    """
    return sum(c.fastener_count_hint for c in get_contacts(panels))


# ================================================================
# 共享棱边查询
# ================================================================

def get_shared_edges(
    pa: Panel, pb: Panel, *, tol: float = DIMENSION_TOLERANCE
) -> list[SharedEdge]:
    """
    返回两块板件之间所有共享棱边。
    不相交时返回空列表。
    """
    hit = _detect_contact(_panel_bbox(pa), _panel_bbox(pb), tol)
    if hit is None:
        return []
    _, contact_face = hit
    return _extract_shared_edges(contact_face)


def longest_shared_edge(pa: Panel, pb: Panel) -> Optional[SharedEdge]:
    """返回两块板件之间最长的共享棱边，用于确定封边/连接件的主方向。"""
    edges = get_shared_edges(pa, pb)
    if not edges:
        return None
    return max(edges, key=lambda e: e.length)


# ================================================================
# 调试
# ================================================================

def print_contacts(panels: list[Panel]) -> None:
    """打印所有接触关系，开发期核查拓扑是否正确。"""
    contacts = get_contacts(panels)
    if not contacts:
        print("[PanelTopology] 无接触关系")
        return
    print(f"[PanelTopology] 共 {len(contacts)} 对接触：")
    for c in contacts:
        print(f"  {c}")
    print(f"  连接件总估算：{total_fastener_hint(panels)} 个")
