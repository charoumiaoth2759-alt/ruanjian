from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from .space_models import Space
from .tree import walk_dfs, walk_bfs, iter_leaves, get_path_names
from .validators import validate, ValidationResult
from ..constants.enums import (
    SplitDirection,
    is_split_along_x,
    is_split_along_y,
    is_split_along_z,
)
from ..constants.tolerance import DIMENSION_TOLERANCE
from ..dirty.dirty_flags import DirtyFlag


# ================================================================
# 求解结果
# ================================================================

class ResolveStatus(Enum):
    OK             = auto()   # 全部节点求解成功
    PARTIAL        = auto()   # 部分节点求解成功，存在 WARNING
    FAILED         = auto()   # 存在 ERROR，求解中止


@dataclass
class NodeResult:
    """单个节点的求解结果快照。"""
    node_id:   str
    node_path: str
    width:     float
    height:    float
    depth:     float
    x:         float
    y:         float
    z:         float
    was_dirty: bool = False    # 求解前是否为脏节点

    def __repr__(self) -> str:
        return (
            f"NodeResult({self.node_path}  "
            f"{self.width:.1f}×{self.height:.1f}×{self.depth:.1f}  "
            f"@({self.x:.1f},{self.y:.1f},{self.z:.1f}))"
        )


@dataclass
class ResolveResult:
    """一次 resolve() 调用的完整输出。"""
    status:       ResolveStatus
    nodes:        list[NodeResult]            = field(default_factory=list)
    validation:   Optional[ValidationResult] = None
    errors:       list[str]                  = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == ResolveStatus.OK

    @property
    def node_map(self) -> dict[str, NodeResult]:
        """按 node_id 索引，O(1) 查询。"""
        return {n.node_id: n for n in self.nodes}

    def print_summary(self) -> None:
        status_mark = "✓" if self.ok else "✗"
        print(f"[Resolver] {status_mark} {self.status.name}  节点数={len(self.nodes)}")
        for err in self.errors:
            print(f"  ✗ {err}")
        if self.validation:
            self.validation.print_all()


# ================================================================
# 内部：单轴分割求解
# ================================================================

def _resolve_split_axis(
    parent: Space,
    children: list[Space],
    parent_size: float,
    get_size: callable,
    set_size: callable,
    get_pos: callable,
    set_pos: callable,
    start_pos: float,
) -> list[str]:
    """
    对一个轴方向上的子节点列表进行尺寸分配和位置设定。

    规则优先级（从高到低）：
      1. 固定尺寸（constraints.fixed_*）：不参与分配，直接使用
      2. 约束范围（min_* / max_*）：参与弹性分配，但结果受限
      3. 弹性权重（constraints.flex_weight）：剩余空间按权重分配

    返回错误信息列表（空列表表示成功）。
    """
    errors: list[str] = []

    # ── 第一轮：收集固定尺寸，计算剩余空间 ──────────────────
    fixed_total = 0.0
    flex_children: list[Space] = []

    for child in children:
        c = child.constraints
        fixed = _get_fixed(c, get_size)
        if fixed is not None:
            set_size(child, fixed)
            fixed_total += fixed
        else:
            flex_children.append(child)

    remaining = parent_size - fixed_total

    if remaining < -DIMENSION_TOLERANCE:
        errors.append(
            f"{get_path_names(parent)}：固定尺寸之和 {fixed_total:.1f} mm "
            f"超过父节点尺寸 {parent_size:.1f} mm"
        )
        # 仍然继续，给弹性子节点分配 0，保证树结构完整
        remaining = 0.0

    # ── 第二轮：弹性子节点按权重分配剩余空间 ────────────────
    if flex_children:
        total_weight = sum(
            getattr(c.constraints, "flex_weight", 1.0) or 1.0
            for c in flex_children
        )
        if total_weight <= 0:
            total_weight = len(flex_children)

        unit = remaining / total_weight

        for child in flex_children:
            c = child.constraints
            weight = getattr(c, "flex_weight", 1.0) or 1.0
            raw = unit * weight

            # 约束夹紧
            lo = _get_min(c, get_size)
            hi = _get_max(c, get_size)
            clamped = raw
            if lo is not None and clamped < lo:
                clamped = lo
            if hi is not None and clamped > hi:
                clamped = hi

            if abs(clamped - raw) > DIMENSION_TOLERANCE:
                errors.append(
                    f"{get_path_names(child)}：弹性分配 {raw:.1f} mm "
                    f"被约束夹紧至 {clamped:.1f} mm"
                )

            set_size(child, clamped)

    # ── 第三轮：依次设定位置（紧贴排列）────────────────────
    cursor = start_pos
    for child in children:
        set_pos(child, cursor)
        cursor += get_size(child)

    return errors


# ================================================================
# 内部：约束字段访问工具
# ================================================================

def _get_fixed(constraints, get_size) -> Optional[float]:
    """
    如果约束要求固定尺寸（min == max），返回该值，否则返回 None。
    """
    lo = _get_min(constraints, get_size)
    hi = _get_max(constraints, get_size)
    if lo is not None and hi is not None and abs(lo - hi) < DIMENSION_TOLERANCE:
        return lo
    return None


def _get_min(constraints, get_size) -> Optional[float]:
    """从约束对象中提取与当前轴对应的 min 值。"""
    if get_size.__name__ == "_get_w":
        return getattr(constraints, "min_width", None)
    if get_size.__name__ == "_get_h":
        return getattr(constraints, "min_height", None)
    if get_size.__name__ == "_get_d":
        return getattr(constraints, "min_depth", None)
    return None


def _get_max(constraints, get_size) -> Optional[float]:
    if get_size.__name__ == "_get_w":
        return getattr(constraints, "max_width", None)
    if get_size.__name__ == "_get_h":
        return getattr(constraints, "max_height", None)
    if get_size.__name__ == "_get_d":
        return getattr(constraints, "max_depth", None)
    return None


# 轴访问器（带 __name__ 供 _get_min/_get_max 识别）
def _get_w(n: Space) -> float: return n.width
def _set_w(n: Space, v: float): n.width  = v
def _get_px(n: Space) -> float: return n.x
def _set_px(n: Space, v: float): n.x = v

def _get_h(n: Space) -> float: return n.height
def _set_h(n: Space, v: float): n.height = v
def _get_py(n: Space) -> float: return n.y
def _set_py(n: Space, v: float): n.y = v

def _get_d(n: Space) -> float: return n.depth
def _set_d(n: Space, v: float): n.depth  = v
def _get_pz(n: Space) -> float: return n.z
def _set_pz(n: Space, v: float): n.z = v


# ================================================================
# 内部：继承父节点非分割轴的尺寸
# ================================================================

def _inherit_non_split_dims(parent: Space, child: Space, direction: SplitDirection):
    """
    非分割轴方向上，子节点继承父节点的尺寸和起始坐标。

    示例：父节点沿 X 切分（SPLIT_X），则所有子节点的 height / depth
    以及 y / z 起点都与父节点相同。
    """
    if not is_split_along_x(direction):
        child.height = parent.height
        child.depth  = parent.depth
        child.y      = parent.y
        child.z      = parent.z

    if not is_split_along_y(direction):
        child.width = parent.width
        child.depth = parent.depth
        child.x     = parent.x
        child.z     = parent.z

    if not is_split_along_z(direction):
        child.width  = parent.width
        child.height = parent.height
        child.x      = parent.x
        child.y      = parent.y


# ================================================================
# 核心求解：单节点向下传播
# ================================================================

def _resolve_node(node: Space) -> list[str]:
    """
    对 node 的直接子节点进行尺寸求解和位置设定。
    只处理一层，递归由 resolve() 的 DFS 遍历保证。
    返回错误信息列表。
    """
    if node.is_leaf or not node.children:
        return []

    direction = node.split_direction
    children  = node.children
    errors: list[str] = []

    # 先让每个子节点继承非分割轴的尺寸
    for child in children:
        _inherit_non_split_dims(node, child, direction)

    # 再对分割轴做弹性分配
    if is_split_along_x(direction):
        errors = _resolve_split_axis(
            node, children,
            parent_size=node.width,
            get_size=_get_w, set_size=_set_w,
            get_pos=_get_px, set_pos=_set_px,
            start_pos=node.x,
        )
    elif is_split_along_y(direction):
        errors = _resolve_split_axis(
            node, children,
            parent_size=node.height,
            get_size=_get_h, set_size=_set_h,
            get_pos=_get_py, set_pos=_set_py,
            start_pos=node.y,
        )
    elif is_split_along_z(direction):
        errors = _resolve_split_axis(
            node, children,
            parent_size=node.depth,
            get_size=_get_d, set_size=_set_d,
            get_pos=_get_pz, set_pos=_set_pz,
            start_pos=node.z,
        )
    else:
        # split_direction == NONE 但有子节点
        # 子节点全部继承父节点完整尺寸（叠加放置，由上层业务决定）
        for child in children:
            child.width  = node.width
            child.height = node.height
            child.depth  = node.depth
            child.x, child.y, child.z = node.x, node.y, node.z

    return errors


# ================================================================
# 主入口
# ================================================================

def resolve(
    root: Space,
    *,
    validate_before: bool = True,
    validate_after:  bool = True,
    dirty_only:      bool = False,
) -> ResolveResult:
    """
    完整求解入口：约束传播 → 尺寸分配 → 位置设定 → 标记 CLEAN。

    Args:
        root:             空间树根节点
        validate_before:  求解前先跑 space/validators，有 ERROR 则中止
        validate_after:   求解后再跑一次校验，确认结果合法
        dirty_only:       True → 只求解 dirty_flag != CLEAN 的节点及其子树
                          False → 全量求解（首次构建或强制刷新时使用）

    Returns:
        ResolveResult，调用 .ok 判断是否成功

    典型调用：
        # solver 前置调用（全量）
        result = resolve(cabinet_root, validate_before=True)
        if not result.ok:
            result.print_summary()
            return

        # incremental_solver 调用（局部）
        result = resolve(dirty_root, dirty_only=True, validate_before=False)
    """
    all_errors: list[str] = []

    # ── 前置校验 ────────────────────────────────────────────
    pre_validation: Optional[ValidationResult] = None
    if validate_before:
        pre_validation = validate(root, stop_on_error=True)
        if not pre_validation.is_valid:
            return ResolveResult(
                status=ResolveStatus.FAILED,
                validation=pre_validation,
                errors=[str(e) for e in pre_validation.errors],
            )

    # ── DFS 自顶向下求解 ─────────────────────────────────────
    solved_nodes: list[NodeResult] = []

    for node in walk_dfs(root, order="pre"):

        # dirty_only 模式：跳过干净节点
        if dirty_only and not node.is_dirty:
            continue

        was_dirty = node.is_dirty

        # 对本节点的子节点进行尺寸分配
        node_errors = _resolve_node(node)
        all_errors.extend(node_errors)

        # 记录求解快照
        solved_nodes.append(NodeResult(
            node_id=node.id,
            node_path=get_path_names(node),
            width=node.width,
            height=node.height,
            depth=node.depth,
            x=node.x,
            y=node.y,
            z=node.z,
            was_dirty=was_dirty,
        ))

        # 标记为 CLEAN
        node.dirty_flag = DirtyFlag.CLEAN

    # ── 后置校验 ─────────────────────────────────────────────
    post_validation: Optional[ValidationResult] = None
    if validate_after:
        post_validation = validate(root, stop_on_error=False)

    # ── 汇总状态 ─────────────────────────────────────────────
    has_errors   = bool(all_errors) or (
        post_validation is not None and not post_validation.is_valid
    )
    has_warnings = post_validation is not None and post_validation.has_warnings

    if has_errors:
        status = ResolveStatus.FAILED
    elif has_warnings:
        status = ResolveStatus.PARTIAL
    else:
        status = ResolveStatus.OK

    return ResolveResult(
        status=status,
        nodes=solved_nodes,
        validation=post_validation or pre_validation,
        errors=all_errors,
    )


def resolve_incremental(
    root: Space,
    dirty_nodes: Optional[list[Space]] = None,
) -> ResolveResult:
    """
    局部增量求解入口，供 incremental_solver 调用。

    dirty_nodes 不为 None 时，只对这些节点所在的子树重新求解，
    其余节点保持 CLEAN 不变。

    实现策略：
      1. 找到每个 dirty 节点的最高脏祖先（避免重复求解同一子树）
      2. 对这些子树根节点分别调用 resolve()
      3. 合并所有 ResolveResult
    """
    if dirty_nodes is None:
        from .tree import find_dirty
        dirty_nodes = find_dirty(root)

    if not dirty_nodes:
        # 没有脏节点，直接返回 OK
        return ResolveResult(status=ResolveStatus.OK)

    # 找每棵脏子树的最高入口（避免对同一节点重复求解）
    subtree_roots = _find_subtree_roots(dirty_nodes)

    merged = ResolveResult(status=ResolveStatus.OK)

    for subtree_root in subtree_roots:
        result = resolve(
            subtree_root,
            validate_before=False,   # 增量求解不做全量前置校验，由 cabinet_solver 统一管理
            validate_after=True,
            dirty_only=True,
        )
        merged.nodes.extend(result.nodes)
        merged.errors.extend(result.errors)

        if result.status == ResolveStatus.FAILED:
            merged.status = ResolveStatus.FAILED
        elif result.status == ResolveStatus.PARTIAL and merged.status == ResolveStatus.OK:
            merged.status = ResolveStatus.PARTIAL

    return merged


def _find_subtree_roots(dirty_nodes: list[Space]) -> list[Space]:
    """
    从脏节点列表中找出互不为祖先关系的最高入口节点。
    避免同一子树被重复求解。

    示例：
        dirty = [A, A.child, A.child.child, B]
        → subtree_roots = [A, B]
    """
    dirty_ids = {n.id for n in dirty_nodes}
    roots = []
    for node in dirty_nodes:
        # 如果任何一个祖先也在 dirty 集合中，则跳过本节点
        is_descendant = any(
            anc.id in dirty_ids
            for anc in _iter_ancestors_ids(node)
        )
        if not is_descendant:
            roots.append(node)
    return roots


def _iter_ancestors_ids(node: Space):
    """向上遍历祖先（不含自身），yield 每个祖先节点。"""
    current = node.parent
    while current is not None:
        yield current
        current = current.parent
