![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/logo.png)

> Optical ray tracing for luminescent materials and spectral converter photovoltaic devices 

## Install

    pip install pvtrace

Tutorials are in Jupyter notebook form so to view those

    pip install jupyter

### pyenv (macOS)

If using macOS you may want to use [pyenv](https://github.com/pyenv/pyenv) to create a clean virtual environment for pvtrace.

    pyenv virtualenv 3.7.2 pvtrace-env
    pyenv activate pvtrace-env
    pip install pvtrace
    # download https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/examples/hello_world.py
    python hello_world.py

### conda (Windows, Linux and macOS)

Conda can also be used but you must manually install the Rtree dependency *before* the `pip install pvtrace` command!

    conda create --name pvtrace-env python=3.7
    conda activate pvtrace-env
    conda install Rtree
    pip install pvtrace
    # download https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/examples/hello_world.py
    python hello_world.py
    
## Introduction


*pvtrace* is a statistical photon path tracer written in Python. 

Rays are followed through a 3D scene and their interactions with objects are recorded to build up statistical information about energy flow.

This is useful in photovoltaics and non-imaging optics where the goal is to design systems which efficiently transport light to target locations.

## Features

### Luminescent solar concentrators


One of the key features of pvtrace is the ability to simulate re-absorption of photons in devices like Luminescent Solar Concentrators.


A basic LSC can be simulated and visualised in a few lines of code,

```python
from pvtrace import *
lsc = LSC((5.0, 5.0, 1.0))  # size in cm
lsc.show()  # open visualiser
lsc.simulate(100)  # emit 100 rays
lsc.report()  # print report
```

This script will render the ray-tracing in real time,

![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/pvtrace-demo.gif)



### Ray optics simulations


*pvtrace* supports ray-tracing a 3D scene of shapes,

* box
* sphere
* cylinder
* mesh

The optical properties of each shape can be customised,

* refractive index
* absorption coefficient
* scattering coefficient
* emission lineshape
* quantum yield
* surface reflection
* surface scattering

Currently, there are no optical components such as lenses, beam-splitter, gratings but these would be constructed using the scene API.

![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/example.png)

For example, the script to ray trace this glass sphere is below,

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

### Scene API

*pvtrace* is designed in layers each with as limited scope as possible.

![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/pvtrace-design.png)


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
  
  <dt>Ray-tracing engine</dt>
  <dd>The algorithm which spawns rays, computes intersections, samples probabilities and travers the rays through the scene.</dd>
</dl>

Currently *pvtrace* supports only one ray-tracing engine: a photon path tracer. This is physically accurate, down to treating individual absorption and emission events, but is slow because the problem cannot be vectorised as each ray is followed individually.

## Documentation

Interactive Jupyter notebooks are in [examples directory](https://github.com/danieljfarrell/pvtrace/tree/master/examples), download and take a look, although they can be viewed online.

API documentation and some background at [https://pvtrace.readthedocs.io](https://pvtrace.readthedocs.io/)

## Contributing

Please use the github [issue](https://github.com/danieljfarrell/pvtrace/issues) tracker for bug fixes, suggestions, or support questions.
 
### Creating a development environment

Get started by creating a development environment. On MaOS or Linux this is easy using `pyenv`,

```bash
# Make workspace and python runtime
mkdir pvtrace-dev
cd pvtrace-dev
pyenv virtualenv 3.7.2 pvtrace-dev
pyenv local pvtrace-dev

# Pull from master
git clone https://github.com/danieljfarrell/pvtrace.git

# Get development dependencies
pip install -r pvtrace/requirements_dev.txt 

# Add local `pvtrace` directory to known packages
pip install -e pvtrace

# Run units tests
pytest pvtrace/tests

# Run an example
python pvtrace/examples/hello_world.py
```

You should now be able to edit the source code and simply run scripts directly without the need to reinstall anything.

### Unit tests

Please add or modifty an exsiting unit tests in the `pvtrace/tests` directory if you are adding new code. This will make it much easier to include your changes in the project.
 
## Questions

You can get in contact with me directly at [dan@excitonlabs.com](mailto:dan@excitonlabs.com?subject=GitHub pvtrace question)

## Dependancies

Basic environment requires the following packages which will be installed with `pip` automatically

* python >= 3.7.2
* numpy
* trimesh[easy]
* meshcat >= 0.0.16
* anytree

