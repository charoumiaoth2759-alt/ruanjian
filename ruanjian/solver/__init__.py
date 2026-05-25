# -*- coding: utf-8 -*-
"""柜体求解门面包：``solve(space_tree, request?) -> SolveResult``。"""

from core.solver.cabinet_solver import (
    CabinetResult,
    CabinetSolveRequest,
    CabinetSolveResult,
    PanelList,
    SolveResult,
    SolverResult,
    solve,
    solve_from_space,
)

__all__ = [
    "solve",
    "solve_from_space",
    "SolveResult",
    "CabinetSolveResult",
    "CabinetSolveRequest",
    "CabinetResult",
    "SolverResult",
    "PanelList",
]
