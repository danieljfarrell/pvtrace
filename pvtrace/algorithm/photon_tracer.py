import traceback
import collections
import traceback
import numpy as np
from typing import Optional, Tuple, Sequence
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
    intersections = scene.intersections(ray.position, ray.direction)
    # Remove on surface intersections
    intersections = \
        [x for x in intersections if not close_to_zero(x.distance)]

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


def trace(scene, ray, maxsteps=20, renderer=None, render_path=False):
    count = 0
    history = [ray]
    while True:
        count += 1
        if count > maxsteps:
            print("Max count reached.")
            break

        info = next_hit(scene, ray)
        print("Info: ", info)
        if info is None:
            print("[1] Exit.")
            break

        hit, (container, adjacent), point, full_distance = info
        print("interface: {}|{} (hit: {})".format(container, adjacent, hit))
        if hit is scene.root:
            print("[2] Exit.")
            break

        material = container.geometry.material
        absorbed, at_distance = material.is_absorbed(ray, full_distance)
        if absorbed:
            ray = ray.propagate(at_distance)
            component = material.component(ray.wavelength)
            if component.is_radiative(ray):
                ray = component.emit(ray)
                history.append(ray)
                print("Step", ray)
                continue
            else:
                history.append(ray)
                print("[3] Exit.")
                break
        else:
            ray = ray.propagate(full_distance)
            surface = hit.geometry.surface
            if surface.is_reflected(ray, hit.geometry, container, adjacent):
                ray = surface.reflect(ray, hit.geometry, container, adjacent)
                history.append(ray)
                print("REFLECT", ray)
                continue
            else:
                ray = surface.transmit(ray, hit.geometry, container, adjacent)
                history.append(ray)
                print("TRANSMIT", ray)
                continue
    return history

