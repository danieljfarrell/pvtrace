from pvtrace import (
    Node,
    Scene,
    MeshcatRenderer,
    Sphere, Box,
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


class CustomBoxReflection(FresnelSurfaceDelegate):
    """ Gives the bottom surface a reflectivity of 1.
    """

    def reflectivity(self, surface, ray, geometry, container, adjacent):
        normal = geometry.normal(ray.position)
        # find bottom facet, it has normal (0, 0, -1)
        if np.allclose((0, 0, -1), normal):
            return 1.0  #  bottom surface is perfect mirror
        return super(CustomBoxReflection, self).reflectivity(surface, ray, geometry, container, adjacent)  # opt-out of handling custom reflection

    def reflected_direction(self, surface, ray, geometry, container, adjacent):
        normal = geometry.normal(ray.position)
        # find bottom facet, it has normal (0, 0, -1)
        if np.allclose((0, 0, -1), normal):
            return tuple(phase_functions.lambertian().tolist())
        return super(CustomBoxReflection, self).reflected_direction(surface, ray, geometry, container, adjacent)  # opt-out of handling custom reflection

    def transmitted_direction(self, surface, ray, geometry, container, adjacent):
        return super(CustomBoxReflection, self).transmitted_direction(surface, ray, geometry, container, adjacent)  # opt-out of handling custom reflection


# Add nodes to the scene graph
world = Node(
    name="world (air)",
    geometry=Sphere(
        radius=10.0,
        material=Material(refractive_index=1.0),
        surface=Surface()
    )
)

box = Node(
    name="box (glass)",
    parent=world,
    geometry=Box(
        (0.5, 0.5, 0.5),
        material=Material(refractive_index=1.5),
        surface=Surface(delegate=CustomBoxReflection())
    ),
)
box.translate((0,0,1))

# Add source of photons
light = Node(
    name="Light (555nm)",
    parent=world,
    light=Light(
        direction=functools.partial(
            phase_functions.cone, np.arcsin(1/1.5)
        )
    )
)

light.translate((0, 0, 1))
light.rotate(np.pi, (1, 0, 0))
scene = Scene(world)
viewer = MeshcatRenderer(open_browser=True)
viewer.render(scene)
for ray in scene.emit(100):
    history = photon_tracer.trace(scene, ray)
    path, events = zip(*history)
    viewer.add_ray_path(path)  

# Keep the script alive until Ctrl-C (optional)
while True:
    try:
        time.sleep(0.1)
    except KeyboardInterrupt:
        break
