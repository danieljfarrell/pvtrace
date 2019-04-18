""" This module contains different physical interaction models that a ray can
have with materials. Material objects are build up from these basic
interactions.
"""
import abc
from dataclasses import replace
from enum import Enum, unique
import numpy as np
from pvtrace.geometry.utils import angle_between, norm, flip
from pvtrace.light.ray import Ray
from pvtrace.common.errors import AppError
from pvtrace.material.properties import Refractive, Emissive, Absorptive
from pvtrace.geometry.utils import magnitude
import logging
logger = logging.getLogger(__name__)

class Mechanism(abc.ABC):
    """ Physical interaction which can alter position, direction or 
    wavelength of the ray.
    """

    def transform(self, ray) -> Ray:
        """ Transform ray according to the physics of the interaction.
        """
        pass

    def __repr__(self):
        return self.__class__.__name__


class FresnelReflection(Mechanism):
    """ A frensel reflection interaction which alters the rays direction.
    """
    
    def __init__(self, context):
        """ context: dict, specific information for this interaction.
        """
        super(FresnelReflection, self).__init__()
        self.context = context

    def probability(self, ray: Ray) -> float:
        """ Returns the probability that the interaction will occur.
        """
        context = self.context
        normal = np.array(context.normal)
        n1 = context.n1
        n2 = context.n2
        
        # Be flexible with how the normal is defined
        ray_ = ray.representation(context.normal_node.root, context.normal_node)
        if np.dot(normal, ray_.direction) < 0.0:
            normal = flip(normal)
        angle = angle_between(normal, np.array(ray_.direction))
        logger.debug("Incident angle {:.2f}".format(np.degrees(angle)))
        if angle < 0.0 or angle > 0.5 * np.pi:
            raise ValueError("The incident angle must be between 0 and pi/2.")

        # Catch TIR case
        if n2 < n1 and angle > np.arcsin(n2/n1):
            return 1.0
        c = np.cos(angle)
        s = np.sin(angle)
        k = np.sqrt(1 - (n1/n2 * s)**2)
        Rs1 = n1 * c - n2 * k
        Rs2 = n1 * c + n2 * k
        Rs = (Rs1/Rs2)**2
        Rp1 = n1 * k - n2 * c
        Rp2 = n1 * k + n2 * c
        Rp = (Rp1/Rp2)**2
        return 0.5 * (Rs + Rp)
    
    def transform(self, ray: Ray) -> Ray:
        """ Transform ray according to the physics of the interaction.
        """
        context = self.context
        normal = np.array(context.normal)
        ray_ = ray.representation(context.normal_node.root, context.normal_node)
        vec = np.array(ray_.direction)
        d = np.dot(normal, vec)
        reflected_direction = vec - 2 * d * normal
        new_ray_ = replace(ray_, direction=tuple(reflected_direction.tolist()))
        new_ray = new_ray_.representation(context.normal_node, context.normal_node.root)
        return new_ray  # back to world node


class FresnelRefraction(Mechanism):
    """ A frensel refraction interaction which alters the rays direction.
    """
    
    def __init__(self, context):
        """ context: dict, specific information for this interaction.
        """
        super(FresnelRefraction, self).__init__()
        self.context = context

    def transform(self, ray: Ray) -> Ray:
        """ Transform ray according to the physics of the interaction.
        """
        context = self.context
        n1 = context.n1
        n2 = context.n2
        ray_ = ray.representation(context.normal_node.root, context.normal_node)
        normal = np.array(context.normal)
        vector = np.array(ray_.direction)
        n = n1/n2
        dot = np.dot(vector, normal)
        c = np.sqrt(1 - n**2 * (1 - dot**2))
        sign = 1
        if dot < 0.0:
            sign = -1
        refracted_direction = n * vector + sign*(c - sign*n*dot) * normal
        new_ray_ = replace(ray_, direction=tuple(refracted_direction.tolist()))
        new_ray = new_ray_.representation(context.normal_node, context.normal_node.root)
        return new_ray


class Absorption(Mechanism):
    """ Optical absorption interaction which alters the rays position.
    """

    def __init__(self, context):
        """ context: dict, specific information for this interaction.
        """
        super(Absorption, self).__init__()
        self.context = context
        self._path_length = None
        self._interaction_material = None

    def path_length(self, ray) -> float:
        """ Samples the Beer-Lambert distribution and returns the path length at which
        the ray will be absorbed. A further test is needed to compare this against the
        known geometrical distance of the line segment to test whether absorption 
        occurred or not.
        """
        if self._path_length is not None:
            raise AppError("Cannot reuse mechanisms. Path length already calculated.")
        if self._interaction_material is not None:
            raise AppError("Cannot reuse mechanisms. Interaction material already calculated.")
        material = self.context.container.geometry.material
        if not isinstance(material, Absorptive):
            AppError("Need an absorptive material.")
        gamma = np.random.uniform()
        alpha = material.absorption_coefficient(ray.wavelength)
        if np.isclose(alpha, 0.0):
            return float('inf')
        logger.debug('Got alpha({}) = {}'.format(ray.wavelength, alpha))
        #if np.isclose(ray.wavelength, 588.8747279142633):
        #    import pdb; pdb.set_trace()
        d = -np.log(1 - gamma)/alpha
        self._path_length = d
        return d

    @property
    def interaction_material(self):
        return self._interaction_material

    def transform(self, ray: Ray) -> Ray:
        """ Transform ray according to the physics of the interaction. An absorption
            event occurred at the path length along rays trajectory.
        """
        if not isinstance(self._path_length, float):
            raise AppError("Path length has not yet be calculated.")
        if self._interaction_material is not None:
            raise AppError("Cannot reuse mechanisms. Interaction material already calculated.")
        material = self.context.container.geometry.material
        self._interaction_material = material.get_interaction_material(ray.wavelength)
        new_ray = ray.propagate(self._path_length)
        return new_ray


class Emission(Mechanism):
    """ Optical absorption interaction which alters the rays wavelength and
    direction. Emission occurs isotropically.
    """

    def __init__(self, context):
        """ context: dict, specific information for this interaction.
        """
        super(Emission, self).__init__()
        self.context = context

    def probability(self, ray: Ray) -> float:
        """ Returns the probability that the interaction will occur.
        """
        # Zero chance of emission if the material is no emissive
        context = self.context
        material = context.interaction_material
        if material is None:
            raise TraceError("Interaction material cannot be None")
        if not isinstance(material, Emissive):
            return 0.0
        context = self.context
        qy = material.quantum_yield
        return qy

    def transform(self, ray: Ray) -> Ray:
        """ Transform ray according to the physics of the interaction.
        """
        context = self.context
        material = context.interaction_material
        if not isinstance(material, Emissive):
            AppError("Need an emissive material.")
        new_wavelength = material.redshift_wavelength(ray.wavelength)
        new_direction = material.emission_direction()
        
        logger.debug("Wavelength was {} and is now {}".format(ray.wavelength, new_wavelength))
        new_ray = replace(ray, wavelength=new_wavelength, direction=new_direction)
        return new_ray


class TravelPath(Mechanism):
    """ An interaction that moves ray to the ends of it's current path.
    """
    
    def __init__(self, context):
        """ context: dict, specific information for this interaction.
        """
        super(TravelPath, self).__init__()
        self.context = context
    
    def transform(self, ray: Ray) -> Ray:
        new_ray = replace(ray, position=self.context.end_path)
        return new_ray


class KillRay(Mechanism):
    """ An interactions which sets `ray.is_alive=False` and ends tracing of the ray.
    
        Notes
        -----
        This is used when a ray is absorbed but not re-emitted.
    """

    
    def __init__(self, context):
        """ context: dict, specific information for this interaction.
        """
        super(KillRay, self).__init__()
        self.context = context

    def transform(self, ray: Ray) -> Ray:
        new_ray = replace(ray, is_alive=False)
        return new_ray

