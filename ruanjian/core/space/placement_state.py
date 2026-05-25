# -*- coding: utf-8 -*-
"""板件在空间变更后的放置语义状态（写入 ``Panel.metadata``，不删板件）。"""

from __future__ import annotations

METADATA_KEY = "placement_state"

PLACED = "PLACED"
INVALID = "INVALID"
UNPLACED = "UNPLACED"
NEEDS_RELAYOUT = "NEEDS_RELAYOUT"
# 锚定板：空间尺寸不足等仍保留在树上，仅作警示（与 INVALID 区分）
BLOCKED = "BLOCKED"


def get_placement_state(panel: object) -> str | None:
    md = getattr(panel, "metadata", None)
    if not isinstance(md, dict):
        return None
    v = md.get(METADATA_KEY)
    return str(v) if v is not None else None


def set_placement_state(panel: object, state: str | None) -> None:
    md = getattr(panel, "metadata", None)
    if not isinstance(md, dict):
        md = {}
        setattr(panel, "metadata", md)
    if state is None:
        md.pop(METADATA_KEY, None)
    else:
        md[METADATA_KEY] = state
