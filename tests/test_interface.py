import pytest
import numpy as np
from dataclasses import replace
from pvtrace.material.material import Dielectric
from pvtrace.material.interface import DielectricInterface
from pvtrace.trace.context import Context, Kind
from pvtrace.scene.node import Node
from pvtrace.geometry.sphere import Sphere
from pvtrace.light.ray import Ray
from pvtrace.geometry.utils import norm, angle_between


class TestInterface:

    def test_zero_reflection(self):
        np.random.seed(0)
        mat1 = Dielectric.make_constant((400, 800), 1.0)
        mat2 = Dielectric.make_constant((400, 800), 1.0)
        root = Node(name="Root", parent=None)
        root.geometry = Sphere(radius=10.0, material=mat1)
        a = Node(name="A", parent=root)
        a.geometry = Sphere(radius=1.0, material=mat2)
        ray = Ray(position=(-1.0, 0.0, 0.0), direction=(0.0, 0.0, 1.0), wavelength=555.0, is_alive=True)
        from_node = root
        to_node = a
        interface = DielectricInterface(from_node, to_node)
        new_ray = interface.trace(ray)
        expected = ray  # unchanged
        assert new_ray == expected

    def test_ray_refracting_interaction(self):
        # air to low refractive index -> refraction
        np.random.seed(0)
        mat1 = Dielectric.make_constant((400, 800), 1.0)
        mat2 = Dielectric.make_constant((400, 800), 1.5)
        root = Node(name="Root", parent=None)
        root.geometry = Sphere(radius=10.0, material=mat1)
        a = Node(name="A", parent=root)
        a.geometry = Sphere(radius=1.0, material=mat2)
        ray = Ray(position=(-1.0, 0.0, 0.0), direction=norm((-0.2, 0.2, 1.0)), wavelength=555.0, is_alive=True)
        from_node = root
        to_node = a
        interface = DielectricInterface(from_node, to_node)
        new_ray = interface.trace(ray)
        # Rays remains travelling in same direction more or less (i.e. is not reflected)
        assert np.sign(ray.direction[0]) == np.sign(new_ray.direction[0])  # Reflected
        # Direction should be different after refracting interface
        assert all([not np.allclose(new_ray.direction, ray.direction),
                    np.allclose(new_ray.position, ray.position),
                    new_ray.wavelength == ray.wavelength,
                    new_ray.is_alive == ray.is_alive])

    def test_ray_reflecting_interaction(self):
        # low > very high refractive index
        np.random.seed(2)
        mat1 = Dielectric.make_constant((400, 800), 1.0)
        mat2 = Dielectric.make_constant((400, 800), 6.0)
        root = Node(name="Root", parent=None)
        root.geometry = Sphere(radius=10.0, material=mat1)
        a = Node(name="A", parent=root)
        a.geometry = Sphere(radius=1.0, material=mat2)
        ray = Ray(position=(-1.0, 0.0, 0.0), direction=norm((-0.2, 0.2, 1.0)), wavelength=555.0, is_alive=True)
        from_node = root
        to_node = a
        interface = DielectricInterface(from_node, to_node)
        new_ray = interface.trace(ray)
        assert np.sign(ray.direction[0]) != np.sign(new_ray.direction[0])  # Reflected
        # Direction should be different after refracting interface
        assert all([not np.allclose(new_ray.direction, ray.direction),
                    np.allclose(new_ray.position, ray.position),
                    new_ray.wavelength == ray.wavelength,
                    new_ray.is_alive == ray.is_alive])

