from pvtrace.geometry.geometry import Geometry
from pvtrace.common.errors import GeometryError
from pvtrace.geometry.utils import angle_between, norm, close_to_zero, ray_z_cylinder
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Cylinder(Geometry):
    """A cylinder defined by a length and radius with centre at (0, 0, 0) and aligned
    along the z axis.
    """

    def __init__(self, length, radius, material=None):
        super(Cylinder, self).__init__()
        self.length = length
        self.radius = radius
        self._material = material

    @property
    def material(self):
        return self._material

    @material.setter
    def set_material(self, new_value):
        self._material = new_value

    def is_on_surface(self, point):
        # Just use any direction for a fake ray, we only need the distance
        _, dist = ray_z_cylinder(self.length, self.radius, point, norm((1, 1, 1)))
        if len(dist) == 0:
            return False
        dist = dist[0]  # Only need closest intersection
        if close_to_zero(dist):
            # print("dist from point {} {} is_on_surface True".format(dist, point))
            return True
        # print("dist from point {} {} is_on_surface False".format(dist, point))
        return False

    def contains(self, point):
        z = point[2]
        r = np.sqrt(np.sum(np.array(point[:2]) ** 2))
        if z > -0.5 * self.length and z < 0.5 * self.length and r < self.radius:
            return True
        return False

    def intersections(self, origin, direction):
        points, _ = ray_z_cylinder(self.length, self.radius, origin, direction)
        return points

    def normal(self, surface_point):
        """ Normal faces outwards by convention.
        """
        z = surface_point[2]
        if np.isclose(z, -0.5 * self.length):
            return (0.0, 0.0, -1.0)
        elif np.isclose(z, 0.5 * self.length):
            return (0.0, 0.0, 1.0)
        elif np.isclose(self.radius, np.sqrt(np.sum(np.array(surface_point[:2]) ** 2))):
            v = np.array(surface_point) - np.array([0.0, 0.0, surface_point[2]])
            n = tuple(norm(v).tolist())
            return n
        else:
            raise GeometryError("Not a surface point.")

    def is_entering(self, surface_point, direction) -> bool:
        """ Returns True if the ray at surface point with direction is heading 
        into the shape. This is tested by checking for a negative dot product between
        the vectors.
        """
        if not self.is_on_surface(surface_point):
            raise GeometryError("Not a surface point.")
        normal = self.normal(surface_point)
        if np.dot(normal, direction) < 0.0:
            return True
        return False
