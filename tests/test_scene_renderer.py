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

@pytest.mark.skipif(sys.platform == 'win32', reason="Fails on Windows")
class TestMeshcatRenderer:
    
    # Meshcat on windows seems to require a running ZMQ broker
    # this is a change of behaviour introduced some point after 
    # meshcat v0.0.16
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

