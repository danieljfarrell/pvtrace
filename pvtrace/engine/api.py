"""Python-facing API for the compiled tracing engine."""
import collections
import multiprocessing
import time

import numpy as np

from pvtrace.engine.compiler import EMIT_METHODS, compile_scene
from pvtrace.engine.recorder import Heatmap
from pvtrace.light.event import Event
from pvtrace.light.ray import Ray

# Properties with always-on moment accumulators, in kernel order
MOMENT_PROPERTIES = ("wavelength", "angle", "duration", "pathlength")


def is_available() -> bool:
    """Returns True if the native kernel has been built and can be imported."""
    try:
        from pvtrace.engine import _kernel  # noqa: F401
    except ImportError:
        return False
    return True


class RecorderResult:
    """Tallied statistics for one recorder.

    `rays` counts distinct rays (a trapped ray crossing several times
    counts once, matching the CLI count queries); `crossings` counts
    every matching interaction. Moments and histograms accumulate per
    distinct ray.
    """

    def __init__(self, spec, rays, crossings, moments, bins):
        self.spec = spec
        self.rays = int(rays)
        self.crossings = int(crossings)
        self._moments = moments  # (4, 2): (sum, sum of squares) per property
        self._bins = bins        # list of arrays matching spec.histograms

    def mean(self, prop):
        index = MOMENT_PROPERTIES.index(prop)
        if self.rays == 0:
            return float("nan")
        return self._moments[index, 0] / self.rays

    def std(self, prop):
        """Population standard deviation of `prop` over recorded rays."""
        index = MOMENT_PROPERTIES.index(prop)
        if self.rays == 0:
            return float("nan")
        mean = self._moments[index, 0] / self.rays
        variance = max(self._moments[index, 1] / self.rays - mean * mean, 0.0)
        return float(np.sqrt(variance))

    def error(self, prop):
        """Standard error of the mean of `prop`."""
        if self.rays == 0:
            return float("nan")
        return self.std(prop) / np.sqrt(self.rays)

    def histogram(self, index=0):
        """Returns (edges, counts) for 1D or (edges_a, edges_b, counts) for 2D."""
        spec = self.spec.histograms[index]
        values = self._bins[index]
        if isinstance(spec, Heatmap):
            edges_a = np.linspace(spec.a.start, spec.a.stop, spec.a.bins + 1)
            edges_b = np.linspace(spec.b.start, spec.b.stop, spec.b.bins + 1)
            return edges_a, edges_b, values.reshape(spec.a.bins, spec.b.bins)
        edges = np.linspace(spec.start, spec.stop, spec.bins + 1)
        return edges, values

    def __repr__(self):
        return (
            f"RecorderResult({self.spec.name!r}, rays={self.rays}, "
            f"crossings={self.crossings})"
        )


class EngineResult:
    """Results of tracing a bundle of rays.

    Recorder tallies cover every traced ray and are available in
    `recorders`. Full event histories are recorded for every
    `record_every`-th ray (all rays when 1, none when 0); the raw event
    data is in `data`, where the row for event `k` of recorded ray `j`
    is `j * max_events + k` with per-recorded-ray counts in
    `data["counts"]`. Use `histories()` for pvtrace-style
    `(Ray, Event, metadata)` tuples.
    """

    def __init__(self, compiled, data, sources, max_events, record_every, elapsed):
        self.compiled = compiled
        self.data = data
        self.sources = sources
        self.max_events = max_events
        self.record_every = record_every
        self.elapsed = elapsed

    @property
    def num_rays(self):
        """Number of rays traced."""
        return len(self.sources)

    @property
    def num_recorded(self):
        """Number of rays with a full event history."""
        return len(self.data["counts"])

    @property
    def recorded_indices(self):
        """Original ray index of each recorded history."""
        if self.record_every <= 0:
            return np.zeros(0, dtype=np.int64)
        return np.arange(0, self.num_rays, self.record_every, dtype=np.int64)

    @property
    def recorders(self):
        """Dict of recorder name to RecorderResult."""
        compiled = self.compiled
        results = {}
        for r, spec in enumerate(compiled.recorder_specs):
            bins = []
            start = compiled.rec_hist_start[r]
            for h, hist in enumerate(spec.histograms):
                offset = compiled.hist_offset[start + h]
                size = compiled.hist_na[start + h] * compiled.hist_nb[start + h]
                bins.append(self.data["rec_bins"][offset:offset + size])
            results[spec.name] = RecorderResult(
                spec,
                self.data["rec_distinct"][r],
                self.data["rec_crossings"][r],
                self.data["rec_sums"][r],
                bins,
            )
        return results

    def event_counts(self):
        """Counter of logged events by Event enum member.

        Note this covers only rays with recorded histories; use
        recorders for lossless counting over every ray.
        """
        counts = self.data["counts"]
        if len(counts) == 0:
            return collections.Counter()
        kinds = self.data["kind"].reshape(self.num_recorded, self.max_events)
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
        """Yields one history per recorded ray: a list of (Ray, Event, metadata)."""
        d = self.data
        indices = self.recorded_indices
        for j in range(self.num_recorded):
            history = []
            base = j * self.max_events
            for k in range(int(d["counts"][j])):
                row = base + k
                source_id = int(d["source"][row])
                source = (
                    self.sources[int(indices[j])]
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
    record_every=1,
):
    """Trace `num_rays` through `scene` with the compiled engine.

    Initial rays are emitted by the scene's light sources in Python (so
    all light delegates are supported); the tracing loop runs in native
    code. Recorders attached to scene nodes tally every ray; full event
    histories are kept for every `record_every`-th ray (all rays when 1,
    none when 0). Raises `UnsupportedSceneError` if the scene cannot be
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
        int(record_every),
    )
    elapsed = time.perf_counter() - tic
    return EngineResult(compiled, data, sources, max_events, record_every, elapsed)
