"""FastAPI backend for pvtrace studio.

The scene document (YAML text) is the single source of truth. The
frontend edits the document; the server validates and parses it,
returns a geometry payload for the 3D viewport, and streams engine
results (recorder tallies and sampled ray paths) over a websocket.
"""
import asyncio
import io
import os
import tempfile
import time
from pathlib import Path

import numpy as np
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import pvtrace.engine as engine
from pvtrace.cli.parse import parse as parse_scene_file
from pvtrace.engine.recorder import Heatmap, Histogram, Recorder

STATIC = Path(__file__).resolve().parent / "static"

GEOM_NAMES = {0: "box", 1: "sphere", 2: "cylinder"}


class Studio:
    """Holds the current document and its parsed scene."""

    def __init__(self, document=""):
        self.document = document
        self.scene = None
        self.recorder_specs = {}

    def apply(self, text):
        """Validate and parse a new document; returns the scene payload."""
        spec = yaml.safe_load(io.StringIO(text))
        if not isinstance(spec, dict):
            raise ValueError("Document is not a YAML mapping.")
        recorders = spec.pop("recorders", {}) or {}

        # parse() validates against the JSON schema and reads from disk
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yml", delete=False, dir=os.getcwd()
        ) as fp:
            yaml.safe_dump(spec, fp)
            path = fp.name
        try:
            scene = parse_scene_file(path)
        finally:
            os.unlink(path)

        self._attach_recorders(scene, recorders)
        compiled = engine.compile_scene(scene)  # raises if unsupported

        self.document = text
        self.scene = scene
        self.recorder_specs = recorders
        return self.scene_payload(compiled)

    def _attach_recorders(self, scene, recorders):
        from anytree import PreOrderIter

        nodes = {node.name: node for node in PreOrderIter(scene.root)}
        for name, spec in recorders.items():
            node_name = spec.get("node")
            if node_name not in nodes:
                raise ValueError(f"Recorder {name!r}: unknown node {node_name!r}.")
            histograms = []
            for prop, values in (spec.get("histograms") or {}).items():
                if prop == "position":
                    prop_a, prop_b, range_a, range_b = values
                    histograms.append(Heatmap(prop_a, prop_b, range_a, range_b))
                else:
                    lo, hi, bins = values
                    histograms.append(Histogram(prop, lo, hi, bins))
            recorder = Recorder(
                name,
                event=spec.get("event", "entering"),
                facet=spec.get("facet"),
                atol=spec.get("atol", 1e-6),
                histograms=histograms,
            )
            nodes[node_name].recorders.append(recorder)

    def scene_payload(self, compiled):
        """Geometry description for the three.js viewport."""
        from anytree import PreOrderIter

        nodes = []
        for i, name in enumerate(compiled.node_names):
            nodes.append(
                {
                    "name": name,
                    "type": GEOM_NAMES[int(compiled.geom_type[i])],
                    "params": compiled.geom_params[i].tolist(),
                    # three.js Matrix4.fromArray expects column-major
                    "matrix": compiled.local_to_world[i].T.ravel().tolist(),
                    "root": i == compiled.root_id,
                }
            )
        lights = []
        for node in PreOrderIter(self.scene.root):
            if node.light is not None:
                matrix = np.asarray(node.transformation_to(self.scene.root))
                lights.append({"name": node.name, "matrix": matrix.T.ravel().tolist()})
        recorders = []
        for name, spec in self.recorder_specs.items():
            recorders.append({"name": name, "node": spec.get("node"),
                              "event": spec.get("event", "entering")})
        return {"nodes": nodes, "lights": lights, "recorders": recorders}


def create_app(document_path=None):
    app = FastAPI(title="pvtrace studio")
    text = ""
    if document_path:
        text = Path(document_path).read_text()
    studio = Studio(text)

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/document")
    async def get_document():
        return {"text": studio.document}

    @app.put("/api/document")
    async def put_document(payload: dict):
        try:
            scene = studio.apply(payload["text"])
        except Exception as exception:  # surface parse errors to the UI
            return JSONResponse({"error": str(exception)}, status_code=422)
        return {"scene": scene}

    @app.websocket("/ws")
    async def websocket(ws: WebSocket):
        await ws.accept()
        stop = {"flag": False}
        task = None

        async def run(params):
            loop = asyncio.get_running_loop()
            num_rays = int(params.get("rays", 100000))
            bundle = int(params.get("bundle", 25000))
            seed = params.get("seed")
            record_every = int(params.get("record_every", 1000))
            max_paths = int(params.get("max_paths", 200))

            compiled = engine.compile_scene(studio.scene)
            hist_meta = _histogram_meta(compiled)
            await ws.send_json({"type": "started", "total": num_rays,
                                "histograms": hist_meta})

            n_rec = len(compiled.recorder_names)
            distinct = np.zeros(n_rec, dtype=np.int64)
            crossings = np.zeros(n_rec, dtype=np.int64)
            sums = np.zeros((n_rec, 4, 2), dtype=np.float64)
            bins = np.zeros(int(compiled.total_bins), dtype=np.int64)
            sent_paths = 0
            tic = time.perf_counter()

            stream = engine.simulate_stream(
                studio.scene, num_rays, bundle=bundle, seed=seed,
                record_every=record_every,
            )
            while True:
                item = await loop.run_in_executor(None, next, stream, None)
                if item is None or stop["flag"]:
                    break
                result, traced = item
                distinct += result.data["rec_distinct"]
                crossings += result.data["rec_crossings"]
                sums += result.data["rec_sums"]
                bins += result.data["rec_bins"]

                paths = []
                if sent_paths < max_paths:
                    paths = _extract_paths(result, max_paths - sent_paths)
                    sent_paths += len(paths)

                elapsed = time.perf_counter() - tic
                await ws.send_json({
                    "type": "bundle",
                    "traced": traced,
                    "total": num_rays,
                    "rays_per_second": traced / elapsed if elapsed > 0 else 0,
                    "recorders": _recorder_payload(
                        compiled, distinct, crossings, sums, bins
                    ),
                    "paths": paths,
                })
            await ws.send_json({"type": "done",
                                "elapsed": time.perf_counter() - tic})

        try:
            while True:
                message = await ws.receive_json()
                command = message.get("cmd")
                if command == "run":
                    if studio.scene is None:
                        await ws.send_json({"type": "error",
                                            "message": "Apply a scene first."})
                        continue
                    stop["flag"] = False
                    task = asyncio.create_task(run(message))
                elif command == "stop":
                    stop["flag"] = True
        except WebSocketDisconnect:
            stop["flag"] = True
            if task:
                task.cancel()

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    # Parse the initial document so the viewport has content on load
    if text:
        try:
            studio.apply(text)
        except Exception:
            pass
    return app


def _histogram_meta(compiled):
    """Static histogram descriptions sent once per run."""
    meta = {}
    for r, spec in enumerate(compiled.recorder_specs):
        entries = []
        start = compiled.rec_hist_start[r]
        for h, hist in enumerate(spec.histograms):
            offset = int(compiled.hist_offset[start + h])
            if isinstance(hist, Heatmap):
                entries.append({
                    "kind": "heatmap", "offset": offset,
                    "prop_a": hist.a.prop, "prop_b": hist.b.prop,
                    "edges_a": np.linspace(hist.a.start, hist.a.stop,
                                           hist.a.bins + 1).tolist(),
                    "edges_b": np.linspace(hist.b.start, hist.b.stop,
                                           hist.b.bins + 1).tolist(),
                })
            else:
                entries.append({
                    "kind": "hist", "offset": offset, "prop": hist.prop,
                    "edges": np.linspace(hist.start, hist.stop,
                                         hist.bins + 1).tolist(),
                })
        meta[spec.name] = {"event": spec.event, "histograms": entries}
    return meta


def _recorder_payload(compiled, distinct, crossings, sums, bins):
    payload = {}
    for r, spec in enumerate(compiled.recorder_specs):
        entries = []
        start = compiled.rec_hist_start[r]
        for h, hist in enumerate(spec.histograms):
            offset = int(compiled.hist_offset[start + h])
            if isinstance(hist, Heatmap):
                size = hist.a.bins * hist.b.bins
                values = bins[offset:offset + size]
                entries.append({"values": values.tolist(),
                                "shape": [hist.a.bins, hist.b.bins]})
            else:
                entries.append({"values": bins[offset:offset + hist.bins].tolist()})
        n = max(int(distinct[r]), 1)
        payload[spec.name] = {
            "rays": int(distinct[r]),
            "crossings": int(crossings[r]),
            "mean_wavelength": float(sums[r, 0, 0] / n),
            "mean_angle": float(sums[r, 1, 0] / n),
            "histograms": entries,
        }
    return payload


def _extract_paths(result, limit):
    """Sampled ray paths as polylines for the viewport."""
    d = result.data
    paths = []
    for j in range(min(result.num_recorded, limit)):
        count = int(d["counts"][j])
        if count < 2:
            continue
        base = j * result.max_events
        points = d["position"][base:base + count]
        # Per-vertex wavelength so luminescent re-emission changes the
        # path colour at the absorption point.
        wavelengths = d["wavelength"][base:base + count]
        paths.append({
            "points": np.round(points, 6).tolist(),
            "wavelengths": np.round(wavelengths, 2).tolist(),
        })
    return paths


def main(document_path=None, host="127.0.0.1", port=8567, open_browser=True):
    import uvicorn

    app = create_app(document_path)
    if open_browser:
        import threading
        import webbrowser

        threading.Timer(1.0, webbrowser.open,
                        args=(f"http://{host}:{port}",)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
