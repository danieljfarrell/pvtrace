"""Validation of the compiled engine against the Python tracer.

The Python tracer is the reference implementation: for supported scenes
the engine must sample the same distributions, so per-ray event rates
from the two tracers are compared within Monte Carlo error.
"""
import functools
import math

import numpy as np
import pytest

from pvtrace import (
    Absorber,
    Box,
    Light,
    Luminophore,
    Material,
    Mesh,
    Node,
    Scene,
    Sphere,
)
from pvtrace.algorithm import photon_tracer
from pvtrace.light.event import Event
from pvtrace.material.utils import cone, gaussian
import pvtrace.engine as engine

pytestmark = pytest.mark.skipif(
    not engine.is_available(),
    reason="engine kernel not built (python -m pvtrace.engine.build)",
)


def make_fresnel_scene():
    """A glass box in air hit by a slightly diverging beam."""
    world = Node(
        name="world",
        geometry=Sphere(radius=10.0, material=Material(refractive_index=1.0)),
    )
    box = Node(
        name="box",
        geometry=Box((1.0, 1.0, 1.0), material=Material(refractive_index=1.5)),
        parent=world,
    )
    box.location = (0.0, 0.0, 2.0)
    Node(
        name="light",
        light=Light(direction=functools.partial(cone, np.pi / 16)),
        parent=world,
    )
    return Scene(world)


def make_lsc_scene():
    """A luminescent slab with a background absorber.

    The background absorption is strong enough that trapped rays are
    absorbed after a handful of internal reflections, keeping every
    history well within the engine's event budget so the comparison
    with the Python tracer is exact.
    """
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


EVENTS = [
    Event.REFLECT,
    Event.TRANSMIT,
    Event.ABSORB,
    Event.NONRADIATIVE,
    Event.EMIT,
    Event.EXIT,
    Event.KILL,
]


def python_per_ray_counts(scene, num_rays, seed):
    np.random.seed(seed)
    counts = {event: np.zeros(num_rays) for event in EVENTS}
    for i, ray in enumerate(scene.emit(num_rays)):
        for _, event in photon_tracer.follow(scene, ray):
            if event in counts:
                counts[event][i] += 1
    return counts


def engine_per_ray_counts(result):
    n, m = result.num_rays, result.max_events
    kinds = result.data["kind"].reshape(n, m)
    valid = np.arange(m)[None, :] < result.data["counts"][:, None]
    return {
        event: ((kinds == event.value) & valid).sum(axis=1).astype(float)
        for event in EVENTS
    }


def assert_means_close(python_counts, engine_counts, nsigma=5.0):
    """Welch comparison of per-ray event count means."""
    for event in EVENTS:
        a = python_counts[event]
        b = engine_counts[event]
        se = math.sqrt(a.var(ddof=1) / a.size + b.var(ddof=1) / b.size)
        diff = abs(a.mean() - b.mean())
        assert diff <= nsigma * se + 1e-9, (
            f"{event.name}: python mean {a.mean():.4f} vs engine mean "
            f"{b.mean():.4f} (tolerance {nsigma * se:.4f})"
        )


def test_engine_matches_python_tracer_fresnel():
    scene = make_fresnel_scene()
    py = python_per_ray_counts(scene, 800, seed=42)
    result = engine.simulate(scene, 20000, seed=7)
    eng = engine_per_ray_counts(result)

    assert result.data["counts"].max() < result.max_events - 1
    assert_means_close(py, eng)
    # Every ray must leave the world sphere in this scene
    assert eng[Event.EXIT].sum() == result.num_rays


def test_engine_matches_python_tracer_lsc():
    scene = make_lsc_scene()
    py = python_per_ray_counts(scene, 400, seed=3)
    result = engine.simulate(scene, 20000, seed=11, max_events=256)
    eng = engine_per_ray_counts(result)

    assert result.data["counts"].max() < result.max_events - 1
    assert_means_close(py, eng)

    # Sanity: emitted wavelengths are red-shifted on average
    kinds = result.data["kind"]
    n, m = result.num_rays, result.max_events
    valid = (np.arange(m)[None, :] < result.data["counts"][:, None]).ravel()
    emitted = result.data["wavelength"][(kinds == Event.EMIT.value) & valid]
    assert emitted.size > 0
    assert emitted.mean() > 550.0


def test_engine_is_deterministic_for_seed():
    scene = make_lsc_scene()
    a = engine.simulate(scene, 500, seed=123, workers=4)
    b = engine.simulate(scene, 500, seed=123, workers=2)
    assert np.array_equal(a.data["counts"], b.data["counts"])
    assert np.array_equal(a.data["kind"], b.data["kind"])
    assert np.allclose(a.data["position"], b.data["position"])
    assert np.allclose(a.data["wavelength"], b.data["wavelength"])


def test_engine_histories_look_like_python_histories():
    scene = make_fresnel_scene()
    result = engine.simulate(scene, 10, seed=5)
    histories = list(result.histories())
    assert len(histories) == 10
    for history in histories:
        ray, event, metadata = history[0]
        assert event == Event.GENERATE
        assert ray.travelled == 0.0
        ray, event, metadata = history[-1]
        assert event in (Event.EXIT, Event.NONRADIATIVE, Event.KILL, Event.REACT)
        if event == Event.EXIT:
            assert metadata["hit"] == "world"


def test_unsupported_scene_raises():
    import trimesh

    world = Node(
        name="world",
        geometry=Sphere(radius=10.0, material=Material(refractive_index=1.0)),
    )
    Node(
        name="mesh",
        geometry=Mesh(
            trimesh.creation.icosphere(radius=1.0),
            material=Material(refractive_index=1.5),
        ),
        parent=world,
    )
    Node(name="light", light=Light(), parent=world)
    scene = Scene(world)
    with pytest.raises(engine.UnsupportedSceneError):
        engine.simulate(scene, 10)
