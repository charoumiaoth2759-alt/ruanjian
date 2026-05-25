from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from .space_models import Space
from .tree import walk_dfs, iter_leaves, max_depth, get_path_names
from ..constants.dimensions import (
    MIN_SPACE_WIDTH,
    MIN_SPACE_HEIGHT,
    MIN_SPACE_DEPTH,
    MAX_SPACE_WIDTH,
    MAX_SPACE_HEIGHT,
    MAX_SPACE_DEPTH,
    MAX_TREE_DEPTH,
)


# ================================================================
# 错误等级 & 错误对象
# ================================================================

class Severity(Enum):
    ERROR   = auto()   # 必须修复，solver 不应继续执行
    WARNING = auto()   # 可继续，但结果可能不合理
    INFO    = auto()   # 提示性，不影响求解


@dataclass
class ValidationIssue:
    """单条校验问题。"""
    severity:  Severity
    code:      str          # 机器可读的错误码，供 UI 层国际化
    message:   str          # 人类可读的描述
    node_id:   str          # 出问题的节点 id
    node_path: str          # 出问题的节点路径，如 "整体柜/左柜/下格"
    detail:    dict = field(default_factory=dict)   # 附加数值，方便 UI 展示

    @property
    def is_error(self) -> bool:
        return self.severity == Severity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == Severity.WARNING

    def __str__(self) -> str:
        tag = f"[{self.severity.name}]"
        return f"{tag} {self.code}  {self.node_path}  {self.message}"


@dataclass
class ValidationResult:
    """一次完整校验的汇总结果。"""
    issues: list[ValidationIssue] = field(default_factory=list)

    # ── 快捷访问 ─────────────────────────────────────────────

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.is_error]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.is_warning]

    @property
    def is_valid(self) -> bool:
        """无 ERROR 级别问题则视为合法。"""
        return len(self.errors) == 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def merge(self, other: "ValidationResult") -> None:
        """合并另一个结果，用于分步校验后汇总。"""
        self.issues.extend(other.issues)

    def print_all(self) -> None:
        if not self.issues:
            print("[Validator] ✓ 无问题")
            return
        for issue in self.issues:
            print(issue)
        print(
            f"\n[Validator] 共 {len(self.issues)} 条："
            f"ERROR={len(self.errors)}  "
            f"WARNING={len(self.warnings)}"
        )


# ================================================================
# 内部工具
# ================================================================

def _issue(
    severity: Severity,
    code: str,
    message: str,
    node: Space,
    **detail,
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        code=code,
        message=message,
        node_id=node.id,
        node_path=get_path_names(node),
        detail=dict(detail),
    )


def _error(code: str, message: str, node: Space, **detail) -> ValidationIssue:
    return _issue(Severity.ERROR, code, message, node, **detail)


def _warning(code: str, message: str, node: Space, **detail) -> ValidationIssue:
    return _issue(Severity.WARNING, code, message, node, **detail)


def _info(code: str, message: str, node: Space, **detail) -> ValidationIssue:
    return _issue(Severity.INFO, code, message, node, **detail)


# ================================================================
# 单项校验函数
# 每个函数接收一棵树（或单节点），返回 ValidationResult
# 相互独立，可单独调用，也可由 validate() 统一编排
# ================================================================

def check_dimensions(root: Space) -> ValidationResult:
    """
    尺寸越界检查。
    对树中每个节点检查 width / height / depth 是否在合法区间内。
    volume == 0 单独报 ERROR（说明节点尺寸从未初始化）。
    """
    result = ValidationResult()

    for node in walk_dfs(root):
        w, h, d = node.width, node.height, node.depth

        # 未初始化
        if node.volume == 0.0:
            result.add(_error(
                "DIM_ZERO_VOLUME",
                f"尺寸未初始化（{w:.1f}×{h:.1f}×{d:.1f}）",
                node, width=w, height=h, depth=d,
            ))
            continue   # 后续检查无意义，跳过

        # 负数尺寸
        for dim_name, val in (("width", w), ("height", h), ("depth", d)):
            if val < 0:
                result.add(_error(
                    "DIM_NEGATIVE",
                    f"{dim_name} = {val:.1f} mm，不能为负数",
                    node, **{dim_name: val},
                ))

        # 低于最小值
        checks = [
            ("width",  w, MIN_SPACE_WIDTH,  MAX_SPACE_WIDTH),
            ("height", h, MIN_SPACE_HEIGHT, MAX_SPACE_HEIGHT),
            ("depth",  d, MIN_SPACE_DEPTH,  MAX_SPACE_DEPTH),
        ]
        for dim_name, val, lo, hi in checks:
            if val < lo:
                result.add(_error(
                    f"DIM_TOO_SMALL_{dim_name.upper()}",
                    f"{dim_name} = {val:.1f} mm，低于最小值 {lo} mm",
                    node, value=val, min=lo,
                ))
            elif val > hi:
                result.add(_warning(
                    f"DIM_TOO_LARGE_{dim_name.upper()}",
                    f"{dim_name} = {val:.1f} mm，超过推荐最大值 {hi} mm",
                    node, value=val, max=hi,
                ))

    return result


def check_children_sum(root: Space) -> ValidationResult:
    """
    子节点尺寸求和校验。
    对非叶节点：沿分割方向，所有子节点的尺寸之和应等于父节点对应尺寸。
    误差超过公差时报 ERROR。
    """
    from ..constants.tolerance import DIMENSION_TOLERANCE
    from ..constants.enums import is_split_along_x, is_split_along_y, is_split_along_z

    result = ValidationResult()

    for node in walk_dfs(root):
        if node.is_leaf or not node.children:
            continue

        direction = node.split_direction

        if is_split_along_x(direction):   # SPLIT_X（旧名 HORIZONTAL）：子节点 width 求和
            total = sum(c.width for c in node.children)
            expected = node.width
            dim_name = "width"
        elif is_split_along_y(direction):   # SPLIT_Y（旧名 VERTICAL）：子节点 height 求和
            total = sum(c.height for c in node.children)
            expected = node.height
            dim_name = "height"
        elif is_split_along_z(direction):   # SPLIT_Z（旧名 DEPTH）：子节点 depth 求和
            total = sum(c.depth for c in node.children)
            expected = node.depth
            dim_name = "depth"
        else:
            # SplitDirection.NONE 但有子节点 → 孤立节点问题，由 check_isolated 报
            continue

        diff = abs(total - expected)
        if diff > DIMENSION_TOLERANCE:
            result.add(_error(
                "CHILDREN_SUM_MISMATCH",
                f"子节点 {dim_name} 之和 {total:.2f} mm "
                f"≠ 父节点 {dim_name} {expected:.2f} mm "
                f"（差值 {diff:.2f} mm，公差 {DIMENSION_TOLERANCE} mm）",
                node,
                direction=direction.value,
                total=total,
                expected=expected,
                diff=diff,
            ))

    return result


def check_overlap(root: Space) -> ValidationResult:
    """
    同级子节点重叠检查。
    对同一父节点下的所有子节点，按分割方向检测区间是否有交叉。
    只检测直接子节点（一级），不递归（递归由框架逐层调用保证）。
    """
    from ..constants.enums import is_split_along_x, is_split_along_y, is_split_along_z
    from ..constants.tolerance import DIMENSION_TOLERANCE

    result = ValidationResult()

    for node in walk_dfs(root):
        if len(node.children) < 2:
            continue

        direction = node.split_direction
        children = node.children

        if is_split_along_x(direction):
            intervals = [(c, c.x, c.x + c.width) for c in children]
        elif is_split_along_y(direction):
            intervals = [(c, c.y, c.y + c.height) for c in children]
        elif is_split_along_z(direction):
            intervals = [(c, c.z, c.z + c.depth) for c in children]
        else:
            continue

        # O(n²) 两两检测，子节点数量通常 < 20，可接受
        for i in range(len(intervals)):
            for j in range(i + 1, len(intervals)):
                ca, lo_a, hi_a = intervals[i]
                cb, lo_b, hi_b = intervals[j]
                overlap = min(hi_a, hi_b) - max(lo_a, lo_b)
                if overlap > DIMENSION_TOLERANCE:
                    result.add(_error(
                        "CHILD_OVERLAP",
                        f"子节点 '{ca.name or ca.id[:8]}' 与 "
                        f"'{cb.name or cb.id[:8]}' 重叠 {overlap:.2f} mm",
                        node,
                        node_a=ca.id, node_b=cb.id, overlap=overlap,
                    ))

    return result


def check_isolated(root: Space) -> ValidationResult:
    """
    孤立节点检测。
    孤立节点定义：非叶节点但 split_direction == NONE，
    说明这个节点有子节点但未定义切割方向，子节点位置无法确定。
    """
    from ..constants.enums import SplitDirection

    result = ValidationResult()

    for node in walk_dfs(root):
        if not node.is_leaf and node.split_direction == SplitDirection.NONE:
            result.add(_warning(
                "ISOLATED_NO_SPLIT_DIRECTION",
                f"非叶节点未设置 split_direction，子节点位置无法确定",
                node, children_count=len(node.children),
            ))

    return result


def check_position_consistency(root: Space) -> ValidationResult:
    """
    位置一致性检查。
    子节点的起始坐标应紧贴父节点原点或上一个兄弟节点的末端。
    误差超过公差时报 WARNING（位置由 splitter 计算，ERROR 会在 check_overlap 里覆盖）。
    """
    from ..constants.enums import is_split_along_x, is_split_along_y, is_split_along_z
    from ..constants.tolerance import DIMENSION_TOLERANCE

    result = ValidationResult()

    for node in walk_dfs(root):
        if not node.children:
            continue

        direction = node.split_direction
        children = node.children

        if is_split_along_x(direction):
            cursor = node.x
            for child in children:
                diff = abs(child.x - cursor)
                if diff > DIMENSION_TOLERANCE:
                    result.add(_warning(
                        "POSITION_GAP_X",
                        f"子节点 x={child.x:.2f} 与预期起点 {cursor:.2f} 相差 {diff:.2f} mm",
                        child, expected_x=cursor, actual_x=child.x,
                    ))
                cursor += child.width

        elif is_split_along_y(direction):
            cursor = node.y
            for child in children:
                diff = abs(child.y - cursor)
                if diff > DIMENSION_TOLERANCE:
                    result.add(_warning(
                        "POSITION_GAP_Y",
                        f"子节点 y={child.y:.2f} 与预期起点 {cursor:.2f} 相差 {diff:.2f} mm",
                        child, expected_y=cursor, actual_y=child.y,
                    ))
                cursor += child.height

        elif is_split_along_z(direction):
            cursor = node.z
            for child in children:
                diff = abs(child.z - cursor)
                if diff > DIMENSION_TOLERANCE:
                    result.add(_warning(
                        "POSITION_GAP_Z",
                        f"子节点 z={child.z:.2f} 与预期起点 {cursor:.2f} 相差 {diff:.2f} mm",
                        child, expected_z=cursor, actual_z=child.z,
                    ))
                cursor += child.depth

    return result


def check_tree_depth(root: Space) -> ValidationResult:
    """
    树深度检查。
    超过 MAX_TREE_DEPTH 说明切割层级异常（通常是递归切割 bug）。
    """
    result = ValidationResult()
    depth = max_depth(root)

    if depth > MAX_TREE_DEPTH:
        result.add(_warning(
            "TREE_TOO_DEEP",
            f"空间树深度 {depth} 超过推荐最大值 {MAX_TREE_DEPTH}，"
            f"可能存在递归切割异常",
            root, depth=depth, max_depth=MAX_TREE_DEPTH,
        ))

    return result


def check_constraints(root: Space) -> ValidationResult:
    """
    约束合法性检查。
    验证每个节点的 SpaceConstraint 内部是否自洽：
      - min_width <= max_width
      - 当前尺寸是否落在约束范围内
    """
    result = ValidationResult()

    for node in walk_dfs(root):
        c = node.constraints

        # min ≤ max 自洽检查
        pairs = [
            ("width",  c.min_width,  c.max_width),
            ("height", c.min_height, c.max_height),
            ("depth",  c.min_depth,  c.max_depth),
        ]
        for dim_name, lo, hi in pairs:
            if lo is not None and hi is not None and lo > hi:
                result.add(_error(
                    f"CONSTRAINT_INVERTED_{dim_name.upper()}",
                    f"约束 min_{dim_name}={lo} > max_{dim_name}={hi}，约束自相矛盾",
                    node, min=lo, max=hi,
                ))

        # 当前尺寸是否违反约束
        dim_vals = [
            ("width",  node.width,  c.min_width,  c.max_width),
            ("height", node.height, c.min_height, c.max_height),
            ("depth",  node.depth,  c.min_depth,  c.max_depth),
        ]
        for dim_name, val, lo, hi in dim_vals:
            if lo is not None and val < lo:
                result.add(_error(
                    f"CONSTRAINT_VIOLATED_MIN_{dim_name.upper()}",
                    f"{dim_name}={val:.1f} mm 违反约束 min_{dim_name}={lo} mm",
                    node, value=val, min=lo,
                ))
            if hi is not None and val > hi:
                result.add(_error(
                    f"CONSTRAINT_VIOLATED_MAX_{dim_name.upper()}",
                    f"{dim_name}={val:.1f} mm 违反约束 max_{dim_name}={hi} mm",
                    node, value=val, max=hi,
                ))

    return result


def check_leaf_usability(root: Space) -> ValidationResult:
    """
    叶节点可用性检查。
    叶节点是最终柜格，尺寸过小会导致板件无法生成或五金无法安装。
    这里用比 MIN_SPACE_* 更宽松的"可用阈值"，报 WARNING 而非 ERROR。
    """
    from ..constants.dimensions import (
        MIN_USABLE_WIDTH,
        MIN_USABLE_HEIGHT,
        MIN_USABLE_DEPTH,
    )

    result = ValidationResult()

    for node in iter_leaves(root):
        checks = [
            ("width",  node.width,  MIN_USABLE_WIDTH),
            ("height", node.height, MIN_USABLE_HEIGHT),
            ("depth",  node.depth,  MIN_USABLE_DEPTH),
        ]
        for dim_name, val, threshold in checks:
            if val < threshold:
                result.add(_warning(
                    f"LEAF_TOO_SMALL_{dim_name.upper()}",
                    f"叶节点 {dim_name}={val:.1f} mm，"
                    f"低于可用阈值 {threshold} mm，"
                    f"板件生成或五金安装可能失败",
                    node, value=val, threshold=threshold,
                ))

    return result


# ================================================================
# 主入口：完整校验流水线
# ================================================================

# 校验步骤列表，按依赖顺序排列
# 格式：(校验函数, 描述)
_CHECKS = [
    (check_dimensions,           "尺寸越界"),
    (check_constraints,          "约束合法性"),
    (check_children_sum,         "子节点求和"),
    (check_overlap,              "子节点重叠"),
    (check_position_consistency, "位置一致性"),
    (check_isolated,             "孤立节点"),
    (check_tree_depth,           "树深度"),
    (check_leaf_usability,       "叶节点可用性"),
]


def validate(
    root: Space,
    *,
    stop_on_error: bool = False,
    checks: Optional[list] = None,
) -> ValidationResult:
    """
    完整校验流水线，依次执行所有单项检查并汇总结果。

    Args:
        root:           要校验的空间树根节点
        stop_on_error:  True → 遇到第一个 ERROR 立即停止，适合 solver 前置门卫
                        False → 跑完所有检查，收集完整问题列表，适合 UI 全量展示
        checks:         指定只跑哪些检查函数（None = 全部）

    Returns:
        ValidationResult，调用 .is_valid 判断是否可以继续求解

    示例：
        result = validate(cabinet_root, stop_on_error=True)
        if not result.is_valid:
            result.print_all()
            return
        solver.solve(cabinet_root)
    """
    active_checks = [
        (fn, desc) for fn, desc in _CHECKS
        if checks is None or fn in checks
    ]

    final = ValidationResult()

    for fn, desc in active_checks:
        partial = fn(root)
        final.merge(partial)

        if stop_on_error and final.errors:
            # 在结果里附一条 INFO 说明提前终止
            final.add(_info(
                "VALIDATION_ABORTED",
                f"在「{desc}」检查发现 ERROR，已提前终止后续校验",
                root,
            ))
            break

    return final


def validate_node(node: Space) -> ValidationResult:
    """
    只校验单个节点（不遍历子树）。
    适合 dirty 节点局部重算后的快速验证。
    """
    # 构造一个只含单节点的临时视图：不改变原树，只借用节点数据
    result = ValidationResult()

    # 尺寸检查
    w, h, d = node.width, node.height, node.depth
    if node.volume == 0.0:
        result.add(_error("DIM_ZERO_VOLUME", "尺寸未初始化", node))

    # 约束检查
    result.merge(check_constraints(node))   # check_constraints 对单节点同样有效

    return result
