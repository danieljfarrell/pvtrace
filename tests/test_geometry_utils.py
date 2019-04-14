import pytest
import numpy as np
from pvtrace.geometry.utils import angle_between, magnitude, norm, smallest_angle_between, close_to_zero, floats_close, EPS_ZERO

class TestGeometryUtils:
    
    def test_close_to_zero(self):
        # Value is considered zero if abs(value) < EPS_ZERO
        zero = 0.0
        assert close_to_zero(zero) == True
        assert close_to_zero(zero + 0.9*EPS_ZERO) == True
        assert close_to_zero(zero - 0.9*EPS_ZERO) == True
        assert close_to_zero(zero + EPS_ZERO) == False
        assert close_to_zero(zero - EPS_ZERO) == False

    def test_floats_close(self):
        a = np.random.random()
        assert floats_close(a, a + EPS_ZERO) == False
        assert floats_close(a, a - EPS_ZERO) == False
        assert floats_close(a, a + 0.9*EPS_ZERO) == True
        assert floats_close(a, a - 0.9*EPS_ZERO) == True
        assert floats_close(a, a) == True

    def test_magnitude(self):
        v = (1.0, 1.0, 1.0)
        assert np.isclose(magnitude(v), np.sqrt(3.0))

    def test_norm(self):
        v = (1.0, 1.0, 1.0)
        expected = np.array(v) / magnitude(v)
        assert np.allclose(norm(v), expected)

    def test_angle_between(self):
        normal = norm((1.0, 0.0, 0.0))
        vector = norm((1.0, 0.0, 0.0))
        assert angle_between(normal, vector) == 0.0
        assert angle_between(-normal, vector) == np.pi

    def test_angle_between_acute(self):
        # 45 deg. between vectors (pi/4)
        v1 = norm((1.0, 1.0, 0.0))
        v2 = norm((1.0, 0.0, 0.0))
        rads = angle_between(v1, v2)
        expected = np.pi/4.0
        assert np.isclose(rads, expected)

    def test_angle_between_obtuse(self):
        """ Negative dot product means vectors form an obtuse angle.
        """
        v1 = norm((1.0, 1.0, 0.0))
        v2 = norm((-1.0, 0.0, 0.0))
        d = np.dot(v1, v2)
        assert d < 0.0
        rads = angle_between(v1, v2)
        expected = np.pi - np.pi/4.0
        assert np.isclose(rads, expected)

    def test_smallest_angle_between(self):
        v1 = norm((1.0, 1.0, 0.0))
        v2 = norm((-1.0, 0.0, 0.0))
        smallest_angle_between(v1, v2)




if __name__ == "__main__":
    pass
