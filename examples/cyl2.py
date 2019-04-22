""" This example simulates a thin and long cylinder which is sometime studied as a
    luminescent concentrator geometry.
"""
from pvtrace.geometry.cylinder import Cylinder
from pvtrace.geometry.sphere import Sphere
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.light.light import Light
from pvtrace.trace.tracer import PhotonTracer
from pvtrace.material.material import Dielectric, Lumophore, Host
import numpy as np
import functools
import sys
import time

# Make a world node filled with air

world = Node(
    name="world (air)",
    geometry=Sphere(
        radius=10.0,
        material=Dielectric.air()
    )
)

# Make a very simple (and probably unphysical) absorption and emission.

def make_absorprtion_coefficient(x_range, wavelengths, absorption_coefficient, cutoff_range, min_alpha=0):
    wavelength1, wavelength2 = cutoff_range
    alpha = absorption_coefficient
    halfway = wavelength1 + 0.5 * (wavelength2 - wavelength1)
    x = [x_range[0], wavelength1, halfway, wavelength2, x_range[1]]
    y = [alpha, alpha, 0.5 * alpha, min_alpha, min_alpha]
    abs_coeff = np.interp(wavelengths, x, y)
    return abs_coeff

def make_emission_spectrum(x_range, wavelengths, cutoff_range, min_ems=0):
    wavelength1, wavelength2 = cutoff_range
    halfway = wavelength1 + 0.5 * (wavelength2 - wavelength1)
    x = [x_range[0], wavelength1, halfway, wavelength2, x_range[1]]
    y = [min_ems, min_ems, 1.0, min_ems, min_ems]
    abs_coeff = np.interp(wavelengths, x, y)
    return abs_coeff

# Use the functions above to make the spectrum needed by the Lumophore. At this point
# you may want to customise this script and import your own experimental data.

x_range = (300, 1000)
wavelength = np.linspace(*x_range)
abs_coef = make_absorprtion_coefficient(x_range, wavelength, 1.0, (700, 800))
ems_spec = make_emission_spectrum(x_range, wavelength, (600, 700))
lumophore = Lumophore(
    np.column_stack((wavelength, abs_coef)),  # abs. coef. spectrum
    np.column_stack((wavelength, ems_spec)),  # emission spectrum
    1.0  # quantum yield
)

# Make a host material which has a refractive index of 1.5 and also contains the 
# lumophore we just created.

material = Host(
    np.column_stack( # refractive index spectrum
        (wavelength,
         np.ones(wavelength.size) * 1.5)
    ), 
    [lumophore],  # list of lumophores, reuse the one we already have.
)

# Make the cylinder node with length 5cm and radius 0.02cm and give the material we 
# just made.

cylinder = Node(
    name="cylinder (glass)",
    geometry=Cylinder(
        length=5.0,
        radius=0.02,
        material=material
    ),
    parent=world
)

# Make a light source. This is a laser emitting light along the whole length of the
# cylinder. We need to translate and rotate the light source to get it to fire along
# the axis. We use the position delegate to generate photons along the same length
# as the cylinder.

light = Node(
    name="light (555nm laser)",
    light=Light(position_delegate=lambda : (np.random.uniform(-2.5, 2.5), 0.0, 0.0)),
    parent=world
)
cylinder.rotate(np.radians(90), (0.0, 1.0, 0.0))
light.translate((0.0, 0.0, -1.0))

# Setup renderer and the scene for tracing
rend = MeshcatRenderer()
scene = Scene(world)
tracer = PhotonTracer(scene)
rend.render(scene)

# Trace 100 photons and visualise
for ray in light.emit(100):
    path = tracer.follow(ray)
    print(path)
    rend.add_ray_path(path)

# You can kill the simulation any time by pressing ctrl-c.
# Do something with the data. Read the pvtrace documentation on how to process data
# for luminescence solar concentrators.
while True:
    try:
        time.sleep(.3)
    except KeyboardInterrupt:
        print("Bye")
        sys.exit()


