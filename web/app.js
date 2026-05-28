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
const overlayStatus = document.querySelector("[data-testid='overlay-status']");
const overlaySummary = document.querySelector("[data-testid='overlay-summary']");
const potentialValue = document.querySelector("[data-testid='potential-value']");
const fieldVectorValue = document.querySelector("#field-vector-value");
const fieldMagnitudeValue = document.querySelector("[data-testid='field-magnitude-value']");
const contributionList = document.querySelector("#contribution-list");
const warningList = document.querySelector("#warning-list");
const probePosition = document.querySelector("[data-testid='probe-position']");
const qualityValue = document.querySelector("[data-testid='quality-value']");
const qualitySelect = document.querySelector("#quality-select");
const presetSelect = document.querySelector("#preset-select");
const presetForm = document.querySelector("#preset-form");
const presetStatus = document.querySelector("[data-testid='preset-status']");
const probeInputs = {
  x: document.querySelector("#probe-x"),
  y: document.querySelector("#probe-y"),
  z: document.querySelector("#probe-z"),
};
const VIEWPORT_METERS_TO_UNITS = 180;
const OVERLAY_SAMPLE_AXIS = [-0.18, -0.09, 0, 0.09, 0.18];

const state = {
  mode: "2D",
  quality: "preview",
  sourceIndex: {
    point: 0,
    line_segment: 0,
    ring: 0,
    disk: 0,
    infinite_plane: 0,
    spherical_shell: 0,
  },
  scene: {
    schema_version: 1,
    id: "browser-interaction-scene",
    title: "Browser interaction scene",
    sources: [],
  },
  probe: { x: 0.2, y: 0.03, z: 0.05 },
  lastResult: null,
  overlayResult: null,
  overlaySamples: [],
};

const KIND_LABELS = {
  point: "点电荷",
  line_segment: "带电线段",
  ring: "带电圆环",
  disk: "带电圆盘",
  infinite_plane: "无限平面",
  spherical_shell: "球壳",
};

let latestProbeRequestId = "";
let latestOverlayRequestId = "";
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

function kindLabel(kind) {
  return KIND_LABELS[kind] ?? kind;
}

function sourceDefaults(kind) {
  state.sourceIndex[kind] += 1;
  const index = state.sourceIndex[kind];
  const idPrefix = kind.replaceAll("_", "-");
  const base = {
    id: `${idPrefix}-${index}`,
    kind,
    label: `${kindLabel(kind)} ${index}`,
    position: { x: 0, y: 0, z: 0, unit: "m" },
  };

  if (kind === "point") {
    return {
      ...base,
      label: `点电荷 ${index}`,
      position: { x: -0.16, y: 0, z: 0, unit: "m" },
      charge_c: 1e-9,
    };
  }
  if (kind === "line_segment") {
    return {
      ...base,
      label: `带电线段 ${index}`,
      position: { x: -0.08, y: 0.08, z: 0, unit: "m" },
      orientation: { x: 1, y: 0, z: 0 },
      length_m: 0.16,
      charge_c: 1.5e-9,
    };
  }
  if (kind === "ring") {
    return {
      ...base,
      label: `带电圆环 ${index}`,
      position: { x: 0.12, y: 0, z: 0, unit: "m" },
      normal: { x: 0, y: 0, z: 1 },
      radius_m: 0.08,
      charge_c: 2e-9,
    };
  }
  if (kind === "disk") {
    return {
      ...base,
      label: `带电圆盘 ${index}`,
      position: { x: 0, y: -0.11, z: 0, unit: "m" },
      normal: { x: 0, y: 0, z: 1 },
      radius_m: 0.09,
      charge_c: 2e-9,
    };
  }
  if (kind === "infinite_plane") {
    return {
      ...base,
      label: `无限平面 ${index}`,
      position: { x: 0.14, y: 0.11, z: 0, unit: "m" },
      normal: { x: 0, y: 0, z: 1 },
      display_extent_m: 0.24,
      surface_charge_density_c_per_m2: 2e-9,
      physical_model: "infinite",
    };
  }
  return {
    ...base,
    label: `球壳 ${index}`,
    position: { x: -0.14, y: -0.11, z: 0, unit: "m" },
    radius_m: 0.08,
    charge_c: 3e-9,
  };
}

function addSource(kind) {
  state.scene.sources.push(sourceDefaults(kind));
  renderAll();
  scheduleEvaluation();
}

function updateSource(sourceId, field, value) {
  const source = state.scene.sources.find((candidate) => candidate.id === sourceId);
  if (!source || !field) {
    return;
  }

  if (field === "label") {
    source.label = value || source.id;
  } else if (field.includes(".")) {
    const [group, key] = field.split(".");
    source[group][key] = Number(value);
  } else if (field !== "physical_model" && field !== "kind" && field !== "id") {
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

function setQuality(value) {
  state.quality = value;
  qualityValue.textContent = value;
  renderResult();
  scheduleEvaluation();
}

function nestedValue(source, field) {
  if (!field.includes(".")) {
    return source[field];
  }
  const [group, key] = field.split(".");
  return source[group][key];
}

function sourceField(source, field, label, step = "0.01") {
  const value = nestedValue(source, field);
  const accessibleLabel = `${source.id} ${label}`;
  return `
    <label>${label}
      <input
        aria-label="${escapeHtml(accessibleLabel)}"
        type="number"
        step="${step}"
        value="${value}"
        data-source-id="${source.id}"
        data-field="${field}"
      >
    </label>
  `;
}

function vectorFields(source, group, heading) {
  if (!source[group]) {
    return "";
  }
  return `
    <div class="vector-fieldset">
      <span>${heading}</span>
      <div class="mini-grid">
        ${sourceField(source, `${group}.x`, `${heading} x`)}
        ${sourceField(source, `${group}.y`, `${heading} y`)}
        ${sourceField(source, `${group}.z`, `${heading} z`)}
      </div>
    </div>
  `;
}

function scalarControls(source) {
  const controlsMarkup = [];
  if ("charge_c" in source && source.charge_c !== null) {
    controlsMarkup.push(sourceField(source, "charge_c", "电荷 C", "1e-10"));
  }
  if ("length_m" in source) {
    controlsMarkup.push(sourceField(source, "length_m", "长度 m", "0.01"));
  }
  if ("radius_m" in source) {
    controlsMarkup.push(sourceField(source, "radius_m", "半径 m", "0.01"));
  }
  if ("display_extent_m" in source) {
    controlsMarkup.push(sourceField(source, "display_extent_m", "显示范围 m", "0.01"));
  }
  if ("surface_charge_density_c_per_m2" in source) {
    controlsMarkup.push(
      sourceField(source, "surface_charge_density_c_per_m2", "面电荷密度 C/m^2", "1e-10"),
    );
  }
  return controlsMarkup.join("");
}

function renderSourceList() {
  sourceCount.textContent = `${state.scene.sources.length} 个源`;

  if (state.scene.sources.length === 0) {
    sourceList.innerHTML = `
      <div class="empty-state">
        <p>还没有可编辑的源。</p>
        <span>加入一个静电源，或加载一个预设场景开始探索。</span>
      </div>
    `;
    return;
  }

  sourceList.innerHTML = state.scene.sources
    .map((source) => {
      const label = escapeHtml(source.label);
      return `
        <article class="source-card" data-testid="source-card-${source.id}">
          <div class="source-card-heading">
            <strong>${label}</strong>
            <span>${KIND_LABELS[source.kind] ?? source.kind}</span>
          </div>
          <label>名称
            <input type="text" value="${label}" data-source-id="${source.id}" data-field="label">
          </label>
          <div class="mini-grid">
            ${sourceField(source, "position.x", "位置 x m")}
            ${sourceField(source, "position.y", "位置 y m")}
            ${sourceField(source, "position.z", "位置 z m")}
            ${scalarControls(source)}
          </div>
          ${vectorFields(source, "orientation", "方向")}
          ${vectorFields(source, "normal", "法向")}
        </article>
      `;
    })
    .join("");
}

function mapToViewport(x, y) {
  return {
    x: 50 + x * VIEWPORT_METERS_TO_UNITS,
    y: 50 - y * VIEWPORT_METERS_TO_UNITS,
  };
}

function physicsNormalToThreeComponents(normal) {
  const vector = { x: normal.x, y: normal.z, z: normal.y };
  const length = Math.hypot(vector.x, vector.y, vector.z);
  if (length === 0) {
    return { x: 0, y: 1, z: 0 };
  }
  return { x: vector.x / length, y: vector.y / length, z: vector.z / length };
}

function threeVectorFromComponents(components) {
  return new THREE.Vector3(components.x, components.y, components.z);
}

function formatThreeNormal(components) {
  return [components.x, components.y, components.z]
    .map((component) => (Math.abs(component) < 1e-9 ? 0 : component))
    .map((component) => Number(component.toFixed(6)).toString())
    .join(",");
}

function renderSource2d(source) {
  const point = mapToViewport(source.position.x, source.position.y);
  const label = escapeHtml(source.label);
  if (source.kind === "line_segment") {
    const halfLength = (source.length_m * VIEWPORT_METERS_TO_UNITS) / 2;
    const angle = Math.atan2(source.orientation.y, source.orientation.x);
    const dx = Math.cos(angle) * halfLength;
    const dy = Math.sin(angle) * halfLength;
    return `
      <g data-testid="source-line-segment-group-2d-${source.id}">
        <line
          class="source-line-segment"
          data-testid="source-line-segment-2d-${source.id}"
          x1="${point.x - dx}"
          y1="${point.y + dy}"
          x2="${point.x + dx}"
          y2="${point.y - dy}"
        ></line>
        <text x="${point.x + 9}" y="${point.y - 9}">${label}</text>
      </g>
    `;
  }
  if (source.kind === "ring" || source.kind === "disk" || source.kind === "spherical_shell") {
    const className = `source-${source.kind.replaceAll("_", "-")}`;
    return `
      <g data-testid="source-${source.kind.replaceAll("_", "-")}-group-2d-${source.id}">
        <circle
          class="${className}"
          data-testid="source-${source.kind.replaceAll("_", "-")}-2d-${source.id}"
          cx="${point.x}"
          cy="${point.y}"
          r="${source.radius_m * VIEWPORT_METERS_TO_UNITS}"
        ></circle>
        <text x="${point.x + 9}" y="${point.y - 9}">${label}</text>
      </g>
    `;
  }
  if (source.kind === "infinite_plane") {
    const extent = (source.display_extent_m * VIEWPORT_METERS_TO_UNITS) / 2;
    return `
      <g data-testid="source-infinite-plane-group-2d-${source.id}">
        <rect
          class="source-infinite-plane"
          data-testid="source-infinite-plane-2d-${source.id}"
          x="${point.x - extent}"
          y="${point.y - extent}"
          width="${extent * 2}"
          height="${extent * 2}"
        ></rect>
        <text x="${point.x + 9}" y="${point.y - 9}">${label}</text>
      </g>
    `;
  }
  return `
    <g data-testid="source-point-group-2d-${source.id}">
      <circle
        class="source-point"
        data-testid="source-point-2d-${source.id}"
        cx="${point.x}"
        cy="${point.y}"
        r="7"
      ></circle>
      <text x="${point.x + 9}" y="${point.y - 9}">${label}</text>
    </g>
  `;
}

function renderOverlay2d() {
  if (!state.overlayResult || state.overlaySamples.length === 0) {
    return '<g data-testid="overlay-vector-layer" data-vector-count="0"></g>';
  }
  const magnitudes = state.overlayResult.samples.map((sample) => sample.field_magnitude_v_per_m);
  const maxMagnitude = Math.max(...magnitudes, 1);
  const vectors = state.overlayResult.samples
    .map((sample, index) => {
      const point = mapToViewport(state.overlaySamples[index].x, state.overlaySamples[index].y);
      const field = sample.field_v_per_m;
      const xyMagnitude = Math.hypot(field.x, field.y);
      const scale = xyMagnitude > 0 ? Math.min(5.5, 1.5 + 4 * (xyMagnitude / maxMagnitude)) : 0;
      const dx = xyMagnitude > 0 ? (field.x / xyMagnitude) * scale : 0;
      const dy = xyMagnitude > 0 ? -(field.y / xyMagnitude) * scale : 0;
      return `
        <line
          class="field-vector"
          x1="${point.x}"
          y1="${point.y}"
          x2="${point.x + dx}"
          y2="${point.y + dy}"
        ></line>
      `;
    })
    .join("");
  return `
    <g
      class="overlay-vector-layer"
      data-testid="overlay-vector-layer"
      data-vector-count="${state.overlayResult.samples.length}"
    >
      ${vectors}
    </g>
  `;
}

function render2d() {
  const sourceMarkup = state.scene.sources.map(renderSource2d).join("");
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
      ${renderOverlay2d()}
      ${sourceMarkup}
      <g>
        <path
          class="probe-marker"
          data-testid="probe-marker-2d"
          data-view-x="${probe.x}"
          data-view-y="${probe.y}"
          d="M ${probe.x - 4} ${probe.y} L ${probe.x + 4} ${probe.y} M ${probe.x} ${probe.y - 4} L ${probe.x} ${probe.y + 4}"
        ></path>
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

function meshForSource(source) {
  if (source.kind === "ring") {
    const geometry = new THREE.TorusGeometry(source.radius_m, 0.004, 10, 72);
    const material = new THREE.MeshBasicMaterial({ color: 0xf7ca6a });
    const mesh = new THREE.Mesh(geometry, material);
    const threeNormal = threeVectorFromComponents(physicsNormalToThreeComponents(source.normal));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), threeNormal);
    return mesh;
  }
  if (source.kind === "line_segment") {
    const geometry = new THREE.CylinderGeometry(0.004, 0.004, source.length_m, 12);
    const material = new THREE.MeshBasicMaterial({ color: 0x8fd0ff });
    const mesh = new THREE.Mesh(geometry, material);
    const direction = threeVectorFromComponents(physicsNormalToThreeComponents(source.orientation));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
    return mesh;
  }
  if (source.kind === "disk" || source.kind === "infinite_plane") {
    const radius = source.kind === "disk" ? source.radius_m : source.display_extent_m * 0.5;
    const geometry = new THREE.CircleGeometry(radius, 72);
    const material = new THREE.MeshBasicMaterial({
      color: source.kind === "disk" ? 0x9fe870 : 0xa580ff,
      opacity: 0.45,
      side: THREE.DoubleSide,
      transparent: true,
    });
    const mesh = new THREE.Mesh(geometry, material);
    const threeNormal = threeVectorFromComponents(physicsNormalToThreeComponents(source.normal));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), threeNormal);
    return mesh;
  }
  const geometry = new THREE.SphereGeometry(
    source.kind === "spherical_shell" ? source.radius_m : 0.018,
    24,
    16,
  );
  const material = new THREE.MeshBasicMaterial({
    color: source.charge_c >= 0 ? 0x48c3c8 : 0xff758f,
    wireframe: source.kind === "spherical_shell",
  });
  return new THREE.Mesh(geometry, material);
}

function render3d() {
  view3d.removeAttribute("data-ring-normal-three");
  const firstRing = state.scene.sources.find((source) => source.kind === "ring");
  if (firstRing) {
    view3d.dataset.ringNormalThree = formatThreeNormal(
      physicsNormalToThreeComponents(firstRing.normal),
    );
  }

  ensure3d();
  sceneGroup.clear();

  for (const source of state.scene.sources) {
    const mesh = meshForSource(source);
    mesh.position.set(source.position.x, source.position.z, source.position.y);
    sceneGroup.add(mesh);
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
    `探针位置 (${formatFixed(state.probe.x)}, ${formatFixed(state.probe.y)}, ` +
    `${formatFixed(state.probe.z)}) m`;
}

function renderResult() {
  qualityValue.textContent = state.quality;
  if (!state.lastResult) {
    return;
  }

  const sample = state.lastResult.samples[0];
  solverStatus.textContent = `已完成 (${state.lastResult.request_id})`;
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
    ? [...new Set(warnings)].map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")
    : "<li>暂无提示。</li>";
}

function renderOverlaySummary() {
  if (!state.overlayResult) {
    return;
  }
  const magnitudes = state.overlayResult.samples.map((sample) => sample.field_magnitude_v_per_m);
  const minMagnitude = Math.min(...magnitudes);
  const maxMagnitude = Math.max(...magnitudes);
  overlayStatus.textContent = `已完成 (${state.overlayResult.request_id})`;
  overlaySummary.textContent =
    `二维箭头层采样 ${state.overlayResult.sample_count} 个点；` +
    `采样 |E| 范围 ${formatNumber(minMagnitude, 3)} 到 ${formatNumber(maxMagnitude, 3)} V/m。` +
    "这是离散采样摘要，不是场线或等势线提取。";
}

function renderAll() {
  renderSourceList();
  render2d();
  renderProbe();
  if (state.mode === "3D") {
    render3d();
  }
  renderResult();
  renderOverlaySummary();
}

function setEmptyComputationState() {
  state.lastResult = null;
  state.overlayResult = null;
  solverStatus.textContent = "等待源";
  overlayStatus.textContent = "等待源";
  potentialValue.textContent = "暂无";
  fieldVectorValue.textContent = "暂无";
  fieldMagnitudeValue.textContent = "暂无";
  contributionList.innerHTML = "<li>还没有源贡献。</li>";
  warningList.innerHTML = "<li>暂无提示。</li>";
  overlaySummary.textContent = "加入源后，二维视图会显示采样电场箭头。";
  render2d();
}

async function postFieldEvaluation(requestId, samplePoints) {
  const response = await fetch("/api/field/evaluate", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      request_id: requestId,
      scene: state.scene,
      sample_points: samplePoints,
      quality: state.quality,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`场计算失败：${response.status} ${detail}`);
  }
  return response.json();
}

async function evaluateProbe(requestId) {
  if (state.scene.sources.length === 0) {
    setEmptyComputationState();
    return;
  }

  solverStatus.textContent = `计算中 (${requestId})`;
  const result = await postFieldEvaluation(requestId, [state.probe]);
  if (result.request_id !== latestProbeRequestId) {
    return;
  }
  state.lastResult = result;
  renderResult();
}

function overlaySamplePoints() {
  const samples = [];
  for (const y of OVERLAY_SAMPLE_AXIS) {
    for (const x of OVERLAY_SAMPLE_AXIS) {
      samples.push({ x, y, z: state.probe.z, unit: "m" });
    }
  }
  return samples;
}

async function evaluateOverlay(requestId) {
  if (state.scene.sources.length === 0) {
    setEmptyComputationState();
    return;
  }

  overlayStatus.textContent = `采样中 (${requestId})`;
  const samples = overlaySamplePoints();
  const result = await postFieldEvaluation(requestId, samples);
  if (result.request_id !== latestOverlayRequestId) {
    return;
  }
  state.overlaySamples = samples;
  state.overlayResult = result;
  render2d();
  renderOverlaySummary();
}

function scheduleEvaluation() {
  requestSerial += 1;
  latestProbeRequestId = `ui-probe-${requestSerial}`;
  latestOverlayRequestId = `ui-overlay-${requestSerial}`;
  const probeRequestId = latestProbeRequestId;
  const overlayRequestId = latestOverlayRequestId;
  window.setTimeout(() => {
    evaluateProbe(probeRequestId).catch((error) => {
      if (probeRequestId === latestProbeRequestId) {
        solverStatus.textContent = error.message;
      }
    });
    evaluateOverlay(overlayRequestId).catch((error) => {
      if (overlayRequestId === latestOverlayRequestId) {
        overlayStatus.textContent = error.message;
      }
    });
  }, 30);
}

function refreshSourceIndexes() {
  for (const kind of Object.keys(state.sourceIndex)) {
    state.sourceIndex[kind] = state.scene.sources.filter((source) => source.kind === kind).length;
  }
}

async function loadPresetOptions() {
  const response = await fetch("/api/presets", { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`预设列表读取失败：${response.status}`);
  }
  const presets = await response.json();
  presetSelect.innerHTML = presets
    .map((preset) => `<option value="${preset.id}">${escapeHtml(preset.title)}</option>`)
    .join("");
  presetStatus.textContent = `可用预设 ${presets.length} 个。`;
}

async function loadSelectedPreset() {
  const presetId = presetSelect.value;
  if (!presetId) {
    return;
  }
  presetStatus.textContent = `正在加载 ${presetId}...`;
  const response = await fetch(`/api/presets/${encodeURIComponent(presetId)}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`预设加载失败：${response.status}`);
  }
  const preset = await response.json();
  state.scene = preset.scene;
  state.lastResult = null;
  state.overlayResult = null;
  refreshSourceIndexes();
  presetStatus.textContent = `已加载：${preset.title}。`;
  renderAll();
  scheduleEvaluation();
}

async function initialiseShell() {
  const response = await fetch("/api/config", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`配置读取失败：${response.status}`);
  }

  const config = await response.json();
  document.title = "电磁工作台 | 静电场";
  runtimeStatus.textContent =
    `本地 Three.js ${config.runtime.three.version} 已就绪。` +
    "二维与三维交互已启用。";
}

document.querySelector("#add-point").addEventListener("click", () => addSource("point"));
document
  .querySelector("#add-line-segment")
  .addEventListener("click", () => addSource("line_segment"));
document.querySelector("#add-ring").addEventListener("click", () => addSource("ring"));
document.querySelector("#add-disk").addEventListener("click", () => addSource("disk"));
document
  .querySelector("#add-infinite-plane")
  .addEventListener("click", () => addSource("infinite_plane"));
document
  .querySelector("#add-spherical-shell")
  .addEventListener("click", () => addSource("spherical_shell"));
button2d.addEventListener("click", () => setMode("2D"));
button3d.addEventListener("click", () => setMode("3D"));
qualitySelect.addEventListener("change", () => setQuality(qualitySelect.value));
document.querySelector("#probe-form").addEventListener("input", setProbeFromInputs);
document.querySelector("#probe-form").addEventListener("change", setProbeFromInputs);
presetForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadSelectedPreset().catch((error) => {
    presetStatus.textContent = error.message;
  });
});
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
    "本地运行配置暂不可用；当前界面状态仍可继续保留。";
});
loadPresetOptions().catch((error) => {
  presetSelect.innerHTML = '<option value="">预设读取失败</option>';
  presetStatus.textContent = error.message;
});
