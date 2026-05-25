# -*- coding: utf-8 -*-
"""空间引擎 —— 房间数据模型"""
from __future__ import annotations
import math, uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class StraightWall:
    x1: float; y1: float
    x2: float; y2: float
    thickness: float = 120.0
    wall_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    @property
    def length(self): return math.hypot(self.x2-self.x1, self.y2-self.y1)

    @property
    def angle_deg(self): return math.degrees(math.atan2(self.y2-self.y1, self.x2-self.x1))

    def wall_polygon_points(self) -> List[Tuple[float,float]]:
        dx, dy = self.x2-self.x1, self.y2-self.y1
        L = math.hypot(dx, dy)
        if L < 1e-6: return [(self.x1,self.y1)]*4
        nx, ny = -dy/L, dx/L
        h = self.thickness/2.0
        ox, oy = nx*h, ny*h
        return [(self.x1+ox,self.y1+oy),(self.x2+ox,self.y2+oy),
                (self.x2-ox,self.y2-oy),(self.x1-ox,self.y1-oy)]

    def __repr__(self):
        return f"StraightWall({self.wall_id}) ({self.x1:.0f},{self.y1:.0f})→({self.x2:.0f},{self.y2:.0f}) L={self.length:.0f} T={self.thickness:.0f}"


class Room:
    def __init__(self, name: str = "房间"):
        self.name = name
        self.room_id = str(uuid.uuid4())[:8]
        self._walls: List[StraightWall] = []

    def add_wall(self, x1, y1, x2, y2, thickness=120.0) -> StraightWall:
        w = StraightWall(x1=x1,y1=y1,x2=x2,y2=y2,thickness=thickness)
        self._walls.append(w); return w

    def remove_wall(self, wall_id: str) -> bool:
        n = len(self._walls)
        self._walls = [w for w in self._walls if w.wall_id != wall_id]
        return len(self._walls) < n

    def remove_wall_by_segment(
        self, x1: float, y1: float, x2: float, y2: float, tol: float = 1.0
    ) -> bool:
        """按中心线端点删除一段墙（与 wall_id 无关，用于旧图元）。"""
        def near(a: float, b: float) -> bool:
            return abs(a - b) <= tol
        for w in list(self._walls):
            if (
                near(w.x1, x1) and near(w.y1, y1) and near(w.x2, x2) and near(w.y2, y2)
            ) or (
                near(w.x2, x1) and near(w.y2, y1) and near(w.x1, x2) and near(w.y1, y2)
            ):
                return self.remove_wall(w.wall_id)
        return False

    def get_wall(self, wall_id: str) -> Optional[StraightWall]:
        return next((w for w in self._walls if w.wall_id==wall_id), None)

    def clear(self): self._walls.clear()

    @property
    def walls(self): return list(self._walls)

    @property
    def wall_count(self): return len(self._walls)

    def __repr__(self): return f"Room({self.name!r}, {self.wall_count} walls)"
