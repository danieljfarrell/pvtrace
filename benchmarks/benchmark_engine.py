"""Benchmark the compiled engine against the Python tracer.

Usage::

    PYTHONPATH=. python benchmarks/benchmark_engine.py
"""
import time

import numpy as np

from pvtrace import (
    Absorber,
    Box,
    Light,
    Luminophore,
    Material,
    Node,
    Scene,
    Sphere,
)
from pvtrace.algorithm import photon_tracer
from pvtrace.material.utils import gaussian
import pvtrace.engine as engine


def make_lsc_scene():
    x = np.linspace(300.0, 1000.0, 200)
    absorption = np.column_stack((x, 5.0 * gaussian(x, 1.0, 480.0, 40.0)))
    emission = np.column_stack((x, gaussian(x, 1.0, 600.0, 40.0)))
    world = Node(
        name="world",
        geometry=Sphere(radius=10.0, material=Material(refractive_index=1.0)),
    )
    Node(
        name="slab",
        geometry=Box(
            (5.0, 5.0, 1.0),
            material=Material(
                refractive_index=1.5,
                components=[
                    Luminophore(
                        coefficient=absorption,
                        emission=emission,
                        quantum_yield=0.9,
                        name="dye",
                    ),
                    Absorber(coefficient=0.3, name="background"),
                ],
            ),
        ),
        parent=world,
    )
    light = Node(name="light", light=Light(), parent=world)
    light.location = (0.0, 0.0, -3.0)
    return Scene(world)


def bench_python(scene, num_rays):
    np.random.seed(0)
    rays = list(scene.emit(num_rays))
    tic = time.perf_counter()
    events = 0
    for ray in rays:
        events += len(photon_tracer.follow(scene, ray))
    elapsed = time.perf_counter() - tic
    return elapsed, events


def bench_engine(scene, num_rays, workers):
    result = engine.simulate(
        scene, num_rays, seed=0, workers=workers, max_events=256
    )
    events = int(result.data["counts"].sum())
    return result.elapsed, events


def main():
    scene = make_lsc_scene()

    n_python = 500
    py_elapsed, py_events = bench_python(scene, n_python)
    py_rate = n_python / py_elapsed
    print(f"python tracer     {n_python:>8d} rays  {py_elapsed:8.2f} s  "
          f"{py_rate:>12,.0f} rays/s  ({py_events} events)")

    if not engine.is_available():
        print("engine kernel not built; run: python -m pvtrace.engine.build")
        return

    n_engine = 200000
    for workers in (1, 4, None):
        elapsed, events = bench_engine(scene, n_engine, workers)
        rate = n_engine / elapsed
        label = "auto" if workers is None else str(workers)
        print(f"engine ({label:>4s} thr) {n_engine:>8d} rays  {elapsed:8.2f} s  "
              f"{rate:>12,.0f} rays/s  ({events} events, "
              f"speedup x{rate / py_rate:,.0f})")


if __name__ == "__main__":
    main()
