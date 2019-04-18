import pytest
import sys
import os
from dataclasses import replace
import numpy as np
from anytree import RenderTree
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.geometry.sphere import Sphere
from pvtrace.light.ray import Ray
from pvtrace.trace.tracer import PhotonTracer
from pvtrace.material.material import Dielectric
from pvtrace.common.errors import TraceError


class TestPhotonTracer:

    def test_kind(self):
        assert type(PhotonTracer(None)) == PhotonTracer

    def test_trace_without_objects(self):
        """ Trace empty scene. Should return intersections with root node.
        """
        root = Node(name="Root", geometry=Sphere(radius=10.0))
        scene = Scene(root)
        tracer = PhotonTracer(scene)
        position = (-2.0, 0.0, 0.0)
        direction = (1.0, 0.0, 0.0)
        initial_ray = Ray(
            position=position, direction=direction, wavelength=555.0, is_alive=True
        )
        expected_history = [
            initial_ray,  # Starting ray
            replace(initial_ray, position=(10.0, 0.0, 0.0), is_alive=False),  # Exit ray
        ]
        history = tracer.follow(initial_ray)
        for pair in zip(history, expected_history):
            assert pair[0] == pair[1]

    def test_trace_with_geometric_object(self):
        """ Contains a single object without an attached material: a geometric object. 
        In this case we expect the tracer to just return the intersection points with
        the scene.
        """
        root = Node(name="Root", geometry=Sphere(radius=10.0))
        a = Node(name="A", parent=root, geometry=Sphere(radius=1.0))
        scene = Scene(root)
        tracer = PhotonTracer(scene)
        position = (-2.0, 0.0, 0.0)
        direction = (1.0, 0.0, 0.0)
        initial_ray = Ray(
            position=position, direction=direction, wavelength=555.0, is_alive=True
        )
        expected_history = [
            initial_ray,  # Starting ray
            replace(initial_ray, position=(-1.0, 0.0, 0.0)),  # Moved to intersection
            replace(initial_ray, position=(1.0, 0.0, 0.0)),  # Moved to intersection
            replace(initial_ray, position=(10.0, 0.0, 0.0), is_alive=False),  # Exit ray
        ]
        history = tracer.follow(initial_ray)
        for pair in zip(history, expected_history):
            assert pair[0] == pair[1]

    def test_trace_with_translated_geometric_object(self):
        """ Single translated geometric objects.
        """
        root = Node(name="Root", geometry=Sphere(radius=10.0))
        a = Node(name="A", parent=root, geometry=Sphere(radius=1.0))
        a.translate((5.0, 0.0, 0.0))
        scene = Scene(root)
        tracer = PhotonTracer(scene)
        position = (-2.0, 0.0, 0.0)
        direction = (1.0, 0.0, 0.0)
        initial_ray = Ray(
            position=position, direction=direction, wavelength=555.0, is_alive=True
        )
        expected_history = [
            initial_ray,  # Starting ray
            replace(initial_ray, position=(4.0, 0.0, 0.0)),  # First intersection
            replace(initial_ray, position=(6.0, 0.0, 0.0)),  # Second intersection
            replace(initial_ray, position=(10.0, 0.0, 0.0), is_alive=False),  # Exit ray
        ]
        history = tracer.follow(initial_ray)
        for pair in zip(history, expected_history):
            assert pair[0] == pair[1]

    def test_trace_with_geometric_objects_1(self):
        """ Only one of the geometric objects has a transformation applied.
        """
        root = Node(name="Root", geometry=Sphere(radius=10.0))
        a = Node(name="A", parent=root, geometry=Sphere(radius=1.0))
        b = Node(name="B", parent=root, geometry=Sphere(radius=1.0))
        b.translate((5.0, 0.0, 0.0))
        scene = Scene(root)
        tracer = PhotonTracer(scene)
        position = (-3.0, 0.0, 0.0)
        direction = (1.0, 0.0, 0.0)
        initial_ray = Ray(
            position=position, direction=direction, wavelength=555.0, is_alive=True
        )
        expected_history = [
            initial_ray,  # Starting ray
            replace(initial_ray, position=(-1.0, 0.0, 0.0)), # Moved to intersection
            replace(initial_ray, position=(1.0, 0.0, 0.0)),  # Moved to intersection
            replace(initial_ray, position=(4.0, 0.0, 0.0)),  # Moved to intersection
            replace(initial_ray, position=(6.0, 0.0, 0.0)),  # Moved to intersection
            replace(initial_ray, position=(10.0, 0.0, 0.0), is_alive=False),  # Exit ray
        ]
        history = tracer.follow(initial_ray)
        for pair in zip(history, expected_history):
            a, b = pair
            print("Testing {} {}".format(a.position, b.position))
            assert np.allclose(a.position, b.position)
            
    def test_trace_with_geometric_objects_2(self):
        """ Both objects in the scene have a translation applied.
        """
        root = Node(name="Root", geometry=Sphere(radius=10.0))
        a = Node(name="A", parent=root, geometry=Sphere(radius=1.0))
        b = Node(name="B", parent=root, geometry=Sphere(radius=1.0))
        a.translate((1.0, 0.0, 0.0))
        b.translate((5.0, 0.0, 0.0))
        scene = Scene(root)
        tracer = PhotonTracer(scene)
        position = (-3.0, 0.0, 0.0)
        direction = (1.0, 0.0, 0.0)
        initial_ray = Ray(
            position=position, direction=direction, wavelength=555.0, is_alive=True
        )
        expected_history = [
            initial_ray,  # Starting ray
            replace(initial_ray, position=(0.0, 0.0, 0.0)), # Moved to intersection
            replace(initial_ray, position=(2.0, 0.0, 0.0)),  # Moved to intersection
            replace(initial_ray, position=(4.0, 0.0, 0.0)),  # Moved to intersection
            replace(initial_ray, position=(6.0, 0.0, 0.0)),  # Moved to intersection
            replace(initial_ray, position=(10.0, 0.0, 0.0), is_alive=False),  # Exit ray
        ]
        history = tracer.follow(initial_ray)
        for pair in zip(history, expected_history):
            a, b = pair
            print("Testing {} {}".format(a.position, b.position))
            assert np.allclose(a.position, b.position)

    def test_trace_with_material_object(self):
        """ Root node and test object has a material attached.
        """
        np.random.seed(1) # No reflections
        # np.random.seed(2)  # Reflection at last inteface
        root = Node(name="Root", geometry=Sphere(radius=10.0, material=Dielectric.make_constant((400, 800), 1.0)))
        b = Node(name="B", parent=root, geometry=Sphere(radius=1.0, material=Dielectric.make_constant((400, 800), 1.5)))
        b.translate((5.0, 0.0, 0.0))
        scene = Scene(root)
        tracer = PhotonTracer(scene)
        position = (-3.0, 0.0, 0.0)
        direction = (1.0, 0.0, 0.0)
        initial_ray = Ray(
            position=position, direction=direction, wavelength=555.0, is_alive=True
        )
        expected_history = [
            initial_ray,  # Starting ray
            replace(initial_ray, position=(4.0, 0.0, 0.0)), # Moved to intersection
            replace(initial_ray, position=(4.0, 0.0, 0.0)), # Refracted into A
            replace(initial_ray, position=(6.0, 0.0, 0.0)),  # Moved to intersection
            replace(initial_ray, position=(6.0, 0.0, 0.0)),  # Refracted out of A
            replace(initial_ray, position=(10.0, 0.0, 0.0), is_alive=False),  # Exit ray
        ]
        history = tracer.follow(initial_ray)
        for pair in zip(history, expected_history):
            a, b = pair
            print("Testing {} {}".format(a.position, b.position))
            assert np.allclose(a.position, b.position)

    def test_trace_raises_trace_error(self):
        """ Tests interface between objects in which only one of them has a material.
        This should raise a RuntimeError because it cannot be traced in a physically
        correct way.
        """
        np.random.seed(2)
        root = Node(name="Root", geometry=Sphere(radius=10.0))
        b = Node(name="B", parent=root, geometry=Sphere(radius=1.0, material=Dielectric.make_constant((400, 800), 1.5)))
        b.translate((5.0, 0.0, 0.0))
        scene = Scene(root)
        tracer = PhotonTracer(scene)
        position = (-3.0, 0.0, 0.0)
        direction = (1.0, 0.0, 0.0)
        initial_ray = Ray(
            position=position, direction=direction, wavelength=555.0, is_alive=True
        )
        did_raise = False
        try:
            tracer.follow(initial_ray)
        except TraceError as err:
            did_raise = True
        assert did_raise



if __name__ == "__main__":
    pass
