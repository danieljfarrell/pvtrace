from __future__ import division
import numpy as np
from pvtrace import transformations as tf
from pvtrace import *
import visual as v

points = [(0,0,0),(0.05,0,0),(0,0.05,0),(0.05,0.05,0),(0.025,0.025,.05)]
convex = Convex(points)

#convex = Box(origin=(0,0,0), extent=(0.05,0.05,0.05))

print convex.on_surface((0,0.01,0))

ray = Ray(position=(0.045,0.019,-0.01), direction=norm((0,0,1)))
print convex.intersection(ray)

v.convex(pos=points)
v.cylinder(pos=ray.position, axis=ray.direction, radius=0.0001)
