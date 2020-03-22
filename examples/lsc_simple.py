""" Simulate a 5cm x 5cm x 1cm plate:
    - bare plate without solar cells
    - refractive index 1.5
    - contains Lumogen F Red 305
    - assumes 0.02 cm-1 background absorption coefficient
    - spotlight illumination on top surface (555nm monochromatic)
"""
from pvtrace import *

lsc = LSC((5.0, 5.0, 1.0))
lsc.show()
lsc.simulate(100)
lsc.report()

