"""Python-facing API for the compiled tracing engine."""
import collections
import multiprocessing
import time

import numpy as np

from pvtrace.engine.compiler import EMIT_METHODS, compile_scene
from pvtrace.light.event import Event
from pvtrace.light.ray import Ray


def is_available() -> bool:
    """Returns True if the native kernel has been built and can be imported."""
    try:
        from pvtrace.engine import _kernel  # noqa: F401
    except ImportError:
        return False
    return True


class EngineResult:
    """Packed event log for a traced bundle of rays.

    The raw event data is available as numpy arrays in `data`; the row
    for event `k` of ray `i` is `i * max_events + k` with per-ray counts
    in `data["counts"]`. Use `histories()` for pvtrace-style
    `(Ray, Event, metadata)` tuples.
    """

    def __init__(self, compiled, data, sources, max_events, elapsed):
        self.compiled = compiled
        self.data = data
        self.sources = sources
        self.max_events = max_events
        self.elapsed = elapsed

    @property
    def num_rays(self):
        return len(self.data["counts"])

    def event_counts(self):
        """Counter of all events by Event enum member."""
        counts = self.data["counts"]
        kinds = self.data["kind"].reshape(self.num_rays, self.max_events)
        mask = np.arange(self.max_events)[None, :] < counts[:, None]
        values, tallies = np.unique(kinds[mask], return_counts=True)
        return collections.Counter(
            {Event(int(v)): int(t) for v, t in zip(values, tallies)}
        )

    def _node_name(self, index):
        return self.compiled.node_names[index] if index >= 0 else None

    def _component_name(self, index):
        return self.compiled.component_names[index] if index >= 0 else None

    def histories(self):
        """Yields one history per ray: a list of (Ray, Event, metadata)."""
        d = self.data
        for i in range(self.num_rays):
            history = []
            base = i * self.max_events
            for k in range(int(d["counts"][i])):
                row = base + k
                source_id = int(d["source"][row])
                source = (
                    self.sources[i]
                    if source_id < 0
                    else self._component_name(source_id)
                )
                ray = Ray(
                    position=tuple(d["position"][row].tolist()),
                    direction=tuple(d["direction"][row].tolist()),
                    wavelength=float(d["wavelength"][row]),
                    travelled=float(d["travelled"][row]),
                    duration=float(d["duration"][row]),
                    source=source,
                )
                event = Event(int(d["kind"][row]))
                metadata = {
                    "hit": self._node_name(int(d["hit"][row])),
                    "container": self._node_name(int(d["container"][row])),
                    "adjacent": self._node_name(int(d["adjacent"][row])),
                    "component": self._component_name(int(d["component"][row])),
                }
                if event in (Event.REFLECT, Event.TRANSMIT):
                    metadata["normal"] = tuple(d["normal"][row].tolist())
                history.append((ray, event, metadata))
            yield history


def simulate(
    scene,
    num_rays,
    seed=None,
    workers=None,
    maxsteps=1000,
    max_events=128,
    emit_method="kT",
):
    """Trace `num_rays` through `scene` with the compiled engine.

    Initial rays are emitted by the scene's light sources in Python (so
    all light delegates are supported); the tracing loop runs in native
    code. Raises `UnsupportedSceneError` if the scene cannot be
    compiled — callers can fall back to the Python tracer.
    """
    from pvtrace.engine import _kernel

    if emit_method not in EMIT_METHODS:
        raise ValueError(f"emit_method must be one of {sorted(EMIT_METHODS)}")

    compiled = compile_scene(scene)

    if workers is None:
        workers = max(1, multiprocessing.cpu_count() // 2)
    if seed is None:
        seed = np.random.randint(0, 2 ** 31 - 1)

    positions = np.zeros((num_rays, 3), dtype=np.float64)
    directions = np.zeros((num_rays, 3), dtype=np.float64)
    wavelengths = np.zeros(num_rays, dtype=np.float64)
    sources = []
    for i, ray in enumerate(scene.emit(num_rays)):
        positions[i] = ray.position
        directions[i] = ray.direction
        wavelengths[i] = ray.wavelength
        sources.append(ray.source)

    tic = time.perf_counter()
    data = _kernel.trace_bundle(
        compiled,
        positions,
        directions,
        wavelengths,
        int(seed),
        int(maxsteps),
        int(max_events),
        EMIT_METHODS[emit_method],
        int(workers),
    )
    elapsed = time.perf_counter() - tic
    return EngineResult(compiled, data, sources, max_events, elapsed)
