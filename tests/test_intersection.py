import pytest
import sys
import os
import numpy as np
from anytree import RenderTree
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.geometry.sphere import Sphere
from pvtrace.geometry.intersection import Intersection


class TestIntersection:
    
    def test_init(self):
        node = Node(name='A')
        inter = Intersection(coordsys=Node, hit=Node, point=(0.0, 0.0, 0.0), distance=0.0)
        assert type(inter) == Intersection
    
    def test_equality(self):
        node = Node(name='A')
        inter1 = Intersection(coordsys=Node, hit=Node, point=(0.0, 0.0, 0.0), distance=0.0)
        inter2 = Intersection(coordsys=Node, hit=Node, point=(0.0, 0.0, 0.0), distance=0.0)
        assert inter1 == inter2
        

if __name__ == '__main__':
    pass
