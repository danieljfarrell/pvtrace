![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/logo.png)

> Optical ray tracing for luminescent materials and spectral converter photovoltaic devices 

## Introduction

pvtrace is a statistical photon path tracer written in Python. It follows photons through a 3D scene and records their interactions with objects to build up statistical information about energy flow. This approach is particularly useful in photovoltaics and non-imaging optics where the goal is to design systems which efficiently transport light to target locations.

## Documentation

Interactive Jupyter notebooks examples and tutorial can be found in the [docs directory](https://github.com/danieljfarrell/pvtrace/tree/master/docs).

Static versions are included in the project documentation, [https://pvtrace.readthedocs.io](https://pvtrace.readthedocs.io/)

## Capabilities

pvtrace was originally written to characterise the performance of Luminescent Solar Concentrators (LSC) and takes a Monte-Carlo approach to ray-tracing. Each ray is independent and can interact with objects in the scene via reflection and refraction. Objects can have different optical properties: refractive index, absorption coefficient, emission spectrum and quantum yield.

One of the key features of pvtrace is the ability to simulate re-absorption of photons in luminescent materials. This requires following thousands of rays to build intensity profiles and spectra of incoming and outgoing photons because these process cannot be approximated in a continuous way.

pvtrace may also be useful to researches or designers interested in ray-optics simulations but will be slower at running these simulations compared to other software packages because it follows each ray individually.

![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/example.png)
    
A minimal working example that traces a glass sphere

```python
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

# Add nodes to the scene graph
world = Node(
    name="world (air)",
    geometry=Sphere(
        radius=10.0,
        material=Material(refractive_index=1.0),
    )
)

box = Node(
    name="box (glass)",
    parent=world,
    geometry=Box(
        (0.5, 0.5, 0.5),
        material=Material(
            refractive_index=1.5,
            surface=Surface(
                delegate=CustomBoxReflection()
            ),
        ),
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
    history = photon_tracer.follow(scene, ray)
    path, events = zip(*history)
    viewer.add_ray_path(path)  

# Keep the script alive until Ctrl-C (optional)
while True:
    try:
        time.sleep(0.1)
    except KeyboardInterrupt:
        break
```
## Install

Using pip

    pip install pvtrace

## Dependancies

* python >= 3.7.2
* trimesh (for mesh shapes)
* meshcat (for visualisation)
* numpy
* anytree