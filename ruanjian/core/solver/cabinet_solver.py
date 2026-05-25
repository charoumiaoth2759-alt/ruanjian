# -*- coding: utf-8 -*-
"""
柜体求解：纯函数引擎 ``solve(space_tree, request=None) -> SolveResult``。

本模块不依赖宿主图形栈；不 ``publish``、不调用展示层刷新。
宿主侧若需连锁动作，读取 ``SolveResult.events``、``panel_groups``、``panel_list`` 等字段，
由 ``commands`` 再 ``publish`` 纯数据事件。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, TypeAlias

from ..space.space_models import Space
from ..space.tree import walk_dfs


def _panel_key(panel: Any) -> str:
    pid = getattr(panel, "id", None)
    if pid is not None and str(pid):
        return str(pid)
    return str(id(panel))


def _flatten_panel_groups(panel_groups: list[Any] | None) -> list[Any]:
    """将各 ``PanelGroup.panels`` 展平为单一列表（顺序：组顺序 × 组内顺序）。"""
    out: list[Any] = []
    for group in panel_groups or []:
        out.extend(getattr(group, "panels", []) or [])
    return out


def _merge_unique_panels(*sequences: list[Any] | None) -> list[Any]:
    """按 ``panel.id``（无则 ``id(panel)``）去重合并，保留各序列中首次出现顺序。"""
    seen: set[str] = set()
    ordered: list[Any] = []
    for seq in sequences:
        for p in seq or []:
            k = _panel_key(p)
            if k in seen:
                continue
            seen.add(k)
            ordered.append(p)
    return ordered


@dataclass(frozen=True)
class CabinetSolveRequest:
    """可选求解请求（纯数据）。solver 不解析宿主控件，仅携带命令名与载荷供扩展。"""

    command_name: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SolveResult:
    """
    一次求解的纯数据输出。

    - ``spaces``: 本次求解所遍历的 ``Space`` 列表（``walk_dfs`` 前序）
    - ``panel_groups``: 按 Space 分组的板件（与 ``GenerateResult.groups`` 一致）
    - ``panel_list``: 展平后的板件列表（便于旧代码与 3D 遍历）
    - ``new_space_tree``: 若求解改写空间树则填入，否则 ``None``
    - ``constraints_result``: 约束检查等结构化结果（预留）
    - ``errors``: 人类可读错误条
    - ``events``: 建议由 ``commands`` 层转发的总线事件名字符串（如 ``SOLVE_COMPLETED``）
    """

    success: bool
    new_space_tree: Space | None = None
    spaces: list[Any] = field(default_factory=list)
    panel_groups: list[Any] = field(default_factory=list)
    panel_list: list[Any] = field(default_factory=list)
    constraints_result: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    message: str | None = None

    @property
    def panels(self) -> list[Any]:
        """兼容旧字段名 ``panels``。"""
        return self.panel_list


PanelList: TypeAlias = list[Any]
CabinetResult: TypeAlias = SolveResult
SolverResult: TypeAlias = SolveResult


def solve(
    space_tree: Space | None,
    request: CabinetSolveRequest | None = None,
) -> SolveResult:
    """
    由 ``Space`` 树（及可选 ``CabinetSolveRequest``）生成 ``SolveResult``。

    不修改入参 ``space_tree``、不写 ``project``、不接触总线。
    ``request`` 预留供后续按命令分支求解；当前实现未分支。
    """
    print("[SOLVER] solve cabinet")
    _ = request
    if space_tree is None:
        return SolveResult(
            success=True,
            new_space_tree=None,
            spaces=[],
            panel_groups=[],
            panel_list=[],
            constraints_result=None,
            errors=[],
            events=["SOLVE_COMPLETED"],
            message=None,
        )
    try:
        # 直接调用 ``panel_generator.generate``，避免依赖 ``core.panel.generator`` 门面
        # （部署若漏掉 ``generator.py`` 会出现 ``No module named 'core.panel.generator'``）。
        from core.panel.panel_generator import collect_space_panels, generate

        res = generate(
            space_tree,
            dirty_only=False,
            include_dividers=True,
            include_skeleton=False,
        )
        groups = list(res.groups)
        # 展平生成器输出的组；再并入树上各 ``panel_groups``（防与 ``GenerateResult.groups`` 不同步）
        generator_flat = _flatten_panel_groups(groups)
        tree_flat = collect_space_panels(space_tree)
        panels = _merge_unique_panels(generator_flat, tree_flat)
        spaces_list = list(walk_dfs(space_tree, order="pre"))
        return SolveResult(
            success=True,
            new_space_tree=None,
            spaces=spaces_list,
            panel_groups=groups,
            panel_list=panels,
            constraints_result=None,
            errors=[],
            events=["SOLVE_COMPLETED"],
            message=None,
        )
    except Exception as exc:  # pragma: no cover - 防御性
        msg = str(exc)
        return SolveResult(
            success=False,
            new_space_tree=None,
            spaces=[],
            panel_groups=[],
            panel_list=[],
            constraints_result=None,
            errors=[msg],
            events=[],
            message=msg,
        )


solve_from_space = solve
CabinetSolveResult = SolveResult


def solve_cabinet(
    *,
    root_space: Space | None = None,
    panel_groups: list[Any] | None = None,
    request: CabinetSolveRequest | None = None,
) -> SolveResult:
    """
    门面：``solve(root_space)`` 后再并入命令层传入的 ``panel_groups`` 展平板件（去重），
    保证 ``panel_list`` 覆盖树上挂载的全部板件，供 3D 一次绘制多块。
    """
    result = solve(root_space, request=request)
    if not result.success or not panel_groups:
        return result
    cmd_flat = _flatten_panel_groups(list(panel_groups))
    if not cmd_flat:
        return result
    merged = _merge_unique_panels(result.panel_list, cmd_flat)
    return replace(result, panel_list=merged)
