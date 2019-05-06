import pytest
import sys
import os
import time
import numpy as np
from anytree import RenderTree
from pvtrace.geometry.sphere import Sphere
from pvtrace.scene.node import Node
from pvtrace.scene.scene import Scene
from pvtrace.scene.renderer import MeshcatRenderer


class TestMeshcatRenderer:
    
    def test_basic_scene(self):
        a = Node(name="A", parent=None)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        b.translate((2.0, 0.0, 0.0))
        s = Scene(root=a)
        r = MeshcatRenderer()
        r.render(s)
        time.sleep(0.5)
        r.remove(s)

