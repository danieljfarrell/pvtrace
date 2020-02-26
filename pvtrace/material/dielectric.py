from pvtrace.material.material import Material, Decision
from pvtrace.material.properties import Refractive, Absorptive
from pvtrace.material.mechanisms import (
    FresnelRefraction, FresnelReflection, TravelPath, Absorption
)
from pvtrace.geometry.utils import flip, angle_between
from pvtrace.common.errors import TraceError
from dataclasses import replace
from typing import Tuple
import numpy as np
import pandas as pd
import logging
logger = logging.getLogger(__name__)

class Dielectric(Refractive, Material):
    """ A material with a refractive index.
    
        Notes
        -----
        The material is unphysical in the sense that it does not absorb or emit light. 
        But it is useful in development and testing to have material which just 
        interacts with ray without in a purely refractive way.

    """

    def __init__(self, refractive_index):
        super(Dielectric, self).__init__(refractive_index)
        self._transit_mechanism = FresnelRefraction()
        self._return_mechanism = FresnelReflection()
        self._path_mechanism = TravelPath()
        self._emit_mechanism = None

    def trace_path(
            self,
            local_ray: "Ray",
            container_geometry: "Geometry",
            distance : float
        ):
        """ Dielectric material does not have any absorption; this moves ray full dist.
        """
        new_ray = self._path_mechanism.transform(local_ray, {"distance": distance})
        yield new_ray, Decision.TRAVEL

    def trace_surface(
        self,
        local_ray: "Ray",
        container_geometry: "Geometry",
        to_geometry: "Geometry",
        surface_geometry: "Geometry",
    ) -> Tuple[Decision, dict]:
        """ 
        """
        # Get reflectivity for the ray
        normal = surface_geometry.normal(local_ray.position)
        n1 = container_geometry.material.refractive_index(local_ray.wavelength)
        n2 = to_geometry.material.refractive_index(local_ray.wavelength)
        # Be flexible with how the normal is defined
        if np.dot(normal, local_ray.direction) < 0.0:
            normal = flip(normal)
        angle = angle_between(normal, np.array(local_ray.direction))
        if angle < 0.0 or angle > 0.5 * np.pi:
            raise TraceError("The incident angle must be between 0 and pi/2.")
        incident = local_ray.direction
        reflectivity = self._return_mechanism.reflectivity(angle, n1, n2)
        #print("Reflectivity: {}, n1: {}, n2: {}, angle: {}".format(reflectivity, n1, n2, angle))
        gamma = np.random.uniform()
        info = {"normal": normal, "n1": n1, "n2": n2}
        # Pick between reflection (return) and transmission (transit)
        if gamma < reflectivity:
            new_ray = self._return_mechanism.transform(local_ray, info)
            decision = Decision.RETURN
            yield new_ray, decision
        else:
            new_ray = self._transit_mechanism.transform(local_ray, info)
            decision = Decision.TRANSIT
            yield new_ray, decision

    def trace_surface(
        self,
        local_ray: "Ray",
        container_geometry: "Geometry",
        to_geometry: "Geometry",
        surface_geometry: "Geometry",
    ) -> Tuple[Decision, dict]:
        """ 
        """
        # Get reflectivity for the ray
        normal = surface_geometry.normal(local_ray.position)
        n1 = container_geometry.material.refractive_index(local_ray.wavelength)
        n2 = to_geometry.material.refractive_index(local_ray.wavelength)
        # Be flexible with how the normal is defined
        if np.dot(normal, local_ray.direction) < 0.0:
            normal = flip(normal)
        angle = angle_between(normal, np.array(local_ray.direction))
        if angle < 0.0 or angle > 0.5 * np.pi:
            raise TraceError("The incident angle must be between 0 and pi/2.")
        incident = local_ray.direction
        reflectivity = self._return_mechanism.reflectivity(angle, n1, n2)
        #print("Reflectivity: {}, n1: {}, n2: {}, angle: {}".format(reflectivity, n1, n2, angle))
        gamma = np.random.uniform()
        info = {"normal": normal, "n1": n1, "n2": n2}
        # Pick between reflection (return) and transmission (transit)
        if gamma < reflectivity:
            new_ray = self._return_mechanism.transform(local_ray, info)
            decision = Decision.RETURN
            yield new_ray, decision
        else:
            new_ray = self._transit_mechanism.transform(local_ray, info)
            decision = Decision.TRANSIT
            yield new_ray, decision

    @classmethod
    def make_constant(cls, x_range: Tuple[float, float], refractive_index: float):
        """ Returns a dielectric material with spectrally constant refractive index.

        """
        refractive_index = np.column_stack(
            (x_range, [refractive_index, refractive_index])
        )
        return cls(refractive_index)

    @classmethod
    def air(cls, x_range: Tuple[float, float] = (300.0, 4000.0)):
        """ Returns a dielectric material with constant refractive index of 1.0 in
            default range.

        """
        return cls.make_constant(x_range=x_range, refractive_index=1.0)

    @classmethod
    def glass(cls, x_range: Tuple[float, float] = (300.0, 4000.0)):
        """ Returns a dielectric material with constant refractive index of 1.5 in
            default range.

        """
        return cls.make_constant(x_range=x_range, refractive_index=1.5)


class LossyDielectric(Absorptive, Dielectric):
    """ A material with a refractive index that also attenuates light.
    
        Notes
        -----
        This can be used to model a host material such as plastic for luminescent
        concentrators or difference classes when ray tracing lenses.

    """

    def __init__(
        self, refractive_index: np.ndarray, absorption_coefficient: np.ndarray
    ):
        super(LossyDielectric, self).__init__(absorption_coefficient, refractive_index)
        self._transit_mechanism = FresnelRefraction()
        self._return_mechanism = FresnelReflection()
        self._path_mechanism = Absorption()
        self._emit_mechanism = None

    def trace_path(
            self,
            local_ray: "Ray",
            container_geometry: "Geometry",
            distance : float
        ):
        """ Returns .PATH is absorption occurred and .FULL if it reaches the full 
            distance. The distance travelled is returned is the info_dict.
        """
        sampled_distance = self._path_mechanism.path_length(
            local_ray.wavelength, container_geometry.material
        )
        logger.info("sampled_distance {}".format(sampled_distance))
        logger.info("max. distance {}".format(distance))
        if sampled_distance < distance:
            new_ray = self._path_mechanism.transform(
                local_ray, {"distance": sampled_distance}
            )
            new_ray = replace(new_ray, is_alive=False)  # Not re-emitted
            yield new_ray, Decision.ABSORB
            return
        new_ray = self._path_mechanism.transform(
            local_ray, {"distance": distance}
        )
        yield new_ray, Decision.TRAVEL

    def transform(
        self,
        local_ray: "Ray",
        decision: Decision,
        user_info: dict,
    ) -> "Ray":
        ray = super(LossyDielectric, self).transform(local_ray, decision, user_info)
        if decision == Decision.PATH:
            # Lossy Dielectric cannot remit
            ray = replace(ray, is_alive=False)
        return ray

    @classmethod
    def make_constant(
        cls,
        x_range: Tuple[float, float],
        refractive_index: float,
        absorption_coefficient: float,
    ):
        """ Returns a dielectric material with spectrally constant refractive index.

        """
        refractive_index = np.column_stack(
            (x_range, [refractive_index, refractive_index])
        )
        absorption_coefficient = np.column_stack(
            (x_range, [absorption_coefficient, absorption_coefficient])
        )
        return cls(refractive_index, absorption_coefficient)

    def get_interaction_material(self, wavelength: float) -> Material:
        """ This method is needed to distinguish between multiple lumophores objects
            when they are used with the Host material type.
        """
        return self
