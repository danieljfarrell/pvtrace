import pytest
import numpy as np
from pvtrace.geometry.utils import flip
from pvtrace.material.utils import fresnel_reflectivity, specular_reflection


class TestFresnelReflection:
    
    def test_reflection_coefficient(self):
        angle, n1, n2 = 0.0, 1.0, 1.5
        assert np.isclose(fresnel_reflectivity(angle, n1, n2), 0.04)

    def test_normal_reflection(self):
        angle, n1, n2 = 0.0, 1.0, 1.5
        normal = (0.0, 0.0, 1.0)  # outward facing normal
        direction = (0.0, 0.0, -1.0)
        new_direction = specular_reflection(direction, normal)
        assert np.allclose((0.0, 0.0, 1.0), new_direction)

    def test_antinormal_reflection(self):
        angle, n1, n2 = 0.0, 1.0, 1.5
        normal = (0.0, 0.0, -1.0)  # inward facing normal
        direction = (0.0, 0.0, -1.0)
        new_direction = specular_reflection(direction, normal)
        # `specular_reflection` assumes the normal is defined incorrectly and 
        # automatically flips it. Thus the ray direction is still reversed.
        assert np.allclose((0.0, 0.0, 1.0), new_direction)
