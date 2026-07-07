import * as THREE from "three";
import { OrbitControls } from "/static/vendor/OrbitControls.js";
import { TransformControls } from "/static/vendor/TransformControls.js";

// ----------------------------------------------------------------------
// View settings (client-side state, persisted locally; not part of the
// scene document)

const view = Object.assign(
  { opacity: 0.55, decades: 3, showWorld: false, showGrid: true,
    showDocument: true, hiddenOverlays: [] },
  JSON.parse(localStorage.getItem("pvtrace-view") || "{}"),
);

function saveView() {
  localStorage.setItem("pvtrace-view", JSON.stringify(view));
}

// ----------------------------------------------------------------------
// Wavelength (nm) to RGB, same approximation as
// pvtrace.light.utils.wavelength_to_rgb; the floor lifts colours so ray
// paths stay visible on a dark background (floor = 0 for saturated bins).

function wavelengthToColor(nm, floor = 0.15) {
  let r = 0, g = 0, b = 0;
  if (nm < 380) nm = 380;
  if (nm > 780) nm = 780;
  if (nm < 440) { r = -(nm - 440) / 60; b = 1; }
  else if (nm < 490) { g = (nm - 440) / 50; b = 1; }
  else if (nm < 510) { g = 1; b = -(nm - 510) / 20; }
  else if (nm < 580) { r = (nm - 510) / 70; g = 1; }
  else if (nm < 645) { r = 1; g = -(nm - 645) / 65; }
  else { r = 1; }
  return new THREE.Color(
    floor + (1 - floor) * r, floor + (1 - floor) * g, floor + (1 - floor) * b);
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

const pickable = [];
const recorderOverlays = {};
let overlayStacks = {};
let extrasByNode = {};
let rootMesh = null;
let lastScene = null;

// Keep edges, light arrows and recorder overlays attached to a node
// while the gizmo drags it (they are re-laid-out on the next render).
function syncNodeVisuals(name, source) {
  for (const extra of extrasByNode[name] || []) {
    extra.object.position.copy(source.position);
    if (extra.rotates) extra.object.quaternion.copy(source.quaternion);
  }
  for (const overlay of Object.values(recorderOverlays)) {
    if (overlay.mesh.userData.node === name) {
      overlay.mesh.position.copy(source.position);
      overlay.mesh.quaternion.copy(source.quaternion);
    }
  }
}

// Translation gizmo; writes back to the document on drop
const gizmo = new TransformControls(camera, renderer.domElement);
gizmo.setMode("translate");
let dragStart = null;
gizmo.addEventListener("dragging-changed", (event) => {
  controls.enabled = !event.value;
  if (event.value && gizmo.object) {
    dragStart = gizmo.object.position.clone();
  } else if (!event.value && gizmo.object && dragStart) {
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
// Real-time mode: re-run while dragging without refreshing the UI
let lastRealtime = 0;
gizmo.addEventListener("objectChange", async () => {
  if (!gizmo.object) return;
  syncNodeVisuals(gizmo.object.userData.name, gizmo.object);
  if (!document.getElementById("realtime").checked) return;
  const now = performance.now();
  if (now - lastRealtime < 150) return;
  lastRealtime = now;
  await fetch("/api/patch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      op: "move",
      node: gizmo.object.userData.name,
      world_position: gizmo.object.position.toArray(),
    }),
  });
  startRun();
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

const AXIS_INDEX = { x: 0, y: 1, z: 2 };

function buildRecorderOverlay(recorder, nodePayload) {
  // Facet recorders on boxes render as a clickable face overlay which
  // becomes a live heatmap texture during a run. The quad is built from
  // explicit node-local vertices so the axis mapping matches the
  // heatmap properties exactly.
  if (!recorder.facet || nodePayload.type !== "box") return null;
  const axis = recorder.facet.findIndex((v) => Math.abs(v) > 0.5);
  if (axis < 0) return null;
  const sign = Math.sign(recorder.facet[axis]);
  const size = nodePayload.params;

  const heatIndex = recorder.histograms.findIndex((h) => h.kind === "heatmap");
  let uAxis, vAxis;
  if (heatIndex >= 0) {
    const heat = recorder.histograms[heatIndex];
    uAxis = AXIS_INDEX[heat.prop_a];
    vAxis = AXIS_INDEX[heat.prop_b];
  }
  if (uAxis === undefined || vAxis === undefined
      || uAxis === axis || vAxis === axis) {
    [uAxis, vAxis] = [0, 1, 2].filter((i) => i !== axis);
  }

  const stackKey = `${recorder.node}:${axis}:${sign}`;
  overlayStacks[stackKey] = (overlayStacks[stackKey] || 0) + 1;
  const level = overlayStacks[stackKey];
  const normalOffset = sign * (size[axis] / 2 + 0.004 * level);

  const positions = [];
  const uvs = [];
  for (const [su, sv] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
    const point = [0, 0, 0];
    point[axis] = normalOffset;
    point[uAxis] = su * size[uAxis] / 2;
    point[vAxis] = sv * size[vAxis] / 2;
    positions.push(...point);
    uvs.push((su + 1) / 2, (sv + 1) / 2);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position",
    new THREE.BufferAttribute(new Float32Array(positions), 3));
  geometry.setAttribute("uv",
    new THREE.BufferAttribute(new Float32Array(uvs), 2));
  geometry.setIndex([0, 1, 2, 0, 2, 3]);
  geometry.computeVertexNormals();

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
  overlayStacks = {};
  extrasByNode = {};
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
      new THREE.Matrix4().fromArray(node.matrix)
        .decompose(edges.position, edges.quaternion, edges.scale);
      geometryGroup.add(edges);
      (extrasByNode[node.name] = extrasByNode[node.name] || [])
        .push({ object: edges, rotates: true });
      pickable.push(mesh);
    }
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
    const arrow = new THREE.ArrowHelper(direction, origin, 0.8, 0xffd54a, 0.2, 0.1);
    geometryGroup.add(arrow);
    (extrasByNode[light.name] = extrasByNode[light.name] || [])
      .push({ object: arrow, rotates: false });
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

  const datalist = document.getElementById("node-list");
  datalist.innerHTML = "";
  for (const node of payload.nodes) {
    if (node.root) continue;
    const option = document.createElement("option");
    option.value = node.name;
    datalist.appendChild(option);
  }

  applyLayer();
  renderInspector();
}

// ----------------------------------------------------------------------
// Information layers (weather-app style)

let isolateName = null;

function applyLayer() {
  const event = document.getElementById("layer-event").value;
  for (const overlay of Object.values(recorderOverlays)) {
    const recorder = overlay.mesh.userData;
    const hiddenByUser = view.hiddenOverlays.includes(recorder.name);
    const ghosted = isolateName && recorder.node !== isolateName;
    overlay.mesh.visible =
      !hiddenByUser && !ghosted && (event === "all" || recorder.event === event);
  }
  for (const mesh of pickable) {
    if (mesh.userData.kind !== "node") continue;
    const ghosted = isolateName && mesh.userData.name !== isolateName;
    mesh.material.opacity = ghosted ? 0.06 : view.opacity;
    for (const extra of extrasByNode[mesh.userData.name] || []) {
      if (extra.object.material) {
        extra.object.material.opacity = ghosted ? 0.08 : 0.6;
      }
    }
  }
}

document.getElementById("layer-event").addEventListener("change", applyLayer);
document.getElementById("isolate").addEventListener("input", (event) => {
  const value = event.target.value.trim();
  isolateName = (lastScene?.nodes || []).some((n) => n.name === value)
    ? value : null;
  applyLayer();
});

// ----------------------------------------------------------------------
// Selection: one model for the whole app. The inspector shows the
// selected item of the active segment; 3D clicks drive the same state.

const SEGMENTS = ["nodes", "components", "recorders", "view"];
let selected = { segment: "nodes", name: null };
let selectionOutline = null;

function spec() { return lastScene?.spec || {}; }

function itemsFor(segment) {
  if (segment === "nodes") return Object.keys(spec().nodes || {});
  if (segment === "components") return Object.keys(spec().components || {});
  if (segment === "recorders") {
    return (lastScene?.recorders || []).map((r) => r.name);
  }
  return [];
}

function select(segment, name) {
  selected = { segment, name };
  renderInspector();
  if (name && view.showDocument) {
    scrollEditorTo(name, segment === "nodes" ? "nodes"
      : segment === "components" ? "components" : "recorders");
  }
}

function syncViewportSelection() {
  for (const mesh of pickable) {
    if (mesh.material.emissive) mesh.material.emissive.setHex(0x000000);
  }
  if (selectionOutline) {
    scene3.remove(selectionOutline);
    selectionOutline = null;
  }
  gizmo.detach();
  if (!selected.name) return;
  if (selected.segment === "nodes") {
    const mesh = pickable.find((m) =>
      (m.userData.kind === "node" || m.userData.kind === "light")
      && m.userData.name === selected.name);
    if (mesh) {
      if (mesh.material.emissive) mesh.material.emissive.setHex(0x1a3f7a);
      gizmo.attach(mesh);
    }
  } else if (selected.segment === "recorders") {
    const overlay = recorderOverlays[selected.name];
    if (overlay) {
      const outlineGeometry = overlay.mesh.geometry.clone();
      outlineGeometry.setIndex(null);
      selectionOutline = new THREE.LineLoop(
        outlineGeometry,
        new THREE.LineBasicMaterial({ color: 0xffd54a }),
      );
      selectionOutline.position.copy(overlay.mesh.position);
      selectionOutline.quaternion.copy(overlay.mesh.quaternion);
      selectionOutline.renderOrder = 10;
      scene3.add(selectionOutline);
    }
  }
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
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(pickable, false);
  if (!hits.length) { select(selected.segment, selected.name ? null : selected.name); return; }
  const data = hits[0].object.userData;
  if (data.kind === "recorder") {
    // First click selects the owning node; a second click on the same
    // face drills into the recorder.
    const ownerSelected =
      (selected.segment === "nodes" && selected.name === data.node)
      || (selected.segment === "recorders" && selected.name === data.name);
    if (!ownerSelected) {
      const nodeHit = hits.find((h) => h.object.userData.kind === "node");
      select("nodes", nodeHit ? nodeHit.object.userData.name : data.node);
    } else if (selected.segment === "nodes") {
      select("recorders", data.name);
    } else {
      select("recorders", data.name);
    }
  } else {
    select("nodes", data.name);
  }
});

// ----------------------------------------------------------------------
// Inspector rendering

const itemSelect = document.getElementById("item-select");
const itemRow = document.getElementById("item-row");
const fieldsDiv = document.getElementById("inspector-fields");
const actionsDiv = document.getElementById("inspector-actions");
const binInfo = document.getElementById("bin-info");
let inspectorPlots = [];

for (const button of document.querySelectorAll("#segments button")) {
  button.addEventListener("click", () => {
    const segment = button.dataset.segment;
    const items = itemsFor(segment);
    const keep = items.includes(selected.name) ? selected.name : items[0] || null;
    select(segment, segment === "view" ? null : keep);
  });
}

itemSelect.addEventListener("change", () => {
  select(selected.segment, itemSelect.value || null);
});

document.getElementById("item-add").addEventListener("click", (event) => {
  if (selected.segment === "nodes") {
    popover(event.target, ["box", "sphere", "cylinder", "light"], (kind) =>
      patch({ op: "add-node", kind }));
  } else if (selected.segment === "components") {
    patch({ op: "add-component" });
  } else if (selected.segment === "recorders") {
    const nodes = Object.keys(spec().nodes || {}).filter((n) => {
      const s = spec().nodes[n];
      return s.box || s.sphere || s.cylinder;
    });
    popover(event.target, nodes, (node) =>
      patch({ op: "add-recorder", node }));
  }
});

function popover(anchor, options, onPick) {
  const existing = document.getElementById("popover");
  if (existing) existing.remove();
  const menu = document.createElement("div");
  menu.id = "popover";
  menu.style.cssText =
    "position:fixed;background:#232733;border:1px solid #2a2e3a;" +
    "border-radius:6px;z-index:50;min-width:120px;box-shadow:0 4px 16px #0008";
  const rect = anchor.getBoundingClientRect();
  menu.style.top = `${rect.bottom + 4}px`;
  menu.style.right = `${window.innerWidth - rect.right}px`;
  for (const option of options) {
    const item = document.createElement("button");
    item.textContent = option;
    item.style.cssText =
      "display:block;width:100%;text-align:left;background:none;border-radius:0";
    item.addEventListener("click", () => { menu.remove(); onPick(option); });
    menu.appendChild(item);
  }
  document.body.appendChild(menu);
  setTimeout(() => document.addEventListener("click",
    () => menu.remove(), { once: true }), 0);
}

function renderInspector() {
  for (const button of document.querySelectorAll("#segments button")) {
    button.classList.toggle("active", button.dataset.segment === selected.segment);
  }
  const items = itemsFor(selected.segment);
  itemRow.hidden = selected.segment === "view";
  itemSelect.innerHTML = "";
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item;
    option.textContent = item;
    option.selected = item === selected.name;
    itemSelect.appendChild(option);
  }
  if (selected.segment !== "view" && !items.includes(selected.name)) {
    selected.name = items[0] || null;
    if (selected.name) itemSelect.value = selected.name;
  }

  fieldsDiv.innerHTML = "";
  actionsDiv.innerHTML = "";
  inspectorPlots = [];
  if (selected.segment === "view") buildViewFields();
  else if (!selected.name) hint("Nothing here yet — use + to add one.");
  else if (selected.segment === "nodes") buildNodeFields(selected.name);
  else if (selected.segment === "components") buildComponentFields(selected.name);
  else buildRecorderFields(selected.name);

  syncViewportSelection();
}

// -- field helpers ------------------------------------------------------

function hint(text) {
  const div = document.createElement("div");
  div.className = "hint";
  div.textContent = text;
  fieldsDiv.appendChild(div);
  return div;
}

function numberField(label, value, onCommit, step = 0.1) {
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
    input.value = Number((+v).toFixed(6));
    input.addEventListener("change", () =>
      onCommit(inputs.map((i) => parseFloat(i.value) || 0)));
    inputs.push(input);
    row.appendChild(input);
  }
  fieldsDiv.appendChild(row);
}

function selectField(label, value, options, onCommit) {
  const row = document.createElement("div");
  row.className = "field";
  row.innerHTML = `<label>${label}</label>`;
  const selectEl = document.createElement("select");
  for (const option of options) {
    const el = document.createElement("option");
    el.value = option;
    el.textContent = option;
    el.selected = option === value;
    selectEl.appendChild(el);
  }
  selectEl.addEventListener("change", () => onCommit(selectEl.value));
  row.appendChild(selectEl);
  fieldsDiv.appendChild(row);
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
  fieldsDiv.appendChild(row);
}

function sliderField(label, value, min, max, step, title, onInput) {
  const row = document.createElement("div");
  row.className = "field";
  row.innerHTML = `<label>${label}</label>`;
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = min; slider.max = max; slider.step = step;
  slider.value = value;
  slider.title = title;
  slider.addEventListener("input", () => onInput(parseFloat(slider.value)));
  row.appendChild(slider);
  fieldsDiv.appendChild(row);
}

function actionButton(label, onClick, danger = false) {
  const button = document.createElement("button");
  button.textContent = label;
  if (danger) button.className = "danger";
  button.addEventListener("click", onClick);
  actionsDiv.appendChild(button);
}

// -- segment bodies -----------------------------------------------------

function buildViewFields() {
  sliderField("opacity", view.opacity, 0.05, 1, 0.05,
    "Geometry opacity, so ray paths inside objects stay visible",
    (value) => {
      view.opacity = value;
      saveView();
      for (const mesh of pickable) {
        if (mesh.userData.kind === "node") {
          mesh.material.depthWrite = value > 0.8;
        }
      }
      applyLayer();
    });
  sliderField("contrast", view.decades, 0.5, 6, 0.25,
    "Heatmap dynamic range in decades below the global maximum",
    (value) => {
      view.decades = value;
      saveView();
      refreshHeatmaps();
    });
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
  hint("Click an object or recorder face in the 3D view to inspect it.");
}

function geometryKey(nodeSpec) {
  for (const key of ["box", "sphere", "cylinder", "mesh"]) {
    if (nodeSpec[key]) return key;
  }
  return null;
}

function buildNodeFields(name) {
  const nodeSpec = (spec().nodes || {})[name] || {};
  const geometry = geometryKey(nodeSpec);
  const isWorld = name === "world";

  if (!isWorld) {
    const nodeNames = Object.keys(spec().nodes).filter((n) => n !== name);
    selectField("parent", nodeSpec.parent || "world", nodeNames, (value) =>
      patch({ op: "set", path: ["nodes", name, "parent"], value }));
    numberField("location", nodeSpec.location || [0, 0, 0], (v) =>
      patch({ op: "set", path: ["nodes", name, "location"], value: v }));
    if (nodeSpec.direction) {
      numberField("direction", nodeSpec.direction, (v) =>
        patch({ op: "set", path: ["nodes", name, "direction"], value: v }));
    }
  }

  if (geometry) {
    const geomSpec = nodeSpec[geometry];
    if (geometry === "box") {
      numberField("size", geomSpec.size, (v) =>
        patch({ op: "set", path: ["nodes", name, "box", "size"], value: v }));
    } else if (geometry === "sphere") {
      numberField("radius", geomSpec.radius, (v) =>
        patch({ op: "set", path: ["nodes", name, "sphere", "radius"], value: v[0] }));
    } else if (geometry === "cylinder") {
      numberField("length", geomSpec.length, (v) =>
        patch({ op: "set", path: ["nodes", name, "cylinder", "length"], value: v[0] }));
      numberField("radius", geomSpec.radius, (v) =>
        patch({ op: "set", path: ["nodes", name, "cylinder", "radius"], value: v[0] }));
    }
    const material = geomSpec.material || {};
    numberField("refr. index", material["refractive-index"] ?? 1.0, (v) =>
      patch({ op: "set",
              path: ["nodes", name, geometry, "material", "refractive-index"],
              value: v[0] }), 0.01);

    // Components attached to this node's material
    const attached = material.components || [];
    const available = Object.keys(spec().components || {})
      .filter((c) => !attached.includes(c));
    const chips = document.createElement("div");
    chips.className = "chips";
    for (const component of attached) {
      const chip = document.createElement("span");
      chip.innerHTML = `${component}<b title="Detach">×</b>`;
      chip.querySelector("b").addEventListener("click", () =>
        patch({ op: "set",
                path: ["nodes", name, geometry, "material", "components"],
                value: attached.filter((c) => c !== component) }));
      chips.appendChild(chip);
    }
    hint("components");
    fieldsDiv.appendChild(chips);
    if (available.length) {
      selectField("attach", "", ["", ...available], (value) => {
        if (value) {
          patch({ op: "set",
                  path: ["nodes", name, geometry, "material", "components"],
                  value: [...attached, value] });
        }
      });
    }

    if (!isWorld) {
      toggleField("record", !!nodeSpec.record, (checked) =>
        patch({ op: "set", path: ["nodes", name, "record"], value: checked }));
    }
  }

  if (nodeSpec.light) {
    const lightSpec = nodeSpec.light;
    numberField("λ (nm)", lightSpec.wavelength ?? 555, (v) =>
      patch({ op: "set", path: ["nodes", name, "light", "wavelength"], value: v[0] }), 1);
    const cone = lightSpec.mask?.direction?.cone;
    if (cone && typeof cone["half-angle"] === "number") {
      numberField("cone (°)", cone["half-angle"], (v) =>
        patch({ op: "set",
                path: ["nodes", name, "light", "mask", "direction", "cone", "half-angle"],
                value: v[0] }), 1);
    }
  }

  // Recorders on this node link into the recorders segment
  const onNode = (lastScene?.recorders || []).filter((r) => r.node === name);
  if (onNode.length) {
    hint("recorders");
    const chips = document.createElement("div");
    chips.className = "chips";
    for (const recorder of onNode) {
      const chip = document.createElement("span");
      chip.textContent = recorder.name;
      chip.style.cursor = "pointer";
      chip.addEventListener("click", () => select("recorders", recorder.name));
      chips.appendChild(chip);
    }
    fieldsDiv.appendChild(chips);
  }

  if (!isWorld) {
    actionButton("delete", () => {
      select("nodes", null);
      patch({ op: "delete-node", node: name });
    }, true);
  }
}

function buildComponentFields(name) {
  const componentSpec = (spec().components || {})[name] || {};
  const type = Object.keys(componentSpec)[0];
  if (!type) { hint("Empty component."); return; }
  const body = componentSpec[type];
  hint(`type: ${type}`);

  if (typeof body.coefficient === "number") {
    numberField("coefficient", body.coefficient, (v) =>
      patch({ op: "set", path: ["components", name, type, "coefficient"], value: v[0] }),
      0.01);
  }
  if (type === "luminophore") {
    const absorption = body.absorption || {};
    if (typeof absorption.coefficient === "number") {
      numberField("abs. coeff", absorption.coefficient, (v) =>
        patch({ op: "set",
                path: ["components", name, "luminophore", "absorption", "coefficient"],
                value: v[0] }), 0.1);
    }
    const emission = body.emission || {};
    if (typeof emission["quantum-yield"] === "number") {
      numberField("q. yield", emission["quantum-yield"], (v) =>
        patch({ op: "set",
                path: ["components", name, "luminophore", "emission", "quantum-yield"],
                value: v[0] }), 0.01);
    }
  }
  hint("Spectra and advanced options are edited in the document.");

  // Which nodes use it
  const users = Object.entries(spec().nodes || {}).filter(([, s]) => {
    const geometry = geometryKey(s);
    return geometry
      && ((s[geometry].material || {}).components || []).includes(name);
  }).map(([n]) => n);
  if (users.length) hint(`used by: ${users.join(", ")}`);

  actionButton("delete", () => {
    select("components", null);
    patch({ op: "delete-component", component: name });
  }, true);
}

function buildRecorderFields(name) {
  const recorder = (lastScene?.recorders || []).find((r) => r.name === name);
  if (!recorder) { hint("Unknown recorder."); return; }
  if (recorder.auto) hint("automatic — from record: true on its node");

  selectField("event", recorder.event,
    ["entering", "escaping", "reflected", "lost", "reacted", "killed", "exit"],
    async (value) => {
      if (await patch({ op: "update-recorder", recorder: name,
                        changes: { event: value } })) {
        startRun();
      }
    });
  if (recorder.facet) {
    numberField("facet", recorder.facet, async (v) => {
      if (await patch({ op: "update-recorder", recorder: name,
                        changes: { facet: v } })) {
        startRun();
      }
    }, 1);
  }
  const overlay = recorderOverlays[name];
  if (overlay) {
    toggleField("on face", !view.hiddenOverlays.includes(name), (checked) => {
      view.hiddenOverlays = view.hiddenOverlays.filter((n) => n !== name);
      if (!checked) view.hiddenOverlays.push(name);
      saveView();
      applyLayer();
    });
  }

  buildRecorderPlots(recorder);

  actionButton("owner: " + recorder.node, () => select("nodes", recorder.node));
  if (!recorder.auto) {
    actionButton("delete", () => {
      select("recorders", null);
      patch({ op: "delete-recorder", recorder: name });
    }, true);
  }
}

function buildRecorderPlots(recorder) {
  const meta = histogramMeta[recorder.name];
  const stats = latest[recorder.name];
  const statsHint = hint("");
  if (!meta || !stats) {
    statsHint.textContent = "run the simulation to collect statistics";
    return;
  }
  statsHint.textContent =
    `${stats.rays.toLocaleString()} rays · ${stats.crossings.toLocaleString()} crossings`
    + ` · ⟨λ⟩ ${stats.mean_wavelength.toFixed(1)} nm`
    + ` · ⟨θ⟩ ${(stats.mean_angle * 180 / Math.PI).toFixed(1)}°`;

  meta.histograms.forEach((histMeta, index) => {
    const label = document.createElement("div");
    label.className = "hint";
    const canvas = document.createElement("canvas");
    canvas.width = 300;
    if (histMeta.kind === "heatmap") {
      label.textContent = `${histMeta.prop_a} × ${histMeta.prop_b}`;
      const spanA = histMeta.edges_a[histMeta.edges_a.length - 1] - histMeta.edges_a[0];
      const spanB = histMeta.edges_b[histMeta.edges_b.length - 1] - histMeta.edges_b[0];
      canvas.height = Math.round(
        Math.min(300, Math.max(28, 300 * Math.abs(spanB / spanA))));
    } else if (histMeta.prop === "angle") {
      label.textContent = "angular distribution (normal up)";
      canvas.height = 130;
    } else {
      label.textContent = histMeta.prop;
      canvas.height = 100;
    }
    canvas.addEventListener("mousemove", (event) =>
      inspectBin(event, recorder.name, index));
    canvas.addEventListener("mouseleave", () => { binInfo.hidden = true; });
    fieldsDiv.append(label, canvas);
    inspectorPlots.push({ canvas, name: recorder.name, index });
  });
  drawInspectorPlots();
}

function drawInspectorPlots() {
  for (const plot of inspectorPlots) {
    const meta = histogramMeta[plot.name];
    const data = latest[plot.name];
    if (!meta || !data) continue;
    const histMeta = meta.histograms[plot.index];
    const values = data.histograms[plot.index].values;
    if (histMeta.kind === "heatmap") {
      drawHeatmapInto(plot.canvas.getContext("2d"),
        plot.canvas.width, plot.canvas.height,
        values, data.histograms[plot.index].shape);
    } else if (histMeta.prop === "angle") {
      drawPolar(plot.canvas, histMeta.edges, values);
    } else {
      drawBars(plot.canvas, histMeta.edges, values,
        histMeta.prop === "wavelength");
    }
  }
}

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
// Plot drawing

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
      ctx.fillStyle = "#" + wavelengthToColor(nm, 0).getHexString();
    } else {
      ctx.fillStyle = "#6ea8fe";
    }
    ctx.fillRect(pad + i * bw, H - pad - h, Math.max(1, bw - 1), h);
  }
}

function drawPolar(canvas, edges, values) {
  // Half-polar plot: radius proportional to counts per unit solid
  // angle, so an isotropic distribution reads as a circular arc.
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H - 8, R = Math.min(W / 2, H) - 12;
  ctx.clearRect(0, 0, W, H);
  ctx.strokeStyle = "#2a2e3a";
  ctx.beginPath();
  ctx.arc(cx, cy, R, Math.PI, 2 * Math.PI);
  ctx.moveTo(cx - R, cy); ctx.lineTo(cx + R, cy);
  ctx.stroke();

  const density = values.map((v, i) => {
    const mid = (edges[i] + edges[i + 1]) / 2;
    return v / Math.max(Math.sin(mid), 0.05);
  });
  const max = Math.max(1e-9, ...density);
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  for (let side = -1; side <= 1; side += 2) {
    const start = side === -1 ? density.length - 1 : 0;
    const end = side === -1 ? -1 : density.length;
    for (let i = start; i !== end; i += side) {
      const mid = (edges[i] + edges[i + 1]) / 2;
      const r = (density[i] / max) * R;
      ctx.lineTo(cx + side * r * Math.sin(mid), cy - r * Math.cos(mid));
    }
  }
  ctx.closePath();
  ctx.fillStyle = "#6ea8fe55";
  ctx.strokeStyle = "#6ea8fe";
  ctx.fill();
  ctx.stroke();
}

// All heatmaps share one colour scale so intensity is comparable
// between surfaces: log-scaled over `view.decades` below the global
// maximum of the current run.
let heatmapMax = 1;

function heatmapT(value) {
  if (value <= 0) return 0;
  return Math.min(1, Math.max(0,
    1 + Math.log10(value / heatmapMax) / (view.decades || 3)));
}

function drawHeatmapInto(ctx, width, height, values, shape) {
  const [na, nb] = shape;
  const image = new ImageData(na, nb);
  for (let ia = 0; ia < na; ia++) {
    for (let ib = 0; ib < nb; ib++) {
      const pixel = ((nb - 1 - ib) * na + ia) * 4;
      const [r, g, b] = viridis(heatmapT(values[ia * nb + ib]));
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

let histogramMeta = {};
let latest = {};

function refreshHeatmaps() {
  heatmapMax = 1;
  for (const data of Object.values(latest)) {
    for (const entry of data.histograms) {
      if (!entry.shape) continue;
      for (const value of entry.values) {
        if (value > heatmapMax) heatmapMax = value;
      }
    }
  }
  for (const [name, data] of Object.entries(latest)) {
    const overlay = recorderOverlays[name];
    if (overlay && overlay.heatIndex >= 0 && data.histograms[overlay.heatIndex]) {
      const entry = data.histograms[overlay.heatIndex];
      drawHeatmapInto(overlay.canvas.getContext("2d"), 256, 256,
        entry.values, entry.shape);
      overlay.texture.needsUpdate = true;
    }
  }
  drawInspectorPlots();
}

function inspectBin(event, name, index) {
  const info = histogramMeta[name];
  const data = latest[name];
  if (!info || !data) return;
  const hist = info.histograms[index];
  if (hist.prop === "angle") return; // polar plot: no bin readout yet
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
    if (/^\S/.test(lines[i])) break;
    if (pattern.test(lines[i])) {
      cm.scrollIntoView({ line: i, ch: 0 }, 80);
      cm.addLineClass(i, "background", "cm-flash");
      setTimeout(() => cm.removeLineClass(i, "background", "cm-flash"), 1200);
      return;
    }
  }
}

const docToggle = document.getElementById("doc-toggle");

function applyDocumentVisibility() {
  document.querySelector("main").classList.toggle("no-document", !view.showDocument);
  docToggle.classList.toggle("active", view.showDocument);
  if (view.showDocument) cm.refresh();
}

docToggle.addEventListener("click", () => {
  view.showDocument = !view.showDocument;
  saveView();
  applyDocumentVisibility();
});

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
    statusEl.textContent = payload.error;
    statusEl.className = "err";
    return false;
  }
  docStatus.textContent = "scene ok";
  docStatus.className = "";
  statusEl.textContent = "connected";
  statusEl.className = "ok";
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

// Drop a CSV (e.g. absorption data) onto the editor to save it next to
// the scene file, then reference it with `spectrum: file: <name>`.
const editorPane = document.getElementById("editor-pane");
editorPane.addEventListener("dragover", (event) => event.preventDefault());
editorPane.addEventListener("drop", async (event) => {
  event.preventDefault();
  const file = event.dataTransfer.files[0];
  if (!file) return;
  const content = await file.text();
  const response = await fetch("/api/upload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: file.name, content }),
  });
  const payload = await response.json();
  docStatus.textContent = payload.error ? payload.error
    : `saved ${payload.saved} — reference it with "spectrum: file: ${payload.saved}"`;
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
      latest = {};
      clearPaths();
      progressFill.style.width = "0%";
      if (selected.segment === "recorders") renderInspector();
    } else if (message.type === "bundle") {
      progressFill.style.width = `${(100 * message.traced / message.total).toFixed(1)}%`;
      runStatus.textContent =
        `${(message.rays_per_second / 1e6).toFixed(2)} M rays/s`;
      const hadData = Object.keys(latest).length > 0;
      latest = message.recorders;
      refreshHeatmaps();
      if (!hadData && selected.segment === "recorders") renderInspector();
      addPaths(message.paths);
    } else if (message.type === "done") {
      progressFill.style.width = "100%";
      runStatus.textContent += " · done";
      if (selected.segment === "recorders") renderInspector();
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

applyDocumentVisibility();
renderInspector();
connect();
loadDocument();
