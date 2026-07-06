import * as THREE from "three";
import { OrbitControls } from "/static/vendor/OrbitControls.js";
import { TransformControls } from "/static/vendor/TransformControls.js";

// ----------------------------------------------------------------------
// View settings (client-side state, persisted locally; not part of the
// scene document)

const view = Object.assign(
  { opacity: 0.55, showWorld: false, showGrid: true },
  JSON.parse(localStorage.getItem("pvtrace-view") || "{}"),
);

function saveView() {
  localStorage.setItem("pvtrace-view", JSON.stringify(view));
}

// ----------------------------------------------------------------------
// Wavelength (nm) to RGB, rough visible-spectrum approximation.

function wavelengthToColor(nm) {
  let r = 0, g = 0, b = 0;
  if (nm < 380) nm = 380;
  if (nm > 780) nm = 780;
  if (nm < 440) { r = -(nm - 440) / 60; b = 1; }
  else if (nm < 490) { g = (nm - 440) / 50; b = 1; }
  else if (nm < 510) { g = 1; b = -(nm - 510) / 20; }
  else if (nm < 580) { r = (nm - 510) / 70; g = 1; }
  else if (nm < 645) { r = 1; g = -(nm - 645) / 65; }
  else { r = 1; }
  return new THREE.Color(0.15 + 0.85 * r, 0.15 + 0.85 * g, 0.15 + 0.85 * b);
}

// ----------------------------------------------------------------------
// 3D viewport

const viewport = document.getElementById("viewport");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
viewport.appendChild(renderer.domElement);

const scene3 = new THREE.Scene();
scene3.background = new THREE.Color(0x14161c);
const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 500);
camera.position.set(6, -9, 5);
camera.up.set(0, 0, 1); // pvtrace scenes are z-up
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene3.add(new THREE.AmbientLight(0xffffff, 0.7));
const keyLight = new THREE.DirectionalLight(0xffffff, 1.2);
keyLight.position.set(5, -8, 10);
scene3.add(keyLight);
const grid = new THREE.GridHelper(20, 20, 0x2a2e3a, 0x20242e);
grid.rotation.x = Math.PI / 2;
grid.visible = view.showGrid;
scene3.add(grid);

const geometryGroup = new THREE.Group();
const pathGroup = new THREE.Group();
scene3.add(geometryGroup, pathGroup);

// Translation gizmo for the selected object; writes back to the document
const gizmo = new TransformControls(camera, renderer.domElement);
gizmo.setMode("translate");
let dragStart = null;
gizmo.addEventListener("dragging-changed", (event) => {
  controls.enabled = !event.value;
  if (event.value && gizmo.object) {
    dragStart = gizmo.object.position.clone();
  } else if (!event.value && gizmo.object && dragStart) {
    // Only write back if the object actually moved; a click that lands
    // on the gizmo must not dirty the document.
    if (gizmo.object.position.distanceTo(dragStart) > 1e-6) {
      patch({
        op: "move",
        node: gizmo.object.userData.name,
        world_position: gizmo.object.position.toArray(),
      });
    }
    dragStart = null;
  }
});
scene3.add(gizmo);

function resize() {
  const w = viewport.clientWidth, h = viewport.clientHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(viewport);

(function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene3, camera);
})();

function buildGeometry(node) {
  const [a, b, c] = node.params;
  if (node.type === "box") return new THREE.BoxGeometry(a, b, c);
  if (node.type === "sphere") return new THREE.SphereGeometry(a, 48, 32);
  // pvtrace cylinders are z-axis; three.js cylinders are y-axis
  const geometry = new THREE.CylinderGeometry(b, b, a, 48);
  geometry.rotateX(Math.PI / 2);
  return geometry;
}

const pickable = [];
const recorderOverlays = {};
let rootMesh = null;

// Rotations that turn a +z facing plane into a face overlay for an
// axis-aligned facet direction.
const FACET_ROTATIONS = {
  "1,0,0": [0, Math.PI / 2, 0],
  "-1,0,0": [0, -Math.PI / 2, 0],
  "0,1,0": [-Math.PI / 2, 0, 0],
  "0,-1,0": [Math.PI / 2, 0, 0],
  "0,0,1": [0, 0, 0],
  "0,0,-1": [Math.PI, 0, 0],
};

function buildRecorderOverlay(recorder, nodePayload) {
  // Facet recorders on boxes render as a clickable face overlay which
  // becomes a live heatmap texture during a run.
  if (!recorder.facet || nodePayload.type !== "box") return null;
  const key = recorder.facet.map((v) => Math.round(v)).join(",");
  const rotation = FACET_ROTATIONS[key];
  if (!rotation) return null;
  const axis = recorder.facet.findIndex((v) => Math.abs(v) > 0.5);
  const dims = nodePayload.params.filter((_, i) => i !== axis);
  const geometry = new THREE.PlaneGeometry(dims[0], dims[1]);
  geometry.rotateX(rotation[0]);
  geometry.rotateY(rotation[1]);
  geometry.rotateZ(rotation[2]);
  const offset = recorder.facet.map(
    (v, i) => v * (nodePayload.params[i] / 2 + 0.004));
  geometry.translate(offset[0], offset[1], offset[2]);

  const heatIndex = recorder.histograms.findIndex((h) => h.kind === "heatmap");
  let material, canvas = null, texture = null;
  if (heatIndex >= 0) {
    canvas = document.createElement("canvas");
    canvas.width = 256; canvas.height = 256;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#6ea8fe30";
    ctx.fillRect(0, 0, 256, 256);
    texture = new THREE.CanvasTexture(canvas);
    material = new THREE.MeshBasicMaterial({
      map: texture, transparent: true, opacity: 0.85,
      side: THREE.DoubleSide, depthWrite: false,
    });
  } else {
    material = new THREE.MeshBasicMaterial({
      color: 0x6ea8fe, transparent: true, opacity: 0.22,
      side: THREE.DoubleSide, depthWrite: false,
    });
  }
  const mesh = new THREE.Mesh(geometry, material);
  new THREE.Matrix4().fromArray(nodePayload.matrix)
    .decompose(mesh.position, mesh.quaternion, mesh.scale);
  mesh.userData = { kind: "recorder", ...recorder };
  recorderOverlays[recorder.name] = { mesh, canvas, texture, heatIndex };
  return mesh;
}

function renderScene(payload) {
  gizmo.detach();
  geometryGroup.clear();
  pickable.length = 0;
  Object.keys(recorderOverlays).forEach((k) => delete recorderOverlays[k]);
  rootMesh = null;
  lastScene = payload;

  for (const node of payload.nodes) {
    const geometry = buildGeometry(node);
    let mesh;
    if (node.root) {
      mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
        color: 0x39415a, wireframe: true, transparent: true, opacity: 0.12,
      }));
      mesh.visible = view.showWorld;
      rootMesh = mesh;
    } else {
      mesh = new THREE.Mesh(geometry, new THREE.MeshPhysicalMaterial({
        color: 0x8fb8ff, metalness: 0, roughness: 0.15,
        transmission: 0.7, transparent: true, opacity: view.opacity,
        side: THREE.DoubleSide, depthWrite: view.opacity > 0.8,
      }));
      const edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry),
        new THREE.LineBasicMaterial({ color: 0x9fb6e8, transparent: true, opacity: 0.6 }),
      );
      edges.matrixAutoUpdate = false;
      edges.matrix.fromArray(node.matrix);
      geometryGroup.add(edges);
      pickable.push(mesh);
    }
    // Decomposed transform (not a frozen matrix) so the gizmo can move it
    new THREE.Matrix4().fromArray(node.matrix)
      .decompose(mesh.position, mesh.quaternion, mesh.scale);
    mesh.userData = { kind: "node", ...node };
    geometryGroup.add(mesh);
  }

  for (const light of payload.lights) {
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 16, 12),
      new THREE.MeshBasicMaterial({ color: 0xffd54a }),
    );
    new THREE.Matrix4().fromArray(light.matrix)
      .decompose(marker.position, marker.quaternion, marker.scale);
    marker.userData = { kind: "light", ...light };
    pickable.push(marker);
    geometryGroup.add(marker);
    const direction = new THREE.Vector3(
      light.matrix[8], light.matrix[9], light.matrix[10]);
    const origin = new THREE.Vector3(
      light.matrix[12], light.matrix[13], light.matrix[14]);
    geometryGroup.add(new THREE.ArrowHelper(direction, origin, 0.8, 0xffd54a, 0.2, 0.1));
  }

  for (const recorder of payload.recorders) {
    const nodePayload = payload.nodes.find((n) => n.name === recorder.node);
    if (!nodePayload) continue;
    const overlay = buildRecorderOverlay(recorder, nodePayload);
    if (overlay) {
      pickable.push(overlay);
      geometryGroup.add(overlay);
    }
  }

  if (selected) reselect();
}

// ----------------------------------------------------------------------
// Selection and the context-aware inspector

let selected = null; // {kind, name}
let lastScene = null;
const inspectorName = document.getElementById("inspector-name");
const inspectorFields = document.getElementById("inspector-fields");
const inspectorActions = document.getElementById("inspector-actions");
const raycaster = new THREE.Raycaster();

function findPickable(kind, name) {
  return pickable.find(
    (mesh) => mesh.userData.kind === kind && mesh.userData.name === name) || null;
}

function select(kind, name) {
  selected = { kind, name };
  reselect();
  scrollEditorTo(name, kind === "recorder" ? "recorders" : "nodes");
}

function reselect() {
  for (const mesh of pickable) {
    if (mesh.material.emissive) mesh.material.emissive.setHex(0x000000);
  }
  gizmo.detach();
  if (!selected) { buildViewInspector(); return; }
  const mesh = findPickable(selected.kind, selected.name);
  if (!mesh) { selected = null; buildViewInspector(); return; }
  const data = mesh.userData;
  if (data.kind === "node") {
    mesh.material.emissive.setHex(0x1a3f7a);
    gizmo.attach(mesh);
    buildNodeInspector(data);
  } else if (data.kind === "light") {
    gizmo.attach(mesh);
    buildLightInspector(data);
  } else {
    buildRecorderInspector(data);
  }
}

function deselect() {
  selected = null;
  gizmo.detach();
  reselect();
}

function clearInspector(title) {
  inspectorName.textContent = title;
  inspectorFields.innerHTML = "";
  inspectorActions.innerHTML = "";
}

function field(label, value, onCommit, options = {}) {
  const row = document.createElement("div");
  row.className = "field";
  const labelEl = document.createElement("label");
  labelEl.textContent = label;
  row.appendChild(labelEl);
  const inputs = [];
  const values = Array.isArray(value) ? value : [value];
  for (const v of values) {
    const input = document.createElement("input");
    input.type = "number";
    input.step = options.step || 0.1;
    input.value = Number(v.toFixed ? v.toFixed(4) : v);
    input.addEventListener("change", () => {
      onCommit(inputs.map((i) => parseFloat(i.value) || 0));
    });
    inputs.push(input);
    row.appendChild(input);
  }
  inspectorFields.appendChild(row);
}

function toggleField(label, value, onChange) {
  const row = document.createElement("div");
  row.className = "field";
  row.innerHTML = `<label>${label}</label>`;
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = value;
  input.addEventListener("change", () => onChange(input.checked));
  row.appendChild(input);
  inspectorFields.appendChild(row);
}

function actionButton(label, onClick, danger = false) {
  const button = document.createElement("button");
  button.textContent = label;
  if (danger) button.className = "danger";
  button.addEventListener("click", onClick);
  inspectorActions.appendChild(button);
}

function buildViewInspector() {
  clearInspector("View");
  const row = document.createElement("div");
  row.className = "field";
  row.innerHTML = `<label>opacity</label>`;
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = "0.05"; slider.max = "1"; slider.step = "0.05";
  slider.value = view.opacity;
  slider.addEventListener("input", () => {
    view.opacity = parseFloat(slider.value);
    saveView();
    for (const mesh of pickable) {
      if (mesh.userData.kind === "node") {
        mesh.material.opacity = view.opacity;
        mesh.material.depthWrite = view.opacity > 0.8;
      }
    }
  });
  row.appendChild(slider);
  inspectorFields.appendChild(row);

  toggleField("world", view.showWorld, (checked) => {
    view.showWorld = checked;
    saveView();
    if (rootMesh) rootMesh.visible = checked;
  });
  toggleField("grid", view.showGrid, (checked) => {
    view.showGrid = checked;
    saveView();
    grid.visible = checked;
  });
  const hint = document.createElement("div");
  hint.className = "hint";
  hint.textContent = "Click an object, light or recorder face for its settings.";
  inspectorFields.appendChild(hint);
}

function buildNodeInspector(node) {
  clearInspector(`${node.name} · ${node.type}`);
  field("position", [node.matrix[12], node.matrix[13], node.matrix[14]],
    (v) => patch({ op: "move", node: node.name, world_position: v }));

  const base = ["nodes", node.name, node.type];
  if (node.type === "box") {
    field("size", node.params.slice(0, 3), (v) =>
      patch({ op: "set", path: [...base, "size"], value: v }));
  } else if (node.type === "sphere") {
    field("radius", node.params[0], (v) =>
      patch({ op: "set", path: [...base, "radius"], value: v[0] }));
  } else {
    field("length", node.params[0], (v) =>
      patch({ op: "set", path: [...base, "length"], value: v[0] }));
    field("radius", node.params[1], (v) =>
      patch({ op: "set", path: [...base, "radius"], value: v[0] }));
  }
  field("refr. index", node.refractive_index, (v) =>
    patch({ op: "set", path: [...base, "material", "refractive-index"], value: v[0] }),
    { step: 0.01 });

  // Recorders attached to this node
  const recorders = (lastScene?.recorders || []).filter((r) => r.node === node.name);
  if (recorders.length) {
    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent = "recorders";
    inspectorFields.appendChild(hint);
    for (const recorder of recorders) {
      const link = document.createElement("button");
      link.className = "rec-link";
      link.innerHTML = `${recorder.name} <span>· ${recorder.event}</span>`;
      link.addEventListener("click", () => select("recorder", recorder.name));
      inspectorFields.appendChild(link);
    }
  }

  actionButton("+ recorder", () =>
    patch({ op: "add-recorder", node: node.name }));
  actionButton("delete", () => {
    const name = node.name;
    deselect();
    patch({ op: "delete-node", node: name });
  }, true);
}

function buildLightInspector(light) {
  clearInspector(`${light.name} · light`);
  field("position", [light.matrix[12], light.matrix[13], light.matrix[14]],
    (v) => patch({ op: "move", node: light.name, world_position: v }));

  const spec = light.spec?.light || {};
  const wavelength = typeof spec.wavelength === "number" ? spec.wavelength : 555;
  field("λ (nm)", wavelength, (v) =>
    patch({ op: "set", path: ["nodes", light.name, "light", "wavelength"], value: v[0] }),
    { step: 1 });

  const cone = spec.mask?.direction?.cone;
  if (cone && typeof cone["half-angle"] === "number") {
    field("cone (°)", cone["half-angle"], (v) =>
      patch({
        op: "set",
        path: ["nodes", light.name, "light", "mask", "direction", "cone", "half-angle"],
        value: v[0],
      }), { step: 1 });
  }

  actionButton("delete", () => {
    const name = light.name;
    deselect();
    patch({ op: "delete-node", node: name });
  }, true);
}

function buildRecorderInspector(recorder) {
  clearInspector(`${recorder.name} · recorder`);
  const row = document.createElement("div");
  row.className = "field";
  row.innerHTML = `<label>event</label>`;
  const selectEl = document.createElement("select");
  for (const event of ["entering", "escaping", "reflected", "lost", "reacted", "killed", "exit"]) {
    const option = document.createElement("option");
    option.value = event;
    option.textContent = event;
    option.selected = event === recorder.event;
    selectEl.appendChild(option);
  }
  selectEl.addEventListener("change", () =>
    patch({ op: "set", path: ["recorders", recorder.name, "event"], value: selectEl.value }));
  row.appendChild(selectEl);
  inspectorFields.appendChild(row);

  if (recorder.facet) {
    field("facet", recorder.facet, (v) =>
      patch({ op: "set", path: ["recorders", recorder.name, "facet"], value: v }),
      { step: 1 });
  }
  const stats = latest[recorder.name];
  const hint = document.createElement("div");
  hint.className = "hint";
  hint.textContent = stats
    ? `${stats.rays.toLocaleString()} rays · ⟨λ⟩ ${stats.mean_wavelength.toFixed(1)} nm`
    : "run the simulation to collect statistics";
  inspectorFields.appendChild(hint);

  actionButton("owner: " + recorder.node, () => select("node", recorder.node));
}

document.getElementById("inspector-close").addEventListener("click", deselect);

for (const button of document.querySelectorAll("#toolbar button")) {
  button.addEventListener("click", () => patch({ op: "add-node", kind: button.dataset.add }));
}

// Click to pick (ignore drags used for orbiting)
let downAt = null;
renderer.domElement.addEventListener("pointerdown", (event) => {
  downAt = [event.clientX, event.clientY];
});
renderer.domElement.addEventListener("pointerup", (event) => {
  if (!downAt) return;
  const moved = Math.hypot(event.clientX - downAt[0], event.clientY - downAt[1]);
  downAt = null;
  if (moved > 4 || gizmo.dragging) return;
  const rect = renderer.domElement.getBoundingClientRect();
  const pointer = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1,
  );
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(pickable, false);
  if (hits.length) {
    const data = hits[0].object.userData;
    select(data.kind, data.name);
  } else {
    deselect();
  }
});

// ----------------------------------------------------------------------
// Ray paths

let pathCount = 0;
const MAX_PATH_LINES = 400;

function addPaths(paths) {
  for (const path of paths) {
    if (pathCount >= MAX_PATH_LINES) return;
    const points = path.points;
    if (points.length < 2) continue;
    const positions = new Float32Array(points.flat());
    const colors = new Float32Array(points.length * 3);
    for (let i = 0; i < points.length; i++) {
      const color = wavelengthToColor(path.wavelengths[i]);
      colors.set([color.r, color.g, color.b], i * 3);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({
      vertexColors: true, transparent: true, opacity: 0.55,
    }));
    pathGroup.add(line);
    pathCount++;
  }
}

function clearPaths() {
  pathGroup.clear();
  pathCount = 0;
}

// ----------------------------------------------------------------------
// Canvas plots

const VIRIDIS = [
  [68, 1, 84], [71, 44, 122], [59, 81, 139], [44, 113, 142], [33, 144, 141],
  [39, 173, 129], [92, 200, 99], [170, 220, 50], [253, 231, 37],
];

function viridis(t) {
  const x = Math.max(0, Math.min(0.9999, t)) * (VIRIDIS.length - 1);
  const i = Math.floor(x), f = x - i;
  const a = VIRIDIS[i], b = VIRIDIS[i + 1];
  return [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])];
}

function drawBars(canvas, edges, values, spectral) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height, pad = 2;
  ctx.clearRect(0, 0, W, H);
  const max = Math.max(1, ...values);
  const bw = (W - 2 * pad) / values.length;
  for (let i = 0; i < values.length; i++) {
    const h = (values[i] / max) * (H - 2 * pad);
    if (spectral) {
      const nm = (edges[i] + edges[i + 1]) / 2;
      ctx.fillStyle = "#" + wavelengthToColor(nm).getHexString();
    } else {
      ctx.fillStyle = "#6ea8fe";
    }
    ctx.fillRect(pad + i * bw, H - pad - h, Math.max(1, bw - 1), h);
  }
}

function drawHeatmapInto(ctx, width, height, values, shape) {
  const [na, nb] = shape;
  const image = new ImageData(na, nb);
  const max = Math.max(1, ...values);
  for (let ia = 0; ia < na; ia++) {
    for (let ib = 0; ib < nb; ib++) {
      const pixel = ((nb - 1 - ib) * na + ia) * 4;
      const [r, g, b] = viridis(values[ia * nb + ib] / max);
      image.data[pixel] = r; image.data[pixel + 1] = g;
      image.data[pixel + 2] = b; image.data[pixel + 3] = 255;
    }
  }
  const off = new OffscreenCanvas(na, nb);
  off.getContext("2d").putImageData(image, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, width, height);
  ctx.drawImage(off, 0, 0, width, height);
}

// ----------------------------------------------------------------------
// Recorder results panel

const recordersDiv = document.getElementById("recorders");
const binInfo = document.getElementById("bin-info");
let histogramMeta = {};
let latest = {};

function ensureCards(meta) {
  recordersDiv.innerHTML = "";
  for (const [name, info] of Object.entries(meta)) {
    const card = document.createElement("div");
    card.className = "recorder-card";
    card.innerHTML = `<h3>${name}</h3><div class="meta" id="meta-${cssId(name)}"></div>`;
    card.querySelector("h3").addEventListener("click", () => select("recorder", name));
    info.histograms.forEach((hist, index) => {
      const label = document.createElement("div");
      label.className = "plot-label";
      label.textContent = hist.kind === "heatmap"
        ? `${hist.prop_a} × ${hist.prop_b}` : hist.prop;
      const canvas = document.createElement("canvas");
      canvas.width = 320;
      canvas.height = hist.kind === "heatmap" ? 220 : 110;
      canvas.dataset.recorder = name;
      canvas.dataset.index = index;
      canvas.addEventListener("mousemove", (event) => inspectBin(event, name, index));
      canvas.addEventListener("mouseleave", () => { binInfo.hidden = true; });
      card.append(label, canvas);
    });
    recordersDiv.appendChild(card);
  }
}

function cssId(s) { return s.replace(/[^a-z0-9]/gi, "-"); }

function updateCards(recorders) {
  latest = recorders;
  for (const [name, data] of Object.entries(recorders)) {
    const meta = document.getElementById(`meta-${cssId(name)}`);
    if (meta) {
      meta.textContent =
        `${data.rays.toLocaleString()} rays · ${data.crossings.toLocaleString()} crossings` +
        ` · ⟨λ⟩ ${data.mean_wavelength.toFixed(1)} nm` +
        ` · ⟨θ⟩ ${(data.mean_angle * 180 / Math.PI).toFixed(1)}°`;
    }
    const info = histogramMeta[name];
    if (!info) continue;
    const canvases = recordersDiv.querySelectorAll(
      `canvas[data-recorder="${name}"]`);
    info.histograms.forEach((hist, index) => {
      const canvas = canvases[index];
      const values = data.histograms[index].values;
      if (hist.kind === "heatmap") {
        drawHeatmapInto(canvas.getContext("2d"), canvas.width, canvas.height,
          values, data.histograms[index].shape);
      } else {
        drawBars(canvas, hist.edges, values, hist.prop === "wavelength");
      }
    });

    // Live heatmap texture on the recorder's face in the viewport
    const overlay = recorderOverlays[name];
    if (overlay && overlay.heatIndex >= 0 && data.histograms[overlay.heatIndex]) {
      const entry = data.histograms[overlay.heatIndex];
      drawHeatmapInto(overlay.canvas.getContext("2d"), 256, 256,
        entry.values, entry.shape);
      overlay.texture.needsUpdate = true;
    }
  }
}

function inspectBin(event, name, index) {
  const info = histogramMeta[name];
  const data = latest[name];
  if (!info || !data) return;
  const hist = info.histograms[index];
  const values = data.histograms[index].values;
  const rect = event.target.getBoundingClientRect();
  const fx = (event.clientX - rect.left) / rect.width;
  let text;
  if (hist.kind === "heatmap") {
    const [na, nb] = data.histograms[index].shape;
    const fy = 1 - (event.clientY - rect.top) / rect.height;
    const ia = Math.min(na - 1, Math.floor(fx * na));
    const ib = Math.min(nb - 1, Math.floor(fy * nb));
    const count = values[ia * nb + ib];
    text = `<b>${name}</b> · ${hist.prop_a} ∈ [${hist.edges_a[ia].toFixed(2)}, ` +
      `${hist.edges_a[ia + 1].toFixed(2)}] · ${hist.prop_b} ∈ [${hist.edges_b[ib].toFixed(2)}, ` +
      `${hist.edges_b[ib + 1].toFixed(2)}] · <b>${count}</b> rays`;
  } else {
    const n = values.length;
    const i = Math.min(n - 1, Math.floor(fx * n));
    const count = values[i];
    const total = values.reduce((s, v) => s + v, 0) || 1;
    const err = Math.sqrt(count);
    text = `<b>${name}</b> · ${hist.prop} ∈ [${hist.edges[i].toFixed(1)}, ` +
      `${hist.edges[i + 1].toFixed(1)}] · <b>${count}</b> ± ${err.toFixed(0)} rays ` +
      `(${(100 * count / total).toFixed(1)}%)`;
  }
  binInfo.innerHTML = text;
  binInfo.hidden = false;
}

// ----------------------------------------------------------------------
// Document editing (CodeMirror)

const docStatus = document.getElementById("doc-status");
const statusEl = document.getElementById("status");
const reactive = document.getElementById("reactive");

const cm = window.CodeMirror.fromTextArea(document.getElementById("editor"), {
  mode: "yaml",
  theme: "material-darker",
  lineNumbers: true,
  tabSize: 2,
  indentWithTabs: false,
  lineWrapping: false,
});
let settingText = false;

function setDocumentText(text) {
  settingText = true;
  const scroll = cm.getScrollInfo();
  cm.setValue(text);
  cm.scrollTo(scroll.left, scroll.top);
  settingText = false;
}

function scrollEditorTo(name, section) {
  const lines = cm.getValue().split("\n");
  const sectionIndex = lines.findIndex((line) => line.startsWith(`${section}:`));
  if (sectionIndex < 0) return;
  const pattern = new RegExp(`^\\s{2}${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}:`);
  for (let i = sectionIndex + 1; i < lines.length; i++) {
    if (/^\S/.test(lines[i])) break; // left the section
    if (pattern.test(lines[i])) {
      cm.scrollIntoView({ line: i, ch: 0 }, 80);
      cm.addLineClass(i, "background", "cm-flash");
      setTimeout(() => cm.removeLineClass(i, "background", "cm-flash"), 1200);
      return;
    }
  }
}

async function loadDocument() {
  const response = await fetch("/api/document");
  const payload = await response.json();
  setDocumentText(payload.text);
  if (payload.text.trim()) applyDocument();
}

async function applyDocument() {
  const response = await fetch("/api/document", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: cm.getValue() }),
  });
  const payload = await response.json();
  if (payload.error) {
    docStatus.textContent = payload.error;
    docStatus.className = "err";
    return false;
  }
  docStatus.textContent = "scene ok";
  docStatus.className = "";
  renderScene(payload.scene);
  return true;
}

async function patch(operation) {
  const response = await fetch("/api/patch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(operation),
  });
  const payload = await response.json();
  if (payload.error) {
    docStatus.textContent = payload.error;
    docStatus.className = "err";
    return false;
  }
  docStatus.textContent = "scene ok";
  docStatus.className = "";
  setDocumentText(payload.text);
  renderScene(payload.scene);
  if (reactive.checked) startRun();
  return true;
}

document.getElementById("apply").addEventListener("click", applyDocument);

document.getElementById("save").addEventListener("click", async () => {
  if (!(await applyDocument())) return;
  const response = await fetch("/api/save", { method: "POST" });
  const payload = await response.json();
  docStatus.textContent = payload.error ? payload.error : "saved";
  docStatus.className = payload.error ? "err" : "";
});

let debounce = null;
cm.on("change", () => {
  if (settingText || !reactive.checked) return;
  clearTimeout(debounce);
  debounce = setTimeout(async () => {
    if (await applyDocument()) startRun();
  }, 700);
});

// ----------------------------------------------------------------------
// Run control over websocket

const runStatus = document.getElementById("run-status");
const progressFill = document.getElementById("progress-fill");
let socket = null;

function connect() {
  socket = new WebSocket(`ws://${location.host}/ws`);
  socket.onopen = () => { statusEl.textContent = "connected"; statusEl.className = "ok"; };
  socket.onclose = () => {
    statusEl.textContent = "disconnected"; statusEl.className = "err";
    setTimeout(connect, 1500);
  };
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "started") {
      histogramMeta = message.histograms;
      ensureCards(histogramMeta);
      clearPaths();
      progressFill.style.width = "0%";
    } else if (message.type === "bundle") {
      progressFill.style.width = `${(100 * message.traced / message.total).toFixed(1)}%`;
      runStatus.textContent =
        `${(message.rays_per_second / 1e6).toFixed(2)} M rays/s`;
      updateCards(message.recorders);
      addPaths(message.paths);
    } else if (message.type === "done") {
      progressFill.style.width = "100%";
      runStatus.textContent += " · done";
    } else if (message.type === "error") {
      docStatus.textContent = message.message;
      docStatus.className = "err";
    }
  };
}

function startRun() {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify({ cmd: "stop" }));
  socket.send(JSON.stringify({
    cmd: "run",
    rays: parseInt(document.getElementById("rays").value, 10) || 100000,
    record_every: parseInt(document.getElementById("record-every").value, 10) || 500,
  }));
}

document.getElementById("run").addEventListener("click", startRun);
document.getElementById("stop").addEventListener("click", () => {
  socket.send(JSON.stringify({ cmd: "stop" }));
});

buildViewInspector();
connect();
loadDocument();
