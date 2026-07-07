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
from pvtrace.engine.recorder import Heatmap

STATIC = Path(__file__).resolve().parent / "static"

GEOM_NAMES = {0: "box", 1: "sphere", 2: "cylinder"}


class Studio:
    """Holds the current document and its parsed scene."""

    def __init__(self, document=""):
        self.document = document
        self.scene = None
        self.spec = None

    def apply(self, text):
        """Validate and parse a new document; returns the scene payload."""
        spec = yaml.safe_load(io.StringIO(text))
        if not isinstance(spec, dict):
            raise ValueError("Document is not a YAML mapping.")

        # parse() validates against the JSON schema and reads from disk
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yml", delete=False, dir=os.getcwd()
        ) as fp:
            fp.write(text)
            path = fp.name
        try:
            scene = parse_scene_file(path)
        finally:
            os.unlink(path)

        compiled = engine.compile_scene(scene)  # raises if unsupported

        self.document = text
        self.scene = scene
        self.spec = spec
        return self.scene_payload(compiled)

    def scene_payload(self, compiled):
        """Geometry description for the three.js viewport."""
        from anytree import PreOrderIter

        node_specs = self.spec.get("nodes", {}) if self.spec else {}
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
                    "refractive_index": float(compiled.refractive_index[i]),
                    "spec": node_specs.get(name, {}),
                }
            )
        lights = []
        for node in PreOrderIter(self.scene.root):
            if node.light is not None:
                matrix = np.asarray(node.transformation_to(self.scene.root))
                lights.append({"name": node.name,
                               "matrix": matrix.T.ravel().tolist(),
                               "spec": node_specs.get(node.name, {})})
        recorders = []
        for node in PreOrderIter(self.scene.root):
            for recorder in getattr(node, "recorders", []):
                histograms = []
                for hist in recorder.histograms:
                    if isinstance(hist, Heatmap):
                        histograms.append({
                            "kind": "heatmap",
                            "prop_a": hist.a.prop, "prop_b": hist.b.prop,
                            "range_a": [hist.a.start, hist.a.stop, hist.a.bins],
                            "range_b": [hist.b.start, hist.b.stop, hist.b.bins],
                        })
                    else:
                        histograms.append({
                            "kind": "hist", "prop": hist.prop,
                            "range": [hist.start, hist.stop, hist.bins],
                        })
                recorders.append({
                    "name": recorder.name,
                    "node": node.name,
                    "event": recorder.event,
                    "facet": list(recorder.facet) if recorder.facet else None,
                    "histograms": histograms,
                })
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

    @app.post("/api/upload")
    async def upload_file(payload: dict):
        """Save a data file (e.g. an absorption spectrum CSV) next to the
        scene document so the YAML can reference it by name."""
        if not document_path:
            return JSONResponse({"error": "No file was opened."}, status_code=422)
        name = os.path.basename(payload["name"])
        if not name or not name.lower().endswith((".csv", ".txt")):
            return JSONResponse({"error": "Only .csv or .txt files."},
                                status_code=422)
        target = Path(document_path).parent / name
        target.write_text(payload["content"])
        return {"saved": name}

    @app.post("/api/save")
    async def save_document():
        if not document_path:
            return JSONResponse({"error": "No file was opened."}, status_code=422)
        Path(document_path).write_text(studio.document)
        return {"saved": str(document_path)}

    @app.post("/api/patch")
    async def patch_document(payload: dict):
        """Apply a structured edit to the document.

        GUI interactions edit the document through this endpoint so the
        YAML text remains the single source of truth; ruamel round-trips
        the document preserving formatting and comments.
        """
        try:
            text = _patch(studio, payload)
            scene = studio.apply(text)
        except Exception as exception:
            return JSONResponse({"error": str(exception)}, status_code=422)
        return {"scene": scene, "text": text}

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


# Node snippets inserted by the add-object toolbar
SNIPPETS = {
    "box": {"location": [0.0, 0.0, 0.0],
            "box": {"size": [1.0, 1.0, 1.0],
                    "material": {"refractive-index": 1.5}}},
    "sphere": {"location": [0.0, 0.0, 0.0],
               "sphere": {"radius": 0.5,
                          "material": {"refractive-index": 1.5}}},
    "cylinder": {"location": [0.0, 0.0, 0.0],
                 "cylinder": {"length": 1.0, "radius": 0.5,
                              "material": {"refractive-index": 1.5}}},
    "light": {"location": [0.0, 0.0, 2.0], "direction": [0.0, 0.0, -1.0],
              "light": {"wavelength": 555,
                        "mask": {"direction": {"cone": {"half-angle": 20}}}}},
}


def _round_trip_yaml():
    from ruamel.yaml import YAML

    ryaml = YAML()
    ryaml.preserve_quotes = True
    return ryaml


def _unique_name(existing, stem):
    index = 1
    while f"{stem}-{index}" in existing:
        index += 1
    return f"{stem}-{index}"


def _flow(value):
    """Lists render inline ([x, y, z]) like hand-written scene files."""
    from ruamel.yaml.comments import CommentedSeq

    if isinstance(value, list):
        seq = CommentedSeq(value)
        seq.fa.set_flow_style()
        return seq
    return value


def _patch(studio, payload):
    """Returns new document text for a structured edit; does not apply it."""
    ryaml = _round_trip_yaml()
    data = ryaml.load(io.StringIO(studio.document))
    operation = payload["op"]

    if operation == "set":
        target = data
        path = payload["path"]
        for key in path[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        target[path[-1]] = _flow(payload["value"])

    elif operation == "move":
        # World position from the viewport gizmo; location is relative
        # to the parent node, so convert through the scene graph.
        from anytree import PreOrderIter

        name = payload["node"]
        world = payload["world_position"]
        nodes = {node.name: node for node in PreOrderIter(studio.scene.root)}
        node = nodes[name]
        if node.parent is None:
            raise ValueError("Cannot move the root node.")
        local = studio.scene.root.point_to_node(tuple(world), node.parent)
        data["nodes"][name]["location"] = _flow(
            [round(float(v), 6) for v in local]
        )

    elif operation == "add-node":
        kind = payload["kind"]
        if kind not in SNIPPETS:
            raise ValueError(f"Unknown object kind {kind!r}")
        name = _unique_name(data.get("nodes", {}), kind)
        import copy

        data["nodes"][name] = copy.deepcopy(SNIPPETS[kind])

    elif operation == "add-recorder":
        node = payload["node"]
        if node not in data.get("nodes", {}):
            raise ValueError(f"Unknown node {node!r}")
        recorders = data.setdefault("recorders", {})
        name = _unique_name(recorders, f"{node}-escaping")
        recorders[name] = {
            "node": node,
            "event": "escaping",
            "histograms": {"wavelength": [400, 900, 80]},
        }

    elif operation == "add-face-recorders":
        # One escaping recorder with a position heatmap per box face
        node = payload["node"]
        node_spec = data.get("nodes", {}).get(node)
        if not node_spec or "box" not in node_spec:
            raise ValueError("Face recorders require a box node.")
        size = [float(v) for v in node_spec["box"]["size"]]
        half = [s / 2.0 for s in size]
        axes = "xyz"
        faces = [
            ("top", [0, 0, 1]), ("bottom", [0, 0, -1]),
            ("east", [1, 0, 0]), ("west", [-1, 0, 0]),
            ("north", [0, 1, 0]), ("south", [0, -1, 0]),
        ]
        recorders = data.setdefault("recorders", {})
        for label, facet in faces:
            name = f"{node}-{label}"
            if name in recorders:
                continue
            axis = [i for i, v in enumerate(facet) if v != 0][0]
            u_axis, v_axis = [i for i in range(3) if i != axis]
            bins_u = max(10, min(60, int(size[u_axis] * 10)))
            bins_v = max(10, min(60, int(size[v_axis] * 10)))
            recorders[name] = {
                "node": node,
                "event": "escaping",
                "facet": _flow(facet),
                "histograms": {
                    "position": _flow([
                        axes[u_axis], axes[v_axis],
                        _flow([-half[u_axis], half[u_axis], bins_u]),
                        _flow([-half[v_axis], half[v_axis], bins_v]),
                    ]),
                },
            }

    elif operation == "update-recorder":
        # Edits to auto recorders (from record: true) materialise them
        # into the document first, then apply the changes.
        name = payload["recorder"]
        recorders = data.setdefault("recorders", {})
        if name not in recorders:
            recorders[name] = _recorder_to_spec(studio, name)
        for key, value in payload["changes"].items():
            if key not in ("event", "facet", "atol"):
                raise ValueError(f"Cannot update recorder key {key!r}")
            recorders[name][key] = _flow(value) if isinstance(value, list) else value

    elif operation == "delete-recorder":
        recorders = data.setdefault("recorders", {})
        if payload["recorder"] in recorders:
            del recorders[payload["recorder"]]
        else:
            # Hide an auto recorder by materialising nothing: turn off
            # record: on its node is the way; report it clearly instead.
            raise ValueError(
                "This recorder comes from record: true on its node; "
                "set record: false to remove the automatic set."
            )

    elif operation == "delete-node":
        name = payload["node"]
        del data["nodes"][name]
        for rec_name in list((data.get("recorders") or {})):
            if data["recorders"][rec_name].get("node") == name:
                del data["recorders"][rec_name]

    else:
        raise ValueError(f"Unknown operation {operation!r}")

    buffer = io.StringIO()
    ryaml.dump(data, buffer)
    return buffer.getvalue()


def _recorder_to_spec(studio, name):
    """Serialise a live Recorder object back into a recorders entry."""
    from anytree import PreOrderIter

    for node in PreOrderIter(studio.scene.root):
        for recorder in getattr(node, "recorders", []):
            if recorder.name != name:
                continue
            histograms = {}
            for hist in recorder.histograms:
                if isinstance(hist, Heatmap):
                    histograms["position"] = _flow([
                        hist.a.prop, hist.b.prop,
                        _flow([hist.a.start, hist.a.stop, hist.a.bins]),
                        _flow([hist.b.start, hist.b.stop, hist.b.bins]),
                    ])
                else:
                    histograms[hist.prop] = _flow(
                        [hist.start, hist.stop, hist.bins])
            spec = {"node": node.name, "event": recorder.event}
            if recorder.facet is not None:
                spec["facet"] = _flow(list(recorder.facet))
            spec["histograms"] = histograms
            return spec
    raise ValueError(f"Unknown recorder {name!r}")


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
        meta[spec.name] = {
            "event": spec.event,
            "node": compiled.node_names[int(compiled.rec_node[r])],
            "histograms": entries,
        }
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
