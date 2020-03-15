import abc
import numpy as np
from typing import Tuple
from dataclasses import replace
from pvtrace.geometry.utils import flip, angle_between
from pvtrace.material.utils import (
    fresnel_reflectivity,
    specular_reflection,
    fresnel_refraction,
)


class SurfaceDelegate(abc.ABC):
    """ Defines a interface for custom surface interactions.
    """

    @abc.abstractmethod
    def reflectivity(self, surface, ray, geometry, container, adjacent) -> float:
        """ Returns the reflectivity given the interaction.
        
            Parameters
            ----------
            surface: Surface
                The surface object owned by the material.
            ray: Ray
                The incident ray.
            geometry: Geometry
                The geometry being hit.
            container: Node
                The node containing the incident ray.
            adjacent: Node
                The node that would contain the ray if transmitted.
        """
        pass

    @abc.abstractmethod
    def reflected_direction(
        self, surface, ray, geometry, container, adjacent
    ) -> Tuple[float, float, float]:
        """ Returns the reflected direction vector (ix, iy, iz).
        
            Parameters
            ----------
            surface: Surface
                The surface object owned by the material.
            ray: Ray
                The incident ray.
            geometry: Geometry
                The geometry being hit.
            container: Node
                The node containing the incident ray.
            adjacent: Node
                The node that would contain the ray if transmitted.
        """
        pass

    @abc.abstractmethod
    def transmitted_direction(
        self, surface, ray, geometry, container, adjacent
    ) -> Tuple[float, float, float]:
        """ Returns the transmitted direction vector (ix, iy, iz).
        
            Parameters
            ----------
            surface: Surface
                The surface object owned by the material.
            ray: Ray
                The incident ray.
            geometry: Geometry
                The geometry being hit.
            container: Node
                The node containing the incident ray.
            adjacent: Node
                The node that would contain the ray if transmitted.
        """
        pass


class NullSurfaceDelegate(SurfaceDelegate):
    """ Only transmits rays, no reflection or refraction.
        
        This is useful for counting rays.
    """

    def reflectivity(self, surface, ray, geometry, container, adjacent):
        """ Returns zero.
        """
        return 0.0

    def reflected_direction(self, surface, ray, geometry, container, adjacent):
        """ raises NotImplementedError if called.
        """
        # This method should never be called but must be implemented.
        raise NotImplementedError("This surface delegate does not reflect.")

    def transmitted_direction(self, surface, ray, geometry, container, adjacent):
        """ Simply returns `ray.direction.`
        """
        return ray.direction


class FresnelSurfaceDelegate(SurfaceDelegate):
    """ Fresnel reflection and refraction on the surface.
    """

    def reflectivity(self, surface, ray, geometry, container, adjacent):
        """ Returns the reflectivity given the interaction.
        
            Parameters
            ----------
            surface: Surface
                The surface object owned by the material.
            ray: Ray
                The incident ray.
            geometry: Geometry
                The geometry being hit.
            container: Node
                The node containing the incident ray.
            adjacent: Node
                The node that would contain the ray if transmitted.
        """
        # Calculate Fresnel reflectivity
        n1 = container.geometry.material.refractive_index
        n2 = adjacent.geometry.material.refractive_index
        # Be tolerance with definition of surface normal
        normal = geometry.normal(ray.position)
        if np.dot(normal, ray.direction) < 0.0:
            normal = flip(normal)
        angle = angle_between(normal, np.array(ray.direction))
        r = fresnel_reflectivity(angle, n1, n2)
        return float(r)

    def reflected_direction(self, surface, ray, geometry, container, adjacent):
        """ Returns the reflected direction vector (ix, iy, iz).
        
            Parameters
            ----------
            surface: Surface
                The surface object owned by the material.
            ray: Ray
                The incident ray.
            geometry: Geometry
                The geometry being hit.
            container: Node
                The node containing the incident ray.
            adjacent: Node
                The node that would contain the ray if transmitted.
        """
        normal = geometry.normal(ray.position)
        direction = ray.direction
        reflected_direction = specular_reflection(direction, normal)
        return tuple(reflected_direction.tolist())

    def transmitted_direction(self, surface, ray, geometry, container, adjacent):
        """ Returns the transmitted direction vector (ix, iy, iz).
        
            Parameters
            ----------
            surface: Surface
                The surface object owned by the material.
            ray: Ray
                The incident ray.
            geometry: Geometry
                The geometry being hit.
            container: Node
                The node containing the incident ray.
            adjacent: Node
                The node that would contain the ray if transmitted.
        """
        n1 = container.geometry.material.refractive_index
        n2 = adjacent.geometry.material.refractive_index
        # Be tolerance with definition of surface normal
        normal = geometry.normal(ray.position)
        if np.dot(normal, ray.direction) < 0.0:
            normal = flip(normal)
        refracted_direction = fresnel_refraction(ray.direction, normal, n1, n2)
        return tuple(refracted_direction.tolist())


class BaseSurface(abc.ABC):
    @property
    @abc.abstractmethod
    def delegate(self):
        """ Return an object which implements the `SurfaceDelegate` protocol.
        """

    @abc.abstractmethod
    def is_reflected(self, ray, geometry, container, adjacent):
        """ Returns `True` is the ray is reflected.
        """

    @abc.abstractmethod
    def reflect(self, ray, geometry, container, adjacent):
        """ Returns ray which is reflected from the interface.
        """

    @abc.abstractmethod
    def transmit(self, ray, geometry, container, adjacent):
        """ Returns ray which is transmitted from the interface.
        """


class Surface(BaseSurface):
    """ Defines a set of possible events that can happen at a material's surface.
    
        A delegate object provides surface reflectivity and reflection and 
        transmission angles.
    
        The default delegate provides Fresnel reflection and refraction.
    
        Custom surface reflection coefficients and transmission and reflection
        directions can be implemented by supplying a custom objects which implements
        SurfaceDelegate interface.
    """

    def __init__(self, delegate=None):
        """ Parameters
            ----------
            delegate: object
                An object that implements the SurfaceDelegate protocol.
        """
        super(Surface, self).__init__()
        self._delegate = FresnelSurfaceDelegate() if delegate is None else delegate

    @property
    def delegate(self):
        """ Return an object which implements the `SurfaceDelegate` protocol.
        """
        return self._delegate

    def is_reflected(self, ray, geometry, container, adjacent):
        """ Returns `True` is the ray is reflected.
        """
        r = self.delegate.reflectivity(self, ray, geometry, container, adjacent)
        if not isinstance(r, (int, float, np.float, np.int)):
            raise ValueError("Reflectivity must be a number.")
        if r == 0.0:
            return False
        gamma = np.random.uniform()
        return gamma < r

    def reflect(self, ray, geometry, container, adjacent):
        """ Returns ray which is reflected from the interface.
        """
        direction = self.delegate.reflected_direction(
            self, ray, geometry, container, adjacent
        )
        if not isinstance(direction, tuple):
            raise ValueError(
                "Delegate method `reflected_direction` should return a tuple."
            )
        if len(direction) != 3:
            raise ValueError(
                "Delegate method `reflected_direction` should return a tuple of length 3."
            )
        return replace(ray, direction=direction)

    def transmit(self, ray, geometry, container, adjacent):
        """ Returns ray which is transmitted from the interface.
        """
        direction = self.delegate.transmitted_direction(
            self, ray, geometry, container, adjacent
        )
        if not isinstance(direction, tuple):
            raise ValueError(
                "Delegate method `transmitted_direction` should return a tuple."
            )
        if len(direction) != 3:
            raise ValueError(
                "Delegate method `transmitted_direction` should return a tuple of length 3."
            )
        return replace(ray, direction=direction)
