
from __future__ import annotations
from typing import Optional, Sequence, Iterator
from anytree import NodeMixin, Walker, PostOrderIter
import numpy as np
from pvtrace.common.errors import AppError
from pvtrace.geometry.intersection import Intersection
from pvtrace.geometry import transformations as tf
from pvtrace.geometry.transformable import Transformable
import logging
logger = logging.getLogger(__name__)


class Node(NodeMixin, Transformable):
    """ A node in a scene graph. Each node represents a new coordinate system
    with position and orientation relative to it's parent node.
    """

    def __init__(self, name=None, parent=None, location=None, geometry=None, light=None):
        super(Node, self).__init__(location=location)
        self.name = name
        self.parent = parent
        self.geometry = geometry
        self.light = light

    def __repr__(self):
        return "Node({})".format(self.name)

    def look_at(self, vector: tuple) -> None:
        """ Align the node so that the Z axis is pointing along the vector.
        """
        raise NotImplementedError()

    # Convert between coordinate systems

    def transformation_to(self, node: Node) -> np.ndarray:
        """ Transformation matrix from this node to another node.
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
        """ Convert point in node coordinate system to the a point in the 
        local coordinate system. Node must be somewhere in the hierarchy tree.
        """
        mat = self.transformation_to(node)
        homogeneous_pt = np.ones(4)
        homogeneous_pt[0:3] = point
        new_pt = np.dot(mat, homogeneous_pt)[0:3]
        new_pt = tuple(new_pt)
        return new_pt

    def vector_to_node(self, vector: tuple, node: Node) -> tuple:
        mat = self.transformation_to(node)[0:3,0:3]
        new_vec = tuple(np.dot(mat, np.array(tuple(vector)))[0:3])
        return new_vec

    def path_to(self, node) -> Sequence[Node]:
        upwards, common, downwards = Walker().walk(self, node)
        path = upwards + (common,) + downwards
        return path

    def intersections(self, ray_origin, ray_direction) -> Sequence[Intersection]:
        """ Returns intersections with node's geometry and child subtree.
        """
        all_intersections = []
        if self.geometry is not None:
            points = self.geometry.intersections(ray_origin, ray_direction)
            for point in points:
                intersection = Intersection(coordsys=self, point=point, hit=self)
                all_intersections.append(intersection)
        all_intersections = tuple(all_intersections)

        for child in self.children:
            # Intersections with node's geometry
            ray_origin_in_child = self.point_to_node(ray_origin, child)
            ray_direction_in_child = self.vector_to_node(ray_direction, child)
            # Intersections with node's subtree
            intersections_in_child = \
                child.intersections(ray_origin_in_child, ray_direction_in_child)
            all_intersections = all_intersections + intersections_in_child
        return all_intersections

    def emit(self, num_rays=None) -> Iterator[Ray]:
        """ Generator of rays using the node's light object.

            Parameters
            ----------
            num_rays : int of None
                The maximum number of rays this light source will generate. If set to
                None then the light will generate until manually terminated.
        
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
            ray = ray.representation(self, self.root)  # local ray to world
            yield ray

if __name__ == '__main__':
    pass
