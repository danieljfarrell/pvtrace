from __future__ import annotations
from typing import Sequence, Iterator
from anytree import NodeMixin, Walker
import numpy as np
from pvtrace.common.errors import AppError
from pvtrace.geometry.intersection import Intersection
from pvtrace.geometry.transformable import Transformable
from pvtrace.geometry.utils import distance_between
from pvtrace.geometry.transformations import rotation_from_matrix
import logging

logger = logging.getLogger(__name__)


class Node(NodeMixin, Transformable):
    """A node in a scene graph. Each node represents a new coordinate system
    with position and orientation relative to it's parent node.
    """

    def __init__(
        self, name=None, parent=None, location=None, geometry=None, light=None, appearance=None
    ):
        super(Node, self).__init__(location=location)
        self.name = name
        self.parent = parent
        self.geometry = geometry
        self.light = light
        self.appearance = appearance if appearance else {}

    def __repr__(self):
        return "Node({})".format(self.name)

    def look_at(self, vector: tuple) -> None:
        """Make the node point in the direction of the vector.

        Discussion
        ----------
        The "face" of the node is defined to be direction [0, 0, 1]. This method
        with always point the face of the node along the direction vector
        specified. Note that the if the node is displaced from the origin this
        will be respected and the node will be rotate around its centre.

        References
        ----------
        [1] https://math.stackexchange.com/q/476311
        """
        a = np.array([0, 0, 1])  # +z direction
        b = np.array(vector)  # direction we want to face
        c = np.dot(a, b)
        if np.isclose(c, -1.0):
            # Anti-parallel rotation can be done without computation
            self.rotate(np.pi, [0, 1, 0])
            return

        v = np.cross(a, b)
        C = 1 / (1 + c)
        v1, v2, v3 = v[0], v[1], v[2]
        vx = np.array([[0, -v3, v2], [v3, 0, -v1], [-v2, v1, 0]])
        r = np.identity(3) + vx + vx @ vx * C
        R = np.identity(4)
        R[:3, :3] = r
        angle, direc, point = rotation_from_matrix(R)
        self.rotate(angle, direc)

    # Convert between coordinate systems

    def transformation_to(self, node: Node) -> np.ndarray:
        """Transformation matrix from this node to another node.

        Parameters
        ----------
        node : Node
            The other node.

        Returns
        -------
        numpy.ndarray
            Homogeneous transformation matrix.
        """
        if self == node:
            return np.identity(4)
        upwards, common, downwards = Walker().walk(self, node)
        transforms = tuple(map(lambda x: x.pose, upwards))
        transforms = transforms + tuple(map(lambda x: np.linalg.inv(x.pose), downwards))
        if len(transforms) == 1:
            transform = transforms[0]
        else:
            transform = np.linalg.multi_dot(transforms[::-1])
        return transform

    def point_to_node(self, point: tuple, node: Node) -> tuple:
        """Convert local point into the the other node coordinate system.

            The `node` must be somewhere in the hierarchy tree.

        Parameters
        ----------
        point : tuple of float
            Cartesian point `(x, y, z)` in the local coordinate system.
        node : Node
            Node in which the point should be represented.
        """
        mat = self.transformation_to(node)
        homogeneous_pt = np.ones(4)
        homogeneous_pt[0:3] = point
        new_pt = np.dot(mat, homogeneous_pt)[0:3]
        new_pt = tuple(new_pt)
        return new_pt

    def vector_to_node(self, vector: tuple, node: Node) -> tuple:
        """Convert local vector into the the other node coordinate system.

            The `node` must be somewhere in the hierarchy tree.

        Parameters
        ----------
        point : tuple of float
            Cartesian vector `(i, j, k)` in the local coordinate system.
        node : Node
            Node in which the point should be represented.
        """
        mat = self.transformation_to(node)[0:3, 0:3]
        new_vec = tuple(np.dot(mat, np.array(tuple(vector)))[0:3])
        return new_vec

    def path_to(self, node) -> Sequence[Node]:
        upwards, common, downwards = Walker().walk(self, node)
        path = upwards + (common,) + downwards
        return path

    def intersections(self, ray_origin, ray_direction) -> Sequence[Intersection]:
        """Returns intersections with node's geometry and child subtree.

        Parameters
        ----------
        ray_origin : tuple of float
            The ray position `(x, y, z)`.
        ray_direction : tuple of float
            The ray position `(a, b, c)`.

        Returns
        -------
        all_intersections : tuple of Intersection
            All intersection with this scene and a list of Intersection objects.
        """
        all_intersections = []
        if self.geometry is not None:
            points = self.geometry.intersections(ray_origin, ray_direction)
            for point in points:
                intersection = Intersection(
                    coordsys=self,
                    point=point,
                    hit=self,
                    distance=distance_between(ray_origin, point),
                )
                all_intersections.append(intersection)
        all_intersections = tuple(all_intersections)

        for child in self.children:
            # Intersections with node's geometry
            ray_origin_in_child = self.point_to_node(ray_origin, child)
            ray_direction_in_child = self.vector_to_node(ray_direction, child)
            # Intersections with node's subtree
            intersections_in_child = child.intersections(
                ray_origin_in_child, ray_direction_in_child
            )
            all_intersections = all_intersections + intersections_in_child
        return all_intersections

    def emit(self, num_rays=None) -> Iterator[Ray]:
        """Generator of rays using the node's light object.

        Parameters
        ----------
        num_rays : int of None
            The maximum number of rays this light source will generate. If set to
            None then the light will generate until manually terminated.

        to_world: Bool
            Represent the ray in the world's coordinate frame.

        Returns
        -------
        ray : Ray
            A ray emitted from the light source.

        Raises
        ------
        AppError
            If the node does not have an attached light object.
        """
        if self.light is None:
            raise AppError("Not a lighting node.")
        for ray in self.light.emit(num_rays=num_rays):
            yield ray


if __name__ == "__main__":
    pass
