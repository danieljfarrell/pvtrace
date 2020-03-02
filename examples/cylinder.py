from pvtrace import *
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

cylinder = Node(
    name="A",
    geometry=Cylinder(
        length=2,
        radius=0.5,
        material=Material(refractive_index=1.5),
    ),
    parent=world
)
cylinder.translate((0, 0, 2))
cylinder.rotate(np.radians(np.random.uniform(-90, 90)), (1, 0, 0))

# Add source of photons
light = Node(
    name="Light (555nm)",
    parent=world,
    light=Light(
        direction=functools.partial(
            cone, np.radians(30)
        )
    )
)

light.translate((0, 0, -1))

# Use meshcat to render the scene (optional)
viewer = MeshcatRenderer(open_browser=True, transparency=False, opacity=0.5, wireframe=True)
scene = Scene(world)
viewer.render(scene)
for ray in scene.emit(100):
    history = photon_tracer.follow(scene, ray)
    path, events = zip(*history)
    viewer.add_ray_path(path)  

# Keep the script alive until Ctrl-C (optional)
while True:
    try:
        time.sleep(0.1)
    except KeyboardInterrupt:
        break