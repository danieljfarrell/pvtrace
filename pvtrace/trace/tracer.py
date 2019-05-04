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
import traceback
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


class MonteCarloTracer(object):
    """ This is version 2 of Photon Tracer, essentially it is just a 
        refactoring.
    """

    def __init__(self, scene: Scene):
        super(MonteCarloTracer, self).__init__()
        self.scene = scene
        
    def container(self, ray: Ray, all_intersections: Tuple[Intersection]) -> Node:
        """ A node contains the ray if the ray only has one intersection with the
        container along its path.
        """
        
        # Does not work with touching interfaces
        all_nodes =[x.hit for x in all_intersections]
        nodes_counter = collections.Counter(all_nodes)
        candidate_nodes = {x : nodes_counter[x] for x in nodes_counter if nodes_counter[x] == 1}
        # `all_intersections` is sorted by distance from the ray so we can just return
        # the node in candidate_nodes that has the lowest index.
        container_index = np.min([all_nodes.index(c) for c in candidate_nodes])
        container_node = all_nodes[container_index]
        return container_node
    
    def follow(self, ray: Ray) -> [Ray]:
        """ Return full history of the ray with the scene.
        """
        print("Start follow:")
        path = [ray]
        idx = 0
        last_ray = ray
        while ray.is_alive:
            intersections = self.scene.intersections(ray.position, ray.direction)
            points, nodes = zip(*[(x.point, x.hit) for x in intersections])
            ray = trace_algo(ray, points, nodes, idx)
            path.append(ray)
            if np.allclose(ray.position, last_ray.position) and np.allclose(ray.direction, last_ray.direction):
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
    print("\n")
    print("find_container")
    nodes = intersection_nodes
    print(nodes)
    if len(nodes) == 0:
        raise ValueError("Node list is empty.")
    
    for n in intersection_nodes:
        local_ray = ray.representation(n.root, n)
        if n.geometry.is_on_surface(local_ray.position):
            raise ValueError("Ray cannot be on surface.")

    import collections
    c = collections.Counter(nodes)
    print(c)
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
    dist = distance_between(min_point, max_point)
    #print("trace path")
    ray = trace_path(ray, container, dist)
    print(ray)
    #import pdb; pdb.set_trace()
    
    #print(container, to_node, surface_node)
    if to_node is None and container.parent is None:
        # Hit world node; kill ray
        ray = replace(ray, is_alive=False)
    elif points_equal(ray.position, max_point) and ray.is_alive:
        # Trace surface
        #print("trace surface:")
        #print("container, to_node, surface_node {} {} {}".format(
        #    container, to_node, surface_node)
        #)
        # Must return a ray that is no longer on the surface of node!
        ray = trace_surface(ray, container, to_node, surface_node)
        local_ray = ray.representation(surface_node.root, surface_node)
        if surface_node.geometry.is_on_surface(ray.position):
            import pdb; pdb.set_trace()
            raise ValueError("After tracing a surface the ray cannot still be on the surface.")
        #print(ray)
    else:
        raise RuntimeError("Something went wrong.")
    return ray


def trace_path(ray, container_node, distance):
    """ Trace ray along path length inside the container node.
    """
    print("trace_path with distance: {}".format(distance))
    # No absorpion for now!
    new_pos = tuple(
        (np.array(ray.position) + 
        distance * np.array(ray.direction)).tolist()
    )
    ray = replace(ray, position=new_pos)
    return ray


def transform_surface(
    local_ray: Ray,
    from_node: Node,
    to_node: Node, 
    surface_node: Node
    ) -> Ray:
    """ Interacts the ray with the node's geometry surface and 
        returns a transformed ray.
    
        local_ray : Ray
            A ray in the local coordinate system of the node.

        Returns
        -------
        transformed_local_ray : Ray
            A transformed ray in the coordinate system of the node.
    """
    
    # Make attempts to exit early for null geometry
    from_geo = from_node.geometry
    to_geo = to_node.geometry
    null_geos = [geo is None for geo in (from_geo, to_geo)]
    if all(null_geos):
        return local_ray
    elif any(null_geos):
        raise TraceError("Both nodes must have a geometry.")

    # Make attempts to exit early for null material
    from_mat = from_geo.material
    to_mat = to_geo.material
    null_mats = [mat is None for mat in (from_mat, to_mat)]
    if all(null_mats):
        return local_ray
    elif any(null_mats):
        raise TraceError("Both nodes must have a material.")

    surf_geo = surface_node.geometry
    event = surf_geo.material.event(
        local_ray, surf_geo
    )
    transformed_local_ray = geometry.material.transform(
        local_ray, from_node, to_node, surface_node, event
    )
    return transformed_local_ray


class TraceDelegate(object):
    """ This is a delegate object attached to every node. It provides
        a common interface for tracing the ray across the node's 
        surface or through the nodes volume; independent of the node's
        material or coating attributes.
    """
    
    # def __init__(self, node: Node):
    #     """
    #         Parameters
    #         ----------
    #         node : Node
    #             The node which delegates to this object.
    #     """
    #     super(TraceDelegate, self).__init__()
    #     self.node = node




def trace_surface(ray, from_node, to_node, surface_node) -> Ray:
    """ Returns a ray after interaction with the surface.
    
        Parameters
        ----------
        ray : Ray
            Ray in the world coordinate system.
        from_node : Node
            The node containing the ray.
        to_node : Node
            The node that will contain the ray if it cross the surface.
        surface_node : Node
            The surface normal of this node should be used to calculate
            incident angle to the surface.

        Notes
        -----
        The from_node and to_node allow refractive index data to be 
        gather from either side of the interace. The surface_node will
        be either from_node or to_node and this node should be used
        for surface normal calculations.
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
    decision, context = surface_node.geometry.material.trace_surface(
        local_ray, from_node.geometry, to_node.geometry, surface_node.geometry 
    )
    print("Decision: {}".format(decision))
    new_local_ray = surface_node.geometry.material.transform(local_ray, decision, context)
    new_ray = new_local_ray.representation(
        surface_node, surface_node.root
    )
    return new_ray


