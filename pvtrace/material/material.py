from typing import Tuple
import numpy as np
from pvtrace.material.component import Component
from pvtrace.material.surface import Surface
import logging

logger = logging.getLogger(__name__)


class Material(object):
    def __init__(self, refractive_index: float, surface=None, components=None):
        self.refractive_index = refractive_index
        self.surface = Surface() if surface is None else surface
        self.components = [] if components is None else components

    # Cache this function!
    def total_attenutation_coefficient(self, wavelength: float) -> float:
        coefs = [x.coefficient(wavelength) for x in self.components]
        alpha = np.sum(coefs)
        return alpha

    def is_absorbed(self, ray, full_distance) -> Tuple[bool, float]:
        distance = self.penetration_depth(ray.wavelength)
        return (distance < full_distance, distance)

    def penetration_depth(self, wavelength: float) -> float:
        """ Monte-Carlo sampling to find penetration depth of ray due to total
            attenuation coefficient of the material.
        
            Arguments
            --------
            wavelength: float
                The ray wavelength in nanometers.

            Returns
            -------
            depth: float
                The penetration depth in centimetres or `float('inf')`.
        """
        alpha = self.total_attenutation_coefficient(wavelength)
        if np.isclose(alpha, 0.0):
            return float("inf")
        elif not np.isfinite(alpha):
            return 0.0
        # Sample exponential distribution
        depth = -np.log(1 - np.random.uniform()) / alpha
        return depth

    def component(self, wavelength: float) -> Component:
        """ Monte-Carlo sampling to find which component captures the ray.
        """
        coefs = np.array([x.coefficient(wavelength) for x in self.components])
        if np.any(coefs < 0.0):
            raise ValueError("Must be positive.")
        count = len(self.components)
        bins = list(range(0, count + 1))
        cdf = np.cumsum(coefs)
        pdf = cdf / max(cdf)
        pdf = np.hstack([0, pdf[:]])
        pdfinv_lookup = np.interp(np.random.uniform(), pdf, bins)
        index = int(np.floor(pdfinv_lookup))
        component = self.components[index]
        return component
