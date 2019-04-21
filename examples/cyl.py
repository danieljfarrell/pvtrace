""" Basic example using a cylinder geometry.
"""
from pvtrace.geometry.cylinder import Cylinder
from pvtrace.geometry.sphere import Sphere
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.light.light import Light
from pvtrace.trace.tracer import PhotonTracer
from pvtrace.material.material import Dielectric
import numpy as np
import functools
import sys
import time

world = Node(
    name="world (air)",
    geometry=Sphere(
        radius=10.0,
        material=Dielectric.air()
    )
)
cylinder = Node(
    name="cylinder (glass)",
    geometry=Cylinder(
        length=1.0,
        radius=1.0,
        material=Dielectric.glass()
    ),
    parent=world
)
light = Node(
    name="light (555nm laser)",
    light=Light(divergence_delegate=functools.partial(Light.cone_divergence, np.radians(60))),
    parent=world
)
light.translate((0.0, 0.0, -1.0))
rend = MeshcatRenderer()
scene = Scene(world)
tracer = PhotonTracer(scene)
rend.render(scene)
for ray in light.emit(10):
    path = tracer.follow(ray)
    print(path)
    rend.add_ray_path(path)

while True:
    try:
        time.sleep(.3)
    except KeyboardInterrupt:
        print("Bye")
        sys.exit()
