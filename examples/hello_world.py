import time
import sys
import functools
import numpy as np
from pvtrace import *

world = Node(
    name="world (air)",
    geometry=Sphere(
        radius=10.0,
        material=Material(refractive_index=1.0),
    ),
)

sphere = Node(
    name="sphere (glass)",
    geometry=Sphere(
        radius=1.0,
        material=Material(refractive_index=1.5),
    ),
    parent=world,
)
sphere.location = (0, 0, 2)

light = Node(
    name="Light (555nm)",
    light=Light(direction=functools.partial(cone, np.pi / 8)),
    parent=world,
)

# Change zmq_url here to be the address of your meshcat-server!
renderer = MeshcatRenderer(
    zmq_url="tcp://127.0.0.1:6000", wireframe=True, open_browser=True
)
scene = Scene(world)
renderer.render(scene)
for ray in scene.emit(100):
    steps = photon_tracer.follow(scene, ray)
    path, events = zip(*steps)
    renderer.add_ray_path(path)
    time.sleep(0.1)

# Wait for Ctrl-C to terminate the script; keep the window open
print("Ctrl-C to close")
while True:
    try:
        time.sleep(0.3)
    except KeyboardInterrupt:
        sys.exit()
