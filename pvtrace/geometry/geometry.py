import abc
from typing import Optional, Sequence, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Geometry(abc.ABC):
    """ A three-dimensional shape. Geometry objects should be attached to
    Nodes to have a coordinate system in the scene graph. This is an 
    abstract base class which defined the methods subclasses with a 
    concrete geometry should implement.
    """

    @property
    @abc.abstractmethod
    def material(self):
        """ Return the material attached to this node.
        """
        pass

    @material.setter
    @abc.abstractmethod
    def material(self, new_value):
        """ Sets the material.
        """
        pass

    @abc.abstractmethod
    def is_on_surface(self, point: tuple) -> bool:
        """Returns `True` is the point is on the surface."""
        pass

    @abc.abstractmethod
    def contains(self, point: tuple) -> bool:
        """ Return True if the point is inside the shape.
        """
        pass

    @abc.abstractmethod
    def intersections(self, position: tuple, direction: tuple) -> Sequence[tuple]:
        """Returns tuple of intersection points sorted by distance from origin.
        """
        pass

    @abc.abstractmethod
    def normal(self, surface_point: tuple) -> tuple:
        """ Returns the unit surface normal at the surface_point. Normal faces outwards
            by convention.
        """
        pass

    @abc.abstractmethod
    def is_entering(self, surface_point: tuple, direction: tuple) -> bool:
        """ Returns the unit surface normal at the surface_point.
        """
        pass
