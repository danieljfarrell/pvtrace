import pytest
import numpy as np
from pvtrace.geometry.utils import flip
from pvtrace.material.mechanisms import FresnelReflection
from pvtrace.light.ray import Ray


class TestFresnelReflection:
    
    def test_init(self):
        assert type(FresnelReflection()) == FresnelReflection
    
    def test_normal_reflection(self):
        n1 = 1.0
        n2 = 1.5
        normal = (0.0, 0.0, 1.0)
        angle = 0.0
        ray = Ray(position=(0.0, 0.0, 0.0), direction=(0.0, 0.0, 1.0), wavelength=None)
        fresnel = FresnelReflection()
        assert np.isclose(fresnel.reflectivity(angle, n1, n2), 0.04)
        new_ray = fresnel.transform(ray, {"normal": normal})
        assert np.allclose(flip(ray.direction), new_ray.direction)

    def test_antinormal_reflection(self):
        """ FresnelReflection takes the smallest angle between the ray direction and 
        the normal. Thus the flipped normal will also work.
        """
        n1 = 1.0
        n2 = 1.5
        normal = (0.0, 0.0, -1.0)
        angle = 0.0
        ray = Ray(position=(0.0, 0.0, 0.0), direction=(0.0, 0.0, 1.0), wavelength=None)
        fresnel = FresnelReflection()
        assert np.isclose(fresnel.reflectivity(angle, n1, n2), 0.04)
        new_ray = fresnel.transform(ray, {"normal": normal})
        assert np.allclose(flip(ray.direction), new_ray.direction)
