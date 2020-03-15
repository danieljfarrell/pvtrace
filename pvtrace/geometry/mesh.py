from pvtrace.geometry.geometry import Geometry
from pvtrace.geometry.utils import EPS_ZERO
from pvtrace.common.errors import GeometryError
from typing import Optional, Sequence, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Mesh(Geometry):
    """ Wrapper making trimesh conform to the pvtrace Geometry protocol.
    """

    def __init__(self, trimesh, material=None):
        super(Mesh, self).__init__()
        trimesh.vertices -= trimesh.center_mass
        self.trimesh = trimesh
        self._material = material

    @property
    def material(self):
        return self._material

    @material.setter
    def material(self, new_value):
        self._material = new_value

    def contains(self, point: tuple) -> bool:
        """ Return True if the point is inside the shape.
        """
        return self.trimesh.contains(np.array([point]))[0]

    def is_on_surface(self, point: tuple) -> bool:
        """Returns `True` is the point is on the surface."""
        # This fails sometimes because surface points can be larger than EPS_ZERO
        mesh = self.trimesh
        closest_points, distances, triangle_id = mesh.nearest.on_surface(
            np.array([point])
        )
        flag = np.any(np.absolute(distances) < EPS_ZERO)
        return flag

    def intersections(self, position: tuple, direction: tuple) -> Sequence[tuple]:
        """Returns tuple of intersection points sorted by distance from origin.
        """
        mesh = self.trimesh
        locations, index_ray, index_tri = mesh.ray.intersects_location(
            ray_origins=np.array([position]), ray_directions=np.array([direction])
        )
        if len(locations) == 0:
            return tuple()
        locations = [tuple(x) for x in locations.tolist()]

        def distance_sort_key(i):
            v = np.array(i) - np.array(position)
            d = np.linalg.norm(v)
            return d

        locations = tuple(sorted(locations, key=distance_sort_key))
        return locations

    def normal(self, surface_point: tuple) -> tuple:
        """ Returns the unit surface normal at the surface_point.
        """
        mesh = self.trimesh
        (closest_points, distances, triangle_id) = mesh.nearest.on_surface(
            np.array([surface_point])
        )
        if closest_points.shape != (1, 3):
            raise GeometryError(
                "Mesh must have a single closest point to calculate normal."
            )
        if not np.any(np.absolute(distances) < EPS_ZERO):
            raise GeometryError(
                "Point is not on surface.",
                {
                    "point": surface_point,
                    "geometry": self,
                    "distances": distances,
                    "threshold": EPS_ZERO,
                },
            )
        normal = tuple(mesh.face_normals[triangle_id[0]])
        return normal

    def is_entering(self, surface_point: tuple, direction: tuple) -> bool:
        """ Returns the unit surface normal at the surface_point.
        """
        normal = self.normal(surface_point)
        if np.dot(normal, direction) < 0.0:
            return True
        return False
