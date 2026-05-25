from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .space_models import Space


@dataclass
class SpaceMetricsConfig:
    """
    评分参数配置（可调优核心🔥）
    """

    fit_weight: float = 0.4
    waste_weight: float = 0.3
    edge_weight: float = 0.2
    constraint_weight: float = 0.1


class SpaceMetrics:
    """
    空间评分系统（核心评估器🔥）

    职责：
    1. 评估空间利用率
    2. 计算浪费程度
    3. 评估贴边优先级
    4. 输出 constraint 适配评分
    """

    def __init__(self, config: SpaceMetricsConfig = SpaceMetricsConfig()):
        self.config = config

    # ==========================================================
    # 主评分入口
    # ==========================================================

    @staticmethod
    def score_left_face_ray(space: "Space", t_hit: float, vol: float) -> float:
        """左面射线拾取：更近的命中优先，容积作极弱 tie-break。"""
        _ = vol
        return -float(t_hit) + 1e-12 * float(
            space.width * space.height * space.depth
        )

    @staticmethod
    def score_world_point(
        space: "Space", wx: float, wy: float, wz: float
    ) -> float:
        """世界点拾取：离空间 AABB 中心越近分越高。"""
        cx = float(space.x) + float(space.width) * 0.5
        cy = float(space.y) + float(space.height) * 0.5
        cz = float(space.z) + float(space.depth) * 0.5
        d2 = (wx - cx) ** 2 + (wy - cy) ** 2 + (wz - cz) ** 2
        return -d2

    def evaluate(self, space: "Space", board: Any) -> float:
        """
        返回 0~1 的空间匹配评分
        """

        fit_score = self.fit_ratio(space, board)
        waste_score = self.waste_score(space, board)
        edge_score = self.edge_score(space)
        constraint_score = self.constraint_score(space, board)

        score = (
            fit_score * self.config.fit_weight +
            waste_score * self.config.waste_weight +
            edge_score * self.config.edge_weight +
            constraint_score * self.config.constraint_weight
        )

        return self._clamp(score)

    # ==========================================================
    # 1. 空间利用率（核心）
    # ==========================================================

    def fit_ratio(self, space: "Space", board: Any) -> float:
        """
        板件体积 / 空间体积
        """

        space_vol = space.width * space.height * space.depth
        bd = float(getattr(board, "depth", 0.0) or getattr(board, "thickness", 0.0))
        board_vol = float(board.width) * float(board.height) * bd

        if space_vol <= 0:
            return 0.0

        return min(board_vol / space_vol, 1.0)

    # ==========================================================
    # 2. 浪费评分（越小越好 → 转成分数）
    # ==========================================================

    def waste_score(self, space: "Space", board: Any) -> float:
        """
        空间剩余浪费惩罚
        """

        dx = space.width - board.width
        dy = space.height - board.height
        bd = float(getattr(board, "depth", 0.0) or getattr(board, "thickness", 0.0))
        dz = space.depth - bd

        waste_volume = max(dx, 0) * max(dy, 0) * max(dz, 0)

        # 转换为 0~1 分数（越小越好）
        return 1.0 / (1.0 + waste_volume)

    # ==========================================================
    # 3. 贴边评分（工业排样核心🔥）
    # ==========================================================

    def edge_score(self, space: "Space") -> float:
        """
        越靠左/靠底/靠前 → 分越高
        """

        x = getattr(space, "x", 0.0)
        y = getattr(space, "y", 0.0)
        z = getattr(space, "z", 0.0)

        x_score = 1.0 / (1.0 + x)
        y_score = 1.0 / (1.0 + y)
        z_score = 1.0 / (1.0 + z)

        return (x_score + y_score + z_score) / 3.0

    # ==========================================================
    # 4. 约束适配评分（对接 ConstraintEngine）
    # ==========================================================

    def constraint_score(self, space: "Space", board: Any) -> float:
        """
        如果空间越符合工艺约束 → 分越高
        """

        engine = getattr(board, "constraint_engine", None)

        if engine is None:
            return 1.0

        try:
            result = engine.validate(space, board)

            # 如果 validate 返回 bool
            if isinstance(result, bool):
                return 1.0 if result else 0.0

            # 如果是结构化结果
            return getattr(result, "score", 1.0)

        except Exception:
            return 0.0

    # ==========================================================
    # 5. 工具函数
    # ==========================================================

    def _clamp(self, value: float) -> float:
        """
        保证评分在 0~1
        """
        return max(0.0, min(1.0, value))