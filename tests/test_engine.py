"""Validation of the compiled engine against the Python tracer.

The Python tracer is the reference implementation: for supported scenes
the engine must sample the same distributions, so per-ray event rates
from the two tracers are compared within Monte Carlo error.
"""
import functools
import math
from pathlib import Path

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
    n, m = result.num_recorded, result.max_events
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
    n, m = result.num_recorded, result.max_events
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


def attach_recorder(scene, node_name, recorder):
    from anytree import PreOrderIter

    for node in PreOrderIter(scene.root):
        if node.name == node_name:
            node.recorders.append(recorder)
            return
    raise ValueError(node_name)


def test_recorders_match_event_log():
    from pvtrace.engine import Heatmap, Histogram, Recorder

    scene = make_lsc_scene()
    attach_recorder(
        scene, "slab",
        Recorder("entering-slab", event="entering",
                 histograms=[Histogram("wavelength", 400, 900, 50)]),
    )
    attach_recorder(
        scene, "slab",
        Recorder("top-escape", event="escaping", facet=(0, 0, 1),
                 histograms=[Heatmap("x", "y", (-2.5, 2.5, 25), (-2.5, 2.5, 25))]),
    )
    attach_recorder(scene, "slab", Recorder("lost-in-slab", event="lost"))
    attach_recorder(scene, "world", Recorder("world-exit", event="exit"))

    result = engine.simulate(scene, 4000, seed=21, max_events=256)
    recs = result.recorders

    # Recompute the same distinct-ray tallies from the engine's own
    # event log; recorders must agree exactly.
    n_enter = n_escape_top = n_lost = n_exit = 0
    for history in result.histories():
        entered = escaped_top = lost_here = exited = False
        for ray, event, meta in history:
            if event == Event.TRANSMIT and meta["hit"] == "slab":
                if meta["adjacent"] == "slab":
                    entered = True
                elif meta["container"] == "slab":
                    normal = meta["normal"]
                    if (abs(normal[0]) <= 1e-6 and abs(normal[1]) <= 1e-6
                            and abs(normal[2] - 1.0) <= 1e-6):
                        escaped_top = True
            elif event == Event.NONRADIATIVE and meta["container"] == "slab":
                lost_here = True
            elif event == Event.EXIT:
                exited = True
        n_enter += entered
        n_escape_top += escaped_top
        n_lost += lost_here
        n_exit += exited

    assert recs["entering-slab"].rays == n_enter > 0
    assert recs["top-escape"].rays == n_escape_top > 0
    assert recs["lost-in-slab"].rays == n_lost > 0
    assert recs["world-exit"].rays == n_exit > 0

    # Histogram totals equal distinct counts when values are in range
    edges, values = recs["entering-slab"].histogram(0)
    assert values.sum() == n_enter
    assert edges.size == 51
    xe, ye, heat = recs["top-escape"].histogram(0)
    assert heat.shape == (25, 25)
    assert heat.sum() == n_escape_top

    # The source is monochromatic so the entering mean is exact
    assert recs["entering-slab"].mean("wavelength") == pytest.approx(555.0)
    assert recs["entering-slab"].crossings >= recs["entering-slab"].rays


def test_recorders_independent_of_history_sampling():
    from pvtrace.engine import Recorder

    scene = make_lsc_scene()
    attach_recorder(scene, "slab", Recorder("entering", event="entering"))

    full = engine.simulate(scene, 3000, seed=9, record_every=1, max_events=256)
    sampled = engine.simulate(scene, 3000, seed=9, record_every=100)
    none = engine.simulate(scene, 3000, seed=9, record_every=0)

    assert (full.recorders["entering"].rays
            == sampled.recorders["entering"].rays
            == none.recorders["entering"].rays)
    assert full.recorders["entering"].crossings == none.recorders["entering"].crossings
    assert full.num_recorded == 3000
    assert sampled.num_recorded == 30
    assert none.num_recorded == 0
    assert len(list(sampled.histories())) == 30
    assert len(list(none.histories())) == 0


def test_python_tally_matches_engine_recorders_exactly():
    """tally_histories over the engine's own histories reproduces the
    kernel's tallies exactly."""
    from pvtrace.engine import Heatmap, Histogram, Recorder, tally_histories

    scene = make_lsc_scene()
    attach_recorder(
        scene, "slab",
        Recorder("entering", event="entering",
                 histograms=[Histogram("wavelength", 400, 900, 50)]),
    )
    attach_recorder(
        scene, "slab",
        Recorder("top", event="escaping", facet=(0, 0, 1),
                 histograms=[Heatmap("x", "y", (-2.5, 2.5, 20), (-2.5, 2.5, 20))]),
    )
    attach_recorder(scene, "slab", Recorder("lost", event="lost"))
    attach_recorder(scene, "world", Recorder("exit", event="exit",
                    histograms=[Histogram("angle", 0.0, np.pi / 2, 18)]))

    result = engine.simulate(scene, 3000, seed=17, max_events=256)
    python_tallies = tally_histories(scene, result.histories())

    for name, engine_side in result.recorders.items():
        python_side = python_tallies[name]
        assert python_side.rays == engine_side.rays, name
        assert python_side.crossings == engine_side.crossings, name
        for index in range(len(engine_side.spec.histograms)):
            assert np.array_equal(
                python_side._bins[index], engine_side._bins[index]
            ), (name, index)
        assert np.allclose(python_side._moments, engine_side._moments,
                           rtol=1e-9), name


def test_python_tracer_tally_matches_engine_statistically():
    """Recorders tallied from Python-tracer histories agree with the
    engine within Monte Carlo error (lockstep)."""
    from pvtrace.engine import Recorder, tally_histories

    scene = make_lsc_scene()
    attach_recorder(scene, "slab", Recorder("entering", event="entering"))
    attach_recorder(scene, "slab", Recorder("lost", event="lost"))

    n_python = 300
    np.random.seed(5)
    histories = []
    for ray in scene.emit(n_python):
        histories.append(
            list(photon_tracer.step_forward(scene, ray))
        )
    python_tallies = tally_histories(scene, histories)

    n_engine = 20000
    result = engine.simulate(scene, n_engine, seed=13, record_every=0)
    engine_tallies = result.recorders

    for name in ("entering", "lost"):
        p_a = python_tallies[name].rays / n_python
        p_b = engine_tallies[name].rays / n_engine
        p = (python_tallies[name].rays + engine_tallies[name].rays) / (
            n_python + n_engine
        )
        se = math.sqrt(max(p * (1 - p), 1e-12) * (1 / n_python + 1 / n_engine))
        assert abs(p_a - p_b) <= 5 * se, (name, p_a, p_b)


def test_yaml_recorders_parse():
    """The recorders section of the scene spec builds Recorder objects."""
    from pvtrace.cli.parse import parse

    scene = parse(str(Path(__file__).parent.parent / "examples" / "studio_lsc.yml"))
    from anytree import PreOrderIter

    recorders = {
        recorder.name: recorder
        for node in PreOrderIter(scene.root)
        for recorder in node.recorders
    }
    # The explicit recorder plus the record: true auto-instrumentation
    assert "edge-escape" in recorders
    assert recorders["edge-escape"].facet == (1.0, 0.0, 0.0)
    auto = {"lsc-top", "lsc-bottom", "lsc-east", "lsc-west",
            "lsc-north", "lsc-south", "lsc-lost"}
    assert auto <= set(recorders)
    assert len(recorders["lsc-top"].histograms) == 3


def test_record_shorthand_instruments_node(tmp_path):
    """record: true on a node desugars into default recorders."""
    from anytree import PreOrderIter

    from pvtrace.cli.parse import parse

    text = """
version: "1.0"
nodes:
  world:
    sphere:
      radius: 10.0
      material:
        refractive-index: 1.0
  slab:
    record: true
    box:
      size: [5, 5, 1]
      material:
        refractive-index: 1.5
  laser:
    location: [0, 0, 3]
    direction: [0, 0, -1]
    light:
      wavelength: 555
"""
    path = tmp_path / "scene.yml"
    path.write_text(text)
    scene = parse(str(path))
    recorders = {
        recorder.name: recorder
        for node in PreOrderIter(scene.root)
        for recorder in node.recorders
    }
    # 6 faces + volume loss
    assert len(recorders) == 7
    assert "slab-top" in recorders and "slab-lost" in recorders
    assert recorders["slab-top"].facet == (0.0, 0.0, 1.0)

    result = engine.simulate(scene, 2000, seed=2, record_every=0)
    top = result.recorders["slab-top"]
    assert top.rays > 0


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
