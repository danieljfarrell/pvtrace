import * as THREE from "three";
import { OrbitControls } from "/static/vendor/OrbitControls.js";
import { TransformControls } from "/static/vendor/TransformControls.js";

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
scene3.add(grid);

const geometryGroup = new THREE.Group();
const pathGroup = new THREE.Group();
scene3.add(geometryGroup, pathGroup);

// Translation gizmo for the selected node; writes back to the document
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

function renderScene(payload) {
  gizmo.detach();
  geometryGroup.clear();
  pickable.length = 0;
  for (const node of payload.nodes) {
    const geometry = buildGeometry(node);
    let mesh;
    if (node.root) {
      mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
        color: 0x39415a, wireframe: true, transparent: true, opacity: 0.12,
      }));
    } else {
      mesh = new THREE.Mesh(geometry, new THREE.MeshPhysicalMaterial({
        color: 0x8fb8ff, metalness: 0, roughness: 0.15,
        transmission: 0.7, transparent: true, opacity: 0.55, side: THREE.DoubleSide,
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
    mesh.userData = node;
    geometryGroup.add(mesh);
  }
  if (selectedName) selectByName(selectedName);
  for (const light of payload.lights) {
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(0.08, 16, 12),
      new THREE.MeshBasicMaterial({ color: 0xffd54a }),
    );
    marker.matrixAutoUpdate = false;
    marker.matrix.fromArray(light.matrix);
    geometryGroup.add(marker);
    const direction = new THREE.Vector3(
      light.matrix[8], light.matrix[9], light.matrix[10]);
    const origin = new THREE.Vector3(
      light.matrix[12], light.matrix[13], light.matrix[14]);
    geometryGroup.add(new THREE.ArrowHelper(direction, origin, 0.8, 0xffd54a, 0.2, 0.1));
  }
}

// ----------------------------------------------------------------------
// Selection, inspector and document patching

let selectedName = null;
const inspector = document.getElementById("inspector");
const inspectorFields = document.getElementById("inspector-fields");
const raycaster = new THREE.Raycaster();

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
  editor.value = payload.text;
  renderScene(payload.scene);
  if (reactive.checked) startRun();
  return true;
}

function meshByName(name) {
  return pickable.find((mesh) => mesh.userData.name === name) || null;
}

function selectByName(name) {
  for (const mesh of pickable) mesh.material.emissive.setHex(0x000000);
  const mesh = meshByName(name);
  if (!mesh) { deselect(); return; }
  selectedName = name;
  mesh.material.emissive.setHex(0x1a3f7a);
  gizmo.attach(mesh);
  buildInspector(mesh.userData);
  inspector.hidden = false;
}

function deselect() {
  selectedName = null;
  gizmo.detach();
  inspector.hidden = true;
  for (const mesh of pickable) mesh.material.emissive.setHex(0x000000);
}

function field(label, value, onCommit, step = 0.1) {
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
    input.step = step;
    input.value = Number(v.toFixed ? v.toFixed(4) : v);
    input.addEventListener("change", () => {
      onCommit(inputs.map((i) => parseFloat(i.value) || 0));
    });
    inputs.push(input);
    row.appendChild(input);
  }
  inspectorFields.appendChild(row);
}

function buildInspector(node) {
  document.getElementById("inspector-name").textContent =
    `${node.name} · ${node.type}`;
  inspectorFields.innerHTML = "";
  const position = [node.matrix[12], node.matrix[13], node.matrix[14]];
  field("position", position, (v) =>
    patch({ op: "move", node: node.name, world_position: v }));

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
    0.01);
}

document.getElementById("inspector-close").addEventListener("click", deselect);
document.getElementById("add-recorder").addEventListener("click", () => {
  if (selectedName) patch({ op: "add-recorder", node: selectedName });
});
document.getElementById("delete-node").addEventListener("click", () => {
  if (!selectedName) return;
  const name = selectedName;
  deselect();
  patch({ op: "delete-node", node: name });
});

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
  if (hits.length) selectByName(hits[0].object.userData.name);
  else deselect();
});

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

function drawHeatmap(canvas, values, shape) {
  const [na, nb] = shape;
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(na, nb);
  const max = Math.max(1, ...values);
  for (let ia = 0; ia < na; ia++) {
    for (let ib = 0; ib < nb; ib++) {
      // image y axis points down; put ib (second property) up
      const pixel = ((nb - 1 - ib) * na + ia) * 4;
      const [r, g, b] = viridis(values[ia * nb + ib] / max);
      image.data[pixel] = r; image.data[pixel + 1] = g;
      image.data[pixel + 2] = b; image.data[pixel + 3] = 255;
    }
  }
  // draw at native resolution then scale up with nearest-neighbour
  const off = new OffscreenCanvas(na, nb);
  off.getContext("2d").putImageData(image, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(off, 0, 0, canvas.width, canvas.height);
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
        drawHeatmap(canvas, values, data.histograms[index].shape);
      } else {
        drawBars(canvas, hist.edges, values, hist.prop === "wavelength");
      }
    });
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
// Document editing

const editor = document.getElementById("editor");
const docStatus = document.getElementById("doc-status");
const statusEl = document.getElementById("status");
const reactive = document.getElementById("reactive");

async function loadDocument() {
  const response = await fetch("/api/document");
  const payload = await response.json();
  editor.value = payload.text;
  if (payload.text.trim()) applyDocument();
}

async function applyDocument() {
  const response = await fetch("/api/document", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: editor.value }),
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

document.getElementById("apply").addEventListener("click", applyDocument);

document.getElementById("save").addEventListener("click", async () => {
  if (!(await applyDocument())) return;
  const response = await fetch("/api/save", { method: "POST" });
  const payload = await response.json();
  docStatus.textContent = payload.error ? payload.error : "saved";
  docStatus.className = payload.error ? "err" : "";
});

let debounce = null;
editor.addEventListener("input", () => {
  if (!reactive.checked) return;
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

connect();
loadDocument();
