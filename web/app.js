import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const runtimeStatus = document.querySelector("#runtime-status");
const sourceList = document.querySelector("#source-list");
const sourceCount = document.querySelector("[data-testid='source-count']");
const modeLabel = document.querySelector("[data-testid='mode-label']");
const view2d = document.querySelector("#view-2d");
const view3d = document.querySelector("#view-3d");
const button2d = document.querySelector("#view-2d-button");
const button3d = document.querySelector("#view-3d-button");
const solverStatus = document.querySelector("[data-testid='solver-status']");
const potentialValue = document.querySelector("[data-testid='potential-value']");
const fieldVectorValue = document.querySelector("#field-vector-value");
const fieldMagnitudeValue = document.querySelector("[data-testid='field-magnitude-value']");
const contributionList = document.querySelector("#contribution-list");
const warningList = document.querySelector("#warning-list");
const probePosition = document.querySelector("[data-testid='probe-position']");
const probeInputs = {
  x: document.querySelector("#probe-x"),
  y: document.querySelector("#probe-y"),
  z: document.querySelector("#probe-z"),
};

const state = {
  mode: "2D",
  quality: "preview",
  pointIndex: 0,
  ringIndex: 0,
  scene: {
    schema_version: 1,
    id: "browser-interaction-scene",
    title: "Browser interaction scene",
    sources: [],
  },
  probe: { x: 0.2, y: 0, z: 0.05 },
  lastResult: null,
};

let latestRequestId = "";
let requestSerial = 0;
let sceneGroup;
let camera;
let renderer;
let controls;

function formatNumber(value, digits = 3) {
  if (!Number.isFinite(value)) {
    return "n/a";
  }
  return value.toExponential ? value.toPrecision(digits) : String(value);
}

function formatFixed(value) {
  return Number(value).toFixed(3);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function sourceDefaults(kind) {
  if (kind === "point") {
    state.pointIndex += 1;
    return {
      id: `point-${state.pointIndex}`,
      kind: "point",
      label: `Point ${state.pointIndex}`,
      position: { x: -0.12, y: 0, z: 0, unit: "m" },
      charge_c: 1e-9,
    };
  }

  state.ringIndex += 1;
  return {
    id: `ring-${state.ringIndex}`,
    kind: "ring",
    label: `Ring ${state.ringIndex}`,
    position: { x: 0.12, y: 0, z: 0, unit: "m" },
    normal: { x: 0, y: 0, z: 1 },
    radius_m: 0.08,
    charge_c: 2e-9,
  };
}

function addSource(kind) {
  state.scene.sources.push(sourceDefaults(kind));
  renderAll();
  scheduleEvaluation();
}

function updateSource(sourceId, field, value) {
  const source = state.scene.sources.find((candidate) => candidate.id === sourceId);
  if (!source) {
    return;
  }

  if (field === "label") {
    source.label = value || source.id;
  } else if (field.startsWith("position.")) {
    source.position[field.split(".")[1]] = Number(value);
  } else if (field === "charge_c" || field === "radius_m") {
    source[field] = Number(value);
  }

  renderAll();
  scheduleEvaluation();
}

function setMode(mode) {
  state.mode = mode;
  button2d.classList.toggle("selected", mode === "2D");
  button2d.setAttribute("aria-pressed", mode === "2D" ? "true" : "false");
  button3d.classList.toggle("selected", mode === "3D");
  button3d.setAttribute("aria-pressed", mode === "3D" ? "true" : "false");
  modeLabel.textContent = mode;
  view2d.classList.toggle("hidden", mode !== "2D");
  view3d.classList.toggle("hidden", mode !== "3D");
  renderAll();
}

function setProbeFromInputs() {
  state.probe = {
    x: Number(probeInputs.x.value),
    y: Number(probeInputs.y.value),
    z: Number(probeInputs.z.value),
  };
  renderAll();
  scheduleEvaluation();
}

function sourceField(source, field, label, step = "0.01") {
  const value = field.startsWith("position.") ? source.position[field.split(".")[1]] : source[field];
  return `
    <label>${label}
      <input type="number" step="${step}" value="${value}" data-source-id="${source.id}" data-field="${field}">
    </label>
  `;
}

function renderSourceList() {
  sourceCount.textContent = `${state.scene.sources.length} source${
    state.scene.sources.length === 1 ? "" : "s"
  }`;

  if (state.scene.sources.length === 0) {
    sourceList.innerHTML = `
      <div class="empty-state">
        <p>No editable sources yet.</p>
        <span>Add a point charge or ring to start computing.</span>
      </div>
    `;
    return;
  }

  sourceList.innerHTML = state.scene.sources
    .map((source) => {
      const radiusControl =
        source.kind === "ring" ? sourceField(source, "radius_m", "Radius m", "0.01") : "";
      const label = escapeHtml(source.label);
      return `
        <article class="source-card" data-testid="source-card-${source.id}">
          <div class="source-card-heading">
            <strong>${label}</strong>
            <span>${source.kind}</span>
          </div>
          <label>Label
            <input type="text" value="${label}" data-source-id="${source.id}" data-field="label">
          </label>
          <div class="mini-grid">
            ${sourceField(source, "position.x", "x m")}
            ${sourceField(source, "position.y", "y m")}
            ${sourceField(source, "position.z", "z m")}
            ${sourceField(source, "charge_c", "Charge C", "1e-10")}
            ${radiusControl}
          </div>
        </article>
      `;
    })
    .join("");
}

function mapToViewport(x, y) {
  const scale = 820;
  return {
    x: 50 + x * scale,
    y: 50 - y * scale,
  };
}

function render2d() {
  const sourceMarkup = state.scene.sources
    .map((source) => {
      const point = mapToViewport(source.position.x, source.position.y);
      const label = escapeHtml(source.label);
      if (source.kind === "ring") {
        return `
          <g>
            <circle class="source-ring" cx="${point.x}" cy="${point.y}" r="${source.radius_m * 820}"></circle>
            <text x="${point.x + 9}" y="${point.y - 9}">${label}</text>
          </g>
        `;
      }
      return `
        <g>
          <circle class="source-point" cx="${point.x}" cy="${point.y}" r="7"></circle>
          <text x="${point.x + 9}" y="${point.y - 9}">${label}</text>
        </g>
      `;
    })
    .join("");
  const probe = mapToViewport(state.probe.x, state.probe.y);

  view2d.innerHTML = `
    <svg class="plane-svg" viewBox="0 0 100 100" role="img" aria-label="Top-down electrostatic scene">
      <defs>
        <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
          <path d="M 10 0 L 0 0 0 10" fill="none"></path>
        </pattern>
      </defs>
      <rect width="100" height="100" fill="url(#grid)"></rect>
      <line class="axis-line" x1="0" y1="50" x2="100" y2="50"></line>
      <line class="axis-line" x1="50" y1="0" x2="50" y2="100"></line>
      ${sourceMarkup}
      <g>
        <path class="probe-marker" d="M ${probe.x - 4} ${probe.y} L ${probe.x + 4} ${probe.y} M ${probe.x} ${probe.y - 4} L ${probe.x} ${probe.y + 4}"></path>
        <text x="${probe.x + 6}" y="${probe.y + 6}">Probe</text>
      </g>
    </svg>
  `;
}

function ensure3d() {
  if (renderer) {
    return;
  }
  const width = view3d.clientWidth || 640;
  const height = view3d.clientHeight || 520;
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(width, height);
  view3d.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x09151c);
  camera = new THREE.PerspectiveCamera(48, width / height, 0.01, 100);
  camera.position.set(0.45, 0.38, 0.42);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  scene.add(new THREE.GridHelper(0.8, 16, 0x305466, 0x223947));
  scene.add(new THREE.AxesHelper(0.28));
  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  sceneGroup = new THREE.Group();
  scene.add(sceneGroup);
  renderer.userData.scene = scene;
}

function render3d() {
  ensure3d();
  sceneGroup.clear();

  for (const source of state.scene.sources) {
    if (source.kind === "ring") {
      const geometry = new THREE.TorusGeometry(source.radius_m, 0.004, 10, 72);
      const material = new THREE.MeshBasicMaterial({ color: 0xf7ca6a });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(source.position.x, source.position.z, source.position.y);
      sceneGroup.add(mesh);
    } else {
      const geometry = new THREE.SphereGeometry(0.018, 24, 16);
      const material = new THREE.MeshBasicMaterial({ color: source.charge_c >= 0 ? 0x48c3c8 : 0xff758f });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(source.position.x, source.position.z, source.position.y);
      sceneGroup.add(mesh);
    }
  }

  const probeGeometry = new THREE.SphereGeometry(0.012, 16, 12);
  const probeMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const probeMesh = new THREE.Mesh(probeGeometry, probeMaterial);
  probeMesh.position.set(state.probe.x, state.probe.z, state.probe.y);
  sceneGroup.add(probeMesh);

  controls.update();
  renderer.render(renderer.userData.scene, camera);
}

function renderProbe() {
  probePosition.textContent =
    `Probe at (${formatFixed(state.probe.x)}, ${formatFixed(state.probe.y)}, ` +
    `${formatFixed(state.probe.z)}) m`;
}

function renderResult() {
  if (!state.lastResult) {
    return;
  }

  const sample = state.lastResult.samples[0];
  solverStatus.textContent = `Ready (${state.lastResult.request_id})`;
  potentialValue.textContent = `${formatNumber(sample.potential_v, 5)} V`;
  fieldVectorValue.textContent =
    `(${formatNumber(sample.field_v_per_m.x, 4)}, ` +
    `${formatNumber(sample.field_v_per_m.y, 4)}, ${formatNumber(sample.field_v_per_m.z, 4)}) V/m`;
  fieldMagnitudeValue.textContent = `${formatNumber(sample.field_magnitude_v_per_m, 5)} V/m`;
  contributionList.innerHTML = sample.contributions
    .map(
      (item) => `
        <li>
          <strong>${item.source_id}</strong>
          ${formatNumber(item.potential_v, 4)} V,
          |E| ${formatNumber(item.field_magnitude_v_per_m, 4)} V/m
        </li>
      `,
    )
    .join("");

  const warnings = [...state.lastResult.warnings, ...sample.warnings];
  warningList.innerHTML = warnings.length
    ? [...new Set(warnings)].map((warning) => `<li>${warning}</li>`).join("")
    : "<li>No warnings.</li>";
}

function renderAll() {
  renderSourceList();
  render2d();
  renderProbe();
  if (state.mode === "3D") {
    render3d();
  }
  renderResult();
}

async function evaluateProbe(requestId) {
  if (state.scene.sources.length === 0) {
    state.lastResult = null;
    solverStatus.textContent = "Waiting for sources";
    potentialValue.textContent = "Unavailable";
    fieldVectorValue.textContent = "Unavailable";
    fieldMagnitudeValue.textContent = "Unavailable";
    contributionList.innerHTML = "<li>No source contributions yet.</li>";
    warningList.innerHTML = "<li>No warnings.</li>";
    return;
  }

  solverStatus.textContent = `Computing (${requestId})`;
  const response = await fetch("/api/field/evaluate", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      request_id: requestId,
      scene: state.scene,
      sample_points: [state.probe],
      quality: state.quality,
    }),
  });
  if (!response.ok) {
    throw new Error(`Field evaluation failed: ${response.status}`);
  }

  const result = await response.json();
  if (result.request_id !== latestRequestId) {
    return;
  }
  state.lastResult = result;
  renderResult();
}

function scheduleEvaluation() {
  requestSerial += 1;
  latestRequestId = `ui-${requestSerial}`;
  const requestId = latestRequestId;
  window.setTimeout(() => {
    evaluateProbe(requestId).catch((error) => {
      if (requestId === latestRequestId) {
        solverStatus.textContent = error.message;
      }
    });
  }, 30);
}

async function initialiseShell() {
  const response = await fetch("/api/config", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Configuration request failed: ${response.status}`);
  }

  const config = await response.json();
  document.title = `${config.product.name} | ${config.product.module}`;
  runtimeStatus.textContent =
    `Local modules staged: Three.js ${config.runtime.three.version}. ` +
    "2D and 3D interaction active.";
}

document.querySelector("#add-point").addEventListener("click", () => addSource("point"));
document.querySelector("#add-ring").addEventListener("click", () => addSource("ring"));
button2d.addEventListener("click", () => setMode("2D"));
button3d.addEventListener("click", () => setMode("3D"));
document.querySelector("#probe-form").addEventListener("input", setProbeFromInputs);
document.querySelector("#probe-form").addEventListener("change", setProbeFromInputs);
sourceList.addEventListener("input", (event) => {
  const input = event.target;
  if (input instanceof HTMLInputElement) {
    updateSource(input.dataset.sourceId, input.dataset.field, input.value);
  }
});
sourceList.addEventListener("change", (event) => {
  const input = event.target;
  if (input instanceof HTMLInputElement) {
    updateSource(input.dataset.sourceId, input.dataset.field, input.value);
  }
});
window.addEventListener("resize", () => {
  if (!renderer) {
    return;
  }
  const width = view3d.clientWidth || 640;
  const height = view3d.clientHeight || 520;
  renderer.setSize(width, height);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  render3d();
});

renderAll();
initialiseShell().catch(() => {
  runtimeStatus.textContent =
    "Local runtime configuration unavailable. Simulation can still use cached UI state.";
});
