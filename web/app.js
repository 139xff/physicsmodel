import { evaluateField, getConfig, getPreset, listPresets } from "./api-client.js";
import { render3d, resize3d, stopAnimLoop } from "./renderers/view3d.js?v=20260529-axis-labels-pan-preserve";

const runtimeStatus = document.querySelector("#runtime-status");
const sourceList = document.querySelector("#source-list");
const sourceCount = document.querySelector("[data-testid='source-count']");
const modeLabel = document.querySelector("[data-testid='mode-label']");
const view2d = document.querySelector("#view-2d");
const view3d = document.querySelector("#view-3d");
const button2d = document.querySelector("#view-2d-button");
const button3d = document.querySelector("#view-3d-button");
const panToolButton = document.querySelector("#pan-tool");
const addInfinitePlaneButton = document.querySelector("#add-infinite-plane");
const addSphericalShellButton = document.querySelector("#add-spherical-shell");
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
let probeInputs = {
  x: document.querySelector("#probe-x"),
  y: document.querySelector("#probe-y"),
  z: document.querySelector("#probe-z"),
};
const probeForm = document.querySelector("#probe-form");
const VIEWPORT_AXIS_LIMIT_M = 10;
const VIEWPORT_METERS_TO_UNITS = 100;
const VIEWPORT_GRID_STEP_UNITS = 1;
const VIEWPORT_MIN_UNITS = -VIEWPORT_AXIS_LIMIT_M * VIEWPORT_METERS_TO_UNITS;
const VIEWPORT_SIZE_UNITS = VIEWPORT_AXIS_LIMIT_M * VIEWPORT_METERS_TO_UNITS * 2;
const VIEWPORT_MIN_ZOOM = 1;
const DEFAULT_VIEW_ZOOM = 100;
const POINT_MARKER_RADIUS_UNITS = 0.2;
const RING_DISPLAY_RADIUS_UNITS = 0.2;
const MIN_VISIBLE_MARKER_RADIUS_UNITS = 1.5;
const MAX_AXIS_TICKS = 36;
const AXIS_TICK_TARGET_COUNT = 36;
const AXIS_TICK_LENGTH_PX = 7;
const AXIS_ARROW_LENGTH_PX = 12;
const AXIS_ARROW_WIDTH_PX = 7;
const AXIS_LABEL_FONT_MIN_PX = 8.75;
const AXIS_LABEL_FONT_MAX_PX = 20;
const AXIS_LABEL_FONT_VIEWPORT_RATIO = 0.0225;
const AXIS_LABEL_X_SPACING_FACTOR = 1.2;
const AXIS_LABEL_Y_SPACING_FACTOR = 0.77;
const AXIS_X_COLOR = "#d92d20";
const AXIS_Y_COLOR = "#175cd3";
const POSITIVE_SOURCE_COLOR = "#0071e3";
const NEGATIVE_SOURCE_COLOR = "#d92d20";
const OVERLAY_SAMPLE_STEPS = [-1, -0.5, 0, 0.5, 1];

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
  view2d: { centerX: 0, centerY: 0, zoom: DEFAULT_VIEW_ZOOM },
  panMode: false,
  showHeatmap: false,
  lastResult: null,
  overlayResult: null,
  overlaySamples: [],
};

const modeStates = {
  "2D": {
    sourceIndex: { ...state.sourceIndex },
    scene: state.scene,
    probe: state.probe,
    lastResult: state.lastResult,
    overlayResult: state.overlayResult,
    overlaySamples: state.overlaySamples,
  },
  "3D": {
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
      id: "browser-interaction-scene-3d",
      title: "Browser interaction scene 3D",
      sources: [],
    },
    probe: { x: 0.2, y: 0.03, z: 0.05 },
    lastResult: null,
    overlayResult: null,
    overlaySamples: [],
  },
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
let active2dPan = null;

function saveModeState(mode = state.mode) {
  modeStates[mode] = {
    sourceIndex: state.sourceIndex,
    scene: state.scene,
    probe: state.probe,
    lastResult: state.lastResult,
    overlayResult: state.overlayResult,
    overlaySamples: state.overlaySamples,
  };
}

function loadModeState(mode) {
  const modeState = modeStates[mode];
  state.sourceIndex = modeState.sourceIndex;
  state.scene = modeState.scene;
  state.probe = modeState.probe;
  state.lastResult = modeState.lastResult;
  state.overlayResult = modeState.overlayResult;
  state.overlaySamples = modeState.overlaySamples;
}
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
  if (state.mode === "2D" && kind === "spherical_shell") {
    return;
  }
  state.scene.sources.push(sourceDefaults(kind));
  renderAll();
  scheduleEvaluation();
}

function removeSource(sourceId) {
  state.scene.sources = state.scene.sources.filter((source) => source.id !== sourceId);
  if (state.scene.sources.length === 0) {
    setEmptyComputationState();
  }
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
  if (mode === state.mode) {
    return;
  }
  saveModeState();
  loadModeState(mode);
  state.mode = mode;
  button2d.classList.toggle("selected", mode === "2D");
  button2d.setAttribute("aria-pressed", mode === "2D" ? "true" : "false");
  button3d.classList.toggle("selected", mode === "3D");
  button3d.setAttribute("aria-pressed", mode === "3D" ? "true" : "false");
  modeLabel.textContent = mode;
  view2d.classList.toggle("hidden", mode !== "2D");
  view3d.classList.toggle("hidden", mode !== "3D");
  addInfinitePlaneButton.classList.toggle("hidden", mode === "2D");
  addSphericalShellButton.classList.toggle("hidden", mode === "2D");
  if (mode === "2D") {
    state.view2d.zoom = DEFAULT_VIEW_ZOOM;
    state.view2d.centerX = 0;
    state.view2d.centerY = 0;
  }
  if (mode !== "3D") {
    stopAnimLoop();
  }
  renderAll({ reset3dView: mode === "3D" });
}

function renderPanTool() {
  panToolButton.classList.toggle("selected", state.panMode);
  panToolButton.setAttribute("aria-pressed", state.panMode ? "true" : "false");
  view2d.classList.toggle("pan-mode", state.panMode);
  view3d.classList.toggle("pan-mode", state.panMode);
}

function togglePanMode() {
  state.panMode = !state.panMode;
  renderPanTool();
  if (state.mode === "2D") {
    render2d();
  } else if (state.mode === "3D") {
    render3d(view3d, state, { panMode: state.panMode, resetView: false });
  }
}

function refreshProbeInputRefs() {
  probeInputs = {
    x: document.querySelector("#probe-x"),
    y: document.querySelector("#probe-y"),
    z: document.querySelector("#probe-z"),
  };
}

function renderProbeForm() {
  if (!probeForm) {
    return;
  }
  const zControl = state.mode === "2D"
    ? ""
    : `<label>探针 z <input id="probe-z" type="number" step="0.01" value="${formatFixed(state.probe.z)}"></label>`;
  probeForm.innerHTML = `
    <label>探针 x <input id="probe-x" type="number" step="0.01" value="${formatFixed(state.probe.x)}"></label>
    <label>探针 y <input id="probe-y" type="number" step="0.01" value="${formatFixed(state.probe.y)}"></label>
    ${zControl}
  `;
  refreshProbeInputRefs();
}

function setProbeFromInputs() {
  state.probe = {
    x: Number(probeInputs.x?.value ?? state.probe.x),
    y: Number(probeInputs.y?.value ?? state.probe.y),
    z: Number(probeInputs.z?.value ?? state.probe.z),
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

function toggleHeatmap() {
  state.showHeatmap = !state.showHeatmap;
  render2d();
}

function potentialColor(potential, maxAbs) {
  if (maxAbs < 1e-30) {
    return "rgb(255,255,255)";
  }
  const t = Math.max(-1, Math.min(1, potential / maxAbs));
  if (t > 0) {
    const r = Math.round(255 * (1 - t));
    const g = Math.round(255 * (1 - t));
    const b = Math.round(255 * (1 - 0.4 * t));
    return `rgb(${r},${g},${b})`;
  }
  const s = -t;
  const r = Math.round(255 * (1 - 0.4 * s));
  const g = Math.round(255 * (1 - s));
  const b = Math.round(255 * (1 - s));
  return `rgb(${r},${g},${b})`;
}

function renderHeatmap2d() {
  if (!state.showHeatmap || !state.overlayResult || state.overlaySamples.length === 0) {
    return "";
  }
  const potentials = state.overlayResult.samples.map((s) => s.potential_v);
  const maxAbs = Math.max(...potentials.map(Math.abs), 1e-12);
  const cellSize = radiusToViewport(overlayCellSizeMeters() * 0.5) * 2;
  const halfCell = cellSize / 2;
  return state.overlaySamples
    .map((sample, index) => {
      const point = mapToViewport(sample.x, sample.y);
      const color = potentialColor(potentials[index], maxAbs);
      return `<rect class="heatmap-cell" x="${point.x - halfCell}" y="${point.y - halfCell}" width="${cellSize}" height="${cellSize}" fill="${color}" rx="1"></rect>`;
    })
    .join("");
}

function nestedValue(source, field) {
  if (!field.includes(".")) {
    return source[field];
  }
  const [group, key] = field.split(".");
  return source[group][key];
}

function vectorMagnitude(vector) {
  if (!vector) {
    return 0;
  }
  return Math.hypot(Number(vector.x), Number(vector.y), Number(vector.z));
}

function sceneValidationMessage() {
  for (const source of state.scene.sources) {
    if (source.orientation && vectorMagnitude(source.orientation) <= 1e-12) {
      return "Direction vector cannot be zero; continue editing before solving.";
    }
    if (source.normal && vectorMagnitude(source.normal) <= 1e-12) {
      return "Normal vector cannot be zero; continue editing before solving.";
    }
  }
  return "";
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
  const zField = state.mode === "2D" ? "" : sourceField(source, `${group}.z`, `${heading} z`);
  return `
    <div class="vector-fieldset">
      <span>${heading}</span>
      <div class="mini-grid">
        ${sourceField(source, `${group}.x`, `${heading} x`)}
        ${sourceField(source, `${group}.y`, `${heading} y`)}
        ${zField}
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
  const listedSources = state.mode === "2D"
    ? state.scene.sources.filter((source) => source.kind !== "spherical_shell")
    : state.scene.sources;
  sourceCount.textContent = `${listedSources.length} 个源`;

  if (listedSources.length === 0) {
    sourceList.innerHTML = `
      <div class="empty-state">
        <p>还没有可编辑的源。</p>
        <span>加入一个静电源，或加载一个预设场景开始探索。</span>
      </div>
    `;
    return;
  }

  sourceList.innerHTML = listedSources
    .map((source) => {
      const label = escapeHtml(source.label);
      const positionZField = state.mode === "2D"
        ? ""
        : sourceField(source, "position.z", "位置 z m");
      return `
        <article class="source-card" data-testid="source-card-${source.id}">
          <div class="source-card-heading">
            <strong>${label}</strong>
            <button class="source-delete-button" type="button" data-source-id="${source.id}" title="移除此源">移除</button>
            <span>${KIND_LABELS[source.kind] ?? source.kind}</span>
          </div>
          <label>名称
            <input type="text" value="${label}" data-source-id="${source.id}" data-field="label">
          </label>
          <div class="mini-grid">
            ${sourceField(source, "position.x", "位置 x m")}
            ${sourceField(source, "position.y", "位置 y m")}
            ${positionZField}
            ${scalarControls(source)}
          </div>
          ${vectorFields(source, "orientation", "方向")}
          ${vectorFields(source, "normal", "法向")}
        </article>
      `;
    })
    .join("");
}

function sourceWorldRadius(source) {
  if (source.kind === "point") {
    return 0.04;
  }
  if (source.kind === "line_segment") {
    return source.length_m * 0.5;
  }
  if (source.kind === "infinite_plane") {
    return source.display_extent_m * 0.5;
  }
  if ("radius_m" in source) {
    return source.radius_m;
  }
  return 0.04;
}

function mapToViewport(x, y) {
  return {
    x: x * VIEWPORT_METERS_TO_UNITS,
    y: -y * VIEWPORT_METERS_TO_UNITS,
  };
}

function radiusToViewport(radius, minimum = 0) {
  return Math.max(minimum, radius * VIEWPORT_METERS_TO_UNITS);
}

function view2dAspectRatio() {
  const rect = view2d.getBoundingClientRect();
  const width = rect.width || view2d.clientWidth || 1;
  const height = rect.height || view2d.clientHeight || 1;
  return Math.max(0.05, width / Math.max(1, height));
}

function compute2dViewDimensions() {
  const baseSize = VIEWPORT_SIZE_UNITS / state.view2d.zoom;
  const aspect = view2dAspectRatio();
  if (aspect >= 1) {
    return {
      width: baseSize * aspect,
      height: baseSize,
    };
  }
  return {
    width: baseSize,
    height: baseSize / aspect,
  };
}

function clamp2dView() {
  if (!Number.isFinite(state.view2d.zoom)) {
    state.view2d.zoom = VIEWPORT_MIN_ZOOM;
  }
  state.view2d.zoom = Math.max(VIEWPORT_MIN_ZOOM, state.view2d.zoom);
  const { width, height } = compute2dViewDimensions();
  const halfWidth = width / 2;
  const halfHeight = height / 2;
  const minCenterX = VIEWPORT_MIN_UNITS + halfWidth;
  const maxCenterX = VIEWPORT_MIN_UNITS + VIEWPORT_SIZE_UNITS - halfWidth;
  const minCenterY = VIEWPORT_MIN_UNITS + halfHeight;
  const maxCenterY = VIEWPORT_MIN_UNITS + VIEWPORT_SIZE_UNITS - halfHeight;
  state.view2d.centerX = minCenterX > maxCenterX
    ? 0
    : Math.min(maxCenterX, Math.max(minCenterX, state.view2d.centerX));
  state.view2d.centerY = minCenterY > maxCenterY
    ? 0
    : Math.min(maxCenterY, Math.max(minCenterY, state.view2d.centerY));
}

function compute2dViewBox() {
  clamp2dView();
  const { width, height } = compute2dViewDimensions();
  return {
    minX: state.view2d.centerX - width / 2,
    minY: state.view2d.centerY - height / 2,
    width,
    height,
  };
}

function compute2dWorldBounds() {
  return {
    minX: -VIEWPORT_AXIS_LIMIT_M,
    maxX: VIEWPORT_AXIS_LIMIT_M,
    minY: -VIEWPORT_AXIS_LIMIT_M,
    maxY: VIEWPORT_AXIS_LIMIT_M,
  };
}

function overlayCellSizeMeters() {
  const bounds = compute2dWorldBounds();
  return Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY) / 5;
}

function sourceChargeValue(source) {
  if ("charge_c" in source && source.charge_c !== null) {
    return Number(source.charge_c);
  }
  if ("surface_charge_density_c_per_m2" in source) {
    return Number(source.surface_charge_density_c_per_m2);
  }
  return 0;
}

function sourceChargeColor(source) {
  return sourceChargeValue(source) >= 0 ? POSITIVE_SOURCE_COLOR : NEGATIVE_SOURCE_COLOR;
}

function sourceChargeSign(source) {
  return sourceChargeValue(source) >= 0 ? "positive" : "negative";
}

function sourceLabelMarkup(source, label, point, scale) {
  const fontSize = scale.fontPx * scale.yUnitsPerPx;
  const textStrokeWidth = 0.7 * scale.yUnitsPerPx;
  const labelOffsetX = (scale.fontPx + 8) * scale.xUnitsPerPx;
  const labelOffsetY = -(scale.fontPx * 0.55 + 8) * scale.yUnitsPerPx;
  return `
    <text
      data-testid="source-label-2d-${source.id}"
      x="${point.x + labelOffsetX}"
      y="${point.y + labelOffsetY}"
      style="font-size: ${fontSize}px; stroke-width: ${textStrokeWidth}px;"
    >${label}</text>
  `;
}

function renderSource2d(source, scale) {
  if (source.kind === "spherical_shell") {
    return "";
  }
  const point = mapToViewport(source.position.x, source.position.y);
  const label = escapeHtml(source.label);
  const markerRadius = (scale.fontPx * Math.min(scale.xUnitsPerPx, scale.yUnitsPerPx)) / 2;
  const markerStrokeWidth = scale.fontPx * ((scale.xUnitsPerPx + scale.yUnitsPerPx) / 2);
  const chargeColor = sourceChargeColor(source);
  const chargeSign = sourceChargeSign(source);
  if (source.kind === "line_segment") {
    const directionMagnitude = Math.hypot(source.orientation.x, source.orientation.y);
    const directionX = directionMagnitude > 1e-12 ? source.orientation.x / directionMagnitude : 1;
    const directionY = directionMagnitude > 1e-12 ? source.orientation.y / directionMagnitude : 0;
    const displayLength = radiusToViewport(source.length_m);
    const dx = directionX * displayLength;
    const dy = directionY * displayLength;
    return `
      <g data-testid="source-line-segment-group-2d-${source.id}">
        <line
          class="source-line-segment"
          data-testid="source-line-segment-2d-${source.id}"
          data-display-length-cm="${displayLength}"
          data-starts-at-position="true"
          x1="${point.x}"
          y1="${point.y}"
          x2="${point.x + dx}"
          y2="${point.y - dy}"
          style="stroke-width: ${markerStrokeWidth}px; stroke: ${chargeColor};"
          data-charge-color="${chargeColor}"
          data-charge-sign="${chargeSign}"
          data-stroke-px="${scale.fontPx.toFixed(2)}"
        ></line>
        ${sourceLabelMarkup(source, label, point, scale)}
      </g>
    `;
  }
  if (source.kind === "ring") {
    return `
      <g data-testid="source-ring-group-2d-${source.id}">
        <circle
          class="source-ring"
          data-testid="source-ring-2d-${source.id}"
          data-display-diameter-cm="${RING_DISPLAY_RADIUS_UNITS * 2}"
          cx="${point.x}"
          cy="${point.y}"
          r="${RING_DISPLAY_RADIUS_UNITS}"
          style="stroke-width: ${markerStrokeWidth}px; stroke: ${chargeColor}; fill: ${chargeColor}; fill-opacity: 0.08;"
          data-charge-color="${chargeColor}"
          data-charge-sign="${chargeSign}"
          data-stroke-px="${scale.fontPx.toFixed(2)}"
        ></circle>
        ${sourceLabelMarkup(source, label, point, scale)}
      </g>
    `;
  }
  if (source.kind === "disk" || source.kind === "spherical_shell") {
    const className = `source-${source.kind.replaceAll("_", "-")}`;
    const radius = radiusToViewport(source.radius_m, MIN_VISIBLE_MARKER_RADIUS_UNITS);
    const shapeStyle = source.kind === "disk"
      ? `stroke: ${chargeColor}; fill: ${chargeColor}; fill-opacity: 1;`
      : `stroke: ${chargeColor}; fill: none; fill-opacity: 0;`;
    return `
      <g data-testid="source-${source.kind.replaceAll("_", "-")}-group-2d-${source.id}">
        <circle
          class="${className}"
          data-testid="source-${source.kind.replaceAll("_", "-")}-2d-${source.id}"
          cx="${point.x}"
          cy="${point.y}"
          r="${radius}"
          style="${shapeStyle}"
          data-charge-color="${chargeColor}"
          data-charge-sign="${chargeSign}"
        ></circle>
        ${sourceLabelMarkup(source, label, point, scale)}
      </g>
    `;
  }
  if (source.kind === "infinite_plane") {
    const extent = radiusToViewport(source.display_extent_m / 2);
    return `
      <g data-testid="source-infinite-plane-group-2d-${source.id}">
        <rect
          class="source-infinite-plane"
          data-testid="source-infinite-plane-2d-${source.id}"
          x="${point.x - extent}"
          y="${point.y - extent}"
          width="${extent * 2}"
          height="${extent * 2}"
          style="stroke: ${chargeColor}; fill: ${chargeColor}; fill-opacity: 0.1;"
          data-charge-color="${chargeColor}"
          data-charge-sign="${chargeSign}"
        ></rect>
        ${sourceLabelMarkup(source, label, point, scale)}
      </g>
    `;
  }
  return `
    <g data-testid="source-point-group-2d-${source.id}">
      <circle
        class="source-point"
        data-testid="source-point-2d-${source.id}"
        data-display-radius-cm="${POINT_MARKER_RADIUS_UNITS}"
        data-visual-size-px="${scale.fontPx.toFixed(2)}"
        data-charge-color="${chargeColor}"
        data-charge-sign="${chargeSign}"
        cx="${point.x}"
        cy="${point.y}"
        r="${markerRadius}"
        style="fill: url(#source-point-${chargeSign}-gradient); stroke: none; stroke-width: 0;"
      ></circle>
      <circle
        class="source-point-highlight"
        data-testid="source-point-highlight-2d-${source.id}"
        cx="${point.x - markerRadius * 0.32}"
        cy="${point.y - markerRadius * 0.34}"
        r="${markerRadius * 0.24}"
        style="fill: rgba(255, 255, 255, 0.78); stroke: none; stroke-width: 0;"
      ></circle>
      ${sourceLabelMarkup(source, label, point, scale)}
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

function screenScaleForViewBox(viewBox) {
  const rect = view2d.getBoundingClientRect();
  const widthPx = Math.max(1, rect.width || view2d.clientWidth || 640);
  const heightPx = Math.max(1, rect.height || view2d.clientHeight || 520);
  return {
    fontPx: Math.min(
      AXIS_LABEL_FONT_MAX_PX,
      Math.max(AXIS_LABEL_FONT_MIN_PX, Math.min(widthPx, heightPx) * AXIS_LABEL_FONT_VIEWPORT_RATIO),
    ),
    widthPx,
    heightPx,
    xUnitsPerPx: viewBox.width / widthPx,
    yUnitsPerPx: viewBox.height / heightPx,
  };
}

function niceAxisStep(spanCm, maxTicks) {
  const targetCount = Math.max(2, Math.min(AXIS_TICK_TARGET_COUNT, maxTicks));
  const rawStep = Math.max(spanCm / Math.max(1, targetCount - 1), 1e-9);
  const exponent = Math.floor(Math.log10(rawStep));
  const base = 10 ** exponent;
  for (const multiplier of [1, 2, 5, 10]) {
    const step = multiplier * base;
    if (Math.floor(spanCm / step) + 1 <= maxTicks) {
      return step;
    }
  }
  return 10 * base;
}

function formatAxisTick(value) {
  if (Math.abs(value) < 1e-10) {
    return "0";
  }
  if (Math.abs(value) >= 10) {
    return value.toFixed(0);
  }
  if (Math.abs(value) >= 1) {
    return value.toFixed(1).replace(/\.0$/, "");
  }
  return value.toFixed(2).replace(/0$/, "").replace(/\.0$/, "");
}

function maxAxisTicksForScreen(spanPx, fontPx, spacingFactor) {
  return Math.max(2, Math.min(MAX_AXIS_TICKS, Math.floor(spanPx / (fontPx * spacingFactor)) + 1));
}

function generateAxisTicks(minCm, maxCm, maxTicks) {
  const span = maxCm - minCm;
  const step = niceAxisStep(span, maxTicks);
  const ticks = [];
  let value = Math.ceil(minCm / step) * step;
  while (value <= maxCm + step * 0.001 && ticks.length < maxTicks) {
    ticks.push(Number(value.toFixed(10)));
    value += step;
  }
  return { ticks, step };
}

function chooseAxisTickData(minXCm, maxXCm, minYCm, maxYCm, scale) {
  const xCapacity = maxAxisTicksForScreen(
    scale.widthPx,
    scale.fontPx,
    AXIS_LABEL_X_SPACING_FACTOR,
  );
  const yCapacity = maxAxisTicksForScreen(
    scale.heightPx,
    scale.fontPx,
    AXIS_LABEL_Y_SPACING_FACTOR,
  );
  const viewportRatio = scale.widthPx / scale.heightPx;
  let best = null;

  for (let xLimit = 2; xLimit <= xCapacity; xLimit += 1) {
    const xData = generateAxisTicks(minXCm, maxXCm, xLimit);
    for (let yLimit = 2; yLimit <= yCapacity; yLimit += 1) {
      const yData = generateAxisTicks(minYCm, maxYCm, yLimit);
      const ratio = xData.ticks.length / yData.ticks.length;
      const ratioError = Math.abs(Math.log(ratio / viewportRatio));
      const tickCount = xData.ticks.length + yData.ticks.length;
      if (
        !best ||
        ratioError < best.ratioError - 0.02 ||
        (Math.abs(ratioError - best.ratioError) <= 0.02 && tickCount > best.tickCount)
      ) {
        best = {
          ratioError,
          tickCount,
          xData,
          xLimit,
          yData,
          yLimit,
        };
      }
    }
  }

  return best;
}

function render2dAxes(viewBox, axisOrigin, scale) {
  const tickHalfX = (AXIS_TICK_LENGTH_PX * scale.xUnitsPerPx) / 2;
  const tickHalfY = (AXIS_TICK_LENGTH_PX * scale.yUnitsPerPx) / 2;
  const arrowLengthX = AXIS_ARROW_LENGTH_PX * scale.xUnitsPerPx;
  const arrowLengthY = AXIS_ARROW_LENGTH_PX * scale.yUnitsPerPx;
  const arrowHalfWidthX = (AXIS_ARROW_WIDTH_PX * scale.xUnitsPerPx) / 2;
  const arrowHalfWidthY = (AXIS_ARROW_WIDTH_PX * scale.yUnitsPerPx) / 2;
  const fontSize = scale.fontPx * scale.yUnitsPerPx;
  const textStrokeWidth = 0.7 * scale.yUnitsPerPx;
  const labelGapX = (scale.fontPx * 0.55 + 8) * scale.xUnitsPerPx;
  const labelGapY = (scale.fontPx * 0.45 + 8) * scale.yUnitsPerPx;
  const minXCm = viewBox.minX;
  const maxXCm = viewBox.minX + viewBox.width;
  const minYCm = -(viewBox.minY + viewBox.height);
  const maxYCm = -viewBox.minY;
  const chosenTickData = chooseAxisTickData(minXCm, maxXCm, minYCm, maxYCm, scale);
  const xTickData = chosenTickData.xData;
  const yTickData = chosenTickData.yData;
  const xTicks = xTickData.ticks
    .map((tick) => {
      const x = tick;
      const line = Math.abs(tick) < 1e-10
        ? ""
        : `<line stroke="${AXIS_X_COLOR}" x1="${x}" y1="${axisOrigin.y - tickHalfY}" x2="${x}" y2="${axisOrigin.y + tickHalfY}"></line>`;
      return `
        <g class="axis-tick axis-tick-x" data-testid="axis-tick-2d-x">
          ${line}
          <text x="${x}" y="${axisOrigin.y + tickHalfY + labelGapY}" style="font-size: ${fontSize}px; stroke-width: ${textStrokeWidth}px;" text-anchor="middle">${formatAxisTick(tick)}</text>
        </g>
      `;
    })
    .join("");
  const yTicks = yTickData.ticks
    .map((tick) => {
      const y = -tick;
      const label = Math.abs(tick) < 1e-10 ? "" : formatAxisTick(tick);
      const line = label
        ? `<line stroke="${AXIS_Y_COLOR}" x1="${axisOrigin.x - tickHalfX}" y1="${y}" x2="${axisOrigin.x + tickHalfX}" y2="${y}"></line>`
        : "";
      return `
        <g class="axis-tick axis-tick-y" data-testid="axis-tick-2d-y">
          ${line}
          <text x="${axisOrigin.x + tickHalfX + labelGapX}" y="${y + fontSize * 0.35}" style="font-size: ${fontSize}px; stroke-width: ${textStrokeWidth}px;" text-anchor="start">${label}</text>
        </g>
      `;
    })
    .join("");
  const xMax = viewBox.minX + viewBox.width;
  const yMin = viewBox.minY;
  return `
    <g
      class="axis-layer"
      data-testid="axis-layer-2d"
      data-x-tick-count="${xTickData.ticks.length}"
      data-y-tick-count="${yTickData.ticks.length}"
      data-visible-x-label-count="${xTickData.ticks.length}"
      data-visible-y-label-count="${yTickData.ticks.filter((tick) => Math.abs(tick) >= 1e-10).length}"
      data-x-tick-limit="${chosenTickData.xLimit}"
      data-y-tick-limit="${chosenTickData.yLimit}"
      data-viewport-ratio="${(scale.widthPx / scale.heightPx).toFixed(3)}"
      data-axis-unit="cm"
      data-tick-length-px="${AXIS_TICK_LENGTH_PX}"
      data-label-font-px="${scale.fontPx.toFixed(2)}"
    >
      <line
        class="axis-line axis-line-x"
        data-testid="axis-line-2d-x"
        x1="${viewBox.minX}"
        y1="${axisOrigin.y}"
        x2="${xMax}"
        y2="${axisOrigin.y}"
      ></line>
      <line
        class="axis-line axis-line-y"
        data-testid="axis-line-2d-y"
        x1="${axisOrigin.x}"
        y1="${viewBox.minY}"
        x2="${axisOrigin.x}"
        y2="${viewBox.minY + viewBox.height}"
      ></line>
      <path
        class="axis-arrow axis-arrow-x"
        data-testid="axis-arrow-2d-x"
        d="M ${xMax} ${axisOrigin.y} L ${xMax - arrowLengthX} ${axisOrigin.y - arrowHalfWidthY} L ${xMax - arrowLengthX} ${axisOrigin.y + arrowHalfWidthY} Z"
      ></path>
      <path
        class="axis-arrow axis-arrow-y"
        data-testid="axis-arrow-2d-y"
        d="M ${axisOrigin.x} ${yMin} L ${axisOrigin.x - arrowHalfWidthX} ${yMin + arrowLengthY} L ${axisOrigin.x + arrowHalfWidthX} ${yMin + arrowLengthY} Z"
      ></path>
      ${xTicks}
      ${yTicks}
    </g>
  `;
}

function render2d() {
  const viewBox = compute2dViewBox();
  const scale = screenScaleForViewBox(viewBox);
  const sourceMarkup = state.scene.sources.map((source) => renderSource2d(source, scale)).join("");
  const axisOrigin = mapToViewport(0, 0);

  view2d.innerHTML = `
    <svg
      class="plane-svg"
      viewBox="${viewBox.minX} ${viewBox.minY} ${viewBox.width} ${viewBox.height}"
      data-zoom="${state.view2d.zoom}"
      role="img"
      aria-label="Top-down electrostatic scene"
    >
      <defs>
        <radialGradient id="source-point-positive-gradient" cx="32%" cy="28%" r="78%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="1"></stop>
          <stop offset="24%" stop-color="#8ec5ff" stop-opacity="0.98"></stop>
          <stop offset="62%" stop-color="${POSITIVE_SOURCE_COLOR}" stop-opacity="1"></stop>
          <stop offset="100%" stop-color="#003f8c" stop-opacity="1"></stop>
        </radialGradient>
        <radialGradient id="source-point-negative-gradient" cx="32%" cy="28%" r="78%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="1"></stop>
          <stop offset="24%" stop-color="#fda29b" stop-opacity="0.98"></stop>
          <stop offset="62%" stop-color="${NEGATIVE_SOURCE_COLOR}" stop-opacity="1"></stop>
          <stop offset="100%" stop-color="#7a170f" stop-opacity="1"></stop>
        </radialGradient>
        <pattern id="grid" width="${VIEWPORT_GRID_STEP_UNITS}" height="${VIEWPORT_GRID_STEP_UNITS}" patternUnits="userSpaceOnUse">
          <path d="M ${VIEWPORT_GRID_STEP_UNITS} 0 L 0 0 0 ${VIEWPORT_GRID_STEP_UNITS}" fill="none"></path>
        </pattern>
      </defs>
      <rect
        x="${viewBox.minX}"
        y="${viewBox.minY}"
        width="${viewBox.width}"
        height="${viewBox.height}"
        fill="url(#grid)"
      ></rect>
      ${render2dAxes(viewBox, axisOrigin, scale)}
      ${renderHeatmap2d()}
      ${renderOverlay2d()}
      ${sourceMarkup}
    </svg>
  `;
}

function zoom2d(deltaY) {
  const nextZoom = state.view2d.zoom * Math.exp(-deltaY * 0.0012);
  state.view2d.zoom = nextZoom;
  clamp2dView();
  render2d();
}

function start2dPan(event) {
  if (!state.panMode || state.mode !== "2D" || event.button !== 0) {
    return;
  }
  const viewBox = compute2dViewBox();
  active2dPan = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    centerX: state.view2d.centerX,
    centerY: state.view2d.centerY,
    width: viewBox.width,
    height: viewBox.height,
  };
  view2d.classList.add("is-panning");
  view2d.setPointerCapture(event.pointerId);
}

function move2dPan(event) {
  if (!active2dPan || active2dPan.pointerId !== event.pointerId) {
    return;
  }
  const rect = view2d.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    return;
  }
  const deltaX = ((event.clientX - active2dPan.startX) / rect.width) * active2dPan.width;
  const deltaY = ((event.clientY - active2dPan.startY) / rect.height) * active2dPan.height;
  state.view2d.centerX = active2dPan.centerX - deltaX;
  state.view2d.centerY = active2dPan.centerY - deltaY;
  clamp2dView();
  render2d();
}

function end2dPan(event) {
  if (!active2dPan || active2dPan.pointerId !== event.pointerId) {
    return;
  }
  active2dPan = null;
  view2d.classList.remove("is-panning");
  if (view2d.hasPointerCapture(event.pointerId)) {
    view2d.releasePointerCapture(event.pointerId);
  }
}

function renderProbe() {
  renderProbeForm();
  probePosition.textContent = state.mode === "2D"
    ? `探针位置 (${formatFixed(state.probe.x)}, ${formatFixed(state.probe.y)}) m`
    : `探针位置 (${formatFixed(state.probe.x)}, ${formatFixed(state.probe.y)}, ` +
      `${formatFixed(state.probe.z)}) m`;
}

function renderResult() {
  qualityValue.textContent = state.quality;
  if (!state.lastResult) {
    solverStatus.textContent = state.scene.sources.length === 0 ? "等待源" : solverStatus.textContent;
    potentialValue.textContent = "暂无";
    fieldVectorValue.textContent = "暂无";
    fieldMagnitudeValue.textContent = "暂无";
    contributionList.innerHTML = "<li>还没有源贡献。</li>";
    warningList.innerHTML = "<li>暂无提示。</li>";
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
    overlayStatus.textContent = state.scene.sources.length === 0 ? "等待源" : overlayStatus.textContent;
    overlaySummary.textContent = "加入源后，二维视图会显示采样电场箭头。";
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

function renderAll(options = {}) {
  renderSourceList();
  render2d();
  renderProbe();
  if (state.mode === "3D") {
    render3d(view3d, state, {
      panMode: state.panMode,
      resetView: Boolean(options.reset3dView),
    });
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
  return evaluateField({
    request_id: requestId,
    scene: state.scene,
    sample_points: samplePoints,
    quality: state.quality,
  });
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
  const bounds = compute2dWorldBounds();
  const centerX = (bounds.minX + bounds.maxX) / 2;
  const centerY = (bounds.minY + bounds.maxY) / 2;
  const halfSpan = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY) / 2;

  for (const yStep of OVERLAY_SAMPLE_STEPS) {
    for (const xStep of OVERLAY_SAMPLE_STEPS) {
      const x = centerX + xStep * halfSpan;
      const y = centerY + yStep * halfSpan;
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

let evaluationTimer = null;

function scheduleEvaluation() {
  requestSerial += 1;
  latestProbeRequestId = `ui-probe-${requestSerial}`;
  latestOverlayRequestId = `ui-overlay-${requestSerial}`;
  const probeRequestId = latestProbeRequestId;
  const overlayRequestId = latestOverlayRequestId;
  if (evaluationTimer) {
    window.clearTimeout(evaluationTimer);
  }
  const validationMessage = sceneValidationMessage();
  if (validationMessage) {
    solverStatus.textContent = validationMessage;
    overlayStatus.textContent = validationMessage;
    return;
  }
  evaluationTimer = window.setTimeout(() => {
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
  }, 180);
}

function refreshSourceIndexes() {
  for (const kind of Object.keys(state.sourceIndex)) {
    state.sourceIndex[kind] = state.scene.sources.filter((source) => source.kind === kind).length;
  }
}

async function loadPresetOptions() {
  const presets = await listPresets();
  presetSelect.innerHTML = presets
    .map((preset) => `<option value="${preset.id}">${escapeHtml(preset.title)}</option>`)
    .join("");
  presetStatus.textContent = `可用预设 ${presets.length} 个。`;
}

async function loadSelectedPreset() {
  const presetId = presetSelect.value;
  if (!presetId) {
    presetStatus.textContent = "请先选择一个预设场景。";
    return;
  }
  presetStatus.textContent = `正在加载 ${presetId}...`;
  const preset = await getPreset(presetId);
  state.scene = preset.scene;
  state.lastResult = null;
  state.overlayResult = null;
  refreshSourceIndexes();
  presetStatus.textContent = `已加载：${preset.title}。`;
  renderAll();
  scheduleEvaluation();
}

async function initialiseShell() {
  const config = await getConfig();
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
panToolButton.addEventListener("click", togglePanMode);
qualitySelect.addEventListener("change", () => setQuality(qualitySelect.value));
view2d.addEventListener(
  "wheel",
  (event) => {
    if (state.mode !== "2D") {
      return;
    }
    event.preventDefault();
    zoom2d(event.deltaY);
  },
  { passive: false },
);
view2d.addEventListener("pointerdown", start2dPan);
view2d.addEventListener("pointermove", move2dPan);
view2d.addEventListener("pointerup", end2dPan);
view2d.addEventListener("pointercancel", end2dPan);
document.querySelector("#toggle-heatmap").addEventListener("click", () => {
  const button = document.querySelector("#toggle-heatmap");
  toggleHeatmap();
  button.classList.toggle("active", state.showHeatmap);
  button.textContent = state.showHeatmap ? "隐藏电势热力图" : "显示电势热力图";
});
document.querySelector("#probe-form").addEventListener("change", setProbeFromInputs);
presetForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadSelectedPreset().catch((error) => {
    presetStatus.textContent = error.message;
  });
});
sourceList.addEventListener("click", (event) => {
  const button = event.target.closest(".source-delete-button");
  if (button) {
    removeSource(button.dataset.sourceId);
  }
});
function handleSourceInput(event) {
  const input = event.target;
  if (input instanceof HTMLInputElement) {
    updateSource(input.dataset.sourceId, input.dataset.field, input.value);
  }
}

sourceList.addEventListener("input", handleSourceInput);
sourceList.addEventListener("change", handleSourceInput);
window.addEventListener("resize", () => {
  if (state.mode === "2D") {
    render2d();
  } else if (state.mode === "3D") {
    resize3d(view3d, state);
  }
});

renderAll();
renderPanTool();
addInfinitePlaneButton.classList.add("hidden");
addSphericalShellButton.classList.add("hidden");
initialiseShell().catch(() => {
  runtimeStatus.textContent =
    "本地运行配置暂不可用；当前界面状态仍可继续保留。";
});
loadPresetOptions().catch((error) => {
  presetSelect.innerHTML = '<option value="">预设读取失败</option>';
  presetStatus.textContent = error.message;
});
