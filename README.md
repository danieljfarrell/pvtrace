![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/logo.png)

> Optical ray tracing for luminescent materials and spectral converter photovoltaic devices 

## Install

    pip install pvtrace

Tutorials are in Jupyter notebook form so to view those

    pip install jupyter

### pyenv

You may want to use [pyenv](https://github.com/pyenv/pyenv) to create a clean virtual environment for pvtrace.

    pyenv virtualenv 3.7.2 pvtrace-env
    pyenv activate pvtrace-env
    pip install pvtrace
    # download the examples/hello_world.py from GitHub
    python hello_world.py

## Introduction

pvtrace is a statistical photon path tracer written in Python. It follows photons through a 3D scene and records their interactions with objects to build up statistical information about energy flow. This approach is particularly useful in photovoltaics and non-imaging optics where the goal is to design systems which efficiently transport light to target locations.

## Documentation

Interactive Jupyter notebooks are in [examples directory](https://github.com/danieljfarrell/pvtrace/tree/master/examples), download and take a look, although they can be viewed online.

API documentation and some background at [https://pvtrace.readthedocs.io](https://pvtrace.readthedocs.io/)

## Capabilities

pvtrace was originally written to characterise the performance of Luminescent Solar Concentrators (LSC) and takes a Monte-Carlo approach to ray-tracing. Each ray is independent and can interact with objects in the scene via reflection and refraction. Objects can have different optical properties: refractive index, absorption coefficient, emission spectrum and quantum yield.

One of the key features of pvtrace is the ability to simulate re-absorption of photons in luminescent materials. This requires following thousands of rays to build intensity profiles and spectra of incoming and outgoing photons because these process cannot be approximated in a continuous way.

pvtrace may also be useful to researches or designers interested in ray-optics simulations but will be slower at running these simulations compared to other software packages because it follows each ray individually.

![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/example.png)
    
A minimal working example that traces a glass sphere

```python
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
    )
)

sphere = Node(
    name="sphere (glass)",
    geometry=Sphere(
        radius=1.0,
        material=Material(refractive_index=1.5),
    ),
    parent=world
)
sphere.location = (0, 0, 2)

light = Node(
    name="Light (555nm)",
    light=Light(direction=functools.partial(cone, np.pi/8)),
    parent=world
)

renderer = MeshcatRenderer(wireframe=True, open_browser=True)
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
        time.sleep(.3)
    except KeyboardInterrupt:
        sys.exit()
```

## Architecture

![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/pvtrace-design.png)

*pvtrace* is designed in layers each with as limited scope as possible.

<dl>
  <dt>Scene</dt>
  <dd>Graph data structure of node and the thing that is ray-traced.</dd>
  
  <dt>Node</dt>
  <dd>Provides a coordinate system, can be nested inside one another, perform arbitrary rotation and translation transformations.</dd>
  
  <dt>Geometry</dt>
  <dd>Attached to nodes to define different shapes (Sphere, Box, Cylinder, Mesh) and handles all ray intersections.</dd>
  
  <dt>Material</dt>
  <dd>Attached to geometry objects to assign physical properties to shapes such as refractive index.</dd>
  
  <dt>Surface</dt>
  <dd>Handles details of interaction between material surfaces and a customisation point for simulation of wavelength selective coatings.</dd>
  
  <dt>Components</dt>
  <dd>Specifies optical properties of the geometries volume, absorption coefficient, scattering coefficient, quantum yield, emission spectrum.</dd>
</dl>

## Dependancies

Basic environment requires the following packages which will be installed with `pip` automatically

* python >= 3.7.2
* numpy
* trimesh[easy]
* meshcat >= 0.0.16
* anytree

