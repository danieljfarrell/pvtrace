from pvtrace.geometry.geometry import Geometry
from pvtrace.geometry.mesh import Mesh
from pvtrace.geometry.utils import angle_between, close_to_zero, EPS_ZERO, allinrange, aabb_intersection, on_aabb_surface
from pvtrace.common.errors import GeometryError
import trimesh
import numpy as np
from collections import Counter
import logging
logger = logging.getLogger(__name__)


# *Outward* surface normals corresponding to (xmin, xmax, ymin, ymax, zmin, xmax)
NORMALS = ((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1))


class BoxMesh(Mesh):
    """ Defines an axis-aligned box with centre (0, 0, 0) and side length.

        Notes
        -----
        This is implemented using trimesh it has more or less the same performance
        to the Box class below.
    """
    
    def __init__(self, size, material=None):
        """ Parameters
            ----------
            size : tuple of float
                The side lengths the box like (length, width, height)
        """
        self._size = np.array(size)
        mesh = trimesh.creation.box(size)
        super(Box, self).__init__(mesh,  material=material)

    def is_on_surface(self, point):
        on_surf, _ = on_aabb_surface(self._size, point,  atol=2*EPS_ZERO)
        return on_surf

    def normal(self, surface_point: tuple) -> tuple:
        on_surf, surf_indexes = on_aabb_surface(self._size, surface_point,  atol=2*EPS_ZERO)
        if not on_surf:
            raise GeometryError(
                "Point is not on surface.",
                {"point": surface_point, "geometry": self}
            )
        if len(surf_indexes) != 1:
            raise GeometryError(
                "Point is on multiple surfaces.",
                {"point": surface_point, "geometry": self}
            )
        idx = surf_indexes[0]
        # normal vector in the local frame
        return NORMALS[idx]


class Box(Geometry):
    """Defines a box of length, width and height with centre (0, 0, 0).
    """

    normals = {'left': (-1, 0, 0), 'right': (1, 0, 0),
               'near': (0, -1, 0), 'right': (0, 1, 0),
               'bottom': (0, 0, -1), 'top': (0, 0, 1)}
    """Define surface normals. This labels are just used internally, outside of this
       class they mean nothing.
    """

    def __init__(self, size, material=None):
        super(Box, self).__init__()
        self.size = size
        self._material = material
        self._upper = np.array(size) * 0.5
        self._lower = -self._upper

    @property
    def material(self):
        return self._material

    @material.setter
    def set_material(self, new_value):
        self._material = new_value

    def is_on_surface(self, point):
        x, y, z = point
        lx, ly, lz = self._lower
        ux, uy, uz = self._upper
        # It's better to exclude because then we can exit early
        if close_to_zero(x - lx): return True
        if close_to_zero(x - uy): return True
        if close_to_zero(y - ly): return True
        if close_to_zero(y - uy): return True
        if close_to_zero(z - lz): return True
        if close_to_zero(z - uz): return True
        return False

    def contains(self, point):
        if self.is_on_surface(point):
            return False
        x, y, z = point
        lx, ly, lz = self._lower
        ux, uy, uz = self._upper
        if x < lx or x > ux: return False
        if y < ly or y > uy: return False
        if z < lz or z > uz: return False
        return True

    def intersections(self, origin, direction):
        hits = aabb_intersection(self._lower, self._upper, origin, direction)
        if hits is None:
            return tuple()
        return hits

    def normal(self, surface_point):
        """ Normal faces outwards by convention.
        """
        magnitude = np.linalg.norm(surface_point)
        normal = np.array(surface_point) / magnitude
        normal = tuple(normal.tolist())
        return normal

    def is_entering(self, surface_point, direction) -> bool:
        """ Returns True if the ray at surface point with direction is heading
        into the shape. This is tested by checking for a negative dot product between
        the vectors.
        """
        if not self.is_on_surface(surface_point):
            raise ValueError('Point is not on surface.')
        normal = self.normal(surface_point)
        if np.dot(normal, direction) < 0.0:
            return True
        return False

