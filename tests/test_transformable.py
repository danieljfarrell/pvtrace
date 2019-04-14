import pytest
import sys
import os
import numpy as np
from pvtrace.geometry.transformable import Transformable

class TestTransformable:
    
    def test_init(self):
        assert type(Transformable()) == Transformable
        assert np.allclose(Transformable().location, (0, 0, 0))
        assert np.allclose(Transformable(location=(1, 1, 1)).location, (1, 1, 1))
        pose = np.random.random((4, 4))
        assert np.allclose(Transformable.from_pose(pose).pose, pose)
