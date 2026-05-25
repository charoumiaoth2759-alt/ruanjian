from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .panel_models import Panel

from ..constants.dimensions import (
    MIN_PANEL_WIDTH,
    MIN_PANEL_HEIGHT,
    MIN_PANEL_THICKNESS,
    MAX_PANEL_SPAN_WIDTH,
    MAX_PANEL_SPAN_HEIGHT,
)
from ..constants.enums import PanelRole, EdgeBandFace


# ================================================================
# 错误等级 & 错误对象
# （与 space/validators.py 保持相同结构，便于 UI 层统一处理）
# ================================================================

class Severity(Enum):
    ERROR   = auto()
    WARNING = auto()
    INFO    = auto()


@dataclass
class ValidationIssue:
    severity:   Severity
    code:       str
    message:    str
    panel_id:   str
    panel_name: str
    detail:     dict = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return self.severity == Severity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == Severity.WARNING

    def __str__(self) -> str:
        return (
            f"[{self.severity.name}] {self.code}"
            f"  '{self.panel_name}'  {self.message}"
        )


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.is_error]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.is_warning]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def merge(self, other: "ValidationResult") -> None:
        self.issues.extend(other.issues)

    def print_all(self) -> None:
        if not self.issues:
            print("[PanelValidator] ✓ 无问题")
            return
        for issue in self.issues:
            print(issue)
        print(
            f"\n[PanelValidator] 共 {len(self.issues)} 条："
            f"ERROR={len(self.errors)}  WARNING={len(self.warnings)}"
        )


# ================================================================
# 内部工具
# ================================================================

def _issue(
    severity: Severity,
    code: str,
    message: str,
    panel: "Panel",
    **detail,
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        code=code,
        message=message,
        panel_id=panel.id,
        panel_name=panel.name or panel.role.value,
        detail=dict(detail),
    )

def _error(code: str, msg: str, panel: "Panel", **kw) -> ValidationIssue:
    return _issue(Severity.ERROR, code, msg, panel, **kw)

def _warning(code: str, msg: str, panel: "Panel", **kw) -> ValidationIssue:
    return _issue(Severity.WARNING, code, msg, panel, **kw)

def _info(code: str, msg: str, panel: "Panel", **kw) -> ValidationIssue:
    return _issue(Severity.INFO, code, msg, panel, **kw)


# ================================================================
# 单项校验
# ================================================================

def check_min_size(panels: list["Panel"]) -> ValidationResult:
    """
    最小尺寸检查。
    width / height 低于行业最小值时报 ERROR；
    thickness 异常时同样报 ERROR。

    典型触发场景：
      - 背板槽导致有效宽度被压缩到极限
      - 切割比例设置过小（如 10mm 的格子）
    """
    result = ValidationResult()

    for p in panels:
        checks = [
            ("width",     p.width,     MIN_PANEL_WIDTH),
            ("height",    p.height,    MIN_PANEL_HEIGHT),
            ("thickness", p.thickness, MIN_PANEL_THICKNESS),
        ]
        for dim, val, lo in checks:
            if val <= 0:
                result.add(_error(
                    f"PANEL_DIM_ZERO_{dim.upper()}",
                    f"{dim} = {val:.1f} mm，尺寸未初始化或为零",
                    p, dim=dim, value=val,
                ))
            elif val < lo:
                result.add(_error(
                    f"PANEL_TOO_SMALL_{dim.upper()}",
                    f"{dim} = {val:.1f} mm，低于最小值 {lo} mm",
                    p, dim=dim, value=val, min=lo,
                ))

    return result


def check_max_span(panels: list["Panel"]) -> ValidationResult:
    """
    最大跨度检查（抗弯强度）。
    板件在无中间支撑的情况下，跨度过大会导致下挠变形。

    规则：
      - 横向跨度（width）超过 MAX_PANEL_SPAN_WIDTH  → WARNING
      - 纵向跨度（height）超过 MAX_PANEL_SPAN_HEIGHT → WARNING
      - 超过 1.5 倍最大跨度 → 升级为 ERROR

    只对水平承重板件（底板、层板、顶板）检查宽度跨度；
    对竖向板件（旁板、中隔板）检查高度跨度。
    """
    result = ValidationResult()

    HORIZONTAL_ROLES = {PanelRole.BOTTOM, PanelRole.TOP, PanelRole.SHELF}
    VERTICAL_ROLES   = {PanelRole.LEFT, PanelRole.RIGHT, PanelRole.DIVIDER}

    for p in panels:
        if p.role in HORIZONTAL_ROLES:
            span, limit, dim = p.width, MAX_PANEL_SPAN_WIDTH, "width"
        elif p.role in VERTICAL_ROLES:
            span, limit, dim = p.height, MAX_PANEL_SPAN_HEIGHT, "height"
        else:
            continue

        if span > limit * 1.5:
            result.add(_error(
                "PANEL_SPAN_CRITICAL",
                f"{dim} = {span:.1f} mm，超过最大跨度 {limit} mm 的 1.5 倍，"
                f"存在严重下挠风险",
                p, span=span, limit=limit, ratio=round(span / limit, 2),
            ))
        elif span > limit:
            result.add(_warning(
                "PANEL_SPAN_EXCEEDED",
                f"{dim} = {span:.1f} mm，超过推荐最大跨度 {limit} mm，"
                f"建议增加中隔板或选用更厚板材",
                p, span=span, limit=limit, ratio=round(span / limit, 2),
            ))

    return result


def check_thickness_consistency(panels: list["Panel"]) -> ValidationResult:
    """
    同角色板件厚度一致性检查。
    同一柜体内同角色的板件（如所有旁板）厚度应相同，
    不一致通常说明材料配置有误。
    """
    result = ValidationResult()

    # 按角色分组
    role_thickness: dict[PanelRole, list[tuple[float, "Panel"]]] = {}
    for p in panels:
        role_thickness.setdefault(p.role, []).append((p.thickness, p))

    for role, items in role_thickness.items():
        thicknesses = {t for t, _ in items}
        if len(thicknesses) <= 1:
            continue
        # 有多种厚度
        for t, p in items:
            result.add(_warning(
                "PANEL_THICKNESS_INCONSISTENT",
                f"同角色 '{role.value}' 下存在多种厚度：{sorted(thicknesses)} mm，"
                f"此板件厚度为 {t} mm",
                p, role=role.value, thickness=t,
                all_thicknesses=sorted(thicknesses),
            ))

    return result


def check_edge_band_completeness(panels: list["Panel"]) -> ValidationResult:
    """
    封边完整性检查。
    规则：
      1. 任何对外暴露的棱边必须有封边记录
      2. 背板一般不需要封边（四面嵌入槽内）
      3. 封边宽度不得小于板件厚度（否则封边条会缩进）
      4. 封边宽度不得大于板件对应面尺寸（逻辑错误）

    Panel.exposed_faces  : set[EdgeBandFace]  — 需要封边的面
    Panel.edge_bands     : dict[EdgeBandFace, EdgeBandSpec] — 已配置的封边
    """
    result = ValidationResult()

    # 背板通常不封边，跳过
    SKIP_ROLES = {PanelRole.BACK}

    for p in panels:
        if p.role in SKIP_ROLES:
            continue

        exposed: set[EdgeBandFace] = p.exposed_faces
        banded: dict[EdgeBandFace, object] = p.edge_bands   # EdgeBandFace → EdgeBandSpec

        # 1. 暴露面未封边
        for face in exposed:
            if face not in banded:
                result.add(_error(
                    "EDGE_BAND_MISSING",
                    f"暴露面 {face.value} 未配置封边",
                    p, face=face.value,
                ))

        # 2. 封边配置了但对应面不在暴露集合内（多余封边，可能配置错误）
        for face in banded:
            if face not in exposed:
                result.add(_warning(
                    "EDGE_BAND_REDUNDANT",
                    f"面 {face.value} 已配置封边，但该面不属于暴露面，"
                    f"可能是配置冗余",
                    p, face=face.value,
                ))

        # 3. 封边宽度合法性
        for face, spec in banded.items():
            band_width = getattr(spec, "width", None)
            if band_width is None:
                continue

            # 封边宽度 < 板件厚度
            if band_width < p.thickness:
                result.add(_warning(
                    "EDGE_BAND_WIDTH_TOO_NARROW",
                    f"面 {face.value} 封边宽度 {band_width} mm "
                    f"< 板件厚度 {p.thickness} mm，封边条会内缩",
                    p, face=face.value,
                    band_width=band_width, thickness=p.thickness,
                ))

            # 封边宽度 > 板件对应尺寸（逻辑错误）
            face_dim = _face_dimension(p, face)
            if face_dim is not None and band_width > face_dim:
                result.add(_error(
                    "EDGE_BAND_WIDTH_OVERFLOW",
                    f"面 {face.value} 封边宽度 {band_width} mm "
                    f"> 该面尺寸 {face_dim} mm，封边配置有误",
                    p, face=face.value,
                    band_width=band_width, face_dim=face_dim,
                ))

    return result


def _face_dimension(panel: "Panel", face: "EdgeBandFace") -> Optional[float]:
    """根据封边面返回板件该方向上的尺寸，用于封边宽度越界检测。"""
    # EdgeBandFace.TOP / BOTTOM → 对应 width
    # EdgeBandFace.LEFT / RIGHT → 对应 height
    # EdgeBandFace.FRONT / BACK → 对应 thickness（封边不检测厚度面）
    mapping = {
        "top":    panel.width,
        "bottom": panel.width,
        "left":   panel.height,
        "right":  panel.height,
    }
    return mapping.get(face.value)


def check_placement(panels: list["Panel"]) -> ValidationResult:
    """
    板件定位合法性检查。
    检查板件是否完全落在其所属 Space 的边界内。
    position (x, y, z) 为板件在世界坐标系中的原点。

    Panel 需持有 space_bounds: tuple(x0,y0,z0,x1,y1,z1) 供此检查使用。
    """
    from ..constants.tolerance import DIMENSION_TOLERANCE as TOL

    result = ValidationResult()

    for p in panels:
        if not hasattr(p, "space_bounds") or p.space_bounds is None:
            continue   # 未绑定 Space，跳过

        sx0, sy0, sz0, sx1, sy1, sz1 = p.space_bounds

        # 板件自身边界
        px0, px1 = p.x, p.x + p.width
        py0, py1 = p.y, p.y + p.height
        pz0, pz1 = p.z, p.z + p.thickness

        violations = []
        if px0 < sx0 - TOL: violations.append(f"x 起点 {px0:.1f} < Space 边界 {sx0:.1f}")
        if px1 > sx1 + TOL: violations.append(f"x 终点 {px1:.1f} > Space 边界 {sx1:.1f}")
        if py0 < sy0 - TOL: violations.append(f"y 起点 {py0:.1f} < Space 边界 {sy0:.1f}")
        if py1 > sy1 + TOL: violations.append(f"y 终点 {py1:.1f} > Space 边界 {sy1:.1f}")
        if pz0 < sz0 - TOL: violations.append(f"z 起点 {pz0:.1f} < Space 边界 {sz0:.1f}")
        if pz1 > sz1 + TOL: violations.append(f"z 终点 {pz1:.1f} > Space 边界 {sz1:.1f}")

        for msg in violations:
            result.add(_error(
                "PANEL_OUT_OF_SPACE",
                f"板件超出所属 Space 边界：{msg}",
                p,
            ))

    return result


def check_duplicate_position(panels: list["Panel"]) -> ValidationResult:
    """
    重叠板件检测。
    同一位置存在两块板（通常是 generator 重复生成）。
    按 (role, x, y, z) 四元组做精确匹配检测。
    """
    from ..constants.tolerance import DIMENSION_TOLERANCE as TOL

    result = ValidationResult()
    seen: list["Panel"] = []

    for p in panels:
        for prev in seen:
            if (
                p.role == prev.role
                and abs(p.x - prev.x) < TOL
                and abs(p.y - prev.y) < TOL
                and abs(p.z - prev.z) < TOL
                and abs(p.width     - prev.width)     < TOL
                and abs(p.height    - prev.height)    < TOL
                and abs(p.thickness - prev.thickness) < TOL
            ):
                result.add(_warning(
                    "PANEL_DUPLICATE",
                    f"与板件 '{prev.name or prev.id[:8]}' 位置和尺寸完全重合，"
                    f"可能是重复生成",
                    p, duplicate_of=prev.id,
                ))
        seen.append(p)

    return result


# ================================================================
# 主入口
# ================================================================

_CHECKS = [
    (check_min_size,               "最小尺寸"),
    (check_max_span,               "最大跨度"),
    (check_thickness_consistency,  "厚度一致性"),
    (check_edge_band_completeness, "封边完整性"),
    (check_placement,              "板件定位"),
    (check_duplicate_position,     "重叠检测"),
]


def validate(
    panels: list["Panel"],
    *,
    stop_on_error: bool = False,
    checks: Optional[list] = None,
) -> ValidationResult:
    """
    板件完整校验流水线。

    Args:
        panels:         要校验的板件列表
        stop_on_error:  True → 遇到第一个 ERROR 立即停止（solver 前置用）
                        False → 跑完所有检查，收集完整问题列表（UI 展示用）
        checks:         指定只跑哪些检查函数（None = 全部）

    示例：
        result = validate(panel_list, stop_on_error=True)
        if not result.is_valid:
            result.print_all()
            return
    """
    active = [
        (fn, desc) for fn, desc in _CHECKS
        if checks is None or fn in checks
    ]

    final = ValidationResult()

    for fn, desc in active:
        partial = fn(panels)
        final.merge(partial)

        if stop_on_error and final.errors:
            final.add(ValidationIssue(
                severity=Severity.INFO,
                code="VALIDATION_ABORTED",
                message=f"在「{desc}」检查发现 ERROR，已提前终止",
                panel_id="",
                panel_name="",
            ))
            break

    return final


def validate_single(panel: "Panel") -> ValidationResult:
    """
    只校验单块板件，供 dirty 节点局部重算后快速验证使用。
    跳过需要全量列表的检查（thickness_consistency / duplicate_position）。
    """
    final = ValidationResult()
    for fn in (check_min_size, check_max_span,
               check_edge_band_completeness, check_placement):
        final.merge(fn([panel]))
    return final
