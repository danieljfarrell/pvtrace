""" A rather slow but physically realistic photon path tracing algorithm.
"""
import traceback
import collections
import traceback
import numpy as np
from typing import Optional, Tuple, Sequence
from dataclasses import dataclass, replace
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.light.ray import Ray
from pvtrace.light.event import Event
from pvtrace.material.component import Scatterer, Luminophore, Reactor
from pvtrace.geometry.utils import (
    distance_between,
    close_to_zero,
    points_equal,
    EPS_ZERO,
)
from pvtrace.common.errors import TraceError
import logging

logger = logging.getLogger(__name__)


def find_container(intersections):
    """Returns the container node.

    Parameters
    ----------
    intersections: List[Intersection]
        Full list of intersections of ray with a scene.

    Returns
    -------
    Node
        The container node

    Example
    -------
    >>> intersections = scene.intersections(ray.position, ray.directions)
    >>> container = find_container(intersections)
    """
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
    """Returns information about the next interface the ray makes with the scene.

    Parameters
    ----------
    scene : Scene
    ray : Ray

    Returns
    -------
    hit_node : Node
        The node corresponding to the geometry object that was hit.
    interface : tuple of Node
        Two node: the `container` and the `adjacent` which correspond to the
        materials either side of the interface.
    point: tuple of float
        The intersection point.
    distance: float
        Distance to the intersection point.
    """
    # Intersections are in the local node's coordinate system
    intersections = scene.intersections(ray.position, ray.direction)

    # Remove on surface intersections
    intersections = [x for x in intersections if not close_to_zero(x.distance)]

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


def step_forward(scene, ray, maxsteps=1000, maxpathlength=np.inf, emit_method="kT"):
    """The main ray-tracing algorithm. Provide a scene and a ray and this generates
     a full photon path history, events and metadata.

    Parameters
    ----------
    scene: Scene
        The `Scene` to trace.
    ray: Ray
        The `Ray` to trace through the scene.
    maxsteps: int
        Abort ray tracing after this number of steps. Default is 1000.
    maxpathlength: float
        Abort ray tracing after ray has travelled more than this distance. Default
        is infinity.
    emit_method: str
        Either `'kT'`, `'redshift'` or `'full'`.

        `'kT'` option allowed emitted rays to have a wavelength
        within 3kT of the absorbed value.

        `'redshift'` option ensures the emitted ray has a longer of equal
        wavelength.

        `'full'` option samples the full emission spectrum allowing the emitted
        ray to take any value.

    Returns
    -------
    history: tuple
        Elements are 2-tuples (Ray, Event)

    Example
    -------

    Trace a scene with 10 rays::

        for ray in scene.emit(10):
            history = photon_tracer.follow(ray, scene)
            rays, events = zip(*history)
    """
    count = 0
    yield (ray, Event.GENERATE, None)
    while True:
        count += 1
        info = next_hit(scene, ray)
        if info is None:
            break

        hit, (container, adjacent), point, full_distance = info

        if count > maxsteps or ray.travelled > maxpathlength:
            yield (
                ray,
                Event.KILL,
                {
                    "maxsteps": count,
                    "maxpathlength": ray.travelled,
                    "container": container.name,
                },
            )
            break

        refractive_index = container.geometry.material.refractive_index
        if hit is scene.root:
            yield (
                ray.propagate(full_distance, refractive_index),
                Event.EXIT,
                {
                    "hit": hit.name,
                    "container": container.name,
                    "adjacent": None if adjacent is None else adjacent.name,
                },
            )
            break

        material = container.geometry.material
        absorbed, at_distance = material.is_absorbed(ray, full_distance)
        if absorbed:
            ray = ray.propagate(at_distance, refractive_index)
            component = material.component(ray.wavelength)
            yield (
                ray,
                Event.ABSORB,
                {"component": component.name, "container": container.name},
            )

            if component.is_radiative(ray):
                ray = component.emit(
                    ray.representation(scene.root, container), method=emit_method
                ).representation(container, scene.root)
                if isinstance(component, Luminophore):
                    event = Event.EMIT
                elif isinstance(component, Scatterer):
                    event = Event.SCATTER
                else:
                    raise ValueError("Unknown component")
                yield (
                    ray,
                    event,
                    {
                        "component": component.name,
                        "emit_method": emit_method,
                        "container": container.name,
                    },
                )
                continue
            else:
                ray = component.nonradiative_absorb(ray)
                if isinstance(component, Reactor):
                    yield (
                        ray,
                        Event.REACT,
                        {"component": component.name, "container": container.name},
                    )
                else:
                    yield (
                        ray,
                        Event.NONRADIATIVE,
                        {"component": component.name, "container": container.name},
                    )
                break
        else:
            ray = ray.propagate(full_distance, refractive_index)
            surface = hit.geometry.material.surface

            # Need the ray in the frame of the hit object to compute normal
            # and to perform relfections and refractions.
            local_ray = ray.representation(scene.root, hit)
            normal = hit.vector_to_node(
                hit.geometry.normal(local_ray.position), scene.root
            )
            if surface.is_reflected(local_ray, hit.geometry, container, adjacent):
                ray = surface.reflect(
                    local_ray, hit.geometry, container, adjacent
                ).representation(hit, scene.root)
                yield (
                    ray,
                    Event.REFLECT,
                    {
                        "hit": hit.name,
                        "container": container.name,
                        "adjacent": None if adjacent is None else adjacent.name,
                        "normal": normal,
                    },
                )
                continue
            else:
                ray = surface.transmit(
                    local_ray, hit.geometry, container, adjacent
                ).representation(hit, scene.root)
                yield (
                    ray,
                    Event.TRANSMIT,
                    {
                        "hit": hit.name,
                        "container": container.name,
                        "adjacent": adjacent.name,
                        "normal": normal,
                    },
                )
                continue


def follow(scene, ray, maxsteps=1000, maxpathlength=np.inf, emit_method="kT"):
    """The main ray-tracing function. Provide a scene and a ray and get a full photon
    path history and list of events.

    Parameters
    ----------
    scene: Scene
        The `Scene` to trace.
    ray: Ray
        The `Ray` to trace through the scene.
    maxsteps: int
        Abort ray tracing after this number of steps. Default is 1000.
    maxpathlength: float
        Abort ray tracing after ray has travelled more than this distance. Default
        is infinity.
    emit_method: str
        Either `'kT'`, `'redshift'` or `'full'`.

        `'kT'` option allowed emitted rays to have a wavelength
        within 3kT of the absorbed value.

        `'redshift'` option ensures the emitted ray has a longer of equal
        wavelength.

        `'full'` option samples the full emission spectrum allowing the emitted
        ray to take any value.

    Returns
    -------
    history: tuple
        Elements are 2-tuples (Ray, Event)

    Example
    -------

    Trace a scene with 10 rays::

        for ray in scene.emit(10):
            history = photon_tracer.follow(ray, scene)
            rays, events = zip(*history)
    """
    history = list(
        step_forward(
            scene,
            ray,
            maxsteps=maxsteps,
            maxpathlength=maxpathlength,
            emit_method=emit_method,
        )
    )
    # Remove metadata for backward compatability
    ray, events, _ = zip(*history)
    return list(zip(ray, events))
