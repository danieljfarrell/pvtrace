""" Simulate a 5cm x 5cm x 1cm plate:
    - perfectly index matched solar cells on edges
    - back surface is covered with a perfect/ideal mirror
    - plate refractive index 1.5
    - contains Lumogen F Red 305
    - assumes 0.02 cm-1 background absorption coefficient
    - spotlight illumination on top surface (555nm monochromatic)
"""
from pvtrace import *

lsc = LSC((5.0, 5.0, 1.0))
# Add solar cells to edge faces
lsc.add_solar_cell({'left', 'right', 'near', 'far'})
# Add a perfect metal mirrors to the bottom surface
lsc.add_back_surface_mirror()
# NB solar cells are not rendered
lsc.show()
lsc.simulate(100)
lsc.report()

"""
Simulation Report
-----------------

Surface Counts:
        Solar In  Solar Out  Luminescent Out  Luminescent In
left           0          0               13               0
right          0          0               13               0
near           0          0                8               0
far            0          0                9               0
top          100          5               26               0
bottom         0          0                0               0

Summary:
Optical Efficiency                                                            0.43
Waveguide Efficiency                                                      0.623188
Waveguide Efficiency (Thermodynamic Prediction)                           0.642857
Non-radiative Loss (fraction):                                                0.26
Incident                                                                       100
Geometric Concentration                                                       1.25
Refractive Index                                                               1.5
Cell Surfaces                                             {far, right, left, near}
Components                                         {Background, Lumogen F Red 305}
Lights                                                                     {Light}
"""

