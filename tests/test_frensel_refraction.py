import pytest
import numpy as np
from pvtrace.material.mechanisms import FresnelRefraction
from pvtrace.light.ray import Ray


class TestFresnelReflection:
    
    def test_init(self):
        assert type(FresnelRefraction()) == FresnelRefraction
    
    def test_normal_reflection(self):
        n1 = 1.0
        n2 = 1.5
        normal = (0.0, 0.0, 1.0)
        angle = 0.0
        ray = Ray(position=(0.0, 0.0, 0.0), direction=(0.0, 0.0, 1.0), wavelength=None)
        fresnel = FresnelRefraction()
        new_ray = fresnel.transform(ray, {"n1":n1, "n2":n2, "normal": normal})
        assert np.allclose(ray.direction, new_ray.direction)

    def test_antinormal_reflection(self):
        """ FresnelReflection takes the smallest angle between the ray direction and 
        the normal. Thus the flipped normal will also work.
        """
        n1 = 1.0
        n2 = 1.5
        normal = (0.0, 0.0, -1.0)
        angle = 0.0
        ray = Ray(position=(0.0, 0.0, 0.0), direction=(0.0, 0.0, 1.0), wavelength=None)
        fresnel = FresnelRefraction()
        new_ray = fresnel.transform(ray, {"n1":n1, "n2":n2, "normal": normal})
        assert np.allclose(ray.direction, new_ray.direction)
