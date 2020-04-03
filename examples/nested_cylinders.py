from pvtrace import (
    Node,
    Scene,
    MeshcatRenderer,
    Sphere, Box, Cylinder,
    Material,
    Surface,
    FresnelSurfaceDelegate,
    Light
)
import pvtrace.material.utils as phase_functions
from pvtrace import photon_tracer
import time
import functools
import numpy as np
import time
import functools
import numpy as np

# Add nodes to the scene graph
world = Node(
    name="World",
    geometry=Sphere(
        radius=10.0,
        material=Material(refractive_index=1.0),
    )
)

cil1 = Node(
    name="A",
    geometry=Cylinder(
        length=2,
        radius=0.5,
        material=Material(refractive_index=1.5),
    ),
    parent=world
)
cil1.translate((0, 0, 2))
cil1.rotate(np.pi*0.2, (0, 1, 0))

cil2 = Node(
    name="B",
    geometry=Cylinder(
        length=2.0,
        radius=0.4,
        material=Material(refractive_index=1.5),
    ),
    parent=cil1
)
cil2.rotate(np.pi/2, (1, 0, 0))

# Add source of photons
light = Node(
    name="Light (555nm)",
    parent=world,
    light=Light(
        direction=functools.partial(
            phase_functions.cone, np.radians(30)
        )
    )
)

light.translate((0, 0, -1))
#light.rotate(np.pi/2, (1, 0, 0))

# Use meshcat to render the scene (optional)
viewer = MeshcatRenderer(open_browser=True, transparency=False, opacity=0.5, wireframe=True)
scene = Scene(world)
viewer.render(scene)
for ray in scene.emit(20):
    history = photon_tracer.follow(scene, ray)
    path, events = zip(*history)
    viewer.add_ray_path(path)  

# Keep the script alive until Ctrl-C (optional)
while True:
    try:
        time.sleep(0.1)
    except KeyboardInterrupt:
        break