import traceback
import numpy as np
import abc
from pvtrace.scene.node import Node
from pvtrace.material.properties import Absorptive
from pvtrace.material.material import Dielectric, Host
from pvtrace.material.mechanisms import TravelPath, Absorption, Emission, KillRay
from pvtrace.trace.context import Context, Kind
from pvtrace.light.ray import Ray
from pvtrace.common.errors import TraceError
from pvtrace.geometry.utils import magnitude
import logging
logger = logging.getLogger(__name__)


class Volume(abc.ABC):
    
    def __init__(self, container_node: "Node", path_length: float):
        super(Volume, self).__init__()
        self.container_node = container_node
        self.path_length = path_length

    def trace(self, ray: Ray) -> Ray:
        """ Default implementation moves ray the full length along the path.
        """
        logger.debug("Using volume default trace.")
        new_ray = ray.propagate(self.path_length)
        return new_ray


class DielectricVolume(Volume):
    """A controller which helps trace the ray through a homogeneous volume.
    """

    def __init__(self, container_node: "Node", path_length: float):
        """ Parameters
            ----------
            container_node : Node
                The ray is located inside the container node's geometry object.
            path_length : float
                The path length in cm the ray will travel is no interactions occur.
        
            Notes
            -----
            Units of path_length is *centimeters*.

        """
        super(DielectricVolume, self).__init__(container_node, path_length)

    def make_context(self, ray):
        """ Make a context for this interface.
        """

        # Wrap everything into a context object.
        end_path = np.array(ray.position) + self.path_length * np.array(ray.direction)
        end_path = tuple(end_path.tolist())
        context = Context(
            kind=Kind.PATH,
            container=self.container_node,
            end_path=end_path,
            normal=None,
            normal_node=None,
            n1=None,
            n2=None
        )
        return context

    def generate_interaction_sequence(self, ray, context):
        """ To-do: implementation attenuation, absorption and emission.
        """
        #import pdb; pdb.set_trace()
        logger.debug("Generating interaction sequence.")
        absorption_mechanism = Absorption(context)
        material = context.container.geometry.material
        logger.debug("Sampling path length")
        sampled_path_length = absorption_mechanism.path_length(ray)
        free_path_length = magnitude(np.array(context.end_path) - np.array(ray.position))
        
        if sampled_path_length < free_path_length:
            yield absorption_mechanism
            logger.debug("Getting interaction material from {}.".format(material))
            interaction_material = absorption_mechanism.interaction_material
            logger.debug("Interaction material is {}.".format(interaction_material))
            if isinstance(material, Host) and interaction_material == material:
                # Problem here. A host always select one of it's lumophore materials.
                raise TraceError("Material selection error.")

            # In multiple lumophore material the interaction material is the one 
            # that actually absorbed the ray. This is decided by the absorption
            # mechanism and that decision needs to communicated with the emission
            # mechanism so that it can sample the correct emission spectrum. NB in 
            # single lumophore material systems the interaction material is simply
            # the material held by the node's geometry.
            context.interaction_material = interaction_material
            emission_mechanism = Emission(context)
            p = emission_mechanism.probability(ray)
            if np.random.uniform() < p:
                yield emission_mechanism
            else:
                yield KillRay(context)
        else:
            yield TravelPath(context)


    def trace(self, ray: Ray) -> Ray:
        """ Trace the ray along it's path through the volume.
        """
        # Apply interaction scheme
        context = self.make_context(ray)
        generator = self.generate_interaction_sequence(ray, context)
        for mechanism in generator:
            logger.debug("{} occurred.".format(mechanism))
            ray = mechanism.transform(ray)
        return ray


def make_volume(container_node: "Node", path_length: float) -> Volume:
    """ Make an interface object dependent on the materials either side of the boundary.
    """
    mat = container_node.geometry.material
    if isinstance(mat, type(None)) or (not isinstance(mat, Absorptive)):
        logger.debug('Making Volume')
        return Volume(container_node, path_length)
    elif isinstance(mat, Absorptive):
        logger.debug('Making DielectricVolume')
        return DielectricVolume(container_node, path_length)
    raise TraceError('Volume type {} not supported.'.format(mat))

