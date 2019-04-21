import pytest
import sys
import os
import numpy as np
from anytree import RenderTree
from pvtrace.geometry.utils import norm
from pvtrace.geometry.cylinder import Cylinder


class TestCylinder:
    
    def test_init(self):
        assert type(Cylinder(length=1.0, radius=1.0)) == Cylinder

    def test_is_on_surface(self):
        obj = Cylinder(length=1.0, radius=1.0)
        assert obj.is_on_surface((0.0, 0.0, 0.5)) == True
        assert obj.is_on_surface((0.0, 0.0, -0.5)) == True
        assert obj.is_on_surface((0.0, 1.0, 0.0)) == True
        assert obj.is_on_surface((-1.0, 0.0, 0.0)) == True
        assert obj.is_on_surface((0.0, 0.0, 0.6)) == False
        assert obj.is_on_surface((0.0, 1.1, 0.0)) == False
        
    def test_contains(self):
        obj = Cylinder(length=1.0, radius=1.0)
        assert obj.contains((0.0, 0.0, 0.5)) == False
        assert obj.contains((0.0, 0.0, -0.5)) == False
        assert obj.contains((0.0, 1.0, 0.0)) == False
        assert obj.contains((-1.0, 0.0, 0.0)) == False
        assert obj.contains((0.0, 0.0, 0.6)) == False
        assert obj.contains((0.0, 1.1, 0.0)) == False
        assert obj.contains((0.0, 0.0, 0.0)) == True
        assert obj.contains((0.25, 0.25, 0.25)) == True

    def test_intersection(self):
        obj = Cylinder(length=1.0, radius=1.0)
        # surface and bottom
        ro = (-2, 0.2, 0.0)
        rd = norm((1.0, 0.2, -0.2))
        expected = (
            (-0.9082895433880116, 0.41834209132239775, -0.2183420913223977),
            (0.5, 0.7, -0.5)
        )
        points = obj.intersections(ro, rd)
        assert all([np.allclose(a, b) for a, b in zip(expected, points)])

    def test_normal(self):
        obj = Cylinder(length=1.0, radius=1.0)
        assert np.allclose(obj.normal((0.0, 0.0, 0.5)), (0.0, 0.0, 1.0))
        assert np.allclose(obj.normal((0.0, 0.0, -0.5)), (0.0, 0.0, -1.0))
        assert np.allclose(obj.normal((0.0, 1.0, 0.0)), (0.0, 1.0, 0.0))
        assert np.allclose(obj.normal((0.0, -1.0, 0.0)), (0.0, -1.0, 0.0))
        

    def test_is_entering_true(self):
        obj = Cylinder(length=1.0, radius=1.0)
        ro, rd = (0.0, 0.0, 0.5), norm((1.0, 1.0, -1.0))
        assert obj.is_entering(ro, rd) == True
        ro, rd = (0.0, 0.0, 0.5), norm((1.0, 1.0, 1.0))
        assert obj.is_entering(ro, rd) == False
        ro, rd = (0.0, 0.0, -0.5), norm((1.0, 1.0, 1.0))
        assert obj.is_entering(ro, rd) == True
        ro, rd = (0.0, 0.0, -0.5), norm((1.0, 1.0, -1.0))
        assert obj.is_entering(ro, rd) == False
        ro, rd = (0.0, 1.0, 0.0), norm((1.0, -1.0, 1.0))
        assert obj.is_entering(ro, rd) == True
        ro, rd = (0.0, 1.0, 0.0), norm((1.0, 1.0, 1.0))
        assert obj.is_entering(ro, rd) == False
        ro, rd = (-1.0, 0.0, 0.0), norm((1.0, 1.0, 1.0))
        assert obj.is_entering(ro, rd) == True
        ro, rd = (-1.0, 0.0, 0.0), norm((-1.0, 1.0, 1.0))
        assert obj.is_entering(ro, rd) == False

