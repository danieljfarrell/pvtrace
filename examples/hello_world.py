from pvtrace.scene.node import Node
from pvtrace.scene.scene import Scene
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.geometry.sphere import Sphere
from pvtrace.material.material import Material
from pvtrace.material.surface import FresnelSurface
from pvtrace.light.light import Light
from pvtrace.algorithm import photon_tracer
import time
import functools
import numpy as np

# Add nodes to the scene graph
world = Node(
    name="world (air)",
    geometry=Sphere(
        radius=10.0,
        material=Material(refractive_index=1.0),
        surface=FresnelSurface()
    )
)
sphere = Node(
    name="sphere (glass)",
    geometry=Sphere(
        radius=1.0,
        material=Material(refractive_index=1.5),
        surface=FresnelSurface()
    ),
    parent=world
)
sphere.translate((0,0,2))

# Add source of photons
light = Node(
    name="Light (555nm)",
    light=Light(
        divergence_delegate=functools.partial(
            Light.cone_divergence, np.radians(20)
        )
    )
)

# Use meshcat to render the scene (optional)
viewer = MeshcatRenderer(open_browser=True)
scene = Scene(world)
viewer.render(scene)
for ray in light.emit(100):
    history = photon_tracer.trace(scene, ray)
    path, events = zip(*history)
    viewer.add_ray_path(path)  

# Keep the script alive until Ctrl-C (optional)
while True:
    try:
        time.sleep(0.1)
    except KeyboardInterrupt:
        break
