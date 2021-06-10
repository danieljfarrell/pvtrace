from __future__ import annotations
import multiprocessing
import os
from typing import Optional, Sequence, Tuple
from anytree import PostOrderIter, LevelOrderIter
from pvtrace.scene.node import Node
from pvtrace.light.light import Light
from pvtrace.light.event import Event
from pvtrace.material.component import Component
from pvtrace.geometry.utils import (
    distance_between,
    close_to_zero,
    intersection_point_is_ahead,
)
from pvtrace.algorithm import photon_tracer
import numpy as np
import logging

logger = logging.getLogger(__name__)


def do_simulation(scene, num_rays, seed):
    """Worker function for multiple processing."""
    # Re-seed for this thread/process
    if seed is not None:
        np.random.seed(seed)

    results = []
    for ray in scene.emit(num_rays):
        ray_history = photon_tracer.follow(scene, ray)
        results.append(ray_history)
    return results


def is_end_ray(event, metadata):
    """Classify ray event in a little more detail to determine if
    this is "end ray" or not. An end ray is a ray entering, exiting
    a node or being absorbed.
    """
    ignored = {Event.EMIT, Event.SCATTER, Event.ABSORB}
    if event in ignored:
        return False

    if event in (
        Event.GENERATE,
        Event.NONRADIATIVE,
        Event.REACT,
        Event.KILL,
        Event.EXIT,
    ):
        return True
    elif event in (Event.REFLECT, Event.TRANSMIT):
        if metadata["hit"] == metadata["adjacent"] and event == Event.REFLECT:
            return True  # reflected from node
        elif metadata["hit"] == metadata["adjacent"] and event == Event.TRANSMIT:
            return True  # transmitted into node
        elif metadata["hit"] == metadata["container"] and event == Event.TRANSMIT:
            return True  # escaped node
    return False


def do_simulation_add_to_queue(scene, num_rays, seed, queue, end_rays):
    """Worker function for multiple processing puts results into queue."""
    # Re-seed for this thread/process
    if seed is not None:
        np.random.seed(seed)

    count = 0
    pid = os.getpid()

    # What is an "end ray"?
    # Only record major ray events should as entering/reflecting from nodes
    # or being absorbed by reactor or non-radiatively. This option speeds
    # up raytracing and allows full ray statistics on surfaces to be known.
    # However, the full ray history is lost. Re-absorption events, and
    # internal proagation details inside nodes are lost. The only details
    # that remain from internal propagation is the total path length travelled
    # and the duration it took.

    for idx, ray in enumerate(scene.emit(num_rays)):
        count = count + 1
        for info in photon_tracer.step_forward(scene, ray):
            ray, event, metadata = info
            if end_rays:
                if is_end_ray(event, metadata):
                    queue.put((pid, idx, ray, event, metadata))
            else:
                queue.put((pid, idx, ray, event, metadata))
    return pid


class Scene(object):
    """A scene graph of nodes."""

    def __init__(self, root=None):
        super(Scene, self).__init__()
        self.root = root

    def finalise_nodes(self):
        """Update bounding boxes of node hierarchy in preparation for tracing."""
        root = self.root
        if root is not None:

            # Clear any existing bounding boxes
            for node in PostOrderIter(root):
                node.bounding_box = None

            # More efficiency to calculate from leaves to root because because
            # the parent's bounding box calculation requires the size of the
            # child's bounding box.
            leaves = self.root.leaves
            for leaf_node in leaves:
                node = leaf_node
                while True:
                    _ = node.bounding_box  # will force recalculation
                    node = node.parent
                    if node is None:
                        break

    @property
    def light_nodes(self) -> Sequence[Node]:
        """Returns all lights in the scene."""
        return [node for node in LevelOrderIter(self.root) if isinstance(node.light, Light)]

    @property
    def component_nodes(self) -> Sequence[Component]:
        """Returns all the components present in the scene."""
        root = self.root
        component = []
        for node in LevelOrderIter(root):
            if node.geometry:
                if node.geometry.material:
                    component.extend(node.geometry.material.components)
        return component

    def emit(self, num_rays: int):
        """Rays are emitted in the coordinate system of the world node.

        Internally the scene cycles through Light nodes, asks them to emit
        a ray and the converts the ray to the world coordinate system.
        """
        lights = self.light_nodes
        for idx in range(num_rays):
            light = lights[idx % len(lights)]
            for ray in light.emit(1):
                yield ray.representation(light, self.root)

    def intersections(self, ray_origin, ray_direction) -> Sequence[Tuple[Node, Tuple]]:
        """Intersections with ray and scene. Ray is defined in the root node's
        coordinate system.
        """
        # to-do: Prune which nodes are queried for intersections by first
        # intersecting the ray with bounding boxes of the node.
        root = self.root
        if root is None:
            return tuple()

        def distance_sort_key(i):
            v = np.array(i.point) - np.array(ray_origin)
            d = np.linalg.norm(v)
            return d

        all_intersections = self.root.intersections(ray_origin, ray_direction)
        # Convert intersection point to root frame/node.
        all_intersections = map(lambda x: x.to(root), all_intersections)
        # Filter for forward intersections only
        all_intersections = tuple(
            filter(
                lambda x: intersection_point_is_ahead(
                    ray_origin, ray_direction, x.point
                ),
                all_intersections,
            )
        )

        # Sort by distance to ray
        all_intersections = tuple(sorted(all_intersections, key=distance_sort_key))
        # to-do: Correctly order touching interfaces
        # touching_idx = []
        # for idx, pair in enumerate(zip(all_intersections[:-1], all_intersections[1:])):
        #     if close_to_zero(distance_between(pair[0].point, pair[1].point)):
        #         touching_idx.append(idx)
        # for idx in touching_idx:
        #     i = list(all_intersections)
        #     a, b = idx - 1, idx
        #     if i[a].hit != i[b].hit:
        #         # Swap order
        #         i[b], i[a] = i[a], i[b]
        #     all_intersections = tuple(i)
        return all_intersections

    def simulate(
        self,
        num_rays: int,
        workers: Optional[int] = None,
        seed: Optional[int] = None,
        queue: Optional[multiprocessing.Queue] = None,
        end_rays: Optional[bool] = False,
    ):
        """Concurrently emit rays from light sources and return results.

        Parameters
        ----------
        num_rays: int
            The total number of rays to throw
        workers: (Optional) int
            The number of sub-processes to use for raytracing. None will set to maximum value.
        seed: (Optional) int
            Only to be used for debugging to get reproducible ray sequence.
        queue: (Optional) multiprocessing.Queue
            If queue is specified results are delivered to the queue _instead_ of returning
            results at the end of the simulation. This helps with reducing memory usage.
        end_rays: (Optional) bool
            Default if False being that all events are sent to the queue.

        Returns
        -------
        result:
            List of ray histories

        Discussion
        ----------
        This method automatically re-seeds the random number generator in each process
        to ensure the same rays are not generated.

        For debugging purposes generating the same ray sequence is useful. This can be
        done by setting the value of `seed`::

            scene.simulate(100, workers=1, seed=0)

        You must also set workers to one during debugging.
        """
        if workers is None:
            workers = max(1, multiprocessing.cpu_count() - 1)

        if workers == 1:
            if queue:
                return do_simulation_add_to_queue(self, num_rays, seed, queue, end_rays)
            return do_simulation(self, num_rays, seed)

        num_rays_per_worker = num_rays // workers
        if num_rays_per_worker == 0:
            if queue:
                return do_simulation_add_to_queue(self, num_rays, seed, queue, end_rays)
            return do_simulation(self, num_rays, seed)

        if num_rays_per_worker * workers < num_rays:
            remainder = num_rays % (num_rays_per_worker * workers)
        else:
            remainder = (num_rays_per_worker * workers) % num_rays

        print(
            f"Simulating with {workers} workers with {num_rays_per_worker} ray per worker (with remainder {remainder})"
        )
        rays = [num_rays_per_worker] * workers
        rays[0] += remainder
        if seed is None:
            seeds = np.random.randint(0, (2 ** 31) - 1, workers)
        else:
            raise ValueError(
                "Seed must be None to ensure different quasi-random sequences in each process"
            )

        pool = multiprocessing.Pool(processes=workers)

        # Results are send to queue
        if queue:
            results_proxy = [
                pool.apply_async(
                    do_simulation_add_to_queue,
                    (self, rays[idx], seeds[idx], queue, end_rays),
                )
                for idx in range(workers)
            ]
            [result.get() for result in results_proxy]
            return

        # Results are processed directly and returned
        results_proxy = [
            pool.apply_async(do_simulation, (self, rays[idx], seeds[idx]))
            for idx in range(workers)
        ]
        results = []
        for result in results_proxy:
            histories = result.get()
            for history in histories:
                results.append(history)
        return results
