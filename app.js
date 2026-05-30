import { evaluateField, getConfig, getPreset, listPresets } from "./api-client.js";
import { render3d, resize3d, stopAnimLoop } from "./renderers/view3d.js";

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
const VIEWPORT_AXIS_LIMIT_M = 10;
const VIEWPORT_METERS_TO_UNITS = 100;
const VIEWPORT_GRID_STEP_UNITS = 1;
const VIEWPORT_MIN_UNITS = -VIEWPORT_AXIS_LIMIT_M * VIEWPORT_METERS_TO_UNITS;
const VIEWPORT_SIZE_UNITS = VIEWPORT_AXIS_LIMIT_M * VIEWPORT_METERS_TO_UNITS * 2;
const VIEWPORT_MAX_UNITS = VIEWPORT_MIN_UNITS + VIEWPORT_SIZE_UNITS;
const VIEWPORT_MIN_ZOOM = 1;
const VIEWPORT_MAX_ZOOM = 80;
const MIN_VISIBLE_MARKER_RADIUS_UNITS = 1.5;
const OVERLAY_SAMPLE_STEPS = [-1, -0.5, 0, 0.5, 1];
const FIELD_LINE_SEEDS_PER_CHARGE = 20;
const FIELD_LINE_STEP_M = 0.018;
const FIELD_LINE_MAX_STEPS = 900;
const FIELD_LINE_SEED_RADIUS_M = 0.045;
const FIELD_LINE_TERMINATION_RADIUS_M = 0.045;
const FIELD_LINE_MIN_POINTS = 8;

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
  view2d: { centerX: 0, centerY: 0, zoom: 1 },
  showHeatmap: false,
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
let active2dDrag = null;
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
  state.mode = mode;
  button2d.classList.toggle("selected", mode === "2D");
  button2d.setAttribute("aria-pressed", mode === "2D" ? "true" : "false");
  button3d.classList.toggle("selected", mode === "3D");
  button3d.setAttribute("aria-pressed", mode === "3D" ? "true" : "false");
  modeLabel.textContent = mode;
  view2d.classList.toggle("hidden", mode !== "2D");
  view3d.classList.toggle("hidden", mode !== "3D");
  if (mode !== "3D") {
    stopAnimLoop();
  }
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
            <button class="source-delete-button" type="button" data-source-id="${source.id}" title="移除此源">移除</button>
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

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function clamp2dView() {
  state.view2d.zoom = clamp(state.view2d.zoom, VIEWPORT_MIN_ZOOM, VIEWPORT_MAX_ZOOM);
  const halfSpan = VIEWPORT_SIZE_UNITS / (2 * state.view2d.zoom);
  state.view2d.centerX = clamp(
    state.view2d.centerX,
    VIEWPORT_MIN_UNITS + halfSpan,
    VIEWPORT_MAX_UNITS - halfSpan,
  );
  state.view2d.centerY = clamp(
    state.view2d.centerY,
    VIEWPORT_MIN_UNITS + halfSpan,
    VIEWPORT_MAX_UNITS - halfSpan,
  );
}

function compute2dViewBox() {
  clamp2dView();
  const width = VIEWPORT_SIZE_UNITS / state.view2d.zoom;
  const height = VIEWPORT_SIZE_UNITS / state.view2d.zoom;
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

function renderSource2d(source) {
  const point = mapToViewport(source.position.x, source.position.y);
  const label = escapeHtml(source.label);
  if (source.kind === "line_segment") {
    const halfLength = radiusToViewport(source.length_m / 2);
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
    const radius = radiusToViewport(source.radius_m, MIN_VISIBLE_MARKER_RADIUS_UNITS);
    return `
      <g data-testid="source-${source.kind.replaceAll("_", "-")}-group-2d-${source.id}">
        <circle
          class="${className}"
          data-testid="source-${source.kind.replaceAll("_", "-")}-2d-${source.id}"
          cx="${point.x}"
          cy="${point.y}"
          r="${radius}"
        ></circle>
        <text x="${point.x + 9}" y="${point.y - 9}">${label}</text>
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
        r="1.5"
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

function pointChargeSources() {
  return state.scene.sources.filter(
    (source) => source.kind === "point" && Number.isFinite(source.charge_c) && source.charge_c !== 0,
  );
}

function pointChargeFieldAt(x, y, sources) {
  let ex = 0;
  let ey = 0;
  for (const source of sources) {
    const rx = x - source.position.x;
    const ry = y - source.position.y;
    const r2 = Math.max(rx * rx + ry * ry, FIELD_LINE_SEED_RADIUS_M ** 2);
    const invR3 = 1 / (r2 * Math.sqrt(r2));
    ex += source.charge_c * rx * invR3;
    ey += source.charge_c * ry * invR3;
  }
  return { x: ex, y: ey, magnitude: Math.hypot(ex, ey) };
}

function isNearCharge(point, charge) {
  return (
    Math.hypot(point.x - charge.position.x, point.y - charge.position.y) <=
    FIELD_LINE_TERMINATION_RADIUS_M
  );
}

function shouldStopFieldLine(point, originId, direction, sources) {
  if (
    point.x < -VIEWPORT_AXIS_LIMIT_M ||
    point.x > VIEWPORT_AXIS_LIMIT_M ||
    point.y < -VIEWPORT_AXIS_LIMIT_M ||
    point.y > VIEWPORT_AXIS_LIMIT_M
  ) {
    return true;
  }

  return sources.some((source) => {
    if (source.id === originId) {
      return false;
    }
    const targetSign = direction > 0 ? source.charge_c < 0 : source.charge_c > 0;
    return targetSign && isNearCharge(point, source);
  });
}

function traceFieldLine(seed, direction, sources, originId) {
  const points = [seed];
  let current = seed;
  for (let step = 0; step < FIELD_LINE_MAX_STEPS; step += 1) {
    const field = pointChargeFieldAt(current.x, current.y, sources);
    if (field.magnitude < 1e-30) {
      break;
    }
    const next = {
      x: current.x + direction * FIELD_LINE_STEP_M * (field.x / field.magnitude),
      y: current.y + direction * FIELD_LINE_STEP_M * (field.y / field.magnitude),
    };
    points.push(next);
    current = next;
    if (shouldStopFieldLine(current, originId, direction, sources)) {
      break;
    }
  }
  return points;
}

function fieldLinePath(points) {
  return points
    .map((point, index) => {
      const mapped = mapToViewport(point.x, point.y);
      return `${index === 0 ? "M" : "L"} ${mapped.x.toFixed(3)} ${mapped.y.toFixed(3)}`;
    })
    .join(" ");
}

function computeFieldLines() {
  const sources = pointChargeSources();
  if (sources.length === 0) {
    return [];
  }

  const positiveSources = sources.filter((source) => source.charge_c > 0);
  const seedSources = positiveSources.length > 0 ? positiveSources : sources;
  const direction = positiveSources.length > 0 ? 1 : -1;
  const lines = [];

  for (const source of seedSources) {
    for (let index = 0; index < FIELD_LINE_SEEDS_PER_CHARGE; index += 1) {
      const angle = (2 * Math.PI * index) / FIELD_LINE_SEEDS_PER_CHARGE;
      const seed = {
        x: source.position.x + Math.cos(angle) * FIELD_LINE_SEED_RADIUS_M,
        y: source.position.y + Math.sin(angle) * FIELD_LINE_SEED_RADIUS_M,
      };
      const points = traceFieldLine(seed, direction, sources, source.id);
      if (points.length >= FIELD_LINE_MIN_POINTS) {
        lines.push(points);
      }
    }
  }

  return lines;
}

function renderFieldLines2d() {
  const lines = computeFieldLines();
  if (lines.length === 0) {
    return '<g data-testid="field-line-layer" data-line-count="0"></g>';
  }
  const paths = lines
    .map((points) => `<path class="field-line" d="${fieldLinePath(points)}"></path>`)
    .join("");
  return `
    <g
      class="field-line-layer"
      data-testid="field-line-layer"
      data-line-count="${lines.length}"
    >
      ${paths}
    </g>
  `;
}

function render2d() {
  const sourceMarkup = state.scene.sources.map((source) => renderSource2d(source)).join("");
  const probe = mapToViewport(state.probe.x, state.probe.y);
  const viewBox = compute2dViewBox();
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
      <line
        class="axis-line"
        x1="${viewBox.minX}"
        y1="${axisOrigin.y}"
        x2="${viewBox.minX + viewBox.width}"
        y2="${axisOrigin.y}"
      ></line>
      <line
        class="axis-line"
        x1="${axisOrigin.x}"
        y1="${viewBox.minY}"
        x2="${axisOrigin.x}"
        y2="${viewBox.minY + viewBox.height}"
      ></line>
      ${renderHeatmap2d()}
      ${renderFieldLines2d()}
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

function viewportPointFromClient(clientX, clientY) {
  const svg = view2d.querySelector("svg");
  if (!svg) {
    return null;
  }
  const rect = svg.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    return null;
  }
  const viewBox = compute2dViewBox();
  return {
    x: viewBox.minX + ((clientX - rect.left) / rect.width) * viewBox.width,
    y: viewBox.minY + ((clientY - rect.top) / rect.height) * viewBox.height,
    normX: (clientX - rect.left) / rect.width,
    normY: (clientY - rect.top) / rect.height,
    viewBox,
  };
}

function zoom2dAt(clientX, clientY, deltaY) {
  const point = viewportPointFromClient(clientX, clientY);
  if (!point) {
    return;
  }
  const nextZoom = clamp(
    state.view2d.zoom * Math.exp(-deltaY * 0.0012),
    VIEWPORT_MIN_ZOOM,
    VIEWPORT_MAX_ZOOM,
  );
  const nextWidth = VIEWPORT_SIZE_UNITS / nextZoom;
  const nextHeight = VIEWPORT_SIZE_UNITS / nextZoom;
  state.view2d.zoom = nextZoom;
  state.view2d.centerX = point.x - (point.normX - 0.5) * nextWidth;
  state.view2d.centerY = point.y - (point.normY - 0.5) * nextHeight;
  clamp2dView();
  render2d();
}

function handle2dPointerDown(event) {
  if (state.mode !== "2D" || event.button !== 0) {
    return;
  }
  const viewBox = compute2dViewBox();
  active2dDrag = {
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

function handle2dPointerMove(event) {
  if (!active2dDrag || active2dDrag.pointerId !== event.pointerId) {
    return;
  }
  const rect = view2d.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    return;
  }
  const deltaX = ((event.clientX - active2dDrag.startX) / rect.width) * active2dDrag.width;
  const deltaY = ((event.clientY - active2dDrag.startY) / rect.height) * active2dDrag.height;
  state.view2d.centerX = active2dDrag.centerX - deltaX;
  state.view2d.centerY = active2dDrag.centerY - deltaY;
  clamp2dView();
  render2d();
}

function handle2dPointerUp(event) {
  if (!active2dDrag || active2dDrag.pointerId !== event.pointerId) {
    return;
  }
  active2dDrag = null;
  view2d.classList.remove("is-panning");
  if (view2d.hasPointerCapture(event.pointerId)) {
    view2d.releasePointerCapture(event.pointerId);
  }
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
  const fieldLineCount = computeFieldLines().length;
  overlaySummary.textContent =
    `二维箭头层采样 ${state.overlayResult.sample_count} 个点；` +
    `采样 |E| 范围 ${formatNumber(minMagnitude, 3)} 到 ${formatNumber(maxMagnitude, 3)} V/m。` +
    `点电荷电场线 ${fieldLineCount} 条。`;
}

function renderAll() {
  renderSourceList();
  render2d();
  renderProbe();
  if (state.mode === "3D") {
    render3d(view3d, state);
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
  overlaySummary.textContent = "加入源后，二维视图会显示采样电场箭头；点电荷还会显示实时电场线。";
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
qualitySelect.addEventListener("change", () => setQuality(qualitySelect.value));
view2d.addEventListener(
  "wheel",
  (event) => {
    if (state.mode !== "2D") {
      return;
    }
    event.preventDefault();
    zoom2dAt(event.clientX, event.clientY, event.deltaY);
  },
  { passive: false },
);
view2d.addEventListener("pointerdown", handle2dPointerDown);
view2d.addEventListener("pointermove", handle2dPointerMove);
view2d.addEventListener("pointerup", handle2dPointerUp);
view2d.addEventListener("pointercancel", handle2dPointerUp);
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
  if (state.mode !== "3D") {
    return;
  }
  resize3d(view3d, state);
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
