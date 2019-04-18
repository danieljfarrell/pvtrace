import traceback
import collections
from typing import Optional, Tuple, Sequence
from dataclasses import dataclass, replace
import numpy as np
from pvtrace.trace.context import Context, Kind, StepContext
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.light.ray import Ray
from pvtrace.geometry.intersection import Intersection
from pvtrace.geometry.utils import distance_between, close_to_zero, points_equal
from pvtrace.common.errors import TraceError
from pvtrace.material.interface import make_interface
from pvtrace.material.volume import make_volume
from anytree import PostOrderIter
import logging
logger = logging.getLogger(__name__)


EPSILON = 1e-9  # 1 nanometer resolution

class PhotonTracer(object):
    """Ray tracing algorithm which follows photons through the scene.
    
    1. Determine container node or surface node
    2. If contained trace path length or if on surface trace surface.
    3. Repeat.
    """

    def __init__(self, scene: Scene):
        super(PhotonTracer, self).__init__()
        self.scene = scene

    def follow(self, ray: Ray) -> [Ray]:
        """ Return full history of the ray with the scene.
        """
        history = [ray]
        while ray.is_alive:
            for step in self.step(ray):
                history.append(step)
            ray = history[-1]
        return history

    def make_step_context(self, ray: Ray) -> StepContext:
        """ Returns a context object which contains all information required to trace
        the ray forward one step.
        """
        all_intersections = self.scene.intersections(ray.position, ray.direction)
        next_index = 1 if points_equal(ray.position, all_intersections[0].point) else 0
        next_intersection_node = all_intersections[next_index].hit
        container_node = self.container(ray, all_intersections) if next_index == 0 else next_intersection_node
        ctx = StepContext(container_node, all_intersections, next_index)
        return ctx

    def step(self, ray: Ray) -> Ray:
        """ Steps the ray one event forward.
        """
        ctx = self.make_step_context(ray)
        logger.debug('Ray is in {}.'.format(ctx.container))
        initial_ray = ray
        next_intersection = ctx.next_intersection()
        logger.debug("Tracing along path.")
        ray, hit_node = self.trace_path(ray, ctx.container, next_intersection.hit, next_intersection.point)
        if hit_node == self.scene.root:            
            ray = replace(ray, is_alive=False)
            logger.debug("Ray died {}".format(ray))
            yield ray
        else:
            logger.debug('Ray moved and hit or is inside {}.'.format(hit_node))
            yield ray # yield ray motion step
            ray_on_hit_node = hit_node.geometry.is_on_surface(self.scene.root.point_to_node(ray.position, hit_node))
            if ray_on_hit_node:
                if np.allclose(ray.direction, initial_ray.direction):
                    interface = (ctx.container, hit_node)
                    if ctx.container == hit_node:
                        interface = (ctx.container, ctx.all_intersections[ctx.next_index+1].hit)
                else:
                    logger.debug('Direction changed. Re-calculating intersections.')
                    ctx = self.make_step_context(ray)
                    interface = (ctx.container, ctx.next_intersection().hit)
                
                logger.debug("Interface {}".format(interface))

                # Check that a material exists on both sides of the interface
                has_material = [side.geometry.material is not None for side in interface]
                if all(has_material):
                    logger.debug("Tracing interface.")
                    ray = self.trace_interface(ray, interface)
                    yield ray # yield ray interface step and exit
                elif all(np.logical_not(has_material)):
                    logger.debug("Interface does not have materials.")
                elif len(set(has_material)) == 2:
                    logger.debug(traceback.format_exc())
                    raise TraceError("Both interface nodes must have a material. At interface {} {}".format(interface[0].geometry.material, interface[1].geometry.material))

    def container(self, ray: Ray, all_intersections: Tuple[Intersection]) -> Node:
        """ A node contains the ray if the ray only has one intersection with the
        container along its path.
        """
        all_nodes =[x.hit for x in all_intersections]
        nodes_counter = collections.Counter(all_nodes)
        candidate_nodes = {x : nodes_counter[x] for x in nodes_counter if nodes_counter[x] == 1}
        # `all_intersections` is sorted by distance from the ray so we can just return
        # the node in candidate_nodes that has the lowest index.
        container_index = np.min([all_nodes.index(c) for c in candidate_nodes])
        container_node = all_nodes[container_index]
        return container_node

    def trace_path(self, ray: Ray, container_node: Node, intersection_node: Node, intersection_point: tuple) -> Tuple[Ray, Node]:
        """ Determines if the ray is absorbed or scattered along it's path and returns
        a new ray is these processes occur. If not, or the container node does not have
        a material attached the ray is moved to the next intersection point.
        """
        # Exit early if possible
        if any([node.geometry is None for node in (container_node, intersection_node)]):
            raise TraceError("Node is missing a geometry.")
        elif container_node.geometry.material is None:
            logger.debug("Container node is missing a material. Will propagate ray the full path length.")
            new_ray = replace(ray, position=intersection_point)
            hit_node = intersection_node
            return (new_ray, hit_node)
        
        # Have a proper material
        root = self.scene.root
        distance = distance_between(ray.position, intersection_point)
        volume = make_volume(container_node, distance)
        new_ray = volume.trace(ray)
        position_in_intersection_node_frame = root.point_to_node(new_ray.position, intersection_node)
        if intersection_node.geometry.is_on_surface(position_in_intersection_node_frame):
            # Hit interface between container node and intersection node
            hit_node = intersection_node
        else:
            # Hit molecule in container node (i.e. was absorbed or scattered)
            hit_node = container_node
        return new_ray, hit_node


    def trace_interface(self, ray: Ray, interface_nodes: Tuple[Node]) -> Ray:
        """ Interacts the ray with the interace between two materials and determines
        the rays new direction. Note that rays position is moved slightly forward along
        its new path so that it is no longer at the intersection point.
        """
        # Try and exit early
        if any([node.geometry is None for node in interface_nodes]):
            raise TraceError("An interface node is missing a geometry.")
        elif any([node.geometry.material is None for node in interface_nodes]):
            logger.debug("An interface node is missing a material. Will propagate ray across interface.")
            return ray
        # Have a proper interface
        interface = make_interface(*interface_nodes)
        new_ray = interface.trace(ray)
        return new_ray
            
            
