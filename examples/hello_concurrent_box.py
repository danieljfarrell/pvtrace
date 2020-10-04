import time
import os
import numpy as np
from pvtrace import *
import logging

# Silence logging from dependencies
logging.getLogger("trimesh").setLevel(logging.CRITICAL)

# The world node must be large enough to contain all other nodes
world = Node(
    name="world (air)",
    geometry=Sphere(
        radius=50.0,
        material=Material(refractive_index=1.0),
    ),
)

# Node representing a box sphere
box = Node(
    name="sphere (glass)",
    geometry=Box(
        (10.0, 10.0, 1.0),
        material=Material(refractive_index=1.5),
    ),
    parent=world,
)

# Add light source node which fires into the box's top surface
light = Node(name="Light (555nm)", light=Light(), parent=world)
light.rotate(np.radians(60), (1.0, 0.0, 0.0))

# Make the scene object
scene = Scene(world)

# Concurrent simulation of 1000 rays using all cores
num_rays = 1000
start_t = time.time()
num_workers = os.cpu_count()
results = scene.simulate(num_rays, workers=num_workers)
print(f"Took {time.time() - start_t:.2f}s to trace {num_rays} rays.")
print(f"Got {len(results)} ray histories")
