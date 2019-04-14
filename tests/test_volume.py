import pytest
import numpy as np
from dataclasses import replace
from pvtrace.material.material import Dielectric
from pvtrace.material.volume import Volume
from pvtrace.trace.context import Context, Kind
from pvtrace.scene.node import Node
from pvtrace.geometry.sphere import Sphere
from pvtrace.light.ray import Ray
from pvtrace.geometry.utils import norm, angle_between


class TestVolume:

    def test_no_interaction(self):
        np.random.seed(0)
        mat = Dielectric.make_constant((400, 800), 1.0)
        root = Node(name="Root", parent=None)
        root.geometry = Sphere(radius=10.0, material=mat)
        a = Node(name="A", parent=root)
        a.geometry = Sphere(radius=1.0, material=mat)
        ray = Ray(position=(-1.0, 0.0, 0.0), direction=(1.0, 0.0, 0.0), wavelength=555.0, is_alive=True)
        volume = Volume(a, 2.0)
        new_ray = volume.trace(ray)
        expected = replace(ray, position=(1.0, 0.0, 0.0))
        assert new_ray == expected


