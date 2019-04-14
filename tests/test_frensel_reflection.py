import pytest
import numpy as np
from pvtrace.material.mechanisms import FresnelReflection
from pvtrace.trace.context import Context, Kind
from pvtrace.light.ray import Ray
from pvtrace.scene.node import Node


class TestFresnelReflection:
    
    def test_init(self):
        node = Node(name="node")
        ctx = Context(n1=1.0, n2=1.5, normal_node=node, normal=(0.0, 0.0, 1.0), kind=Kind.SURFACE, end_path=(10, 10, 10), container=None)
        assert type(FresnelReflection(ctx)) == FresnelReflection
    
    def test_normal_reflection(self):
        node = Node(name="node")
        ctx = Context(n1=1.0, n2=1.5, normal_node=node, normal=(0.0, 0.0, 1.0), kind=Kind.SURFACE, end_path=(10, 10, 10), container=None)
        ray = Ray(position=(0.0, 0.0, 0.0), direction=(0.0, 0.0, 1.0), wavelength=None)
        interaction = FresnelReflection(ctx)
        p = interaction.probability(ray)
        assert np.isclose(p, 0.04)

    def test_antinormal_reflection(self):
        """ FresnelReflection takes the smallest angle between the ray direction and 
        the normal. Thus the flipped normal will also work.
        """
        node = Node(name="node")
        ctx = Context(n1=1.0, n2=1.5, normal_node=node, normal=(0.0, 0.0, -1.0), kind=Kind.SURFACE, end_path=(10, 10, 10), container=None)
        ray = Ray(position=(0.0, 0.0, 0.0), direction=(0.0, 0.0, 1.0), wavelength=None)
        interaction = FresnelReflection(ctx)
        p = interaction.probability(ray)
        assert np.isclose(p, 0.04)
