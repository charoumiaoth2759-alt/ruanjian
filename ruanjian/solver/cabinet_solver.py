# -*- coding: utf-8 -*-
"""
柜体统一求解门面：``solve(space_tree, request=None) -> SolveResult``。

在 ``core.solver`` 生成结果之上，追加各 ``Space.panels`` 与 ``Space.panel_groups`` 内挂载的板件，
供 3D 显示；无 PySide、无总线。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.space.space_models import Space
from core.space.tree import walk_dfs
from core.solver.cabinet_solver import (
    CabinetSolveRequest,
    CabinetSolveResult,
    SolveResult,
    solve as _solve_core,
)


def _flatten_attached_panels(root: Space) -> list[Any]:
    """收集树上各节点 ``panels`` 与 ``panel_groups`` 内的板件（DFS 前序）。"""
    out: list[Any] = []
    for node in walk_dfs(root):
        ps = getattr(node, "panels", None)
        if ps:
            out.extend(list(ps))
        for grp in getattr(node, "panel_groups", None) or []:
            gp = getattr(grp, "panels", None)
            if gp:
                out.extend(list(gp))
    return out


def _attached_panel_groups(root: Space) -> list[Any]:
    """收集树上各节点 ``panel_groups`` 引用（去重，按 DFS 顺序）。"""
    seen: set[int] = set()
    out: list[Any] = []
    for node in walk_dfs(root):
        for grp in getattr(node, "panel_groups", None) or []:
            gid = id(grp)
            if gid in seen:
                continue
            seen.add(gid)
            out.append(grp)
    return out


def solve(
    space_tree: Space | None,
    request: CabinetSolveRequest | None = None,
) -> SolveResult:
    """``Space`` 树 + 可选请求 → ``SolveResult``（含 ``Space.panels`` / ``panel_groups`` 挂载项）。"""
    result = _solve_core(space_tree, request)
    if space_tree is None:
        return result

    extra_panels = _flatten_attached_panels(space_tree)
    attached_groups = _attached_panel_groups(space_tree)
    gen_gid = {id(g) for g in result.panel_groups}
    extra_groups = [g for g in attached_groups if id(g) not in gen_gid]

    if not extra_panels and not extra_groups:
        return result

    merged_panels = list(result.panel_list) + extra_panels if extra_panels else list(result.panel_list)
    merged_groups = list(result.panel_groups) + extra_groups
    return replace(
        result,
        panel_list=merged_panels,
        panel_groups=merged_groups,
    )
