import traceback
import collections
import traceback
import numpy as np
from typing import Optional, Tuple, Sequence
from enum import Enum
from dataclasses import dataclass, replace
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.light.ray import Ray
from pvtrace.geometry.utils import distance_between, close_to_zero, points_equal, EPS_ZERO
from pvtrace.common.errors import TraceError
import logging
logger = logging.getLogger(__name__)


def find_container(intersections):
    # Find container node that has two properties:
    # 1. only appears in the intersection list once
    # 2. of the above is the has closest intersection to ray position
    if len(intersections) == 1:
        return intersections[0].hit
    count = collections.Counter([x.hit for x in intersections]).most_common()
    candidates = [x[0] for x in count if x[1] == 1]
    pairs = []
    for intersection in intersections:
        node = intersection.hit
        if node in candidates:
            pairs.append((node, intersection.distance))
    # [(node, dist), (node, dist)... ]
    pairs = sorted(pairs, key=lambda tup: tup[1])
    containers, _ = zip(*pairs)
    container = containers[0]
    return container


def next_hit(scene, ray):
    # Intersections are in the local node's coordinate system
    intersections = scene.intersections(ray.position, ray.direction)
    
    # Remove on surface intersections
    intersections = \
        [x for x in intersections if not close_to_zero(x.distance)]
    
    print(intersections)
    # Convert intersection points to world node
    intersections = [x.to(scene.root) for x in intersections]
    
    # Node which owns the surface
    if len(intersections) == 0:
        return None

    # The surface being hit
    hit = intersections[0]
    if len(intersections) == 1:
        hit_node = hit.hit
        return hit_node, (hit_node, None), hit.point, hit.distance
    
    container = find_container(intersections)
    hit = intersections[0]
    # Intersection point and distance from ray
    point = hit.point
    hit_node = hit.hit
    distance = distance_between(ray.position, point)
    if container == hit_node:
        adjacent = intersections[1].hit
    else:
        adjacent = hit_node
    return hit_node, (container, adjacent), point, distance


class Event(Enum):
    GENERATE = 0
    REFLECT = 1
    TRANSMIT = 2
    ABSORB = 3
    SCATTER = 4
    EMIT = 5
    EXIT = 6
    MAXSTEP = 7


def trace(scene, ray, maxsteps=1000):
    count = 0
    history = [(ray, Event.GENERATE)]
    while True:
        count += 1
        if count > maxsteps:
            history.append([ray, Event.MAXSTEP])
            break

        info = next_hit(scene, ray)
        if info is None:
            break

        hit, (container, adjacent), point, full_distance = info
        if hit is scene.root:
            history.append((ray.propagate(full_distance), Event.EXIT))
            break

        material = container.geometry.material
        absorbed, at_distance = material.is_absorbed(ray, full_distance)
        if absorbed:
            ray = ray.propagate(at_distance)
            component = material.component(ray.wavelength)
            if component.is_radiative(ray):
                ray = component.emit(ray.representation(scene.root, container))
                ray = ray.representation(container, scene.root)
                if isinstance(component, Luminophore):
                    event = Event.EMIT
                elif isinstance(component, Scatterer):
                    event = Event.SCATTER
                history.append((ray, event))
                continue
            else:
                history.append((ray, Event.ABSORB))
                break
        else:
            ray = ray.propagate(full_distance)
            surface = hit.geometry.surface
            ray = ray.representation(scene.root, hit)
            if surface.is_reflected(ray, hit.geometry, container, adjacent):
                ray = surface.reflect(ray, hit.geometry, container, adjacent)
                ray = ray.representation(hit, scene.root)
                history.append((ray, Event.REFLECT))
                #print("REFLECT", ray)
                continue
            else:
                ref_ray = surface.transmit(ray, hit.geometry, container, adjacent)
                #if points_equal(ref_ray.direction, ray.direction):
                #    raise ValueError("Ray did not refract.")
                ray = ref_ray
                ray = ray.representation(hit, scene.root)
                history.append((ray, Event.TRANSMIT))
                #print("TRANSMIT", ray)
                continue
    return history

