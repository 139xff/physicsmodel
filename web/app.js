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
const toggleFieldLinesButton = document.querySelector("#toggle-field-lines");
const addInfinitePlaneButton = document.querySelector("#add-infinite-plane");
const addSphericalShellButton = document.querySelector("#add-spherical-shell");
const pointSourceForm = document.querySelector("#point-source-form");
const pointSourceXInput = document.querySelector("#point-source-x");
const pointSourceYInput = document.querySelector("#point-source-y");
const pointSourceZInput = document.querySelector("#point-source-z");
const pointSourceZField = document.querySelector("#point-source-z-field");
const pointSourceChargeInput = document.querySelector("#point-source-charge");
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
const POINT_VISUAL_RADIUS_CM = 0.5;
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
const POSITIVE_SOURCE_COLOR = "#d92d20";
const NEGATIVE_SOURCE_COLOR = "#175cd3";
const OVERLAY_SAMPLE_STEPS = [-1, -0.5, 0, 0.5, 1];
const FIELD_LINE_TARGET_TOTAL_CHARGE_RAYS = 96;
const FIELD_LINE_MIN_CHARGE_RAYS = 24;
const FIELD_LINE_MAX_CHARGE_RAYS = 64;
const FIELD_LINE_DISPLAY_MAX_COUNT = 120;
const FIELD_LINE_MAX_PAIR_DISPLAY_COUNT = 72;
const FIELD_LINE_START_RADIUS_M = POINT_VISUAL_RADIUS_CM / 100;
const FIELD_LINE_ENDPOINT_MARGIN_M = 0.0015;
const FIELD_LINE_BASE_STEP_M = 0.025;
const FIELD_LINE_MIN_STEP_M = 0.004;
const FIELD_LINE_MAX_STEP_M = 0.06;
const FIELD_LINE_MAX_STEPS = 700;
const FIELD_LINE_MAX_POINTS = 420;
const FIELD_LINE_MIN_FIELD = 1e-15;
const FIELD_LINE_SINGULARITY_RADIUS_M = 1e-6;
const FIELD_LINE_REVERSAL_DOT_LIMIT = -0.2;
const FIELD_LINE_ADAPT_RETRY_DOT = 0.985;
const FIELD_LINE_ADAPT_GROW_DOT = 0.998;
const FIELD_LINE_ADAPT_SHRINK_DOT = 0.992;
const FIELD_LINE_ADAPT_ERROR_MIN_M = 0.0012;
const FIELD_LINE_ADAPT_ERROR_FRACTION = 0.035;
const FIELD_LINE_SELF_APPROACH_M = 0.006;
const FIELD_LINE_SEED_ATTEMPTS = 1;
const FIELD_LINE_MIN_RENDER_POINTS = 4;
const FIELD_LINE_ACCEPTED_CLEARANCE_M = 0.001;
const FIELD_LINE_CHARGE_CLEARANCE_RADIUS_M = 0.025;
const FIELD_LINE_SPATIAL_CELL_M = 0.025;
const FIELD_LINE_CURVE_CONTROL_FACTOR = 0.42;
const FIELD_LINE_DISPLAY_SMOOTHING_ITERATIONS = 0;
const FIELD_LINE_DISPLAY_SMOOTHING_WEIGHT = 0.18;
const FIELD_LINE_DIRECTION_DOT_MIN = -0.05;
const FIELD_LINE_DISPLAY_STRATEGY = "uniform-charge-angle";
const FIELD_LINE_ARROW_FRACTION_BASE = 0.42;
const FIELD_LINE_ARROW_FRACTION_SPREAD = 0.18;
const FIELD_LINE_ARROW_FRACTION_MIN = 0.22;
const FIELD_LINE_ARROW_FRACTION_MAX = 0.72;
const FIELD_LINE_ARROW_LENGTH_PX = 9;
const FIELD_LINE_ARROW_WIDTH_PX = 7;

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
  showFieldLines: false,
  lastResult: null,
  overlayResult: null,
  overlaySamples: [],
};

let fieldLineTraceCache = {
  key: "",
  result: null,
};

const modeStates = {
  "2D": {
    sourceIndex: { ...state.sourceIndex },
    scene: state.scene,
    probe: state.probe,
    lastResult: state.lastResult,
    overlayResult: state.overlayResult,
    overlaySamples: state.overlaySamples,
    showFieldLines: state.showFieldLines,
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
    showFieldLines: false,
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
    showFieldLines: state.showFieldLines,
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
  state.showFieldLines = Boolean(modeState.showFieldLines);
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

function metersToCentimeters(value) {
  return Number(value) * 100;
}

function centimetersToMeters(value) {
  return Number(value) / 100;
}

function formatCentimeters(value) {
  return metersToCentimeters(value).toFixed(2).replace(/\.?0+$/, "");
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

function sourceDefaults(kind, overrides = {}) {
  state.sourceIndex[kind] += 1;
  const index = state.sourceIndex[kind];
  const idPrefix = kind.replaceAll("_", "-");
  const overridePosition = overrides.position || {};
  const base = {
    id: `${idPrefix}-${index}`,
    kind,
    label: `${kindLabel(kind)} ${index}`,
    position: {
      x: Number(overridePosition.x ?? 0),
      y: Number(overridePosition.y ?? 0),
      z: Number(overridePosition.z ?? 0),
      unit: "m",
    },
  };

  if (kind === "point") {
    return {
      ...base,
      label: `点电荷 ${index}`,
      position: {
        x: Number(overridePosition.x ?? -0.16),
        y: Number(overridePosition.y ?? 0),
        z: Number(overridePosition.z ?? 0),
        unit: "m",
      },
      charge_c: Number(overrides.charge_c ?? 1e-9),
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

function addSource(kind, overrides = {}) {
  if (state.mode === "2D" && kind === "spherical_shell") {
    return;
  }
  state.scene.sources.push(sourceDefaults(kind, overrides));
  fieldLineTraceCache = { key: "", result: null };
  renderAll();
  scheduleEvaluation();
}

function inputNumberValue(input, fallback = 0) {
  if (!input) {
    return fallback;
  }
  const value = Number(input.value);
  return Number.isFinite(value) ? value : fallback;
}

function addPointSourceFromForm(event) {
  event.preventDefault();
  const xCm = inputNumberValue(pointSourceXInput);
  const yCm = inputNumberValue(pointSourceYInput);
  const zCm = state.mode === "2D" ? 0 : inputNumberValue(pointSourceZInput);
  const charge = inputNumberValue(pointSourceChargeInput, 1e-9);
  if (![xCm, yCm, zCm, charge].every(Number.isFinite)) {
    solverStatus.textContent = "点电荷参数必须是有限数值。";
    return;
  }
  addSource("point", {
    position: {
      x: centimetersToMeters(xCm),
      y: centimetersToMeters(yCm),
      z: centimetersToMeters(zCm),
    },
    charge_c: charge,
  });
}

function renderPointSourceForm() {
  if (!pointSourceForm || !pointSourceZField) {
    return;
  }
  pointSourceZField.hidden = state.mode === "2D";
}

function removeSource(sourceId) {
  state.scene.sources = state.scene.sources.filter((source) => source.id !== sourceId);
  fieldLineTraceCache = { key: "", result: null };
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

  fieldLineTraceCache = { key: "", result: null };
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
    : `<label>探针 z / cm <input id="probe-z" type="number" step="0.1" value="${formatCentimeters(state.probe.z)}"></label>`;
  probeForm.innerHTML = `
    <label>探针 x / cm <input id="probe-x" type="number" step="0.1" value="${formatCentimeters(state.probe.x)}"></label>
    <label>探针 y / cm <input id="probe-y" type="number" step="0.1" value="${formatCentimeters(state.probe.y)}"></label>
    ${zControl}
    <button id="probe-submit" class="probe-submit" type="submit">确定</button>
  `;
  refreshProbeInputRefs();
}

function setProbeFromInputs() {
  state.probe = {
    x: centimetersToMeters(probeInputs.x?.value ?? metersToCentimeters(state.probe.x)),
    y: centimetersToMeters(probeInputs.y?.value ?? metersToCentimeters(state.probe.y)),
    z: probeInputs.z
      ? centimetersToMeters(probeInputs.z.value)
      : state.probe.z,
  };
  renderAll();
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

function toggleFieldLines() {
  state.showFieldLines = !state.showFieldLines;
  render2d();
  renderOverlaySummary();
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

function sourceReadout(source, key, label, value) {
  return `
    <div class="source-readout" data-testid="source-readout-${source.id}-${key}">
      <span>${label}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function readonlyPointSourceCard(source, label) {
  const zReadout = state.mode === "2D"
    ? ""
    : sourceReadout(source, "position-z", "位置 z / cm", formatCentimeters(source.position.z));
  return `
    <article
      class="source-card"
      data-testid="source-card-${source.id}"
      data-source-readonly="true"
    >
      <div class="source-card-heading">
        <strong>${label}</strong>
        <button class="source-delete-button" type="button" data-source-id="${source.id}" title="移除此源">移除</button>
        <span>${KIND_LABELS[source.kind] ?? source.kind}</span>
      </div>
      <div class="source-readout-grid">
        ${sourceReadout(source, "position-x", "位置 x / cm", formatCentimeters(source.position.x))}
        ${sourceReadout(source, "position-y", "位置 y / cm", formatCentimeters(source.position.y))}
        ${zReadout}
        ${sourceReadout(source, "charge-c", "电荷量 C", formatNumber(source.charge_c, 4))}
      </div>
    </article>
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
      if (source.kind === "point") {
        return readonlyPointSourceCard(source, label);
      }
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
  const markerRadius = POINT_VISUAL_RADIUS_CM;
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
        data-display-radius-cm="${POINT_VISUAL_RADIUS_CM}"
        data-visual-radius-cm="${POINT_VISUAL_RADIUS_CM}"
        data-physics-model="ideal-point"
        data-physics-center="position"
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

function sourceChargeSamples2d(source) {
  const charge = sourceChargeValue(source);
  if (!Number.isFinite(charge) || Math.abs(charge) < 1e-30 || !source.position) {
    return [];
  }

  if (source.kind === "line_segment") {
    const segmentCount = 16;
    const directionMagnitude = Math.hypot(source.orientation.x, source.orientation.y);
    const directionX = directionMagnitude > 1e-12 ? source.orientation.x / directionMagnitude : 1;
    const directionY = directionMagnitude > 1e-12 ? source.orientation.y / directionMagnitude : 0;
    return Array.from({ length: segmentCount }, (_, index) => {
      const t = (index + 0.5) / segmentCount;
      return {
        x: source.position.x + directionX * source.length_m * t,
        y: source.position.y + directionY * source.length_m * t,
        charge: charge / segmentCount,
      };
    });
  }

  if (source.kind === "ring") {
    const sampleCount = 24;
    return Array.from({ length: sampleCount }, (_, index) => {
      const angle = (Math.PI * 2 * index) / sampleCount;
      return {
        x: source.position.x + Math.cos(angle) * source.radius_m,
        y: source.position.y + Math.sin(angle) * source.radius_m,
        charge: charge / sampleCount,
      };
    });
  }

  if (source.kind === "disk") {
    const ringCount = 3;
    const samples = [{ x: source.position.x, y: source.position.y, weight: 1 }];
    for (let ringIndex = 1; ringIndex <= ringCount; ringIndex += 1) {
      const radius = source.radius_m * (ringIndex / ringCount);
      const sampleCount = ringIndex * 12;
      for (let index = 0; index < sampleCount; index += 1) {
        const angle = (Math.PI * 2 * index) / sampleCount;
        samples.push({
          x: source.position.x + Math.cos(angle) * radius,
          y: source.position.y + Math.sin(angle) * radius,
          weight: ringIndex,
        });
      }
    }
    const totalWeight = samples.reduce((sum, sample) => sum + sample.weight, 0);
    return samples.map((sample) => ({
      x: sample.x,
      y: sample.y,
      charge: (charge * sample.weight) / totalWeight,
    }));
  }

  if (source.kind === "infinite_plane" || source.kind === "spherical_shell") {
    return [];
  }

  return [{ x: source.position.x, y: source.position.y, charge }];
}

function electricField2dAt(x, y, fieldSamples) {
  return fieldSamples.reduce(
    (field, sample) => {
      const dx = x - sample.x;
      const dy = y - sample.y;
      const distanceSq = dx * dx + dy * dy;
      if (distanceSq < FIELD_LINE_SINGULARITY_RADIUS_M * FIELD_LINE_SINGULARITY_RADIUS_M) {
        return field;
      }
      const invDistanceCubed = 1 / (distanceSq * Math.sqrt(distanceSq));
      return {
        x: field.x + sample.charge * dx * invDistanceCubed,
        y: field.y + sample.charge * dy * invDistanceCubed,
      };
    },
    { x: 0, y: 0 },
  );
}

function fieldLineDirectionAt(x, y, traceDirection, fieldSamples) {
  const field = electricField2dAt(x, y, fieldSamples);
  const magnitude = Math.hypot(field.x, field.y);
  if (!Number.isFinite(magnitude) || magnitude < FIELD_LINE_MIN_FIELD) {
    return null;
  }
  return {
    x: (field.x / magnitude) * traceDirection,
    y: (field.y / magnitude) * traceDirection,
    magnitude,
  };
}

function rk4FieldLineStep(x, y, traceDirection, fieldSamples, stepSize) {
  const k1 = fieldLineDirectionAt(x, y, traceDirection, fieldSamples);
  if (!k1) {
    return null;
  }
  const halfStep = stepSize / 2;
  const k2 = fieldLineDirectionAt(
    x + k1.x * halfStep,
    y + k1.y * halfStep,
    traceDirection,
    fieldSamples,
  );
  if (!k2) {
    return null;
  }
  const k3 = fieldLineDirectionAt(
    x + k2.x * halfStep,
    y + k2.y * halfStep,
    traceDirection,
    fieldSamples,
  );
  if (!k3) {
    return null;
  }
  const k4 = fieldLineDirectionAt(
    x + k3.x * stepSize,
    y + k3.y * stepSize,
    traceDirection,
    fieldSamples,
  );
  if (!k4) {
    return null;
  }

  return {
    x: x + (stepSize / 6) * (k1.x + 2 * k2.x + 2 * k3.x + k4.x),
    y: y + (stepSize / 6) * (k1.y + 2 * k2.y + 2 * k3.y + k4.y),
    direction: k1,
    stepSize,
  };
}

function fieldLineSeedSources2d() {
  const chargedSources = state.scene.sources.filter((source) => Math.abs(sourceChargeValue(source)) > 1e-30);
  const pointSources = chargedSources.filter((source) => source.kind === "point");
  if (pointSources.length > 0) {
    return pointSources;
  }
  const positiveSources = chargedSources.filter((source) => sourceChargeValue(source) > 0 && source.position);
  return positiveSources.length > 0 ? positiveSources : chargedSources.filter((source) => source.position);
}

function fieldLineStartRadiusMeters(source) {
  if (source.kind === "point") {
    return FIELD_LINE_START_RADIUS_M;
  }
  return Math.max(FIELD_LINE_START_RADIUS_M, sourceWorldRadius(source) + 0.008);
}

function fieldLineTerminalRadiusMeters(source) {
  if (source.kind === "point") {
    return fieldLineStartRadiusMeters(source) + FIELD_LINE_ENDPOINT_MARGIN_M;
  }
  return Math.max(FIELD_LINE_START_RADIUS_M, sourceWorldRadius(source) + FIELD_LINE_ENDPOINT_MARGIN_M);
}

function isInsideFieldLineBounds(x, y, bounds) {
  const margin = FIELD_LINE_MAX_STEP_M * 2;
  return (
    x >= bounds.minX - margin &&
    x <= bounds.maxX + margin &&
    y >= bounds.minY - margin &&
    y <= bounds.maxY + margin
  );
}

function fieldLineTerminalAt(x, y, seedSource) {
  let nearestTerminal = null;
  for (const source of state.scene.sources) {
    if (
      source.id === seedSource.id ||
      source.kind !== "point" ||
      !source.position ||
      Math.abs(sourceChargeValue(source)) <= 1e-30
    ) {
      continue;
    }
    const radius = fieldLineTerminalRadiusMeters(source);
    const distance = Math.hypot(x - source.position.x, y - source.position.y);
    if (distance > radius) {
      continue;
    }
    if (!nearestTerminal || distance < nearestTerminal.distance) {
      nearestTerminal = { source, distance };
    }
  }
  return nearestTerminal;
}

function isNearExistingFieldLinePoint(x, y, points) {
  return points.slice(0, -8).some((point) => (
    Math.hypot(x - point.x, y - point.y) < FIELD_LINE_SELF_APPROACH_M
  ));
}

function isNearFieldLineCharge(x, y) {
  return state.scene.sources.some((source) => (
    source.kind === "point" &&
    source.position &&
    Math.abs(sourceChargeValue(source)) > 1e-30 &&
    Math.hypot(x - source.position.x, y - source.position.y) <= FIELD_LINE_CHARGE_CLEARANCE_RADIUS_M
  ));
}

function fieldLineSegmentMidpoint(start, end) {
  return {
    x: (start.x + end.x) / 2,
    y: (start.y + end.y) / 2,
  };
}

function fieldLineOrientation(a, b, c) {
  return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}

function fieldLinePointOnSegment(point, start, end) {
  const tolerance = 1e-10;
  return (
    point.x >= Math.min(start.x, end.x) - tolerance &&
    point.x <= Math.max(start.x, end.x) + tolerance &&
    point.y >= Math.min(start.y, end.y) - tolerance &&
    point.y <= Math.max(start.y, end.y) + tolerance
  );
}

function fieldLineSegmentsIntersect(a, b, c, d) {
  const boxSeparated =
    Math.max(a.x, b.x) < Math.min(c.x, d.x) ||
    Math.max(c.x, d.x) < Math.min(a.x, b.x) ||
    Math.max(a.y, b.y) < Math.min(c.y, d.y) ||
    Math.max(c.y, d.y) < Math.min(a.y, b.y);
  if (boxSeparated) {
    return false;
  }

  const o1 = fieldLineOrientation(a, b, c);
  const o2 = fieldLineOrientation(a, b, d);
  const o3 = fieldLineOrientation(c, d, a);
  const o4 = fieldLineOrientation(c, d, b);
  const tolerance = 1e-12;

  if (
    ((o1 > tolerance && o2 < -tolerance) || (o1 < -tolerance && o2 > tolerance)) &&
    ((o3 > tolerance && o4 < -tolerance) || (o3 < -tolerance && o4 > tolerance))
  ) {
    return true;
  }

  return (
    (Math.abs(o1) <= tolerance && fieldLinePointOnSegment(c, a, b)) ||
    (Math.abs(o2) <= tolerance && fieldLinePointOnSegment(d, a, b)) ||
    (Math.abs(o3) <= tolerance && fieldLinePointOnSegment(a, c, d)) ||
    (Math.abs(o4) <= tolerance && fieldLinePointOnSegment(b, c, d))
  );
}

function fieldLinePointToSegmentDistance(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSq = dx * dx + dy * dy;
  if (lengthSq <= 1e-18) {
    return Math.hypot(point.x - start.x, point.y - start.y);
  }
  const projection = ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSq;
  const t = Math.max(0, Math.min(1, projection));
  return Math.hypot(point.x - (start.x + dx * t), point.y - (start.y + dy * t));
}

function fieldLineSegmentDistance(a, b, c, d) {
  if (fieldLineSegmentsIntersect(a, b, c, d)) {
    return 0;
  }
  return Math.min(
    fieldLinePointToSegmentDistance(a, c, d),
    fieldLinePointToSegmentDistance(b, c, d),
    fieldLinePointToSegmentDistance(c, a, b),
    fieldLinePointToSegmentDistance(d, a, b),
  );
}

function createFieldLineSpatialIndex() {
  return {
    cells: new Map(),
    nextSegmentId: 1,
  };
}

function fieldLineSpatialKey(cellX, cellY) {
  return `${cellX}:${cellY}`;
}

function fieldLineSegmentCells(start, end) {
  const padding = FIELD_LINE_ACCEPTED_CLEARANCE_M;
  const minX = Math.floor((Math.min(start.x, end.x) - padding) / FIELD_LINE_SPATIAL_CELL_M);
  const maxX = Math.floor((Math.max(start.x, end.x) + padding) / FIELD_LINE_SPATIAL_CELL_M);
  const minY = Math.floor((Math.min(start.y, end.y) - padding) / FIELD_LINE_SPATIAL_CELL_M);
  const maxY = Math.floor((Math.max(start.y, end.y) + padding) / FIELD_LINE_SPATIAL_CELL_M);
  const cells = [];
  for (let cellX = minX; cellX <= maxX; cellX += 1) {
    for (let cellY = minY; cellY <= maxY; cellY += 1) {
      cells.push(fieldLineSpatialKey(cellX, cellY));
    }
  }
  return cells;
}

function addAcceptedFieldLine(spatialIndex, points) {
  for (let index = 1; index < points.length; index += 1) {
    const start = points[index - 1];
    const end = points[index];
    const midpoint = fieldLineSegmentMidpoint(start, end);
    if (isNearFieldLineCharge(midpoint.x, midpoint.y)) {
      continue;
    }
    const segment = {
      id: spatialIndex.nextSegmentId,
      start,
      end,
      midpoint,
    };
    spatialIndex.nextSegmentId += 1;
    for (const cell of fieldLineSegmentCells(start, end)) {
      const segments = spatialIndex.cells.get(cell) || [];
      segments.push(segment);
      spatialIndex.cells.set(cell, segments);
    }
  }
}

function fieldLineConflictsWithAccepted(points, spatialIndex) {
  if (spatialIndex.cells.size === 0) {
    return false;
  }
  const checkedSegmentIds = new Set();
  for (let index = 1; index < points.length; index += 1) {
    const start = points[index - 1];
    const end = points[index];
    const midpoint = fieldLineSegmentMidpoint(start, end);
    if (isNearFieldLineCharge(midpoint.x, midpoint.y)) {
      continue;
    }
    checkedSegmentIds.clear();
    for (const cell of fieldLineSegmentCells(start, end)) {
      const segments = spatialIndex.cells.get(cell) || [];
      for (const segment of segments) {
        if (checkedSegmentIds.has(segment.id)) {
          continue;
        }
        checkedSegmentIds.add(segment.id);
        if (isNearFieldLineCharge(segment.midpoint.x, segment.midpoint.y)) {
          continue;
        }
        if (
          fieldLineSegmentsIntersect(start, end, segment.start, segment.end) ||
          fieldLineSegmentDistance(start, end, segment.start, segment.end) < FIELD_LINE_ACCEPTED_CLEARANCE_M
        ) {
          return true;
        }
      }
    }
  }
  return false;
}

function fieldLineCandidateAngle(index, lineCount, attempt) {
  if (attempt === 0) {
    return (Math.PI * 2 * index) / lineCount;
  }
  const direction = attempt % 2 === 1 ? 1 : -1;
  const offsetRank = Math.ceil(attempt / 2);
  const slotOffset = (direction * offsetRank) / ((FIELD_LINE_SEED_ATTEMPTS + 1) * lineCount);
  return Math.PI * 2 * (index / lineCount + slotOffset);
}

function roundFieldLineRayCount(value) {
  return Math.max(
    FIELD_LINE_MIN_CHARGE_RAYS,
    Math.min(FIELD_LINE_MAX_CHARGE_RAYS, Math.round(value / 4) * 4),
  );
}

function fieldLineChargeRayCount(seedSources) {
  const sourceCount = Math.max(1, seedSources.length);
  return roundFieldLineRayCount(FIELD_LINE_TARGET_TOTAL_CHARGE_RAYS / sourceCount);
}

function fieldLineTraceCandidates(seedSources) {
  const candidates = [];
  const rayCount = fieldLineChargeRayCount(seedSources);
  for (const [sourceOrder, source] of seedSources.entries()) {
    const charge = sourceChargeValue(source);
    const startRadius = fieldLineStartRadiusMeters(source);
    const traceDirection = charge >= 0 ? 1 : -1;
    for (let index = 0; index < rayCount; index += 1) {
      for (let attempt = 0; attempt < FIELD_LINE_SEED_ATTEMPTS; attempt += 1) {
        const angle = fieldLineCandidateAngle(index, rayCount, attempt);
        candidates.push({
          source,
          charge,
          traceDirection,
          seed: {
            x: source.position.x + Math.cos(angle) * startRadius,
            y: source.position.y + Math.sin(angle) * startRadius,
          },
          seedAttempt: attempt,
          seedIndex: index,
          seedCount: rayCount,
          sourceOrder,
          seedKind: "charge",
        });
      }
    }
  }

  return { candidates, rayCount };
}

function fieldLineEndpointClass(stopReason) {
  if (stopReason === "opposite-charge") {
    return "opposite-charge";
  }
  if (stopReason === "view-boundary") {
    return "infinity";
  }
  if (stopReason === "field-null") {
    return "zero-field";
  }
  return "numerical-artifact";
}

function fieldLineDisplayEndpoints(candidate, trace) {
  const source = candidate.source;
  const charge = candidate.charge;
  if (candidate.seedKind === "boundary") {
    if (trace.stopReason === "opposite-charge" && trace.terminalSourceId) {
      const terminalSource = fieldLineSourceById(trace.terminalSourceId);
      const terminalCharge = terminalSource ? sourceChargeValue(terminalSource) : 0;
      if (candidate.traceDirection < 0 && terminalCharge > 0) {
        return {
          startId: trace.terminalSourceId,
          endId: "infinity",
          topology: "charge-to-infinity",
        };
      }
      if (candidate.traceDirection > 0 && terminalCharge < 0) {
        return {
          startId: "infinity",
          endId: trace.terminalSourceId,
          topology: "infinity-to-charge",
        };
      }
    }
    return {
      startId: "infinity",
      endId: "infinity",
      topology: "infinity-to-infinity",
    };
  }
  if (trace.stopReason === "opposite-charge" && trace.terminalSourceId) {
    return charge >= 0
      ? {
          startId: source.id,
          endId: trace.terminalSourceId,
          topology: "charge-to-charge",
        }
      : {
          startId: trace.terminalSourceId,
          endId: source.id,
          topology: "charge-to-charge",
        };
  }
  if (trace.stopReason === "view-boundary") {
    return charge >= 0
      ? {
          startId: source.id,
          endId: "infinity",
          topology: "charge-to-infinity",
        }
      : {
          startId: "infinity",
          endId: source.id,
          topology: "infinity-to-charge",
        };
  }
  return {
    startId: source.id,
    endId: trace.terminalSourceId || "",
    topology: "artifact",
  };
}

function isRenderableFieldLine(trace, candidate) {
  if (candidate.seedKind === "boundary") {
    return trace.points.length >= FIELD_LINE_MIN_RENDER_POINTS && trace.stopReason === "opposite-charge";
  }
  return (
    trace.points.length >= FIELD_LINE_MIN_RENDER_POINTS &&
    (trace.stopReason === "opposite-charge" || trace.stopReason === "view-boundary")
  );
}

function traceFieldLine(
  seed,
  seedSource,
  traceDirection,
  fieldSamples,
  bounds,
  acceptedLineIndex,
  useConflictFilter,
) {
  const points = [seed];
  let x = seed.x;
  let y = seed.y;
  let previousDirection = null;
  let stopReason = "max-steps";
  let terminalSourceId = "";
  let stepSize = FIELD_LINE_BASE_STEP_M;

  for (let step = 0; step < FIELD_LINE_MAX_STEPS; step += 1) {
    let next = null;
    let directionDot = 1;
    let blockedByReversal = false;
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const fullStep = rk4FieldLineStep(x, y, traceDirection, fieldSamples, stepSize);
      if (!fullStep) {
        break;
      }
      next = fullStep;
      directionDot = previousDirection
        ? previousDirection.x * fullStep.direction.x + previousDirection.y * fullStep.direction.y
        : 1;
      if (directionDot < FIELD_LINE_REVERSAL_DOT_LIMIT) {
        blockedByReversal = true;
        break;
      }
      if (stepSize > FIELD_LINE_MIN_STEP_M) {
        const halfStepSize = stepSize / 2;
        const halfStep = rk4FieldLineStep(x, y, traceDirection, fieldSamples, halfStepSize);
        const secondHalfStep = halfStep
          ? rk4FieldLineStep(halfStep.x, halfStep.y, traceDirection, fieldSamples, halfStepSize)
          : null;
        if (!secondHalfStep) {
          stepSize = Math.max(FIELD_LINE_MIN_STEP_M, stepSize * 0.5);
          continue;
        }
        const stepError = Math.hypot(fullStep.x - secondHalfStep.x, fullStep.y - secondHalfStep.y);
        const allowedError = Math.max(FIELD_LINE_ADAPT_ERROR_MIN_M, stepSize * FIELD_LINE_ADAPT_ERROR_FRACTION);
        if (stepError > allowedError) {
          stepSize = Math.max(FIELD_LINE_MIN_STEP_M, stepSize * 0.5);
          continue;
        }
        next = {
          ...secondHalfStep,
          direction: fullStep.direction,
          stepSize,
        };
      }
      if (directionDot < FIELD_LINE_ADAPT_RETRY_DOT && stepSize > FIELD_LINE_MIN_STEP_M) {
        stepSize = Math.max(FIELD_LINE_MIN_STEP_M, stepSize * 0.5);
        continue;
      }
      break;
    }
    if (!next) {
      stopReason = "field-null";
      break;
    }
    if (blockedByReversal) {
      stopReason = "direction-reversal";
      break;
    }

    if (isNearExistingFieldLinePoint(next.x, next.y, points)) {
      stopReason = "self-approach";
      break;
    }
    if (
      useConflictFilter &&
      acceptedLineIndex &&
      fieldLineConflictsWithAccepted([{ x, y }, { x: next.x, y: next.y }], acceptedLineIndex)
    ) {
      stopReason = "line-conflict";
      break;
    }

    x = next.x;
    y = next.y;
    points.push({ x, y });
    previousDirection = next.direction;

    if (points.length >= FIELD_LINE_MAX_POINTS) {
      stopReason = "point-budget";
      break;
    }
    if (directionDot > FIELD_LINE_ADAPT_GROW_DOT) {
      stepSize = Math.min(FIELD_LINE_MAX_STEP_M, stepSize * 1.35);
    } else if (directionDot < FIELD_LINE_ADAPT_SHRINK_DOT) {
      stepSize = Math.max(FIELD_LINE_MIN_STEP_M, stepSize * 0.7);
    }

    if (!isInsideFieldLineBounds(x, y, bounds)) {
      stopReason = "view-boundary";
      break;
    }
    const terminal = fieldLineTerminalAt(x, y, seedSource);
    if (terminal) {
      const terminalSign = traceDirection > 0 ? -1 : 1;
      const sourceSign = sourceChargeValue(terminal.source) >= 0 ? 1 : -1;
      stopReason = sourceSign === terminalSign ? "opposite-charge" : "same-charge";
      terminalSourceId = terminal.source.id;
      break;
    }
  }

  return { points, stopReason, terminalSourceId };
}

function fieldLinePath(points) {
  const viewportPoints = points.map((point) => mapToViewport(point.x, point.y));
  if (viewportPoints.length <= 2) {
    return viewportPoints
      .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(3)} ${point.y.toFixed(3)}`)
      .join(" ");
  }

  const tangents = viewportPoints.map((point, index) => {
    const previous = viewportPoints[Math.max(0, index - 1)];
    const next = viewportPoints[Math.min(viewportPoints.length - 1, index + 1)];
    const previousDistance = Math.hypot(point.x - previous.x, point.y - previous.y);
    const nextDistance = Math.hypot(next.x - point.x, next.y - point.y);
    const tangentX = next.x - previous.x;
    const tangentY = next.y - previous.y;
    const tangentLength = Math.hypot(tangentX, tangentY);
    if (tangentLength <= 1e-9) {
      return { x: 0, y: 0 };
    }
    const controlLength = Math.min(previousDistance || nextDistance, nextDistance || previousDistance) *
      FIELD_LINE_CURVE_CONTROL_FACTOR;
    return {
      x: (tangentX / tangentLength) * controlLength,
      y: (tangentY / tangentLength) * controlLength,
    };
  });
  const commands = [`M ${viewportPoints[0].x.toFixed(3)} ${viewportPoints[0].y.toFixed(3)}`];
  for (let index = 0; index < viewportPoints.length - 1; index += 1) {
    const start = viewportPoints[index];
    const end = viewportPoints[index + 1];
    const controlStart = {
      x: start.x + tangents[index].x,
      y: start.y + tangents[index].y,
    };
    const controlEnd = {
      x: end.x - tangents[index + 1].x,
      y: end.y - tangents[index + 1].y,
    };
    commands.push(
      `C ${controlStart.x.toFixed(3)} ${controlStart.y.toFixed(3)} ` +
      `${controlEnd.x.toFixed(3)} ${controlEnd.y.toFixed(3)} ` +
      `${end.x.toFixed(3)} ${end.y.toFixed(3)}`,
    );
  }
  return commands.join(" ");
}

function fieldLinePointTangent(points, index) {
  const previous = points[Math.max(0, index - 1)];
  const next = points[Math.min(points.length - 1, index + 1)];
  const directionX = next.x - previous.x;
  const directionY = next.y - previous.y;
  const directionLength = Math.hypot(directionX, directionY);
  if (directionLength <= 1e-12) {
    return null;
  }
  return {
    x: directionX / directionLength,
    y: directionY / directionLength,
  };
}

function fieldLineArrowPoint(points) {
  const anchorIndex = points.findIndex((point) => point.fieldLineArrowAnchor === true);
  if (anchorIndex >= 0) {
    const tangent = fieldLinePointTangent(points, anchorIndex);
    if (tangent) {
      return {
        point: points[anchorIndex],
        directionX: tangent.x,
        directionY: tangent.y,
      };
    }
  }

  const fallbackIndex = Math.max(1, Math.min(points.length - 2, Math.floor(points.length / 2)));
  const tangent = fieldLinePointTangent(points, fallbackIndex);
  return tangent
    ? {
        point: points[fallbackIndex],
        directionX: tangent.x,
        directionY: tangent.y,
      }
    : null;
}

function fieldLineArrowFraction(entry) {
  const sourceOffset = (((entry.seedIndex || 0) % 7) - 3) * 0.03;
  const topologyOffset = entry.topology === "infinity-to-charge"
    ? 0.16
    : entry.topology === "charge-to-infinity"
      ? -0.08
      : 0;
  const rawFraction = FIELD_LINE_ARROW_FRACTION_BASE + topologyOffset +
    sourceOffset * FIELD_LINE_ARROW_FRACTION_SPREAD / 0.18;
  return Math.max(
    FIELD_LINE_ARROW_FRACTION_MIN,
    Math.min(FIELD_LINE_ARROW_FRACTION_MAX, rawFraction),
  );
}

function fieldLinePointsWithArrowAnchor(points, entry) {
  if (points.length < 2) {
    return points;
  }
  let totalLength = 0;
  for (let index = 1; index < points.length; index += 1) {
    totalLength += Math.hypot(points[index].x - points[index - 1].x, points[index].y - points[index - 1].y);
  }
  if (totalLength <= 1e-12) {
    return points;
  }
  const targetDistance = totalLength * fieldLineArrowFraction(entry);
  let traveled = 0;

  for (let index = 1; index < points.length; index += 1) {
    const start = points[index - 1];
    const end = points[index];
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const segmentLength = Math.hypot(dx, dy);
    if (segmentLength <= 1e-12) {
      continue;
    }
    if (traveled + segmentLength >= targetDistance) {
      const t = Math.max(0, Math.min(1, (targetDistance - traveled) / segmentLength));
      const anchor = {
        x: start.x + dx * t,
        y: start.y + dy * t,
        fieldLineArrowAnchor: true,
      };
      const anchoredPoints = [...points];
      anchoredPoints.splice(index, 0, anchor);
      return anchoredPoints;
    }
    traveled += segmentLength;
  }
  return points;
}

function smoothFieldLineDisplayPoints(points, source) {
  if (points.length < 5 || FIELD_LINE_DISPLAY_SMOOTHING_ITERATIONS <= 0) {
    return points;
  }
  let smoothedPoints = points.map((point) => ({ ...point }));
  const sourceX = source.position.x;
  const sourceY = source.position.y;
  let arrowAnchorIndex = smoothedPoints.findIndex((point) => point.fieldLineArrowAnchor === true);
  let closestArrowDistance = Infinity;
  if (arrowAnchorIndex < 0) {
    arrowAnchorIndex = 0;
    for (let index = 0; index < smoothedPoints.length; index += 1) {
      const distance = Math.hypot(smoothedPoints[index].x - sourceX, smoothedPoints[index].y - sourceY);
      if (distance < closestArrowDistance) {
        closestArrowDistance = distance;
        arrowAnchorIndex = index;
      }
    }
  }

  for (let iteration = 0; iteration < FIELD_LINE_DISPLAY_SMOOTHING_ITERATIONS; iteration += 1) {
    smoothedPoints = smoothedPoints.map((point, index) => {
      if (
        index === 0 ||
        index === smoothedPoints.length - 1 ||
        index === arrowAnchorIndex ||
        isNearFieldLineCharge(point.x, point.y)
      ) {
        return point;
      }
      const previous = smoothedPoints[index - 1];
      const next = smoothedPoints[index + 1];
      return {
        x:
          previous.x * FIELD_LINE_DISPLAY_SMOOTHING_WEIGHT +
          point.x * (1 - FIELD_LINE_DISPLAY_SMOOTHING_WEIGHT * 2) +
          next.x * FIELD_LINE_DISPLAY_SMOOTHING_WEIGHT,
        y:
          previous.y * FIELD_LINE_DISPLAY_SMOOTHING_WEIGHT +
          point.y * (1 - FIELD_LINE_DISPLAY_SMOOTHING_WEIGHT * 2) +
          next.y * FIELD_LINE_DISPLAY_SMOOTHING_WEIGHT,
      };
    });
  }
  return smoothedPoints;
}

function fieldLineSourceById(sourceId) {
  if (!sourceId || sourceId === "infinity") {
    return null;
  }
  return state.scene.sources.find((source) => source.id === sourceId) || null;
}

function fieldLineDisplayRadiusMeters(source) {
  if (!source) {
    return 0;
  }
  return source.kind === "point"
    ? FIELD_LINE_START_RADIUS_M
    : Math.max(FIELD_LINE_START_RADIUS_M, sourceWorldRadius(source));
}

function fieldLinePointOnSourceSurface(source, adjacentPoint) {
  const radius = fieldLineDisplayRadiusMeters(source);
  const dx = adjacentPoint.x - source.position.x;
  const dy = adjacentPoint.y - source.position.y;
  const distance = Math.hypot(dx, dy);
  if (distance <= 1e-12) {
    return {
      x: source.position.x + radius,
      y: source.position.y,
    };
  }
  return {
    x: source.position.x + (dx / distance) * radius,
    y: source.position.y + (dy / distance) * radius,
  };
}

function snapFieldLineEndpointsToSources(points, entry) {
  if (points.length < 2) {
    return points;
  }
  const snappedPoints = points.map((point) => ({ ...point }));
  const startSource = fieldLineSourceById(entry.fieldStartId);
  const endSource = fieldLineSourceById(entry.fieldEndId);
  if (startSource) {
    snappedPoints[0] = fieldLinePointOnSourceSurface(startSource, snappedPoints[1]);
  }
  if (endSource) {
    const lastIndex = snappedPoints.length - 1;
    snappedPoints[lastIndex] = fieldLinePointOnSourceSurface(endSource, snappedPoints[lastIndex - 1]);
  }
  return snappedPoints;
}

function fieldLineArrowSource(entry) {
  return fieldLineSourceById(entry.fieldStartId) ||
    fieldLineSourceById(entry.fieldEndId) ||
    fieldLineSourceById(entry.source.id);
}

function fieldLineDirectionQuality(points, fieldSamples) {
  if (points.length < 2) {
    return { valid: false, score: -Infinity, minDot: -1 };
  }
  let minDot = 1;
  let totalDot = 0;
  let sampleCount = 0;
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const segmentX = current.x - previous.x;
    const segmentY = current.y - previous.y;
    const segmentLength = Math.hypot(segmentX, segmentY);
    if (segmentLength <= 1e-12) {
      continue;
    }
    const midX = (previous.x + current.x) / 2;
    const midY = (previous.y + current.y) / 2;
    if (isNearFieldLineCharge(midX, midY)) {
      continue;
    }
    const field = electricField2dAt(midX, midY, fieldSamples);
    const fieldMagnitude = Math.hypot(field.x, field.y);
    if (fieldMagnitude <= FIELD_LINE_MIN_FIELD) {
      return { valid: false, score: -Infinity, minDot: -1 };
    }
    const dot = (segmentX / segmentLength) * (field.x / fieldMagnitude) +
      (segmentY / segmentLength) * (field.y / fieldMagnitude);
    minDot = Math.min(minDot, dot);
    totalDot += dot;
    sampleCount += 1;
  }
  if (sampleCount === 0) {
    return { valid: true, score: 1, minDot: 1 };
  }
  const averageDot = totalDot / sampleCount;
  return {
    valid: minDot >= FIELD_LINE_DIRECTION_DOT_MIN,
    score: averageDot,
    minDot,
  };
}

function prepareDisplayFieldLineEntry(entry, fieldSamples) {
  const arrowSource = fieldLineArrowSource(entry);
  if (!arrowSource || !arrowSource.position || entry.topology === "infinity-to-infinity") {
    return null;
  }
  const snappedPoints = snapFieldLineEndpointsToSources(entry.renderPoints, entry);
  const arrowFraction = fieldLineArrowFraction(entry);
  const anchoredPoints = fieldLinePointsWithArrowAnchor(snappedPoints, entry);
  const displayPoints = smoothFieldLineDisplayPoints(anchoredPoints, arrowSource);
  const directionQuality = fieldLineDirectionQuality(displayPoints, fieldSamples);
  if (!directionQuality.valid) {
    return null;
  }
  return {
    ...entry,
    arrowSource,
    displayPoints,
    qualityScore: directionQuality.score,
    minDirectionDot: directionQuality.minDot,
    arrowFraction,
  };
}

function fieldLineArrowMarkup(points, entry, fieldSamples, scale) {
  const arrow = fieldLineArrowPoint(points);
  if (!arrow) {
    return "";
  }
  const field = electricField2dAt(arrow.point.x, arrow.point.y, fieldSamples);
  const fieldMagnitude = Math.hypot(field.x, field.y);
  let worldDirection = fieldMagnitude > FIELD_LINE_MIN_FIELD
    ? { x: field.x / fieldMagnitude, y: field.y / fieldMagnitude }
    : { x: arrow.directionX, y: arrow.directionY };
  const tangentDot = worldDirection.x * arrow.directionX + worldDirection.y * arrow.directionY;
  if (tangentDot < 0) {
    worldDirection = { x: arrow.directionX, y: arrow.directionY };
  }
  const viewportDirection = {
    x: worldDirection.x,
    y: -worldDirection.y,
  };
  const directionMagnitude = Math.hypot(viewportDirection.x, viewportDirection.y);
  if (directionMagnitude <= 1e-12) {
    return "";
  }
  const unit = {
    x: viewportDirection.x / directionMagnitude,
    y: viewportDirection.y / directionMagnitude,
  };
  const normal = { x: -unit.y, y: unit.x };
  const tip = mapToViewport(arrow.point.x, arrow.point.y);
  const averageUnitsPerPx = (scale.xUnitsPerPx + scale.yUnitsPerPx) / 2;
  const arrowLength = FIELD_LINE_ARROW_LENGTH_PX * averageUnitsPerPx;
  const arrowWidth = FIELD_LINE_ARROW_WIDTH_PX * averageUnitsPerPx;
  const baseCenter = {
    x: tip.x - unit.x * arrowLength,
    y: tip.y - unit.y * arrowLength,
  };
  const left = {
    x: baseCenter.x + normal.x * arrowWidth * 0.5,
    y: baseCenter.y + normal.y * arrowWidth * 0.5,
  };
  const right = {
    x: baseCenter.x - normal.x * arrowWidth * 0.5,
    y: baseCenter.y - normal.y * arrowWidth * 0.5,
  };
  return `
    <path
      class="field-line-arrow"
      data-testid="field-line-arrow-2d"
      data-arrow-on-line="true"
      data-arrow-size-px="${FIELD_LINE_ARROW_LENGTH_PX}"
      data-arrow-direction="field"
      data-arrow-placement="arc-fraction"
      data-arrow-fraction="${entry.arrowFraction.toFixed(3)}"
      d="M ${tip.x.toFixed(3)} ${tip.y.toFixed(3)} L ${left.x.toFixed(3)} ${left.y.toFixed(3)} L ${right.x.toFixed(3)} ${right.y.toFixed(3)} Z"
    ></path>
  `;
}

function fieldLineCacheKey(seedSources) {
  return JSON.stringify({
    sources: state.scene.sources,
    seedSourceIds: seedSources.map((source) => source.id),
    displayStrategy: FIELD_LINE_DISPLAY_STRATEGY,
    targetTotalChargeRays: FIELD_LINE_TARGET_TOTAL_CHARGE_RAYS,
    minChargeRays: FIELD_LINE_MIN_CHARGE_RAYS,
    maxChargeRays: FIELD_LINE_MAX_CHARGE_RAYS,
    displayMaxCount: FIELD_LINE_DISPLAY_MAX_COUNT,
    baseStep: FIELD_LINE_BASE_STEP_M,
    minStep: FIELD_LINE_MIN_STEP_M,
    maxStep: FIELD_LINE_MAX_STEP_M,
    maxPoints: FIELD_LINE_MAX_POINTS,
  });
}

function fieldLineOppositePairKey(entry) {
  return entry.topology === "charge-to-charge"
    ? `${entry.fieldStartId}->${entry.fieldEndId}`
    : "";
}

function fieldLineDisplayPointOrder(candidate, trace, endpoints) {
  if (candidate.seedKind === "boundary") {
    return endpoints.startId === "infinity" ? trace.points : [...trace.points].reverse();
  }
  return candidate.charge >= 0 ? trace.points : [...trace.points].reverse();
}

function tryAcceptDisplayFieldLine(entry, acceptedLineIndex) {
  if (fieldLineConflictsWithAccepted(entry.displayPoints, acceptedLineIndex)) {
    return false;
  }
  addAcceptedFieldLine(acceptedLineIndex, entry.displayPoints);
  return true;
}

function sortFieldLineEntriesByUniformAngle(entries) {
  return [...entries].sort((a, b) => {
    if (a.seedAttempt !== b.seedAttempt) {
      return a.seedAttempt - b.seedAttempt;
    }
    if (a.seedIndex !== b.seedIndex) {
      return a.seedIndex - b.seedIndex;
    }
    if (a.sourceOrder !== b.sourceOrder) {
      return a.sourceOrder - b.sourceOrder;
    }
    if (Math.abs(b.qualityScore - a.qualityScore) > 1e-6) {
      return b.qualityScore - a.qualityScore;
    }
    return a.source.id.localeCompare(b.source.id);
  });
}

function selectDisplayFieldLineEntries(rawEntries, fieldSamples) {
  const acceptedLineIndex = createFieldLineSpatialIndex();
  const selectedEntries = [];
  const preparedEntries = [];
  const pairCounts = new Map();
  let lowQualityLineCount = 0;
  let dedupedLineCount = 0;
  let conflictRejectedLineCount = 0;

  for (const entry of rawEntries) {
    const displayEntry = prepareDisplayFieldLineEntry(entry, fieldSamples);
    if (!displayEntry) {
      lowQualityLineCount += 1;
      continue;
    }
    preparedEntries.push(displayEntry);
  }

  const candidateEntries = sortFieldLineEntriesByUniformAngle(preparedEntries);
  for (const entry of candidateEntries) {
    if (selectedEntries.length >= FIELD_LINE_DISPLAY_MAX_COUNT) {
      break;
    }
    const pairKey = fieldLineOppositePairKey(entry);
    if (
      pairKey &&
      (pairCounts.get(pairKey) || 0) >= FIELD_LINE_MAX_PAIR_DISPLAY_COUNT
    ) {
      dedupedLineCount += 1;
      continue;
    }
    if (tryAcceptDisplayFieldLine(entry, acceptedLineIndex)) {
      selectedEntries.push(entry);
      if (pairKey) {
        pairCounts.set(pairKey, (pairCounts.get(pairKey) || 0) + 1);
      }
    } else {
      conflictRejectedLineCount += 1;
    }
  }

  return {
    entries: selectedEntries,
    dedupedLineCount,
    conflictRejectedLineCount,
    lowQualityLineCount,
    pairedLineCount: selectedEntries.filter((entry) => entry.topology === "charge-to-charge").length,
  };
}

function computeFieldLineTraceResult(fieldSamples, seedSources) {
  const bounds = compute2dWorldBounds();
  const rawEntries = [];
  const { candidates, rayCount } = fieldLineTraceCandidates(seedSources, bounds);
  let rejectedLineCount = 0;
  for (const candidate of candidates) {
    const trace = traceFieldLine(
      candidate.seed,
      candidate.source,
      candidate.traceDirection,
      fieldSamples,
      bounds,
      null,
      false,
    );
    if (!isRenderableFieldLine(trace, candidate)) {
      rejectedLineCount += 1;
      continue;
    }
    const endpoints = fieldLineDisplayEndpoints(candidate, trace);
    const renderPoints = fieldLineDisplayPointOrder(candidate, trace, endpoints);
    rawEntries.push({
      source: candidate.source,
      charge: candidate.charge,
      endpointClass: fieldLineEndpointClass(trace.stopReason),
      fieldStartId: endpoints.startId,
      fieldEndId: endpoints.endId,
      topology: endpoints.topology,
      renderPoints,
      seedAttempt: candidate.seedAttempt,
      seedIndex: candidate.seedIndex,
      seedCount: candidate.seedCount,
      sourceOrder: candidate.sourceOrder,
      seedKind: candidate.seedKind,
      stopReason: trace.stopReason,
      terminalSourceId: trace.terminalSourceId,
    });
  }
  const displayResult = selectDisplayFieldLineEntries(rawEntries, fieldSamples);
  return {
    entries: displayResult.entries,
    rawLineCount: rawEntries.length,
    candidateLineCount: candidates.length,
    chargeRayCount: rayCount,
    rejectedLineCount,
    dedupedLineCount: displayResult.dedupedLineCount,
    displayConflictRejectedLineCount: displayResult.conflictRejectedLineCount,
    lowQualityLineCount: displayResult.lowQualityLineCount,
    pairedLineCount: displayResult.pairedLineCount,
    useConflictFilter: rawEntries.length > 1,
  };
}

function getFieldLineTraceResult(fieldSamples, seedSources) {
  const key = fieldLineCacheKey(seedSources);
  if (fieldLineTraceCache.key === key && fieldLineTraceCache.result) {
    return fieldLineTraceCache.result;
  }
  const result = computeFieldLineTraceResult(fieldSamples, seedSources);
  fieldLineTraceCache = { key, result };
  return result;
}

function renderFieldLines2d(scale) {
  if (!state.showFieldLines) {
    return '<g data-testid="field-line-layer" data-field-line-count="0" data-enabled="false"></g>';
  }

  const fieldSamples = state.scene.sources.flatMap((source) => sourceChargeSamples2d(source));
  const seedSources = fieldLineSeedSources2d();
  if (fieldSamples.length === 0 || seedSources.length === 0) {
    return '<g data-testid="field-line-layer" data-field-line-count="0" data-enabled="true"></g>';
  }

  const traceResult = getFieldLineTraceResult(fieldSamples, seedSources);
  const paths = [];
  const arrows = [];
  for (const entry of traceResult.entries) {
    const charge = entry.charge;
    const renderPoints = entry.displayPoints;
    const sourceSign = charge > 0 ? "positive" : charge < 0 ? "negative" : "boundary";
    paths.push(`
        <path
          class="field-line"
          data-testid="field-line-2d"
          data-source-id="${entry.source.id}"
          data-source-sign="${sourceSign}"
          data-field-start-id="${entry.fieldStartId}"
          data-field-end-id="${entry.fieldEndId}"
          data-field-topology="${entry.topology}"
          data-seed-kind="${entry.seedKind}"
          data-trace-method="adaptive-rk4"
          data-path-model="adaptive-rk4-spline"
          data-display-smoothing="weighted"
          data-endpoint-class="${entry.endpointClass}"
          data-terminal-source-id="${entry.terminalSourceId}"
          data-seed-attempt="${entry.seedAttempt}"
          data-seed-index="${entry.seedIndex}"
          data-stop-reason="${entry.stopReason}"
          data-point-count="${renderPoints.length}"
          data-direction-min-dot="${entry.minDirectionDot.toFixed(3)}"
          d="${fieldLinePath(renderPoints)}"
        ></path>
      `);
    arrows.push(fieldLineArrowMarkup(renderPoints, entry, fieldSamples, scale));
  }

  return `
    <g
      class="field-line-layer"
      data-testid="field-line-layer"
      data-field-line-count="${paths.length}"
      data-display-strategy="${FIELD_LINE_DISPLAY_STRATEGY}"
      data-candidates-per-point-charge="${traceResult.chargeRayCount}"
      data-target-total-charge-rays="${FIELD_LINE_TARGET_TOTAL_CHARGE_RAYS}"
      data-min-charge-rays="${FIELD_LINE_MIN_CHARGE_RAYS}"
      data-max-charge-rays="${FIELD_LINE_MAX_CHARGE_RAYS}"
      data-boundary-candidates-per-direction="0"
      data-boundary-candidate-count="0"
      data-display-max-line-count="${FIELD_LINE_DISPLAY_MAX_COUNT}"
      data-target-line-count="${FIELD_LINE_DISPLAY_MAX_COUNT}"
      data-candidate-line-count="${traceResult.candidateLineCount}"
      data-raw-line-count="${traceResult.rawLineCount}"
      data-rejected-line-count="${traceResult.rejectedLineCount}"
      data-display-deduped-line-count="${traceResult.dedupedLineCount}"
      data-display-conflict-rejected-line-count="${traceResult.displayConflictRejectedLineCount}"
      data-display-low-quality-line-count="${traceResult.lowQualityLineCount}"
      data-paired-line-count="${traceResult.pairedLineCount}"
      data-arrow-placement="arc-fraction"
      data-arrow-fraction-base="${FIELD_LINE_ARROW_FRACTION_BASE}"
      data-conflict-filter="${traceResult.useConflictFilter ? "display-spatial" : "off"}"
      data-enabled="true"
    >
      ${paths.join("")}
      ${arrows.join("")}
    </g>
  `;
}

function renderOverlay2d(scale) {
  return `
    <g data-testid="overlay-vector-layer" data-vector-count="0"></g>
    ${renderFieldLines2d(scale)}
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

function decimalPlacesForStep(step) {
  for (let precision = 0; precision <= 6; precision += 1) {
    const scale = 10 ** precision;
    if (Math.abs(Math.round(step * scale) - step * scale) < 1e-8) {
      return precision;
    }
  }
  return 6;
}

function formatAxisTick(value, precision = 0) {
  if (Math.abs(value) < 1e-10) {
    return "0";
  }
  if (precision === 0) {
    return value.toFixed(0);
  }
  return value.toFixed(precision).replace(/0+$/, "").replace(/\.$/, "");
}

function axisTickLabelPrecision(ticks, step) {
  for (let precision = decimalPlacesForStep(step); precision <= 6; precision += 1) {
    const labels = ticks.map((tick) => formatAxisTick(tick, precision));
    if (new Set(labels).size === labels.length) {
      return precision;
    }
  }
  return 6;
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
  const xTickLabelPrecision = axisTickLabelPrecision(xTickData.ticks, xTickData.step);
  const yTickLabelPrecision = axisTickLabelPrecision(yTickData.ticks, yTickData.step);
  const xTicks = xTickData.ticks
    .map((tick) => {
      const x = tick;
      const line = Math.abs(tick) < 1e-10
        ? ""
        : `<line stroke="${AXIS_X_COLOR}" x1="${x}" y1="${axisOrigin.y - tickHalfY}" x2="${x}" y2="${axisOrigin.y + tickHalfY}"></line>`;
      return `
        <g class="axis-tick axis-tick-x" data-testid="axis-tick-2d-x">
          ${line}
          <text x="${x}" y="${axisOrigin.y + tickHalfY + labelGapY}" style="font-size: ${fontSize}px; stroke-width: ${textStrokeWidth}px;" text-anchor="middle">${formatAxisTick(tick, xTickLabelPrecision)}</text>
        </g>
      `;
    })
    .join("");
  const yTicks = yTickData.ticks
    .map((tick) => {
      const y = -tick;
      const label = Math.abs(tick) < 1e-10 ? "" : formatAxisTick(tick, yTickLabelPrecision);
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
      data-x-tick-label-precision="${xTickLabelPrecision}"
      data-y-tick-label-precision="${yTickLabelPrecision}"
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
          <stop offset="24%" stop-color="#fda29b" stop-opacity="0.98"></stop>
          <stop offset="62%" stop-color="${POSITIVE_SOURCE_COLOR}" stop-opacity="1"></stop>
          <stop offset="100%" stop-color="#7a170f" stop-opacity="1"></stop>
        </radialGradient>
        <radialGradient id="source-point-negative-gradient" cx="32%" cy="28%" r="78%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="1"></stop>
          <stop offset="24%" stop-color="#8ec5ff" stop-opacity="0.98"></stop>
          <stop offset="62%" stop-color="${NEGATIVE_SOURCE_COLOR}" stop-opacity="1"></stop>
          <stop offset="100%" stop-color="#003f8c" stop-opacity="1"></stop>
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
      ${renderOverlay2d(scale)}
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
    ? `探针位置 (${formatCentimeters(state.probe.x)}, ${formatCentimeters(state.probe.y)}) cm`
    : `探针位置 (${formatCentimeters(state.probe.x)}, ${formatCentimeters(state.probe.y)}, ` +
      `${formatCentimeters(state.probe.z)}) cm`;
}

function renderResult() {
  qualityValue.textContent = state.quality;
  if (!state.lastResult) {
    solverStatus.textContent = state.scene.sources.length === 0 ? "等待源" : solverStatus.textContent;
    if (potentialValue) {
      potentialValue.textContent = "暂无";
    }
    fieldVectorValue.textContent = "暂无";
    fieldMagnitudeValue.textContent = "暂无";
    contributionList.innerHTML = "<li>还没有源贡献。</li>";
    warningList.innerHTML = "<li>暂无提示。</li>";
    return;
  }

  const sample = state.lastResult.samples[0];
  solverStatus.textContent = `已完成 (${state.lastResult.request_id})`;
  if (potentialValue) {
    potentialValue.textContent = `${formatNumber(sample.potential_v, 5)} V`;
  }
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
  if (state.showFieldLines) {
    const lineCount = view2d.querySelectorAll("[data-testid='field-line-2d']").length;
    overlayStatus.textContent = state.scene.sources.length === 0 ? "等待源" : `电场线 ${lineCount} 条`;
    overlaySummary.textContent = lineCount > 0
      ? "二维视图已显示电场线；方向按合电场追踪，箭头表示电场方向。"
      : "当前二维源不足以生成电场线。";
    return;
  }
  if (!state.overlayResult) {
    overlayStatus.textContent = state.scene.sources.length === 0 ? "等待源" : overlayStatus.textContent;
    overlaySummary.textContent = "点击“显示电场”后，二维视图会显示电场线。";
    return;
  }
  const magnitudes = state.overlayResult.samples.map((sample) => sample.field_magnitude_v_per_m);
  const minMagnitude = Math.min(...magnitudes);
  const maxMagnitude = Math.max(...magnitudes);
  overlayStatus.textContent = `已完成 (${state.overlayResult.request_id})`;
  overlaySummary.textContent =
    `已完成 ${state.overlayResult.sample_count} 个采样点；` +
    `|E| 范围 ${formatNumber(minMagnitude, 3)} 到 ${formatNumber(maxMagnitude, 3)} V/m。`;
}

function renderAll(options = {}) {
  renderPointSourceForm();
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
  if (potentialValue) {
    potentialValue.textContent = "暂无";
  }
  fieldVectorValue.textContent = "暂无";
  fieldMagnitudeValue.textContent = "暂无";
  contributionList.innerHTML = "<li>还没有源贡献。</li>";
  warningList.innerHTML = "<li>暂无提示。</li>";
  overlaySummary.textContent = "点击“显示电场”后，二维视图会显示电场线。";
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

function measureProbeFromInputs(event) {
  event.preventDefault();
  if (evaluationTimer) {
    window.clearTimeout(evaluationTimer);
    evaluationTimer = null;
  }
  setProbeFromInputs();
  requestSerial += 1;
  latestProbeRequestId = `ui-probe-${requestSerial}`;
  latestOverlayRequestId = `ui-overlay-manual-${requestSerial}`;
  const probeRequestId = latestProbeRequestId;
  const validationMessage = sceneValidationMessage();
  if (validationMessage) {
    solverStatus.textContent = validationMessage;
    return;
  }
  evaluateProbe(probeRequestId).catch((error) => {
    if (probeRequestId === latestProbeRequestId) {
      solverStatus.textContent = error.message;
    }
  });
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

pointSourceForm.addEventListener("submit", addPointSourceFromForm);
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
toggleFieldLinesButton.addEventListener("click", () => {
  toggleFieldLines();
  toggleFieldLinesButton.classList.toggle("active", state.showFieldLines);
  toggleFieldLinesButton.textContent = state.showFieldLines ? "隐藏电场" : "显示电场";
});
probeForm.addEventListener("submit", measureProbeFromInputs);
probeForm.addEventListener("input", () => {
  solverStatus.textContent = state.scene.sources.length === 0 ? "等待源" : "等待确定";
});
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
