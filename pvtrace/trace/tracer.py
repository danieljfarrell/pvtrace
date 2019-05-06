import traceback
import collections
from typing import Optional, Tuple, Sequence
from dataclasses import dataclass, replace
import numpy as np
from pvtrace.trace.context import Context, Kind, StepContext
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.light.ray import Ray
from pvtrace.material.material import Decision
from pvtrace.geometry.intersection import Intersection
from pvtrace.geometry.utils import distance_between, close_to_zero, points_equal, EPS_ZERO
from pvtrace.common.errors import TraceError
from anytree import PostOrderIter
import traceback
import logging
logger = logging.getLogger(__name__)


class MonteCarloTracer(object):
    """ This is version 2 of Photon Tracer, essentially it is just a 
        refactoring.
    """

    def __init__(self, scene: Scene):
        super(MonteCarloTracer, self).__init__()
        self.scene = scene
    
    def follow(self, ray: Ray) -> [Tuple[Ray, Decision]]:
        """ Return full history of the ray with the scene.
        """
        print("Start follow:")
        path = [(ray, Decision.EMIT)]
        idx = 0
        last_ray = ray
        while ray.is_alive:
            intersections = self.scene.intersections(ray.position, ray.direction)
            points, nodes = zip(*[(x.point, x.hit) for x in intersections])
            for ray, decision in trace_algo(ray, points, nodes, idx):
                path.append((ray, decision))
            if points_equal(ray.position, last_ray.position) and np.allclose(ray.direction, last_ray.direction):
                import pdb; pdb.set_trace()
                raise RuntimeError("Ray did not move.")
            last_ray = ray
            idx += 1
            if idx > 10:
                raise RuntimeError("Got stuck!")
        return path


def find_container(ray, intersection_nodes):
    """ Returns the container of the ray.
    
        Parameters
        ----------
        intersection_nodes : [Node]
            List of future intersection nodes.
    
        Raises
        ------
        ValueError
            If the container cannot be found.

        Notes
        -----
        This algorithm fails for points that are on surfaces of nodes.

        Returns
        -------
        Node
            The container node.
    """
    #print("find_container")
    nodes = intersection_nodes
    #print(nodes)
    if len(nodes) == 0:
        raise ValueError("Node list is empty.")
    
    for n in intersection_nodes:
        local_ray = ray.representation(n.root, n)
        if n.geometry.is_on_surface(local_ray.position):
            raise ValueError("Ray cannot be on surface.")

    import collections
    c = collections.Counter(nodes)
    #print(c)
    container = None
    if len(nodes) in (1, 2):
        return nodes[0]
    else:
        for node, count in c.items():
            if count == 1:
                container = node
                break
    if container is None:
        raise ValueError("Cannot determine container.")
    print("Container:", container)
    return container


def ray_status(ray, points, nodes):
    """ Returns classification information about the location of the ray in the scene.

        Parameters
        ----------
        ray : Ray
            The ray.
        points : list of tuple
            The intersection points as a list of 3- tuples e.g. [(0.0, 0.0, 0.0), 
            (1.0, 1.0, 1.0)]
        nodes : list of Node
            The intersection nodes.

        Notes
        -----
        This is not a general algorithm, this only works when the ray is not located
        on the surface of a node.

        Returns
        -------
        status: tuple
            Tuple like (container, to_node, surface_node) where,

            container : Node
                The node containing the ray.
            to_node : Node
                The node on the other side of the next hit location.
            surface_node : Node
                The node on this side of the next hit location.

    """
    container = find_container(ray, nodes)
    
    # Handle special case of last step where ray is hitting the world node
    root = nodes[0].root
    if container == root and len(nodes) == 1:
        status = root, None, root
        return status

    if nodes[0] == container:
        surface_node = nodes[0]
        to_node = nodes[1]
    else:
        surface_node = nodes[0]
        to_node = nodes[0]
    status = container, to_node, surface_node
    return status


def trace_algo(ray, points, nodes, idx):
    """ Isolated trace algorithm as a function.
    """
    print("\n")
    print("Start step:")
    print(ray)
    print(points, nodes)
    
    container, to_node, surface_node = ray_status(ray, points, nodes)
    min_point = ray.position
    max_point = points[0]
    
    #print("trace path")
    dist = distance_between(min_point, max_point)
    if dist < 1e-10:
        print("Distance is tiny")
        import pdb; pdb.set_trace()
    for (ray, decision) in trace_path(ray, container, dist):
        yield ray, decision
        

    if not ray.is_alive:
        # Killed by non-radiative absorption in material path trace.
        yield ray, decision
    elif to_node is None and container.parent is None:
        # Hit world node; kill ray here.
        ray = replace(ray, is_alive=False)
        yield ray, Decision.KILL
    elif points_equal(ray.position, max_point):
        # Hit surface
        # NB This *must* return a ray that is *not* on the surface of node!
        print("pos (before): {}".format(ray.position))
        for ray, decision in trace_surface(ray, container, to_node, surface_node):
            print("pos (after): {}".format(ray.position))
            yield ray, decision
        # this is for debug only
        if __debug__:
            local_ray = ray.representation(surface_node.root, surface_node)
            if surface_node.geometry.is_on_surface(local_ray.position):
                print("pos: {}".format(ray.position))
                import pdb; pdb.set_trace()
                raise ValueError("After tracing a surface the ray cannot still be on the surface.")
    print("Ending step!")


def trace_path(ray, container_node, distance) -> Tuple[Ray, Decision]:
    """ Trace ray along path length inside the container node.
    """
    print("trace_path with distance: {}".format(distance))
    if distance < 1e-10:
        print("Distance is tiny")
        import pdb; pdb.set_trace()
    # No absorpion for now!
    local_ray = ray.representation(
        container_node.root, container_node
    )
    for (local_ray, decision) in container_node.geometry.material.trace_path(
            local_ray, container_node.geometry, distance):
        new_ray = local_ray.representation(
            container_node, container_node.root
        )
        print("Decision: {}, ray: {}".format(decision, new_ray))
        yield new_ray, decision

# def transform_surface(
#     local_ray: Ray,
#     from_node: Node,
#     to_node: Node,
#     surface_node: Node
#     ) -> Ray:
#     """ Interacts the ray with the node's geometry surface and
#         returns a transformed ray.
#
#         local_ray : Ray
#             A ray in the local coordinate system of the node.
#
#         Returns
#         -------
#         transformed_local_ray : Ray
#             A transformed ray in the coordinate system of the node.
#     """
#
#     # Make attempts to exit early for null geometry
#     from_geo = from_node.geometry
#     to_geo = to_node.geometry
#     null_geos = [geo is None for geo in (from_geo, to_geo)]
#     if all(null_geos):
#         return local_ray
#     elif any(null_geos):
#         raise TraceError("Both nodes must have a geometry.")
#
#     # Make attempts to exit early for null material
#     from_mat = from_geo.material
#     to_mat = to_geo.material
#     null_mats = [mat is None for mat in (from_mat, to_mat)]
#     if all(null_mats):
#         return local_ray
#     elif any(null_mats):
#         raise TraceError("Both nodes must have a material.")
#
#     surf_geo = surface_node.geometry
#     event = surf_geo.material.event(
#         local_ray, surf_geo
#     )
#     transformed_local_ray = geometry.material.transform(
#         local_ray, from_node, to_node, surface_node, event
#     )
#     return transformed_local_ray
#
#
# class TraceDelegate(object):
#     """ This is a delegate object attached to every node. It provides
#         a common interface for tracing the ray across the node's
#         surface or through the nodes volume; independent of the node's
#         material or coating attributes.
#     """
#
#     # def __init__(self, node: Node):
#     #     """
#     #         Parameters
#     #         ----------
#     #         node : Node
#     #             The node which delegates to this object.
#     #     """
#     #     super(TraceDelegate, self).__init__()
#     #     self.node = node
#
#
#

def trace_surface(ray, container_node, to_node, surface_node) -> Tuple[Ray, Decision]:
    """ Returns a ray after interaction with the surface.
    
        Parameters
        ----------
        ray : Ray
            Ray in the world coordinate system.
        container_node : Node
            The node containing the ray.
        to_node : Node
            The node that will contain the ray if it cross the surface.
        surface_node : Node
            The surface normal of this node should be used to calculate
            incident angle to the surface.

        Notes
        -----
        The container_node and to_node allow refractive index data to be 
        gather from either side of the interace. The surface_node will
        be either container_node or to_node and this node should be used
        for surface normal calculations.
    
        Returns
        -------
        tuple
            Like, (Ray, Decision) where the first element is the new ray and the 
            second element is a decision enum value indicating what occurred.
    """
    
    # to-do: this uses a new attribute on node: a trace delegate. The
    # idea here is that the trace delegate implements a simple set of
    # functions that the tracer can use to trace the ray through the 
    # scene, without getting bogged down into the details of the 
    # material properties. i.e. it is a common interface.

    local_ray = ray.representation(
        surface_node.root, surface_node
    )
    # Handle the transformation possibilities. This will perform 
    # a single transformation to the ray; either reflection, 
    # refraction or scattering depending on the material 
    # properties. If the node does not have a material then the default
    # is to propagate forwards.
    for local_ray, decision in surface_node.geometry.material.trace_surface(
        local_ray, container_node.geometry, to_node.geometry, surface_node.geometry):
        new_ray = local_ray.representation(
            surface_node, surface_node.root
        )
        print("Decision: {}, ray: {}".format(decision, ray))
        yield new_ray, decision



