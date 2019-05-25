""" This example simulates a thin and long cylinder which is sometime studied as a
    luminescent concentrator geometry.
"""
from pvtrace.geometry.cylinder import Cylinder
from pvtrace.geometry.sphere import Sphere
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.light.light import Light
from pvtrace.algorithm import photon_tracer
from pvtrace.material.dielectric import Dielectric
from pvtrace.material.lumophore import Lumophore
from pvtrace.material.host import Host
import numpy as np
import functools
import sys
import time


# World node contains the simulation; large sphere filled with air
world = Node(
    name="world (air)",
    geometry=Sphere(
        radius=10.0,
        material=Dielectric.air()
    )
)


# Use the functions above to make the spectrum needed by the Lumophore. At this point
# you may want to customise this script and import your own experimental data.
wavelength = np.linspace(300, 1000, 200)
peak_abs_coeff_per_cm = 1000.0
quantum_yield = 1.0
lumophore = Lumophore.make_lumogen_f_red(
    wavelength, peak_abs_coeff_per_cm, quantum_yield
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

# cylinder = Node(
#     name="cylinder (glass)",
#     geometry=Cylinder(
#         length=5.0,
#         radius=2.0,
#         material=material
#     ),
#     parent=world
# )

cylinder = Node(
    name="cylinder (glass)",
    geometry=Cylinder(
        length=5.0,
        radius=2.0,
        material=lumophore
    ),
    parent=world
)

# Internal light source.
# Light source is along the axis of the cylinder at the centre.
light = Node(
    name="light (555nm laser)",
    light=Light(position_delegate=lambda: (np.random.uniform(-2.5, 2.5), 0.0, 0.0)),
    parent=world
)
cylinder.rotate(
    np.radians(90), (0.0, 1.0, 0.0)
)
light.translate(
    (0.0, 0.0, 0.0)
)

# Setup renderer and the scene for tracing
rend = MeshcatRenderer(open_browser=True)
scene = Scene(world)
rend.render(scene)

# Trace 100 photons and visualise
for ray in light.emit(100):
    info = photon_tracer.follow(ray, scene)
    rays, events = zip(*info)
    rend.add_ray_path(rays)

# You can kill the simulation any time by pressing ctrl-c.
# Do something with the data. Read the pvtrace documentation on how to process data
# for luminescence solar concentrators.
print("Ctrl-C to close")
while True:
    try:
        time.sleep(.3)
    except KeyboardInterrupt:
        print("Bye")
        sys.exit()


