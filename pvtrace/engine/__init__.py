"""Compiled tracing engine.

The engine traces bundles of rays through a compiled scene using native
code. The public API mirrors the results of the pure Python tracer in
``pvtrace.algorithm.photon_tracer``: for scenes which use only built-in
surface delegates, phase functions and geometry primitives the two
tracers sample the same distributions and are statistically
interchangeable. Scenes that fall outside this subset raise
``UnsupportedSceneError`` and should be traced with the Python tracer.

The native kernel is optional: if it has not been built, ``is_available``
returns ``False``. Build it in-place with::

    python -m pvtrace.engine.build
"""
from pvtrace.engine.compiler import (
    CompiledScene,
    UnsupportedSceneError,
    compile_scene,
)
from pvtrace.engine.recorder import Heatmap, Histogram, Recorder
from pvtrace.engine.tally import tally_histories
from pvtrace.engine.api import (
    EngineResult,
    RecorderResult,
    is_available,
    simulate,
    simulate_stream,
)

__all__ = [
    "CompiledScene",
    "UnsupportedSceneError",
    "compile_scene",
    "Recorder",
    "Histogram",
    "Heatmap",
    "EngineResult",
    "RecorderResult",
    "is_available",
    "simulate",
    "simulate_stream",
    "tally_histories",
]
