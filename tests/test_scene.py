import pytest
import sys
import functools
import os
import numpy as np
from anytree import RenderTree
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.geometry.sphere import Sphere
from pvtrace.geometry.box import Box
from pvtrace.light.light import Light
import functools
from pvtrace.material.utils import cone
from pvtrace.light.ray import Ray

from pvtrace.material.material import Material

# Throw small amount of rays in comparison to number of CPUs
RAYS = max(16, os.cpu_count())


def make_test_scene():
    world = Node(
        name="world (air)",
        geometry=Sphere(
            radius=50.0,
            material=Material(refractive_index=1.0),
        ),
    )

    # Node representing a box sphere
    box = Node(
        name="sphere (glass)",
        geometry=Box(
            (10.0, 10.0, 1.0),
            material=Material(refractive_index=1.5),
        ),
        parent=world,
    )

    # Add light source node which fires into the box's top surface
    light = Node(
        name="Light (555nm)",
        light=Light(direction=functools.partial(cone, np.pi / 16)),
        parent=world,
    )
    light.rotate(np.radians(60), (1.0, 0.0, 0.0))

    scene = Scene(world)
    return scene


class TestScene:
    def test_intersection(self):
        root = Node(name="Root")
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
        root = Node(name="Root")
        a = Node(name="A", parent=root)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        b.translate((1.0, 0.0, 0.0))
        # Rotation around x therefore no displace in x
        b.rotate(np.pi / 2, (1.0, 0.0, 0.0))
        loc = (-2.0, 0.0, 0.0)
        vec = (1.0, 0.0, 0.0)
        scene = Scene(root=root)
        intersections = scene.intersections(loc, vec)
        points = tuple([x.point for x in intersections])
        assert points == ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0))

    def test_intersection_with_rotation_around_y(self):
        root = Node(name="Root")
        a = Node(name="A", parent=root)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        b.translate((1.0, 0.0, 0.0))
        # This rotation make an x translation in b become a z translation in a
        b.rotate(np.pi / 2, (0.0, 1.0, 0.0))
        loc = (-2.0, 0.0, 0.0)
        vec = (1.0, 0.0, 0.0)
        scene = Scene(root=root)
        intersections = scene.intersections(loc, vec)
        points = tuple([x.point for x in intersections])
        assert np.allclose(points, ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))

    def test_intersection_with_rotation_around_z(self):
        root = Node(name="Root")
        a = Node(name="A", parent=root)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        a.translate((1.0, 0.0, 0.0))
        # This rotation make an z translation in b becomes a -y translation in a
        a.rotate(np.pi / 2, axis=(0.0, 0.0, 1.0))
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
        )
        scene_intersections = scene.intersections(
            initial_ray.position, initial_ray.direction
        )
        a_intersections = tuple(map(lambda x: x.to(root), scene_intersections))
        assert scene_intersections == a_intersections

    def test_simulate_workers_set_to_one(self):
        scene = make_test_scene()
        results = scene.simulate(RAYS, workers=1)
        assert len(results) == RAYS, "Missing simulation results"

    def test_simulate_workers_set_to_none(self):
        scene = make_test_scene()
        results = scene.simulate(RAYS, workers=None)
        assert len(results) == RAYS, "Missing simulation results"

    def test_simulate_with_constant_seed_1_cpu(self):
        scene = make_test_scene()
        r1 = scene.simulate(RAYS, workers=1, seed=1)
        r2 = scene.simulate(RAYS, workers=1, seed=1)
        assert r1 == r2, "Simulation should be identical"

    def test_simulate_with_constant_seed_multiple_cpus(self):
        scene = make_test_scene()
        # Seed is for debugging only on a single CPU. Trying to set
        # seed on multiple processes will return a ValueError.
        did_raise = False
        try:
            scene.simulate(RAYS, workers=os.cpu_count(), seed=1)
        except ValueError:
            did_raise = True

        assert (
            did_raise == True
        ), "Setting seed with multiple workers should raise an exception"

    def test_simulate_with_different_seed_1_cpu(self):
        scene = make_test_scene()
        r1 = scene.simulate(RAYS, workers=1, seed=1)
        r2 = scene.simulate(RAYS, workers=1, seed=2)
        assert r1 != r2, "Simulation should not be identical"

    def test_simulate_with_auto_seed_multiple_cpu(self):
        scene = make_test_scene()
        r1 = scene.simulate(RAYS, workers=os.cpu_count())
        r2 = scene.simulate(RAYS, workers=os.cpu_count())
        assert r1 != r2, "Simulation should not be identical"

    def test_simulate_with_auto_seed_auto_cpu(self):
        scene = make_test_scene()
        r1 = scene.simulate(RAYS)
        r2 = scene.simulate(RAYS)
        assert r1 != r2, "Simulation should not be identical"

    def test_simulate_with_auto_seed_auto_cpu_low_count(self):
        scene = make_test_scene()
        r1 = scene.simulate(1)
        r2 = scene.simulate(1)
        assert r1 != r2, "Simulation should not be identical"


if __name__ == "__main__":
    pass
