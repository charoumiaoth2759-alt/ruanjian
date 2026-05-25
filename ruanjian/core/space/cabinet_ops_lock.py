# -*- coding: utf-8 -*-
"""
柜体叶空间「用户允许编辑」开关（与结构 OCCUPIED / 放置 ALLOWED 视觉区分）。

- 结构 ``infer_space_state == OCCUPIED`` 且未显式允许时：拾取与柜体加板/分割等命令拦截；
- 用户在 3D / 参数视图中单击该叶 AABB 可在允许/锁定间切换（metadata 布尔）。
"""

from __future__ import annotations

from typing import Any

from .enums import SpaceState as PickSpaceState
from .space_models import Space
from .space_state import infer_space_state
from .tree import iter_leaves

UI_METADATA_CABINET_OPS_USER_ALLOW = "cabinet_ops_user_allow"

# 经 ``run_cabinet_dispatch_command`` 与属性面板「添加/修改」等路径的柜体编辑命令
GATED_CABINET_COMMAND_NAMES: frozenset[str] = frozenset(
    {
        "add_left_panel",
        "add_right_panel",
        "add_top_panel",
        "add_bottom_panel",
        "add_back_panel",
        "add_door",
        "add_drawer",
        "apply_add_or_modify",
    }
)

CABINET_OPS_LOCKED_HINT = (
    "当前空间为占用锁定状态，请单击空间盒切换至允许编辑（ALLOWED）；"
    "或按住 Ctrl 再单击可在允许/锁定间切换。"
)


def _metadata_dict(space: Space) -> dict[str, Any]:
    md = getattr(space, "metadata", None)
    if not isinstance(md, dict):
        md = {}
        setattr(space, "metadata", md)
    return md


def read_cabinet_ops_user_allow(space: Space) -> bool:
    """结构 OCCUPIED 叶是否已用户解锁（metadata 显式为真）。"""
    md = getattr(space, "metadata", None)
    if not isinstance(md, dict):
        return False
    v = md.get(UI_METADATA_CABINET_OPS_USER_ALLOW)
    if v is True:
        return True
    if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes"):
        return True
    return False


def write_cabinet_ops_user_allow(space: Space, allowed: bool) -> None:
    """写入解锁状态；``False`` 时移除键（与默认锁定语义一致）。"""
    md = _metadata_dict(space)
    if allowed:
        md[UI_METADATA_CABINET_OPS_USER_ALLOW] = True
    else:
        md.pop(UI_METADATA_CABINET_OPS_USER_ALLOW, None)


def toggle_cabinet_ops_user_allow(space: Space) -> bool:
    """翻转允许位，返回新值（``True``=允许编辑）。"""
    new_val = not read_cabinet_ops_user_allow(space)
    write_cabinet_ops_user_allow(space, new_val)
    return new_val


def cabinet_leaf_user_ops_allowed(space: Space) -> bool:
    """供 ``ConstraintEngine`` 拾取：非 OCCUPIED 叶始终可拾取；OCCUPIED 须用户解锁。"""
    if infer_space_state(space) is not PickSpaceState.OCCUPIED:
        return True
    return read_cabinet_ops_user_allow(space)


def is_space_cabinet_ops_locked(space: Space | None) -> bool:
    """当前目标空间是否因 OCCUPIED 且未解锁而不可编辑。"""
    if space is None:
        return False
    if infer_space_state(space) is not PickSpaceState.OCCUPIED:
        return False
    return not read_cabinet_ops_user_allow(space)


def cabinet_target_space_from_ctx(ctx: dict[str, Any]) -> Space | None:
    """命令目标空间：``current_space``（与 ``handle_add_left_panel`` 一致）→ ``active_space`` → root。"""
    selection = ctx.get("selection")
    if selection is not None:
        s = getattr(selection, "current_space", None)
        if isinstance(s, Space):
            return s
        s = getattr(selection, "active_space", None)
        if isinstance(s, Space):
            return s
    root = ctx.get("root_space")
    if isinstance(root, Space):
        return root
    project = ctx.get("project")
    if project is not None:
        rs = getattr(project, "root_space", None)
        if isinstance(rs, Space):
            return rs
    return None


def cabinet_command_should_respect_ops_lock(command_name: str) -> bool:
    return command_name in GATED_CABINET_COMMAND_NAMES


def ctx_cabinet_ops_locked(ctx: dict[str, Any] | None) -> bool:
    if not ctx:
        return False
    return is_space_cabinet_ops_locked(cabinet_target_space_from_ctx(ctx))


def ray_hit_space_aabb_t(
    space: Space,
    ox: float,
    oy: float,
    oz: float,
    dx: float,
    dy: float,
    dz: float,
    *,
    eps: float = 1e-9,
) -> float | None:
    """
    射线与 ``space`` 轴对齐盒相交时返回非负入射参数 ``t``（沿单位方向长度），否则 ``None``。
    """
    x0, y0, z0 = float(space.x), float(space.y), float(space.z)
    x1 = x0 + float(space.width)
    y1 = y0 + float(space.height)
    z1 = z0 + float(space.depth)
    t_min = 0.0
    t_max = float("inf")
    for p0, p1, o, d in (
        (x0, x1, ox, dx),
        (y0, y1, oy, dy),
        (z0, z1, oz, dz),
    ):
        if abs(d) < eps:
            if o < p0 - eps or o > p1 + eps:
                return None
            continue
        inv = 1.0 / d
        t0 = (p0 - o) * inv
        t1 = (p1 - o) * inv
        t_near = min(t0, t1)
        t_far = max(t0, t1)
        t_min = max(t_min, t_near)
        t_max = min(t_max, t_far)
        if t_min > t_max:
            return None
    if t_max < 0.0:
        return None
    t_hit = t_min if t_min >= 0.0 else t_max
    return float(t_hit) if t_hit >= 0.0 else None


def pick_closest_structural_occupied_leaf_for_ray(
    root: Space,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> Space | None:
    """沿射线命中 AABB 且结构为 OCCUPIED 的 **叶** 中 ``t`` 最小者；用于单击切换允许编辑。"""
    ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])
    dx, dy, dz = float(direction[0]), float(direction[1]), float(direction[2])
    ln = (dx * dx + dy * dy + dz * dz) ** 0.5
    if ln < 1e-12:
        return None
    dx, dy, dz = dx / ln, dy / ln, dz / ln
    best: Space | None = None
    best_t = float("inf")
    for leaf in iter_leaves(root):
        if infer_space_state(leaf) is not PickSpaceState.OCCUPIED:
            continue
        t_hit = ray_hit_space_aabb_t(leaf, ox, oy, oz, dx, dy, dz)
        if t_hit is not None and t_hit < best_t:
            best_t = t_hit
            best = leaf
    return best


def cabinet_space_constraint_engine() -> "ConstraintEngine":
    """与柜体占用锁一致的拾取 / 放置校验引擎（``extra_rules``）。"""
    from .constraint_engine import ConstraintEngine

    return ConstraintEngine(
        extra_rules=[lambda sp, board: cabinet_leaf_user_ops_allowed(sp)]
    )


def unlock_closest_occ_leaf_if_locked(
    root: Space,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> Space | None:
    """
    若射线命中的最近结构 OCCUPIED 叶处于锁定（未用户解锁），则置为允许编辑并返回该叶。

    用于主 3D / 参数视图 **普通单击** 从科技蓝锁定态进入 ALLOWED 配色；已解锁时返回 ``None``。
    """
    leaf = pick_closest_structural_occupied_leaf_for_ray(root, origin, direction)
    if leaf is None:
        return None
    if read_cabinet_ops_user_allow(leaf):
        return None
    write_cabinet_ops_user_allow(leaf, True)
    return leaf


def reset_cabinet_ops_visual_to_locked_after_left_panel_added(space: Space) -> None:
    """
    添加左侧板后清除用户「允许编辑」标记。

    结构已为 OCCUPIED 时，``space_visual_mapper`` 即显示科技蓝面片 (70,140,255) α 60/255、
    棱线蓝 (35,100,230)；再编辑前请 **单击** 空间盒解锁（ALLOWED），或 **Ctrl+单击** 在允许/锁定间切换。
    """
    write_cabinet_ops_user_allow(space, False)


__all__ = [
    "CABINET_OPS_LOCKED_HINT",
    "GATED_CABINET_COMMAND_NAMES",
    "UI_METADATA_CABINET_OPS_USER_ALLOW",
    "cabinet_command_should_respect_ops_lock",
    "cabinet_leaf_user_ops_allowed",
    "cabinet_space_constraint_engine",
    "cabinet_target_space_from_ctx",
    "ctx_cabinet_ops_locked",
    "is_space_cabinet_ops_locked",
    "pick_closest_structural_occupied_leaf_for_ray",
    "read_cabinet_ops_user_allow",
    "reset_cabinet_ops_visual_to_locked_after_left_panel_added",
    "toggle_cabinet_ops_user_allow",
    "unlock_closest_occ_leaf_if_locked",
    "write_cabinet_ops_user_allow",
]
