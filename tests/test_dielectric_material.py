import pytest
import numpy as np
from dataclasses import replace
from pvtrace.material.material import Dielectric
from pvtrace.trace.context import Context, Kind
from pvtrace.light.ray import Ray

class TestDielectric:
    
    def test_init(self):
        assert type(Dielectric.make_constant((400, 800), 1.0)) == Dielectric

    def test_ior(self):
        assert Dielectric.make_constant((400, 800), 1.5).refractive_index(555) == 1.5