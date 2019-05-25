""" Basic example using a cylinder geometry.
"""
from pvtrace.geometry.cylinder import Cylinder
from pvtrace.geometry.sphere import Sphere
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.light.light import Light
from pvtrace.algorithm import photon_tracer
from pvtrace.material.dielectric import Dielectric
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

# A small cylinder shape made from glass
cylinder = Node(
    name="cylinder (glass)",
    geometry=Cylinder(
        length=1.0,
        radius=1.0,
        material=Dielectric.glass()
    ),
    parent=world
)

# A light source with 60-deg divergence
light = Node(
    name="light (555nm laser)",
    light=Light(divergence_delegate=functools.partial(Light.cone_divergence, np.radians(60))),
    parent=world
)
light.translate((0.0, 0.0, -1.0))

# Make a renderer object and scene for tracing
viewer = MeshcatRenderer(open_browser=True)
scene = Scene(world)
viewer.render(scene)

# Generate some rays from the light source and trace them through the scene
for ray in light.emit(10):
    info = photon_tracer.follow(ray, scene)
    rays, events = zip(*info)
    viewer.add_ray_path(rays)

# Wait for Ctrl-C to terminate the script; keep the window open
print("Ctrl-C to close")
while True:
    try:
        time.sleep(.3)
    except KeyboardInterrupt:
        print("Bye")
        sys.exit()
