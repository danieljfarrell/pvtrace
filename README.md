[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.592982.svg)](https://doi.org/10.5281/zenodo.592982)

![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/logo.png)

> Optical ray tracing for luminescent materials and spectral converter photovoltaic devices

# Ray-tracing luminescent solar concentrators

*pvtrace* is a statistical photon path tracer written in Python. Rays are followed through a 3D scene and their interactions with objects are recorded to build up statistical information about energy flow.

This is useful in photovoltaics and non-imaging optics where the goal is to design systems which efficiently transport light to target locations. 

One of its key features is the ability to simulate re-absorption in luminescent materials. For example, like in devices like Luminescent Solar Concentrators (LSCs).

A basic LSC can be simulated and visualised in five lines of code,

```python
from pvtrace import *
lsc = LSC((5.0, 5.0, 1.0))  # size in cm
lsc.show()                  # open visualiser
lsc.simulate(100)           # emit 100 rays
lsc.report()                # print report
```

This script will render the ray-tracing in real time,

![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/pvtrace-demo.gif)

pvtrace has been validate against three other luminescent concentrator codes. For full details see [Validation.ipynb](https://github.com/danieljfarrell/pvtrace/blob/master/examples/Validation.ipynb) notebook

![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/examples/Validation.png)

# Install

## MacOS using pyenv

On MacOS *pvtrace* can be installed easily using [pyenv](https://github.com/pyenv/pyenv), the `pip` command and [homebrew](https://brew.sh). First install [homebrew](https://brew.sh), then install `spatialindex` for the RTree dependency,

    brew install spatialindex

Next, create a clean virtual environment for pvtrace

    pyenv install 3.7.8
    pyenv virtualenv 3.7.8 pvtrace-env
    pyenv activate pvtrace-env
    pip install pvtrace

## Linux and Windows using Conda

On Linux and Windows you must use conda to create the python environment. Optionally you can also use this method on MacOS too if you prefer conda over pyenv.

    conda create --name pvtrace-env python=3.7.8
    conda activate pvtrace-env
    conda install Rtree
    pip install pvtrace

# Run the example script and notebooks

Download the [hello_world.py](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/examples/hello_world.py) example script either manually or using `curl`,

    # Download example script
    curl https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/examples/hello_world.py > hello_world.py

Now active your python environment! 

If you installed using **pyenv** do the following,

    pyenv local pvtrace-env

If you are using **conda** to this,

    conda activate pvtrace-env

Now start the meshcat server with the command,

    meshcat-server

This will print information like,

    zmq_url=tcp://127.0.0.1:6000
    web_url=http://127.0.0.1:7000/static/

Open a new terminal window and again activate your pvtrace-env.

Open `hello_world.py` and make sure the line below has `zmq_url` of your meshcat-server,

    # Change zmq_url here to be the address of your meshcat-server!
    renderer = MeshcatRenderer(
        zmq_url="tcp://127.0.0.1:6000", wireframe=True, open_browser=True
    )   

You can now run pvtrace scripts! Run this following command,

    python hello_world.py

Also take a look at the online Jupyter notebook tutorial series which provide an overview of pvtrace and examples,

 1. [Quick Start.ipynb](https://github.com/danieljfarrell/pvtrace/blob/master/examples/001%20Quick%20Start.ipynb), an interactive ray-tracing tutorial (download an run locally)
 2. [Materials.ipynb](https://github.com/danieljfarrell/pvtrace/blob/master/examples/002%20Materials.ipynb), include physical properties with materials
 3. [Lights.ipynb](https://github.com/danieljfarrell/pvtrace/blob/master/examples/003%20Lights.ipynb), place photon sources in the scene and customise their properties
 4. [Nodes.ipynb](https://github.com/danieljfarrell/pvtrace/blob/master/examples/004%20Nodes.ipynb) translate and rotate scene objects with nodes
 5. [Geometry.ipynb](https://github.com/danieljfarrell/pvtrace/blob/master/examples/005%20Geometry.ipynb) define the shapes of objects in your scene
 6. [Coatings.ipynb](https://github.com/danieljfarrell/pvtrace/blob/master/examples/006%20Coatings.ipynb) introduce custom reflections with coatings

Download and run these notebooks locally for a more interactive experience, but first install jupyter,

    pip install jupyter

or with conda,

    conda install jupyter

Then launch the jupyter notebook,

    jupyter notebook

# Features

## Ray optics simulations

*pvtrace* supports 3D ray optics simulations shapes,

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

![](https://raw.githubusercontent.com/danieljfarrell/pvtrace/master/docs/example.png)

## High and low-level API

*pvtrace* has a high-level API for handling common problems with LSCs and a low-level API where objects can be positioned in a 3D scene and optical properties customised.

For example, a script using the low-level API to ray trace this glass sphere is below,

```python
import time
import sys
import functools
import numpy as np
from pvtrace import *

# World node contains all objects
world = Node(
    name="world (air)",
    geometry=Sphere(
        radius=10.0,
        material=Material(refractive_index=1.0),
    )
)

# The glass sphere
sphere = Node(
    name="sphere (glass)",
    geometry=Sphere(
        radius=1.0,
        material=Material(refractive_index=1.5),
    ),
    parent=world
)
sphere.location = (0, 0, 2)

# The source of rays
light = Node(
    name="Light (555nm)",
    light=Light(direction=functools.partial(cone, np.pi/8)),
    parent=world
)

# Render and ray-trace
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

## Scene Graph

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
  <dd>The algorithm which spawns rays, computes intersections, samples probabilities and traverses the rays through the scene.</dd>
</dl>

## Ray-tracing engine

Currently *pvtrace* supports only one ray-tracing engine: a photon path tracer. This is physically accurate, down to treating individual absorption and emission events, but is slow because the problem cannot be vectorised as each ray is followed individually.

# Documentation

Interactive Jupyter notebooks are in [examples directory](https://github.com/danieljfarrell/pvtrace/tree/master/examples), download and take a look, although they can be viewed online.

# Contributing

Please use the github [issue](https://github.com/danieljfarrell/pvtrace/issues) tracker for bug fixes, suggestions, or support questions.

If you are considering contributing to pvtrace, first fork the project. This will make it easier to include your contributions using pull requests.

## Creating a development environment

1. First create a new development environment using [MacOS instructions](#macos-using-pyenv) or [Linux and Windows instructions](#linux-and-windows-using-conda), but do not install pvtrace using pip! You will need to clone your own copy of the source code in the following steps.
2. Use the GitHub fork button to make your own fork of the project. This will make it easy to include your changes in pvtrace using a pull request.
3. Follow the steps below to clone and install the development dependencies

```bash
# Pull from your fork
git clone https://github.com/<your username>/pvtrace.git

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

## Unit tests

Please add or modify an existing unit tests in the `pvtrace/tests` directory if you are adding new code. This will make it much easier to include your changes in the project.

## Pull requests

Pull requests will be considered. Please make contact before doing a lot of work, to make sure that the changes will definitely be included in the main project.

# Questions

You can get in contact with me directly at dan@excitonlabs.com or raise an issue on the issue tracker.

# Dependencies

Basic environment requires the following packages which will be installed with `pip` automatically

* python >= 3.7.2
* numpy
* pandas
* trimesh[easy]
* meshcat >= 0.0.16
* anytree
