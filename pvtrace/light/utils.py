from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def wavelength_to_rgb(nanometers: float) -> Tuple[int, int, int]:
    """ Convert wavelength in nanometers to an RGB colour using method published here[1].
    
        Parameters
        ----------
        nanometers : float
            The wavelength in nanometers.

        Returns
        -------
        rgb : tuple of int
            Like (r, g, b) where the colour is represented as integer RGB components 
            between 0 and 255.
            
        Notes
        -----
        [1] http://codingmess.blogspot.com/2009/05/conversion-of-wavelength-in-nanometers.html"""
    w = int(nanometers)

    # colour
    if w >= 380 and w < 440:
        r, g, b = -(w - 440.0) / (440.0 - 350.0), 0.0, 1.0
    elif w >= 440 and w < 490:
        r, g, b = 0.0, (w - 440.0) / (490.0 - 440.0), 1.0
    elif w >= 490 and w < 510:
        r, g, b = 0.0, 1.0, -(w - 510.0) / (510.0 - 490.0)
    elif w >= 510 and w < 580:
        r, g, b = (w - 510.0) / (580.0 - 510.0), 1.0, 0.0
    elif w >= 580 and w < 645:
        r, g, b = 1.0, -(w - 645.0) / (645.0 - 580.0), 0.0
    elif w >= 645 and w <= 780:
        r, g, b = 1.0, 0.0, 0.0
    else:
        r, g, b = 0.0, 0.0, 0.0

    # intensity correction
    if w >= 380 and w < 420:
        s = 0.3 + 0.7 * (w - 350) / (420 - 350)
    elif w >= 420 and w <= 700:
        s = 1.0
    elif w > 700 and w <= 780:
        s = 0.3 + 0.7 * (780 - w) / (780 - 700)
    else:
        s = 0.0
    s *= 255

    return (int(s * r), int(s * g), int(s * b))


def rgb_to_hex_int(rgb: Tuple[int]) -> int:
    """ Converts an RGB tuple to a hex value using the method [1].
    
    Parameters
    ----------
    rgb : tuple of int
        Like (r, g, b) where the colour is represented as integer RGB components 
        between 0 and 255.
    
    Returns
    -------
    hex_int : int
        Returns an integer like 0xff0000 given the input (255, 0, 0).
    
    Notes
    -----
    In Python 0xff0000 is a shorthand for writing hexadecimal integer values. These are
    converted to base 10 integer representation. This reference [1] was useful when 
    implementing this function.

    [1] https://stackoverflow.com/questions/3380726/converting-a-rgb-color-tuple-to-a-six-digit-code-in-python
    
    """

    def clamp(x):
        return max(0, min(x, 255))

    string_value = "0x{0:02x}{1:02x}{2:02x}".format(*list(map(clamp, rgb)))
    hex_int = int(string_value, 0)
    return hex_int


def wavelength_to_hex_int(nanometers: float) -> int:
    return rgb_to_hex_int(wavelength_to_rgb(nanometers))
