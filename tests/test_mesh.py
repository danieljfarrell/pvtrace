import pytest
import numpy as np
from pvtrace.geometry.utils import norm
from pvtrace.geometry.mesh import Mesh
from pvtrace.common.errors import GeometryError
import trimesh

class TestMesh:
    
    def test_init(self):
        assert type(Mesh(trimesh.creation.icosphere())) == Mesh

    def test_intersections_1(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1)
        direction = (0, 0, 1)
        # Assert two intersection points
        assert np.allclose(m.intersections(position, direction), ((0.0, 0.0, -1.0), (0.0, 0.0, 1.0)))
    
    def test_intersections_2(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, 1)
        direction = (0, 0, -1)
        # Assert two intersection points
        assert np.allclose(m.intersections(position, direction), ((0.0, 0.0, 1.0), (0.0, 0.0, -1.0)))
    
    def test_intersection_3(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, 1)
        direction = (0, 0, 1)
        # Assert one intersection points
        m.intersections(position, direction)
        assert np.allclose(m.intersections(position, direction), ((0.0, 0.0, 1.0)))

    def test_intersection_4(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1)
        direction = (0, 0, -1)
        # Assert one intersection points
        m.intersections(position, direction)
        assert np.allclose(m.intersections(position, direction), ((0.0, 0.0, -1.0)))

    def test_intersection_5(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1.1)
        direction = (0, 0, -1)
        # Assert zero intersection points
        assert len(m.intersections(position, direction)) == 0

    def test_fat_point_not_contained(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1.1)
        # Assert not contained
        assert m.contains(position) == False

    def test_interior_point_contained(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, 0.9)
        # Assert not contained
        assert m.contains(position) == True

    def test_surface_point_not_contained(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, 1.0)
        # Assert not contained
        assert m.contains(position) == False
    
    def test_far_point_not_on_surface(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1.1)
        # Assert not on surface
        assert m.is_on_surface(position) == False

    def test_interior_point_not_on_surface(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, 0.9)
        # Assert not on surface
        assert m.is_on_surface(position) == False

    def test_on_surface(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, 1.0)
        # Assert not on surface
        assert m.is_on_surface(position) == True

    def test_surface_point_is_entering_1(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1)
        direction = (0, 0, 1)
        # Assert surface point is entering
        assert m.is_entering(position, direction) == True

    def test_surface_point_is_exiting_2(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1)
        direction = (0, 0, -1)
        # Assert surface point is entering
        assert m.is_entering(position, direction) == False

    def test_surface_point_is_exiting_3(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1)
        direction = norm((1, 0, -1))  # tangential ray
        # Assert surface point is entering
        assert m.is_entering(position, direction) == False

    def test_far_point_arg_to_is_entering_raises(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1.1)
        direction = (0, 0, -1)  # travelling away
        try:
            m.is_entering(position, direction)
        except GeometryError:
            assert True
        else:
            assert False, "Expected GeometryError to be raised."

    def test_interior_point_arg_to_is_entering_raises(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -0.9)
        direction = (0, 0, -1)
        try:
            m.is_entering(position, direction)
        except GeometryError:
            # Raises because point is not on surface
            assert True
        else:
            assert False, "Expected GeometryError to be raised."

    def test_is_entering_1(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1.0)
        direction = (0, 0, -1)  # Travelling away, not entering
        assert m.is_entering(position, direction) == False

    def test_is_entering_2(self):
        m = Mesh(trimesh.creation.icosphere())
        position = (0, 0, -1.0)
        direction = (0, 0, 1.0)  # Travelling towards, is entering
        assert m.is_entering(position, direction) == True

