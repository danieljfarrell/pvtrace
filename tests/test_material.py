import pytest
from pvtrace.material.material import Material

class TestMaterial:
    
    def test_init(self):
        assert type(Material(1.5) == Material)

    def test_ior(self):
        assert Material(1.5).refractive_index == 1.5