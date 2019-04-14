import pytest
import numpy as np
from pvtrace.light.utils import wavelength_to_rgb, rgb_to_hex_int

class TestLightUtils:

    def test_wavelength_to_rgb(self):
        expected = (163, 255, 0)
        result = wavelength_to_rgb(555)  # Green (mostly)!
        assert result == expected
    
    def test_rgb_to_hex_int(self):
        expected = int("0xff0000", 0)
        result = rgb_to_hex_int((255, 0, 0))
        assert result == expected



