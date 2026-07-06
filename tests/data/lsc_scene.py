import time
import sys
import functools
import numpy as np
from pvtrace import *
from pvtrace.data import lumogen_f_red_305

world = Node(
    name="world",
    geometry=Sphere(
        radius=100.0,
        material=Material(refractive_index=1.0),
    ),
)

x = np.arange(500, 1002, 2)  # wavelength, units: nm
absorption_spectrum = lumogen_f_red_305.absorption(x)  # units: nm-1
emission_spectrum = lumogen_f_red_305.emission(x)  # units: nm-1
absorption_spectrum = absorption_spectrum / np.max(absorption_spectrum) * 5
my_lumogen_dye = Luminophore(
    name="my-lumogen-dye",
    coefficient=np.column_stack((x, absorption_spectrum)),
    emission=np.column_stack((x, emission_spectrum)),
    quantum_yield=0.98,
    phase_function=isotropic,
    hist=True,
)


lsc = Node(
    name="lsc",
    geometry=Box(
        size=[5, 5, 1],
        material=Material(
            refractive_index=1.5,
            components=[my_lumogen_dye],
        ),
    ),
    location=(0, 0, 0.5),
    parent=world,
)

green_laser = Node(
    name="green-laser",
    light=Light(
        direction=functools.partial(cone, np.radians(22.5)), name="green-laser"
    ),
    parent=world,
    location=(0, 0, 1.5),
)
green_laser.look_at((0, 0, -1))

scene = Scene(world)