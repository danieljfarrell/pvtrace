from pvtrace.geometry.geometry import Geometry
from pvtrace.geometry.utils import angle_between, EPS_ZERO
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Sphere(Geometry):
    """A sphere defined by a radius. The sphere centre is always at (0, 0, 0)
    in it's own coordinate system.
    """

    def __init__(self, radius, material=None):
        super(Sphere, self).__init__()
        self.radius = radius
        self._material = material

    @property
    def material(self):
        return self._material

    @material.setter
    def set_material(self, new_value):
        self._material = new_value

    def is_on_surface(self, point):
        r = np.sqrt(np.sum(np.array(point) ** 2))
        return np.abs(r - self.radius) < EPS_ZERO

    def contains(self, point):
        r = np.sqrt(np.sum(np.array(point) ** 2))
        return self.radius - (r + EPS_ZERO) > 0.0

    def intersections(self, origin, direction):
        # Compute a, b and b coefficients
        origin = np.array(origin)
        direction = np.array(direction)
        a = np.dot(direction, direction)
        b = 2.0 * np.dot(direction, origin)
        c = np.dot(origin, origin) - self.radius ** 2

        # Find discriminant
        discriminant = b ** 2 - 4 * a * c

        # if discriminant is negative there are no real roots
        if discriminant < 0:
            return []

        # Discriminant is zero = one solution, positive == two solutions.
        if np.isclose(discriminant, 0.0):
            t = np.array([-b / (2 * a)])
        else:
            t = np.array(
                [
                    (-b - np.sqrt(discriminant)) / (2 * a),
                    (-b + np.sqrt(discriminant)) / (2 * a),
                ]
            )
        t = np.sort(t)
        hits = []
        for distance in t:
            if distance >= 0.0:
                point = origin + distance * direction
                hits.append(tuple(point.tolist()))
        return tuple(hits)

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
            raise ValueError("Point is not on surface.")
        normal = self.normal(surface_point)
        if np.dot(normal, direction) < 0.0:
            return True
        return False
