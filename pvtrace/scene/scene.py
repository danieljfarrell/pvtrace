from __future__ import annotations
from typing import Optional, Sequence
from anytree import NodeMixin, Walker, PostOrderIter, LevelOrderIter
from pvtrace.light.ray import Ray
from pvtrace.light.light import Light
from pvtrace.geometry.utils import (
    distance_between,
    close_to_zero,
    intersection_point_is_ahead,
)
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Scene(object):
    """ A scene graph of nodes.
    """

    def __init__(self, root=None):
        super(Scene, self).__init__()
        self.root = root

    def finalise_nodes(self):
        """ Update bounding boxes of node hierarchy in prepration for tracing.
        """
        root = self.root
        if root is not None:

            # Clear any existing bounding boxes
            for node in PostOrderIter(root):
                node.bounding_box = None

            # More efficiency to calcualte from leaves to root because because
            # the parent's bounding box calculation requires the size of the
            # child's bounding box.
            leaves = self.root.leaves
            for leaf_node in leaves:
                node = leaf_node
                while True:
                    _ = node.bounding_box  # will force recalculation
                    node = node.parent
                    if node is None:
                        break

    @property
    def light_nodes(self) -> Sequence[Light]:
        """ Returns all lights in the scene.
        """
        root = self.root
        found_nodes = []
        for node in LevelOrderIter(root):
            if isinstance(node.light, Light):
                found_nodes.append(node)
        return found_nodes

    @property
    def component_nodes(self) -> Sequence[Component]:
        """ Returns all lights in the scene.
        """
        root = self.root
        found_nodes = []
        for node in LevelOrderIter(root):
            if node.geometry:
                if node.geometry.material:
                    found_nodes.extend(node.geometry.material.components)
        return found_nodes

    def emit(self, num_rays):
        """ Rays are emitted in the coordinate system of the world node.
        
            Internally the scene cycles through Light nodes, askes them to emit
            a ray and the converts the ray to the world coordinate system.
        """
        world = self.root
        lights = self.light_nodes
        for idx in range(num_rays):
            light = lights[idx % len(lights)]
            for ray in light.emit(1):
                yield ray.representation(light, world)

    def intersections(self, ray_origin, ray_direction) -> Sequence[Tuple[Node, Tuple]]:
        """ Intersections with ray and scene. Ray is defined in the root node's
        coordinate system.
        """
        # to-do: Prune which nodes are queried for intersections by first
        # intersecting the ray with bounding boxes of the node.
        root = self.root
        if root is None:
            return tuple()

        def distance_sort_key(i):
            v = np.array(i.point) - np.array(ray_origin)
            d = np.linalg.norm(v)
            return d

        all_intersections = self.root.intersections(ray_origin, ray_direction)
        # Convert intersection point to root frame/node.
        all_intersections = map(lambda x: x.to(root), all_intersections)
        # Filter for forward intersections only
        all_intersections = tuple(
            filter(
                lambda x: intersection_point_is_ahead(
                    ray_origin, ray_direction, x.point
                ),
                all_intersections,
            )
        )

        # Sort by distance to ray
        all_intersections = tuple(sorted(all_intersections, key=distance_sort_key))
        # to-do: Correctly order touching interfaces
        # touching_idx = []
        # for idx, pair in enumerate(zip(all_intersections[:-1], all_intersections[1:])):
        #     if close_to_zero(distance_between(pair[0].point, pair[1].point)):
        #         touching_idx.append(idx)
        # for idx in touching_idx:
        #     i = list(all_intersections)
        #     a, b = idx - 1, idx
        #     if i[a].hit != i[b].hit:
        #         # Swap order
        #         i[b], i[a] = i[a], i[b]
        #     all_intersections = tuple(i)
        return all_intersections
