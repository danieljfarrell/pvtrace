"""Pure-Python recorder tallies over photon tracer histories.

This is the reference implementation of recorders: it reproduces the
engine's tally semantics by walking `(ray, event, metadata)` histories
from `photon_tracer.step_forward` (or `EngineResult.histories`). Use it
to tally scenes the engine cannot compile, and to validate the engine.
"""
import numpy as np
from anytree import PreOrderIter

from pvtrace.engine.recorder import Heatmap
from pvtrace.light.event import Event


def _local_position(root, node, position):
    if node is root:
        return tuple(position)
    return root.point_to_node(position, node)


def _incidence_angle(direction, normal):
    dot = abs(float(np.dot(direction, normal)))
    return float(np.arccos(min(dot, 1.0)))


def _matches(recorder, node, event, metadata):
    """Does this history event match the recorder's selector?"""
    name = node.name
    kind = recorder.event
    if event == Event.TRANSMIT and metadata.get("hit") == name:
        if kind == "entering":
            return metadata.get("adjacent") == name
        if kind == "escaping":
            return metadata.get("container") == name
        return False
    if event == Event.REFLECT and kind == "reflected":
        return (metadata.get("hit") == name
                and metadata.get("adjacent") == name)
    if event == Event.NONRADIATIVE and kind == "lost":
        return metadata.get("container") == name
    if event == Event.REACT and kind == "reacted":
        return metadata.get("container") == name
    if event == Event.KILL and kind == "killed":
        return metadata.get("container") == name
    if event == Event.EXIT and kind == "exit":
        return metadata.get("hit") == name
    return False


class _TallyState:
    def __init__(self, recorder):
        self.recorder = recorder
        self.rays = 0
        self.crossings = 0
        self.moments = np.zeros((4, 2))
        self.bins = []
        for hist in recorder.histograms:
            if isinstance(hist, Heatmap):
                self.bins.append(np.zeros(hist.a.bins * hist.b.bins, dtype=np.int64))
            else:
                self.bins.append(np.zeros(hist.bins, dtype=np.int64))

    def accumulate(self, values):
        self.rays += 1
        for index, prop in enumerate(("wavelength", "angle", "duration", "pathlength")):
            value = values[prop]
            self.moments[index, 0] += value
            self.moments[index, 1] += value * value
        for hist, bins in zip(self.recorder.histograms, self.bins):
            if isinstance(hist, Heatmap):
                ia = _bin_index(values[hist.a.prop], hist.a)
                ib = _bin_index(values[hist.b.prop], hist.b)
                if ia >= 0 and ib >= 0:
                    bins[ia * hist.b.bins + ib] += 1
            else:
                index = _bin_index(values[hist.prop], hist)
                if index >= 0:
                    bins[index] += 1


def _bin_index(value, hist):
    index = int((value - hist.start) / (hist.stop - hist.start) * hist.bins)
    return index if 0 <= index < hist.bins else -1


def tally_histories(scene, histories):
    """Tally recorder statistics from ray histories.

    Parameters
    ----------
    scene: Scene
        Scene whose nodes carry `Recorder` objects.
    histories: iterable
        One history per ray: a sequence of `(ray, event, metadata)`
        tuples as produced by `photon_tracer.step_forward` or
        `EngineResult.histories`.

    Returns
    -------
    dict of recorder name to `RecorderResult`.
    """
    from pvtrace.engine.api import RecorderResult

    root = scene.root
    pairs = []  # (node, recorder, state)
    for node in PreOrderIter(root):
        for recorder in getattr(node, "recorders", []):
            pairs.append((node, recorder, _TallyState(recorder)))

    for history in histories:
        seen = set()
        previous_ray = None
        for ray, event, metadata in history:
            metadata = metadata or {}
            for node, recorder, state in pairs:
                if not _matches(recorder, node, event, metadata):
                    continue
                normal = metadata.get("normal")
                if event == Event.EXIT and normal is None:
                    local = _local_position(root, node, ray.position)
                    normal = node.geometry.normal(local)
                    normal = node.vector_to_node(normal, root)
                if recorder.facet is not None:
                    if normal is None or any(
                        abs(f - n) > recorder.atol
                        for f, n in zip(recorder.facet, normal)
                    ):
                        continue
                state.crossings += 1
                if recorder.name in seen:
                    continue
                seen.add(recorder.name)

                if event == Event.EXIT:
                    incident = ray.direction
                else:
                    incident = (previous_ray or ray).direction
                angle = 0.0
                if normal is not None:
                    angle = _incidence_angle(incident, normal)
                local = _local_position(root, node, ray.position)
                state.accumulate({
                    "wavelength": ray.wavelength,
                    "angle": angle,
                    "duration": ray.duration,
                    "pathlength": ray.travelled,
                    "x": local[0], "y": local[1], "z": local[2],
                })
            previous_ray = ray

    return {
        recorder.name: RecorderResult(
            recorder, state.rays, state.crossings, state.moments, state.bins
        )
        for _, recorder, state in pairs
    }
