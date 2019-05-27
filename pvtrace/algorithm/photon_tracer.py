import traceback
import collections
from typing import Optional, Tuple, Sequence
from dataclasses import dataclass, replace
import numpy as np
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



def follow(ray: Ray, scene: Scene, max_iters=1000, renderer=None) -> [Tuple[Ray, Decision]]:
    """ Follow the ray through a scene.
    
        This the highest level ray-tracing function. It moves the ray through the
        scene and returns a list of rays a Monte Carlo decision events. Each decision
        is an interaction which alters one of the rays properties such as position, 
        direction or wavelength.

        Raises
        ------
        TraceError
            If an error occurred while tracing.

        Returns
        -------
        List of (Ray, Decision) tuples.
    
    """
    path = [(ray, Decision.EMIT)]
    idx = 0
    last_ray = ray
    while ray.is_alive:
        intersections = scene.intersections(ray.position, ray.direction)
        points, nodes = zip(*[(x.point, x.hit) for x in intersections])
        for ray, decision in step(ray, points, nodes, renderer=renderer):
            path.append((ray, decision))
        if points_equal(ray.position, last_ray.position) and np.allclose(ray.direction, last_ray.direction):
            raise TraceError("Ray did not move.")
        last_ray = ray
        if idx > max_iters:
            raise TraceError("Ray got stuck.")
    return path


def find_container(ray, intersection_nodes):
    """ Returns the container of the ray.
    
        Parameters
        ----------
        intersection_nodes : [Node]
            List of future intersection nodes. This should be the return value of
            `scene.intersections(position, direction)`.
    
        Raises
        ------
        ValueError
            If intersections_nodes is empty.
        TraceError
            If the ray is on the surface of a node or the container could not be found.

        Notes
        -----
        This is not a general algorithm, this only works when the ray is not located
        on the surface of a node.

        Returns
        -------
        Node
            The container node.
    """
    nodes = intersection_nodes
    if len(nodes) == 0:
        raise ValueError("Node list is empty.")
    
    # This is an expensive operation; avoid in production
    if __debug__:
        for node in intersection_nodes:
            local_ray = ray.representation(node.root, node)
            if node.geometry.is_on_surface(local_ray.position):
                raise TraceError("Ray cannot be on surface.")

    c = collections.Counter(nodes)
    container = None
    if len(nodes) in (1, 2):
        return nodes[0]
    else:
        for node, count in c.items():
            if count == 1:
                container = node
                break
    if container is None:
        raise TraceError("Cannot determine container.")
    return container


def ray_status(ray, points, nodes):
    """ Returns classification information about the location of the ray in the scene.

        Parameters
        ----------
        ray : Ray
            The ray.
        points : list of tuple
            List of intersection points.
        nodes : list of Node
            The list of intersection nodes.

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


def step(ray, points, nodes, renderer=None):
    """ Step the ray through the scene until the next Monte Carlo decision.
        
        This is generator function because it cannot be known exactly how many events
        will occur on a give step and allows much of the state of the ray to be 
        reused rather than recalculated.

        Parameters
        ----------
        ray : Ray
            The ray being traced. It must *not* be on the surface of a node.
        points : tuple
            A tuple of point tuples like ((float, float, float), ...)
        nodes : tuple
            A tuple of Node objects.

        Raises
        ------
        TraceError
            If logical error occurs.

        Yields
        ------
        tuple
            A tuple of (Ray, Decision) objects.
    """
    container, to_node, surface_node = ray_status(ray, points, nodes)
    min_point = ray.position
    max_point = points[0]
    
    dist = distance_between(min_point, max_point)
    _ray = ray
    for (ray, decision) in trace_path(ray, container, dist):
        if renderer:
            renderer.add_ray_path([_ray, ray])
            _ray = ray
        yield ray, decision

    if to_node is None and container.parent is None:
        # Case: Hit world node; kill ray here.
        ray = replace(ray, is_alive=False)
        yield ray, Decision.KILL
    elif points_equal(ray.position, max_point):
        # Case: Hit surface
        # NB The ray argument of `trace_surface` *must* be a ray on the surface of the 
        # node and the returned ray must *not* be on the node!
        before_ray = ray
        _ray = ray
        for ray, decision in trace_surface(ray, container, to_node, surface_node):
            if renderer:
                renderer.add_ray_path([_ray, ray])
                _ray = ray
            yield ray, decision
        # Avoid error checks in production
        if __debug__:
            local_ray = ray.representation(surface_node.root, surface_node)
            if surface_node.geometry.is_on_surface(local_ray.position):
                logger.warning("(before) pos: {}".format(before_ray.position))
                logger.warning("(after) pos: {}".format(ray.position))
                raise TraceError("After tracing a surface the ray cannot still be on the surface.")

def trace_path(ray, container_node, distance):
    """ Trace the ray through the material of the container node.
        
        Parameters
        ----------
        ray : Ray
            The ray being traced.
        container_node : Node
            The node container the ray. The material of this node will be used to 
            calculate optical absorption.
        distance : float
            The maximum distance the ray can travel in the material before hitting
            a surface. Units of centimetres.

        Yields
        ------
        tuple
            A tuple of (Ray, Decision) objects.
    """
    if distance < 2*EPS_ZERO:
        # This is a very small step size. It could occur naturally, but it is much
        # more likely to be a bug
        raise TraceError("Distance is on the order of trace epsilon.")

    # Trace the ray through the material
    local_ray = ray.representation(
        container_node.root, container_node
    )
    for (local_ray, decision) in container_node.geometry.material.trace_path(
            local_ray, container_node.geometry, distance):
        new_ray = local_ray.representation(
            container_node, container_node.root
        )
        yield new_ray, decision


def trace_surface(ray, container_node, to_node, surface_node):
    """ Trace ray with a surface.
    
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
    
        Yields
        ------
        tuple
            A tuple of (Ray, Decision) objects.
    """
    local_ray = ray.representation(
        surface_node.root, surface_node
    )
    for local_ray, decision in surface_node.geometry.material.trace_surface(
        local_ray, container_node.geometry, to_node.geometry, surface_node.geometry):
        new_ray = local_ray.representation(
            surface_node, surface_node.root
        )
        yield new_ray, decision

