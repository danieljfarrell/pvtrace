import pytest
import sys
import os
import numpy as np
from anytree import RenderTree
from pvtrace.geometry.box import Box


class TestBox:
    
    def test_init(self):
        assert type(Box(size=(1,1,1))) == Box

    def test_is_on_surface(self):
        b = Box(size=(1,1,1))
        assert b.is_on_surface((0.5, 0.0, 0.0)) == True
        assert b.is_on_surface((0.0, 0.5, 0.0)) == True
        assert b.is_on_surface((0.0, 0.0, 0.5)) == True
        assert b.is_on_surface((-0.5, 0.0, 0.0)) == True
        assert b.is_on_surface((0.0, -0.5, 0.0)) == True
        assert b.is_on_surface((0.0, 0.0, -0.5)) == True
        assert b.is_on_surface((0.0, 0.0, 0.0)) == False
        assert b.is_on_surface((0.501, 0.0, 0.0)) == False
    
    def test_is_on_surface_bad(self):
        b = Box(size=(1.0, 1.0, 0.02))
        bad_pos = (0.06608370507653762, 0.5, -0.007798573829629238)
        bad_dir = (0.2108918904984852, 0.8577010754312269, 0.4689066812555477)
        ray_pos = np.array(bad_pos) - 0.0001 * np.array(bad_dir)
        ray_dir = bad_dir
        #import pdb; pdb.set_trace()
        assert b.is_on_surface(bad_pos) == True  # this should be on surface!
        
        b = Box(size=(1.0, 3.0, 0.02))
        bad_pos = (-0.5, -0.2415708917159319, -0.008736363958583498)
        assert b.is_on_surface(bad_pos) == True 

    def test_contains(self):
        b = Box(size=(1,1,1))
        assert b.contains((0.0, 0.0, 0.0)) == True
        assert b.contains((0.0, 0.0, 0.5)) == False
        assert b.contains((0.0, 0.0, 1.0)) == False

    def test_intersection(self):
        b = Box(size=(1,1,1))
        ro = (-2.0, 0.0, 0.0)
        rd = (1.0, 0.0, 0.0)
        assert b.intersections(ro, rd) == ((-0.5, 0.0, 0.0), (0.5, 0.0, 0.0))

    def test_normal(self):
        b = Box(size=(1,1,1))
        assert np.allclose(b.normal(( 0.5,  0.0,  0.0)), ( 1.0,  0.0,  0.0))
        assert np.allclose(b.normal(( 0.0,  0.5,  0.0)), ( 0.0,  1.0,  0.0))
        assert np.allclose(b.normal(( 0.0,  0.0,  0.5)), ( 0.0,  0.0,  1.0))
        assert np.allclose(b.normal((-0.5,  0.0,  0.0)), (-1.0,  0.0,  0.0))
        assert np.allclose(b.normal(( 0.0, -0.5,  0.0)), ( 0.0, -1.0,  0.0))
        assert np.allclose(b.normal(( 0.0,  0.0, -0.5)), ( 0.0,  0.0, -1.0))

    def test_is_entering(self):
        b = Box(size=(1,1,1))
        assert b.is_entering((0.5, 0.0, 0.0), (-1.0,  0.0,  0.0)) == True
        assert b.is_entering((0.5, 0.0, 0.0), ( 1.0,  0.0,  0.0)) == False
        assert b.is_entering((0.0, 0.5, 0.0), ( 0.0, -1.0,  0.0)) == True
        assert b.is_entering((0.0, 0.5, 0.0), ( 0.0,  1.0,  0.0)) == False
        assert b.is_entering((0.0, 0.0, 0.5), ( 0.0,  0.0, -1.0)) == True
        assert b.is_entering((0.0, 0.0, 0.5), ( 0.0,  0.0,  1.0)) == False

