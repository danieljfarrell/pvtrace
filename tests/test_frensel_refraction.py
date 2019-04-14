import pytest
import numpy as np
from pvtrace.material.mechanisms import FresnelRefraction
from pvtrace.trace.context import Context, Kind
from pvtrace.light.ray import Ray
from pvtrace.scene.node import Node


class TestFresnelRefraction:
    
    def test_init(self):
        node = Node(name="node")
        ctx = Context(n1=1.0, n2=1.5, normal_node=node, normal=(0.0, 0.0, 1.0), kind=Kind.SURFACE, end_path=(10, 10, 10), container=None)
        assert type(FresnelRefraction(ctx)) == FresnelRefraction
    
    def test_normal_refraction(self):
        node = Node(name="node")
        ctx = Context(n1=1.0, n2=1.5, normal_node=node, normal=(0.0, 0.0, 1.0), kind=Kind.SURFACE, end_path=(10, 10, 10), container=None)
        ray = Ray(position=(0.0, 0.0, 0.0), direction=(0.0, 0.0, 1.0), wavelength=None)
        interaction = FresnelRefraction(ctx)
        new_ray = interaction.transform(ray)
        assert ray == new_ray
