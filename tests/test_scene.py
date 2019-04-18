import pytest
import sys
import os
import numpy as np
from anytree import RenderTree
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.geometry.sphere import Sphere
from pvtrace.light.ray import Ray


class TestScene:
    
    def test_intersection(self):
        root = Node(name='Root')
        a = Node(name="A", parent=root)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        a.translate((1.0, 0.0, 0.0))
        loc = (-2.0, 0.0, 0.0)
        vec = (1.0, 0.0, 0.0)
        scene = Scene(root=root)
        intersections = scene.intersections(loc, vec)
        points = tuple([x.point for x in intersections])
        # In frame of a everything is shifed 1 along x
        assert points == ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0))

    def test_intersection_with_rotation_around_x(self):
        root = Node(name='Root')
        a = Node(name="A", parent=root)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        b.translate((1.0, 0.0, 0.0))
        # Rotation around x therefore no displace in x
        b.rotate(np.pi/2, (1.0, 0.0, 0.0))
        loc = (-2.0, 0.0, 0.0)
        vec = (1.0, 0.0, 0.0)
        scene = Scene(root=root)
        intersections = scene.intersections(loc, vec)
        points = tuple([x.point for x in intersections])
        assert points == ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0))

    def test_intersection_with_rotation_around_y(self):
        root = Node(name='Root')
        a = Node(name="A", parent=root)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        b.translate((1.0, 0.0, 0.0))
        # This rotation make an x translation in b become a z translation in a
        b.rotate(np.pi/2, (0.0, 1.0, 0.0))
        loc = (-2.0, 0.0, 0.0)
        vec = (1.0, 0.0, 0.0)
        scene = Scene(root=root)
        intersections = scene.intersections(loc, vec)
        points = tuple([x.point for x in intersections])
        assert np.allclose(points, ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))

    def test_intersection_with_rotation_around_z(self):
        root = Node(name='Root')
        a = Node(name="A", parent=root)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        a.translate((1.0, 0.0, 0.0))
        # This rotation make an z translation in b becomes a -y translation in a
        a.rotate(np.pi/2, axis=(0.0, 0.0, 1.0))
        loc = (-2.0, 0.0, 0.0)
        vec = (1.0, 0.0, 0.0)
        scene = Scene(root=root)
        intersections = scene.intersections(loc, vec)
        points = tuple([x.point for x in intersections])
        assert np.allclose(points, ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))
    
    def test_intersection_coordinate_system(self):
        root = Node(name="Root", geometry=Sphere(radius=10.0))
        a = Node(name="A", parent=root, geometry=Sphere(radius=1.0))
        a.translate((1.0, 0.0, 0.0))
        scene = Scene(root)
        initial_ray = Ray(
            position=(-2.0, 0.0, 0.0),
            direction=(1.0, 0.0, 0.0),
            wavelength=None,
            is_alive=True,
        )
        scene_intersections = scene.intersections(
            initial_ray.position,
            initial_ray.direction
        )
        a_intersections = tuple(map(lambda x: x.to(root), scene_intersections))
        assert scene_intersections == a_intersections

if __name__ == '__main__':
    pass
