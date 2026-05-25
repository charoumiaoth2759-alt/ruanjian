from dataclasses import dataclass


@dataclass
class SpaceConstraint:

    min_width: float = 0.0

    min_height: float = 0.0

    min_depth: float = 0.0

    max_width: float = 999999.0

    max_height: float = 999999.0

    max_depth: float = 999999.0