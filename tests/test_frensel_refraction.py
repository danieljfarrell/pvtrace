import pytest
import numpy as np
from pvtrace.material.utils import fresnel_refraction


class TestFresnelRefraction:

    def test_normal_refraction(self):
        """ Angle between the normal and ray > 90. Normal is automatically 
            flipped, direction is calculated and then flipped to ensure the 
            ray is travelling the forwards direction after refraction.
        """
        angle, n1, n2 = 0.0, 1.0, 1.5
        normal = (0.0, 0.0, 1.0)  # outward facing normal
        direction = (0.0, 0.0, -1.0)
        new_direction = fresnel_refraction(direction, normal, n1, n2)
        assert np.allclose(direction, new_direction)

    def test_antinormal_refraction(self):
        angle, n1, n2 = 0.0, 1.0, 1.5
        normal = (0.0, 0.0, -1.0)  # inward facing normal
        direction = (0.0, 0.0, -1.0)
        new_direction = fresnel_refraction(direction, normal, n1, n2)
        assert np.allclose(direction, new_direction)
