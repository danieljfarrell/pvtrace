import pytest
import sys
import os
import numpy as np
from anytree import RenderTree
from pvtrace.geometry.sphere import Sphere


class TestSphere:
    
    def test_init(self):
        assert type(Sphere(radius=1)) == Sphere

    def test_is_on_surface(self):
        s = Sphere(radius=1)
        assert s.is_on_surface((0.0, 0.0, 1.0)) == True
        assert s.is_on_surface((0.0, 0.0, 0.0)) == False
    
    def test_contains(self):
        s = Sphere(radius=1)
        assert s.contains((0.0, 0.0, 2.0)) == False
        assert s.contains((0.0, 0.0, 1.0)) == False
        assert s.contains((0.0, 0.0, 0.0)) == True

    def test_intersection(self):
        s = Sphere(radius=1)
        ro = (-2.0, 0.0, 0.0)
        rd = (1.0, 0.0, 0.0)
        assert s.intersections(ro, rd) == ((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0))

    def test_normal(self):
        s = Sphere(radius=1)
        assert np.allclose(s.normal((0.0, 0.0, 1.0)), (0.0, 0.0, 1.0))
    
    def test_is_entering_true(self):
        s = Sphere(radius=1)
        assert s.is_entering((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)) == True

    def test_is_entering_false(self):
        s = Sphere(radius=1)
        assert s.is_entering((-1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)) == False

