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
from pvtrace.scene.node import Node
from pvtrace.scene.scene import Scene
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.geometry.sphere import Sphere
from pvtrace.material.dielectric import Dielectric
from pvtrace.light.light import Light
from pvtrace.algorithm import photon_tracer
import functools
import numpy as np

# Add nodes to the scene graph
world = Node(
    name="world (air)",
    geometry=Sphere(
        radius=10.0,
        material=Dielectric.air()
    )
)
sphere = Node(
    name="sphere (glass)",
    geometry=Sphere(
        radius=1.0,
        material=Dielectric.glass()
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

# Trace the scene
scene = Scene(world)
for ray in light.emit(100):
    # Do something with this optical path information
    path = photon_tracer.follow(ray, scene)
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