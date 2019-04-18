from typing import Optional, Tuple, Sequence
from dataclasses import dataclass
from enum import Enum, unique
from pvtrace.geometry.geometry import Geometry
from pvtrace.geometry.intersection import Intersection
#from pvtrace.material.material import Material
from pvtrace.scene.node import Node
import logging
logger = logging.getLogger(__name__)


@unique
class Kind(Enum):
    """ Additional data passed to the interaction code from the tracer. SURFACE value
    indicates that the ray is at a material boundary and PATH indicates that the ray 
    is contained inside or outside a material.
    """
    PATH = 1
    SURFACE = 2


@dataclass
class StepContext(object):
    """ Context summerising the next possible steps for a ray.
    """
    #: Node geometry containing the ray
    container: Node
    #: All intersections
    all_intersections: Sequence[Intersection]
    #: The index of the next intersection
    next_index: int

    def next_intersection(self):
        return self.all_intersections[self.next_index]


@dataclass
class Context(object):
    """ Context carrying additional information from the tracer to the 
    material interactions.
    """
    #: Metadata from ray tracer to be used in interaction decision tree
    kind: Kind

    #: The containing object when kind is PATH
    container: Optional[Geometry]

    #: Location of next intersection when kind is PATH or SURFACE
    end_path: Optional[Tuple]

    #: The surface normal for the interaction when kind is SURFACE
    normal: Optional[Tuple]

    #: The node which defines the coordinate system of the normal when kind is SURFACE
    normal_node: Optional[Node]

    #: Refractive index of the departing material when kind is SURFACE
    n1: Optional[float]

    #: Refractive index of the destination material when kind is SURFACE
    n2: Optional[float]

