from dataclasses import dataclass, field
from typing import Tuple
import numpy as np
from pvtrace.geometry.utils import distance_between, floats_close
import logging

logger = logging.getLogger(__name__)


class Intersection:
    pass


@dataclass
class Intersection:
    #: Coordinate system node of `point` (not necessarily the hit node). Intersections
    #: can be prepresented in different coordinate systems.
    coordsys: "Node"
    #: (x, y, z) intersection point
    point: Tuple[float]
    #: The node owning the geometry in which `point` is an intersection with its
    #: surface.
    hit: "Node"
    #: distance between the ray location and the hit point
    distance: float

    def to(self, other_node: "Node") -> Intersection:
        return Intersection(
            coordsys=other_node,
            point=self.coordsys.point_to_node(self.point, other_node),
            hit=self.hit,
            distance=self.distance,
        )

    def __eq__(self, other):
        return all(
            [
                self.coordsys == other.coordsys,
                np.allclose(self.point, other.point),
                self.hit == other.hit,
                floats_close(self.distance, other.distance),
            ]
        )
