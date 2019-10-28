import numpy as np
from dataclasses import replace
from pvtrace.geometry.utils import (
    flip,
    angle_between
)
from pvtrace.material.utils import (
    fresnel_reflectivity,
    specular_reflection,
    fresnel_refraction
)


class NullSurface(object):
    """ A surface between two material that only transmits.
    """

    def is_reflected(self, ray, geometry, container, adjacent):
        """ Monte-Carlo sampling. Default is to transmit.
        """
        return False

    def reflect(self, ray, geometry, container, adjacent):
        """ Specular reflection.
        """
        normal = geometry.normal(ray.position)
        direction = ray.direction
        reflected_direction = specular_reflection(direction, normal)
        ray = replace(
            ray,
            direction=tuple(reflected_direction.tolist())
        )
        return ray

    def transmit(self, ray, geometry, container, adjacent):
        """ Simply propgate."""
        return ray


class Surface(NullSurface):
    """ Implements reflection and refraction at an interface of two dielectrics.
    """
    
    def __init__(self, delegate=None):
        """ Parameters
            ----------
            delegate: object
                An object that implements the SurfaceDelegate protocol.
        """
        super(Surface, self).__init__()
        self._delegate = delegate
    
    @property
    def delegate(self):
        return self._delegate

    def reflectivity(self, ray, geometry, container, adjacent):
        if self.delegate:
            r = self.delegate.reflectivity(self, ray, geometry, container, adjacent)
            if r is not None:
                return r
        
        # Calculate Fresnel reflectivity
        n1 = container.geometry.material.refractive_index
        n2 = adjacent.geometry.material.refractive_index
        # Be tolerance with definition of surface normal
        normal = geometry.normal(ray.position)
        if np.dot(normal, ray.direction) < 0.0:
            normal = flip(normal)
        angle = angle_between(normal, np.array(ray.direction))
        r = fresnel_reflectivity(angle, n1, n2)
        return r

    def is_reflected(self, ray, geometry, container, adjacent):
        """ Monte-Carlo sampling. Default is to transmit.
        """
        # to-do: express ray in local coordinate system
        r = self.reflectivity(ray, geometry, container, adjacent)
        gamma = np.random.uniform()
        return gamma < r

    def transmit(self, ray, geometry, container, adjacent):
        """ Refract through the interface.
        """
        # to-do: express ray in local coordinate system
        n1 = container.geometry.material.refractive_index
        n2 = adjacent.geometry.material.refractive_index
        # Be tolerance with definition of surface normal
        normal = geometry.normal(ray.position)
        if np.dot(normal, ray.direction) < 0.0:
            normal = flip(normal)
        refracted_direction = fresnel_refraction(ray.direction, normal, n1, n2)
        ray = replace(
            ray,
            direction=tuple(refracted_direction.tolist())
        )
        return ray

