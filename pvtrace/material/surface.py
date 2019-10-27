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


class Surface(object):
    """ Surface of a geometry which handles details of reflection at an interface.
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
        print("Incident ray", direction)
        reflected_direction = specular_reflection(direction, normal)
        print("Reflected ray", reflected_direction)
        ray = replace(
            ray,
            direction=tuple(reflected_direction.tolist())
        )
        return ray

    def transmit(self, ray, geometry, container, adjacent):
        """ Simply propgate."""
        return ray


class FresnelSurface(Surface):
    """ Implements reflection and refraction at an interface of two dielectrics.
    """
    
    def is_reflected(self, ray, geometry, container, adjacent):
        """ Monte-Carlo sampling. Default is to transmit.
        """
        # to-do: express ray in local coordinate system
        n1 = container.geometry.material.refractive_index
        n2 = adjacent.geometry.material.refractive_index
        # Be tolerance with definition of surface normal
        normal = geometry.normal(ray.position)
        if np.dot(normal, ray.direction) < 0.0:
            normal = flip(normal)
        angle = angle_between(normal, np.array(ray.direction))
        print("angle {}".format(angle))
        gamma = np.random.uniform()
        return gamma < fresnel_reflectivity(angle, n1, n2)

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

