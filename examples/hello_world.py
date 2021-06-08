import time
import sys
import functools
import numpy as np
from pvtrace import *


def make_hello_world_scene():

    world = Node(
        name="world",
        geometry=Sphere(
            radius=10.0,
            material=Material(refractive_index=1.0),
        ),
    )
    ball_lens = Node(
        name="ball-lens",
        location=(0,0,2),
        geometry=Sphere(
            radius=1.0,
            material=Material(refractive_index=1.5),
        ),
        parent=world,
    )

    green_laser = Node(
        name="green-laser",
        light=Light(direction=functools.partial(cone, np.pi / 8), name="green-laser"),
        parent=world,
    )
    return Scene(world)


# Change zmq_url here to be the address of your meshcat-server!
renderer = MeshcatRenderer(
    zmq_url="tcp://127.0.0.1:6000", wireframe=True, open_browser=True
)
scene = make_hello_world_scene()
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
