import numpy as np
import pathlib
import time
import sys
import os
import matplotlib
import pandas as pd
from dataclasses import asdict
import functools
from pvtrace.light.utils import wavelength_to_rgb
from pvtrace.scene.scene import Scene
from pvtrace.algorithm import photon_tracer
from pvtrace.scene.node import Node
from pvtrace.common.errors import TraceError
from pvtrace.light.light import Light
from pvtrace.light.ray import Ray
from pvtrace.geometry.mesh import Mesh
from pvtrace.geometry.box import Box
from pvtrace.geometry.sphere import Sphere
from pvtrace.material.dielectric import Dielectric, LossyDielectric
from pvtrace.material.lumophore import Lumophore
from pvtrace.material.host import Host
from pvtrace.scene.node import Node
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.geometry.utils import magnitude
import logging

# We want to see pvtrace logging here
#logging.getLogger('pvtrace').setLevel(logging.CRITICAL)
logging.getLogger('trimesh').setLevel(logging.CRITICAL)
logging.getLogger('matplotlib').setLevel(logging.CRITICAL)

wavelength_range = (200, 800)
wavelength = np.linspace(*wavelength_range, 1000)
lumogen = Lumophore.make_lumogen_f_red(wavelength, 1000, 1.0)
linear_background = Lumophore.make_linear_background(wavelength, 1.0)

# Make a world coordinate system
world_node = Node(name='world')
world_node.geometry = Sphere(
    radius=10.0,
    material=Dielectric.make_constant((300, 1000.0), 1.0)
)

refractive_index = np.column_stack(
    (wavelength, np.ones(wavelength.shape) * 1.5)
)
# Add LSC
size = (1.0, 1.0, 0.02)
lsc = Node(name="LSC", parent=world_node)
lsc.geometry = Box(
    size, 
    material=Host(
        refractive_index,  # LSC refractive index
        [linear_background, lumogen]          # LSC list of lumophore materials
    )
)

# Light source
light = Light(
    divergence_delegate=functools.partial(
        Light.cone_divergence,
        np.radians(20)
    )
)
light_node = Node(
    name='light',
    parent=world_node,
    location=(0.0, 0.0, 1.0)
)
light_node.rotate(np.radians(180), (1, 0, 0))
light_node.light = light
scene = Scene(root=world_node)
renderer = MeshcatRenderer(max_histories=None, open_browser=True)
renderer.render(scene)


if __name__ == "__main__":
    np.random.seed(1)
    for light_node in scene.light_nodes:
        for ray in light.emit(20):
            ray = ray.representation(light_node, world_node)
            steps = photon_tracer.follow(ray, scene, renderer=renderer)
            path, decisions = zip(*steps)
            print(decisions)
            renderer.add_ray_path(path)
