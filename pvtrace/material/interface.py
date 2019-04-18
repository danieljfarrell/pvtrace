import traceback
import collections
import numpy as np
import abc
#from pvtrace.material.interactor import DielectricInteractor
from pvtrace.common.errors import TraceError
from pvtrace.trace.context import Context, Kind
from pvtrace.scene.node import Node
from pvtrace.material.properties import Refractive
from pvtrace.material.material import Dielectric
from pvtrace.material.mechanisms import FresnelReflection, FresnelRefraction
from pvtrace.light.ray import Ray
from pvtrace.geometry.utils import angle_between
from pvtrace.common.errors import TraceError
import logging
logger = logging.getLogger(__name__)


class Interface(object):
    """ Describes an interface between two geometric objects in the scene. Interfaces
    can either be embedded or touching.
    """
    
    def __init__(self, from_node: "Node", to_node: "Node"):
        super(Interface, self).__init__()
        if from_node == to_node:
            raise TraceError('Interface must be defined between different nodes.')
        self.from_node = from_node
        self.to_node = to_node

    def normal(self, ray: Ray) -> tuple:
        """ Return outward facing surface normal at the interface intersection point. 
        """
        from_node = self.from_node
        to_node = self.to_node
        root1 = from_node.root
        root2 = to_node.root
        if root1 != root2:
            raise TraceError('Nodes are in different trees.')
        root = root1
        node1, node2 = from_node, to_node
        pos_in_node1 = root.point_to_node(ray.position, node1)
        dir_in_node1 = root.vector_to_node(ray.direction, node1)
        pos_in_node2 = root.point_to_node(ray.position, node2)
        dir_in_node2 = root.vector_to_node(ray.direction, node2)
        # Need to find the surface normal with respect to the geometry we are entering.
        # This is not necessarily the to_node for embedded nodes because we could be
        # exiting node1 and be contained in node2. The correct normal would be for 
        # node1 in this case.
        surfaces = ((node1, pos_in_node1), (node2, pos_in_node2))
        on_surfaces = [node.geometry.is_on_surface(pos) for (node, pos) in surfaces]
        touching_interface = collections.Counter([True, True])
        embedded_interface = collections.Counter([False, True])
        interface_type = collections.Counter(on_surfaces)
        if interface_type == touching_interface:
            # Use angle to determine the normal of the exiting surface
            if node1.geometry.is_entering(pos_in_node1, dir_in_node1):
                node = node1
                normal = node1.geometry.normal(pos_in_node1)
            elif node2.geometry.is_entering(pos_in_node2, dir_in_node2):
                node = node2
                normal = node2.geometry.normal(pos_in_node2)
            else:
                raise TraceError("Cannot determine how ray is crossing the interface.")
            logger.debug('Touching Interface {}|{} normal {}, angle {}.'.format(from_node, to_node, normal, np.degrees(angle)))
            return normal, node
        elif interface_type == embedded_interface:
            idx = on_surfaces.index(True)
            node, pos = surfaces[idx]
            normal = node.geometry.normal(pos)
            dirvec = None
            if node == node1:
                dirvec = dir_in_node1
            else:
                dirvec = dir_in_node2
            angle = angle_between(normal, np.array(dirvec))
            logger.debug('Embedded Interface {}|{} normal {}, angle {}.'.format(from_node, to_node, normal, np.degrees(angle)))
            return normal, node
        else:
            raise TraceError("Cannot determine how ray is crossing the interface.")

    def trace(self, ray: Ray) -> Ray:
        """ Default implementation does nothing. Subclasses with use materials to 
        apply physically meaningful interactions at the interface between two 
        materials.
        """
        return ray


class DielectricInterface(Interface):
    """An interface between two dielectric materials.
    """

    def __init__(self, from_node: "Node", to_node: "Node"):
        super(DielectricInterface, self).__init__(from_node, to_node)

    def make_context(self, ray):
        """ Make a context for this interface.
        """
        node1, node2 = self.from_node, self.to_node
        material1, material2 = node1.geometry.material, node2.geometry.material
        n1 = material1.refractive_index(ray.wavelength)
        n2 = material2.refractive_index(ray.wavelength)
        normal, normal_node = self.normal(ray)

        # Wrap everything into a context object.
        context = Context(
            kind=Kind.SURFACE,
            normal=normal,
            normal_node=normal_node,
            n1=n1,
            n2=n2,
            container=None,
            end_path=None,
        )
        return context

    def generate_interaction_sequence(self, ray, context):
        """ Decision tree for crossing a dielectric interface:

            - Test for reflection.
                - If reflected
                    - reflect and exit
                - If not reflected
                    - refract and exit.
        """
        # Test for reflection.
        mech = FresnelReflection(context)
        p = mech.probability(ray)
        gamma = np.random.uniform()
        if gamma < p:
            yield mech
        else:
            yield FresnelRefraction(context)

    def trace(self, ray: Ray) -> Ray:

        # Apply interaction scheme
        context = self.make_context(ray)
        generator = self.generate_interaction_sequence(ray, context)
        for mechanism in generator:
            logger.debug("{} occurred.".format(mechanism))
            ray = mechanism.transform(ray)
        return ray


def make_interface(from_node: "Node", to_node: "Node") -> Interface:
    """ Make an interface object dependent on the materials either side of the boundary.
    """
    t1 = isinstance(from_node.geometry.material, Refractive)
    t2 = isinstance(to_node.geometry.material, Refractive)
    if all((t1, t2)):
        logger.debug("Making DielectricInterface")
        return DielectricInterface(from_node, to_node)
    elif any((t1, t2)):
        logger.debug("Generic Interface")
        return Interface(from_node, to_node)
    raise TraceError('Interface type not supported.')

