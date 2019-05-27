""" This module contains different physical interaction models that a ray can
have with materials. Material objects are build up from these basic
interactions.
"""
import abc
from dataclasses import replace
from enum import Enum, unique
import numpy as np
from pvtrace.geometry.utils import angle_between, norm, flip, EPS_ZERO
from pvtrace.light.ray import Ray
from pvtrace.common.errors import AppError
#from pvtrace.material.properties import Refractive, Emissive, Absorptive
from pvtrace.geometry.utils import magnitude
import logging
logger = logging.getLogger(__name__)


def _check_required_keys(required: set, context: dict):
    keys = set(list(context.keys()))
    if not required.issubset(keys):
        missing = sorted(required - keys)
        KeyError("Context dictionary has missing keys {}.".format(missing))


class Mechanism(abc.ABC):
    """ Physical interaction which can alter position, direction or 
    wavelength of the ray.
    """    

    @abc.abstractmethod
    def transform(self, ray: Ray, context: dict) -> Ray:
        """ Transform ray according to the physics of the interaction.
        
            Parameters
            ----------
            ray : Ray
                The ray undergoing the transformation.
            context : dict
                Dictionary containing information of the calculation.
        """

    def __repr__(self):
        return self.__class__.__name__


class FresnelReflection(Mechanism):
    """ A frensel reflection interaction which alters the rays direction.
    """

    def reflectivity(self, angle: float, n1: float, n2: float) -> float:
        """ Returns the probability that the interaction will occur.

            Parameters
            ----------
            angle : float
                The angle of incidence in radians
            n1: float
                The refractive index of origin side of the interface
            n2 : float
                The refractive index of the destination side of the interface

            Returns
            -------
            r: float
                The reflectivity of the interface
        """
        
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
        r = 0.5 * (Rs + Rp)
        return r

    def transform(self, ray: Ray, context: dict) -> Ray:
        """ Transform ray according to the physics of the interaction.
        
            Parameters
            ----------
            ray : Ray
                The ray undergoing the transformation.
            context : dict
                Dictionary containing information of the calculation.

            Raises
            ------
            KeyError
                If the context dictionary has missing keys.

            Notes
            -----
            The ray and any position or direction vectors in the context dictionary
            must be in the same coordinate system.
        
            This method required the following items in the dictionary,
        
            normal : 3-tuple of floats
                The normal vector of the surface
            
        """
        required = set(["normal"])
        _check_required_keys(required, context)
        # Must be in the local frame
        normal = np.array(context["normal"])
        if np.dot(normal, ray.direction) < 0.0:
            normal = flip(normal)
        
        vec = np.array(ray.direction)
        d = np.dot(normal, vec)
        reflected_direction = vec - 2 * d * normal
        new_position = np.array(ray.position) +  2 * EPS_ZERO * np.array(flip(normal))
        new_ray = replace(
            ray,
            position=new_position, 
            direction=tuple(reflected_direction.tolist())
        )
        return new_ray


class FresnelRefraction(Mechanism):
    """ A frensel refraction interaction which alters the rays direction.
    """

    def transform(self, ray: Ray, context: dict) -> Ray:
        """ Transform ray according to the physics of the interaction.
        
            Parameters
            ----------
            ray : Ray
                The ray undergoing the transformation.
            context : dict
                Dictionary containing information of the calculation.
            
            Notes
            -----
            The ray and any position or direction vectors in the context dictionary
            must be in the same coordinate system.
        
            This method required the following items in the dictionary,
        
            normal : 3-tuple of floats
                The normal vector of the surface.
            n1 : float
                The refractive index of the origin material.
            n2: float
                The refractive index of the destination material.
        """
        required = set(["normal", "n1", "n2"])
        _check_required_keys(required, context)
        normal = np.array(context["normal"])
        if np.dot(normal, ray.direction) < 0.0:
            normal = flip(normal)
        n1 = context["n1"]
        n2 = context["n2"]
        vector = np.array(ray.direction)
        n = n1/n2
        dot = np.dot(vector, normal)
        c = np.sqrt(1 - n**2 * (1 - dot**2))
        sign = 1
        if dot < 0.0:
            sign = -1
        refracted_direction = n * vector + sign*(c - sign*n*dot) * normal
        # maybe not best to use refracted direction; better to use normal because it 
        # moves a constant distance from the surface everytime?
        new_position = np.array(ray.position) +  2 * EPS_ZERO * np.array(normal)
        new_ray = replace(
            ray,
            position=tuple(new_position.tolist()),
            direction=tuple(refracted_direction.tolist())
        )
        return new_ray


class Absorption(Mechanism):
    """ Optical absorption interaction which alters the rays position.
    """

    def path_length(self, wavelength: float, material: "Material") -> float:
        """ Samples the Beer-Lambert distribution and returns the path length at which
        the ray will be absorbed. A further test is needed to compare this against the
        known geometrical distance of the line segment to test whether absorption 
        occurred or not.
        """
        from pvtrace.material.properties import Absorptive
        if not isinstance(material, Absorptive):
            AppError("Need an absorptive material.")
        gamma = np.random.uniform()
        alpha = material.absorption_coefficient(wavelength)
        if np.isclose(alpha, 0.0):
            return float('inf')
        logger.info('Got alpha({}) = {}'.format(wavelength, alpha))
        d = -np.log(1 - gamma)/alpha
        return d

    def transform(self, ray: Ray, context: dict) -> Ray:
        """ Transform ray according to the physics of the interaction. An absorption
            event occurred at the path length along rays trajectory.
        """
        _check_required_keys(set(["distance"]), context)
        distance = context["distance"]
        new_ray = ray.propagate(distance)
        return new_ray


class Emission(Mechanism):
    """ Optical absorption interaction which alters the rays wavelength and
    direction. Emission occurs isotropically.
    """

    def quantum_yield(self, material: "Material") -> float:
        """ Returns the probability that the interaction will occur.
        """
        # Zero chance of emission if the material is no emissive
        if material is None:
            raise TraceError("Interaction material cannot be None")
        from pvtrace.material.properties import Emissive
        if not isinstance(material, Emissive):
            return 0.0
        qy = material.quantum_yield
        return qy

    def transform(self, ray: Ray, context: dict) -> Ray:
        """ Redshift and re-emit picking a new emission direction.
        """
        _check_required_keys(set(["material"]), context)
        material = context["material"]
        from pvtrace.material.properties import Emissive
        if not isinstance(material, Emissive):
            AppError("Need an emissive material.")
        new_wavelength = material.redshift_wavelength(ray.wavelength)
        new_direction = material.emission_direction()
        logger.debug("Wavelength was {} and is now {}".format(ray.wavelength, new_wavelength))
        new_ray = replace(ray, wavelength=new_wavelength, direction=new_direction)
        return new_ray


class CrossInterface(Mechanism):
    """ An interaction which moves a ray across an interface without altering
        any of the ray attributes.
    """

    def transform(self, ray: Ray, context: dict) -> Ray:
        _check_required_keys(set(["normal"]), context)
        normal = context["normal"]
        # check for angle > 90
        if np.dot(normal, ray.direction) < 0.0:
            normal = flip(normal)
        distance = 2*EPS_ZERO
        new_position = np.array(ray.position) + distance * np.array(normal)
        new_ray = replace(ray, position=tuple(new_position.tolist()))
        return new_ray


class TravelPath(Mechanism):
    """ An interaction that moves ray to the ends of it's current path.
    """
    
    def transform(self, ray: Ray, context: dict) -> Ray:
        _check_required_keys(set(["distance"]), context)
        distance = context["distance"]
        new_position = np.array(ray.position) + distance * np.array(ray.direction)
        new_ray = replace(ray, position=tuple(new_position.tolist()))
        return new_ray


class KillRay(Mechanism):
    """ An interactions which sets `ray.is_alive=False` and ends tracing of the ray.
    
        Notes
        -----
        This is used when a ray is absorbed but not re-emitted.
    """

    def transform(self, ray: Ray, context: dict) -> Ray:
        new_ray = replace(ray, is_alive=False)
        return new_ray

