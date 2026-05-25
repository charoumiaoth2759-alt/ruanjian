from __future__ import annotations

from typing import Any

from .enums import SpaceType
from .space_models import Space


class SpaceSplitter:
    """
    空间切分器（预留）：按板件占用生成子空间。

    锚定板（``PlacementMode.ANCHOR_FIXED``）不参与切分。
    """

    def split(self, space: Space, board: Any) -> list[Space]:
        """对一个空间进行切分，返回新生成的子空间。"""
        from ..constants.enums import PlacementMode

        pm = getattr(board, "placement_mode", None)
        if pm == PlacementMode.ANCHOR_FIXED or getattr(pm, "value", None) == "anchor_fixed":
            return []

        setattr(space, "is_occupied", True)

        children = self._generate_sub_spaces(space, board)
        if not hasattr(space, "children") or space.children is None:
            space.children = []
        space.children.extend(children)
        return children

    def _generate_sub_spaces(self, space: Space, board: Any) -> list[Space]:
        children: list[Space] = []

        bx = float(getattr(board, "x", 0.0))
        by = float(getattr(board, "y", 0.0))
        bz = float(getattr(board, "z", 0.0))

        bw = float(getattr(board, "width", 0.0))
        bh = float(getattr(board, "height", 0.0))
        bd = float(getattr(board, "depth", 0.0) or getattr(board, "thickness", 0.0))

        sx = float(space.x)
        sy = float(space.y)
        sz = float(space.z)

        sw = float(space.width)
        sh = float(space.height)
        sd = float(space.depth)

        right_w = (sx + sw) - (bx + bw)
        if right_w > 0:
            children.append(
                self._create_space(
                    x=bx + bw,
                    y=sy,
                    z=sz,
                    width=right_w,
                    height=sh,
                    depth=sd,
                )
            )

        top_h = (sy + sh) - (by + bh)
        if top_h > 0:
            children.append(
                self._create_space(
                    x=sx,
                    y=by + bh,
                    z=sz,
                    width=sw,
                    height=top_h,
                    depth=sd,
                )
            )

        front_d = (sz + sd) - (bz + bd)
        if front_d > 0:
            children.append(
                self._create_space(
                    x=sx,
                    y=sy,
                    z=bz + bd,
                    width=sw,
                    height=sh,
                    depth=front_d,
                )
            )

        return children

    def _create_space(
        self,
        x: float,
        y: float,
        z: float,
        width: float,
        height: float,
        depth: float,
    ) -> Space:
        return Space(
            x=x,
            y=y,
            z=z,
            width=width,
            height=height,
            depth=depth,
            space_type=SpaceType.NORMAL,
        )
