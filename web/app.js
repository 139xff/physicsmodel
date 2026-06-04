import { evaluateField, evaluateFieldLines, evaluateTrajectory, getComputeStatus, getConfig, getPreset, listPresets } from "./api-client.js";
import { render3d, resize3d, stopAnimLoop } from "./renderers/view3d.js?v=20260529-axis-labels-pan-preserve";

document.documentElement.classList.toggle("desktop-runtime", Boolean(window.emWorkbenchBridgeReady));

const runtimeStatus = document.querySelector("#runtime-status");
const computeBackend = document.querySelector("[data-testid='compute-backend']");
const computeWarmup = document.querySelector("[data-testid='compute-warmup']");
const sourceList = document.querySelector("#source-list");
const sourceCount = document.querySelector("[data-testid='source-count']");
const modeLabel = document.querySelector("[data-testid='mode-label']");
const view2d = document.querySelector("#view-2d");
const view3d = document.querySelector("#view-3d");
const button2d = document.querySelector("#view-2d-button");
const button3d = document.querySelector("#view-3d-button");
const panToolButton = document.querySelector("#pan-tool");
const toggleFieldLinesButton = document.querySelector("#toggle-field-lines");
const toggleEquipotentialLinesButton = document.querySelector("#toggle-equipotential-lines");
const addInfinitePlaneButton = document.querySelector("#add-infinite-plane");
const addSphericalShellButton = document.querySelector("#add-spherical-shell");
const pointSourceForm = document.querySelector("#point-source-form");
const pointSourceXInput = document.querySelector("#point-source-x");
const pointSourceYInput = document.querySelector("#point-source-y");
const pointSourceZInput = document.querySelector("#point-source-z");
const pointSourceZField = document.querySelector("#point-source-z-field");
const pointSourceChargeInput = document.querySelector("#point-source-charge");
const lineSegmentSourceForm = document.querySelector("#line-segment-source-form");
const lineSegmentSourceInputs = {
  x: document.querySelector("#line-segment-source-x"),
  y: document.querySelector("#line-segment-source-y"),
  z: document.querySelector("#line-segment-source-z"),
  orientationX: document.querySelector("#line-segment-source-orientation-x"),
  orientationY: document.querySelector("#line-segment-source-orientation-y"),
  orientationZ: document.querySelector("#line-segment-source-orientation-z"),
  length: document.querySelector("#line-segment-source-length"),
  charge: document.querySelector("#line-segment-source-charge"),
};
const ringSourceForm = document.querySelector("#ring-source-form");
const ringSourceInputs = {
  x: document.querySelector("#ring-source-x"),
  y: document.querySelector("#ring-source-y"),
  z: document.querySelector("#ring-source-z"),
  radius: document.querySelector("#ring-source-radius"),
  charge: document.querySelector("#ring-source-charge"),
};
const diskSourceForm = document.querySelector("#disk-source-form");
const diskSourceInputs = {
  x: document.querySelector("#disk-source-x"),
  y: document.querySelector("#disk-source-y"),
  z: document.querySelector("#disk-source-z"),
  radius: document.querySelector("#disk-source-radius"),
  charge: document.querySelector("#disk-source-charge"),
};
const sourceLibraryZFields = [
  pointSourceZField,
  document.querySelector("#line-segment-source-z-field"),
  document.querySelector("#line-segment-source-orientation-z-field"),
  document.querySelector("#ring-source-z-field"),
  document.querySelector("#disk-source-z-field"),
];
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
const motionState = document.querySelector("[data-testid='motion-state']");
const motionReadout = document.querySelector("[data-testid='motion-readout']");
const motionInputs = {
  charge: document.querySelector("#motion-charge"),
  mass: document.querySelector("#motion-mass"),
  x: document.querySelector("#motion-x"),
  y: document.querySelector("#motion-y"),
  vx: document.querySelector("#motion-vx"),
  vy: document.querySelector("#motion-vy"),
  dt: document.querySelector("#motion-dt"),
  steps: document.querySelector("#motion-steps"),
};
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
const COULOMB_CONSTANT = 8.9875517923e9;
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
const FIELD_LINE_BASE_STEP_M = 0.01;
const FIELD_LINE_MIN_STEP_M = 0.0012;
const FIELD_LINE_MAX_STEP_M = 0.025;
const FIELD_LINE_MAX_STEPS = 1600;
const FIELD_LINE_MAX_POINTS = 1000;
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
const FIELD_LINE_ACCEPTED_CLEARANCE_M = 0.00035;
const FIELD_LINE_CHARGE_CLEARANCE_RADIUS_M = FIELD_LINE_START_RADIUS_M + 0.003;
const FIELD_LINE_SPATIAL_CELL_M = 0.015;
const FIELD_LINE_CURVE_CONTROL_FACTOR = 0.34;
const FIELD_LINE_DISPLAY_SMOOTHING_ITERATIONS = 0;
const FIELD_LINE_DISPLAY_SMOOTHING_WEIGHT = 0.18;
const FIELD_LINE_DIRECTION_DOT_MIN = 0.2;
const FIELD_LINE_DISPLAY_STRATEGY = "uniform-charge-angle-field-tangent";
const FIELD_LINE_TRACE_TARGET_STEP_PX = 5;
const FIELD_LINE_CURVE_SAMPLE_SPACING_PX = 4;
const FIELD_LINE_CURVE_MIN_SAMPLE_SPACING_M = 0.001;
const FIELD_LINE_CURVE_MAX_SAMPLE_SPACING_M = 0.02;
const FIELD_LINE_MIN_VISIBLE_LENGTH_PX = 18;
const FIELD_LINE_BOUNDS_PADDING_PX = 56;
const FIELD_LINE_ARROW_FRACTION_BASE = 0.42;
const FIELD_LINE_ARROW_FRACTION_SPREAD = 0.18;
const FIELD_LINE_ARROW_FRACTION_MIN = 0.22;
const FIELD_LINE_ARROW_FRACTION_MAX = 0.72;
const FIELD_LINE_ARROW_LENGTH_PX = 9;
const FIELD_LINE_ARROW_WIDTH_PX = 7;
const ENABLE_LEGACY_FIELD_LINE_DEBUG_COMPARISON = false;
const EQUIPOTENTIAL_GRID_TARGET_PX = 8;
const EQUIPOTENTIAL_GRID_MIN_SIZE = 42;
const EQUIPOTENTIAL_GRID_MAX_SIZE = 128;
const EQUIPOTENTIAL_TARGET_LEVEL_COUNT = 18;
const EQUIPOTENTIAL_MAX_LEVEL_COUNT = 32;
const EQUIPOTENTIAL_MAX_RENDER_PATHS = 140;
const EQUIPOTENTIAL_MIN_PATH_POINTS = 6;
const EQUIPOTENTIAL_MIN_PATH_LENGTH_PX = 24;
const EQUIPOTENTIAL_SINGULARITY_RADIUS_M = POINT_VISUAL_RADIUS_CM / 100 + 0.001;
const EQUIPOTENTIAL_LABEL_MAX_COUNT = 48;
const EQUIPOTENTIAL_LABEL_MIN_PATH_LENGTH_PX = 90;
const EQUIPOTENTIAL_LABEL_DOUBLE_MIN_PATH_LENGTH_PX = 620;
const EQUIPOTENTIAL_LABEL_FONT_RATIO = 0.84;
const EQUIPOTENTIAL_LABEL_PADDING_PX = 4;
const EQUIPOTENTIAL_LABEL_COLLISION_PADDING_PX = 7;
const EQUIPOTENTIAL_LABEL_WIDTH_FACTOR = 0.62;
const EQUIPOTENTIAL_LABEL_LOCAL_SAMPLE_PX = 20;
const EQUIPOTENTIAL_LABEL_STRAIGHTNESS_MIN_DOT = 0.55;
const EQUIPOTENTIAL_LABEL_EDGE_MARGIN_PX = 12;
const EQUIPOTENTIAL_LABEL_CANDIDATE_FRACTIONS = [0.5, 0.42, 0.58, 0.34, 0.66];
const EQUIPOTENTIAL_LABEL_DOUBLE_FRACTIONS = [
  [0.34, 0.3, 0.38, 0.26],
  [0.66, 0.7, 0.62, 0.74],
];

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
  fieldLineResult: null,
  fieldLineRequestId: "",
  showEquipotentials: false,
  lastResult: null,
  overlayResult: null,
  overlaySamples: [],
  motion: {
    samples: [],
    frameIndex: 0,
    animationId: null,
    running: false,
  },
};

let fieldLineTraceCache = {
  key: "",
  result: null,
};

let equipotentialTraceCache = {
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
    fieldLineResult: state.fieldLineResult,
    fieldLineRequestId: state.fieldLineRequestId,
    showEquipotentials: state.showEquipotentials,
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
    fieldLineResult: null,
    fieldLineRequestId: "",
    showEquipotentials: false,
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
let fieldLineRequestSerial = 0;
let fieldLineEvaluationTimer = null;
let computeStatusRefreshTimer = null;
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
    fieldLineResult: state.fieldLineResult,
    fieldLineRequestId: state.fieldLineRequestId,
    showEquipotentials: state.showEquipotentials,
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
  state.fieldLineResult = modeState.fieldLineResult || null;
  state.fieldLineRequestId = modeState.fieldLineRequestId || "";
  state.showEquipotentials = Boolean(modeState.showEquipotentials);
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

function renderComputeStatus(status) {
  const cuda = status.cuda;
  computeBackend.textContent = cuda.available
    ? `CPU 可用；CUDA ${cuda.device_name} 可用`
    : `CPU 可用；CUDA 未启用`;
  computeWarmup.textContent = `预热状态：${status.warmup.state}`;
  if (status.warmup.failure_reason) {
    computeWarmup.textContent += ` (${status.warmup.failure_reason})`;
  }
}

function renderExecutionStatus(execution) {
  if (!execution) {
    return;
  }
  computeBackend.textContent =
    `${execution.backend_effective} · ${execution.device} · ${execution.precision}`;
}

async function refreshComputeStatus() {
  const status = await getComputeStatus();
  renderComputeStatus(status);
  if (status.warmup.state === "warming") {
    if (computeStatusRefreshTimer) {
      window.clearTimeout(computeStatusRefreshTimer);
    }
    computeStatusRefreshTimer = window.setTimeout(() => {
      refreshComputeStatus().catch((error) => {
        computeWarmup.textContent = error.message;
      });
    }, 250);
  }
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
  const overrideOrientation = overrides.orientation || {};
  const overrideNormal = overrides.normal || {};
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
      position: {
        x: Number(overridePosition.x ?? -0.08),
        y: Number(overridePosition.y ?? 0.08),
        z: Number(overridePosition.z ?? 0),
        unit: "m",
      },
      orientation: {
        x: Number(overrideOrientation.x ?? 1),
        y: Number(overrideOrientation.y ?? 0),
        z: Number(overrideOrientation.z ?? 0),
      },
      length_m: Number(overrides.length_m ?? 0.16),
      charge_c: Number(overrides.charge_c ?? 1.5e-9),
    };
  }
  if (kind === "ring") {
    return {
      ...base,
      label: `带电圆环 ${index}`,
      position: {
        x: Number(overridePosition.x ?? 0.12),
        y: Number(overridePosition.y ?? 0),
        z: Number(overridePosition.z ?? 0),
        unit: "m",
      },
      normal: {
        x: Number(overrideNormal.x ?? 0),
        y: Number(overrideNormal.y ?? 0),
        z: Number(overrideNormal.z ?? 1),
      },
      radius_m: Number(overrides.radius_m ?? 0.08),
      charge_c: Number(overrides.charge_c ?? 2e-9),
    };
  }
  if (kind === "disk") {
    return {
      ...base,
      label: `带电圆盘 ${index}`,
      position: {
        x: Number(overridePosition.x ?? 0),
        y: Number(overridePosition.y ?? -0.11),
        z: Number(overridePosition.z ?? 0),
        unit: "m",
      },
      normal: {
        x: Number(overrideNormal.x ?? 0),
        y: Number(overrideNormal.y ?? 0),
        z: Number(overrideNormal.z ?? 1),
      },
      radius_m: Number(overrides.radius_m ?? 0.09),
      charge_c: Number(overrides.charge_c ?? 2e-9),
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
  clearMotionTrajectory();
  state.scene.sources.push(sourceDefaults(kind, overrides));
  fieldLineTraceCache = { key: "", result: null };
  state.fieldLineResult = null;
  equipotentialTraceCache = { key: "", result: null };
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

function addLineSegmentFromForm(event) {
  event.preventDefault();
  const xCm = inputNumberValue(lineSegmentSourceInputs.x, -8);
  const yCm = inputNumberValue(lineSegmentSourceInputs.y, 8);
  const zCm = state.mode === "2D" ? 0 : inputNumberValue(lineSegmentSourceInputs.z, 0);
  const orientation = {
    x: inputNumberValue(lineSegmentSourceInputs.orientationX, 1),
    y: inputNumberValue(lineSegmentSourceInputs.orientationY, 0),
    z: state.mode === "2D"
      ? 0
      : inputNumberValue(lineSegmentSourceInputs.orientationZ, 0),
  };
  const lengthCm = inputNumberValue(lineSegmentSourceInputs.length, 16);
  const charge = inputNumberValue(lineSegmentSourceInputs.charge, 1.5e-9);
  const values = [xCm, yCm, zCm, orientation.x, orientation.y, orientation.z, lengthCm, charge];
  if (!values.every(Number.isFinite) || lengthCm <= 0 || vectorMagnitude(orientation) <= 1e-12) {
    solverStatus.textContent = "带电线段参数必须有限，长度和方向必须有效。";
    return;
  }
  addSource("line_segment", {
    position: {
      x: centimetersToMeters(xCm),
      y: centimetersToMeters(yCm),
      z: centimetersToMeters(zCm),
    },
    orientation,
    length_m: centimetersToMeters(lengthCm),
    charge_c: charge,
  });
}

function addRingFromForm(event) {
  event.preventDefault();
  const xCm = inputNumberValue(ringSourceInputs.x, 12);
  const yCm = inputNumberValue(ringSourceInputs.y, 0);
  const zCm = state.mode === "2D" ? 0 : inputNumberValue(ringSourceInputs.z, 0);
  const radiusCm = inputNumberValue(ringSourceInputs.radius, 8);
  const charge = inputNumberValue(ringSourceInputs.charge, 2e-9);
  if (![xCm, yCm, zCm, radiusCm, charge].every(Number.isFinite) || radiusCm <= 0) {
    solverStatus.textContent = "带电圆环参数必须有限，半径必须大于 0。";
    return;
  }
  addSource("ring", {
    position: {
      x: centimetersToMeters(xCm),
      y: centimetersToMeters(yCm),
      z: centimetersToMeters(zCm),
    },
    normal: { x: 0, y: 0, z: 1 },
    radius_m: centimetersToMeters(radiusCm),
    charge_c: charge,
  });
}

function addDiskFromForm(event) {
  event.preventDefault();
  const xCm = inputNumberValue(diskSourceInputs.x, 0);
  const yCm = inputNumberValue(diskSourceInputs.y, -11);
  const zCm = state.mode === "2D" ? 0 : inputNumberValue(diskSourceInputs.z, 0);
  const radiusCm = inputNumberValue(diskSourceInputs.radius, 9);
  const charge = inputNumberValue(diskSourceInputs.charge, 2e-9);
  if (![xCm, yCm, zCm, radiusCm, charge].every(Number.isFinite) || radiusCm <= 0) {
    solverStatus.textContent = "带电圆盘参数必须有限，半径必须大于 0。";
    return;
  }
  addSource("disk", {
    position: {
      x: centimetersToMeters(xCm),
      y: centimetersToMeters(yCm),
      z: centimetersToMeters(zCm),
    },
    normal: { x: 0, y: 0, z: 1 },
    radius_m: centimetersToMeters(radiusCm),
    charge_c: charge,
  });
}

function renderPointSourceForm() {
  if (!pointSourceForm || !pointSourceZField) {
    return;
  }
  pointSourceZField.hidden = state.mode === "2D";
  for (const field of sourceLibraryZFields) {
    if (field) {
      field.hidden = state.mode === "2D";
    }
  }
}

function removeSource(sourceId) {
  clearMotionTrajectory();
  state.scene.sources = state.scene.sources.filter((source) => source.id !== sourceId);
  fieldLineTraceCache = { key: "", result: null };
  state.fieldLineResult = null;
  equipotentialTraceCache = { key: "", result: null };
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

  clearMotionTrajectory();
  if (field === "label") {
    source.label = value || source.id;
  } else if (field.includes(".")) {
    const [group, key] = field.split(".");
    source[group][key] = Number(value);
  } else if (field !== "physical_model" && field !== "kind" && field !== "id") {
    source[field] = Number(value);
  }

  fieldLineTraceCache = { key: "", result: null };
  state.fieldLineResult = null;
  equipotentialTraceCache = { key: "", result: null };
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
  if (mode === "2D") {
    scheduleFieldLineEvaluation();
  }
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
  if (state.showFieldLines) {
    scheduleFieldLineEvaluation();
  } else {
    fieldLineRequestSerial += 1;
    state.fieldLineRequestId = "";
    if (fieldLineEvaluationTimer) {
      window.clearTimeout(fieldLineEvaluationTimer);
      fieldLineEvaluationTimer = null;
    }
  }
  renderOverlaySummary();
}

function toggleEquipotentials() {
  state.showEquipotentials = !state.showEquipotentials;
  render2d();
  renderOverlaySummary();
}

function renderOverlayControls() {
  toggleFieldLinesButton.classList.toggle("active", state.showFieldLines);
  toggleFieldLinesButton.textContent = state.showFieldLines ? "隐藏电场" : "显示电场";
  toggleEquipotentialLinesButton.classList.toggle("active", state.showEquipotentials);
  toggleEquipotentialLinesButton.textContent = state.showEquipotentials ? "隐藏等势线" : "显示等势线";
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

function fieldLineAverageMetersPerPx(scale) {
  if (!scale) {
    return FIELD_LINE_BASE_STEP_M / FIELD_LINE_TRACE_TARGET_STEP_PX;
  }
  const averageUnitsPerPx = (scale.xUnitsPerPx + scale.yUnitsPerPx) / 2;
  return Math.max(1e-6, averageUnitsPerPx / VIEWPORT_METERS_TO_UNITS);
}

function fieldLineStepMetrics(scale) {
  const metersPerPx = fieldLineAverageMetersPerPx(scale);
  const targetStep = Math.max(
    FIELD_LINE_MIN_STEP_M,
    Math.min(FIELD_LINE_MAX_STEP_M, metersPerPx * FIELD_LINE_TRACE_TARGET_STEP_PX),
  );
  return {
    metersPerPx,
    baseStep: targetStep,
    minStep: Math.max(FIELD_LINE_MIN_STEP_M, targetStep * 0.35),
    maxStep: Math.min(FIELD_LINE_MAX_STEP_M, Math.max(targetStep * 1.8, targetStep + FIELD_LINE_MIN_STEP_M)),
    sampleSpacing: Math.max(
      FIELD_LINE_CURVE_MIN_SAMPLE_SPACING_M,
      Math.min(FIELD_LINE_CURVE_MAX_SAMPLE_SPACING_M, metersPerPx * FIELD_LINE_CURVE_SAMPLE_SPACING_PX),
    ),
  };
}

function compute2dFieldLineBounds(scale) {
  const viewBox = compute2dViewBox();
  const worldBounds = compute2dWorldBounds();
  const paddingX = ((scale?.xUnitsPerPx || 1) * FIELD_LINE_BOUNDS_PADDING_PX) / VIEWPORT_METERS_TO_UNITS;
  const paddingY = ((scale?.yUnitsPerPx || 1) * FIELD_LINE_BOUNDS_PADDING_PX) / VIEWPORT_METERS_TO_UNITS;
  const minX = viewBox.minX / VIEWPORT_METERS_TO_UNITS;
  const maxX = (viewBox.minX + viewBox.width) / VIEWPORT_METERS_TO_UNITS;
  const minY = -(viewBox.minY + viewBox.height) / VIEWPORT_METERS_TO_UNITS;
  const maxY = -viewBox.minY / VIEWPORT_METERS_TO_UNITS;

  return {
    minX: Math.max(worldBounds.minX, minX - paddingX),
    maxX: Math.min(worldBounds.maxX, maxX + paddingX),
    minY: Math.max(worldBounds.minY, minY - paddingY),
    maxY: Math.min(worldBounds.maxY, maxY + paddingY),
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
    const radius = radiusToViewport(source.radius_m, MIN_VISIBLE_MARKER_RADIUS_UNITS);
    const physicalRadiusCm = formatCentimeters(source.radius_m);
    return `
      <g data-testid="source-ring-group-2d-${source.id}">
        <circle
          class="source-ring"
          data-testid="source-ring-2d-${source.id}"
          data-display-diameter-cm="${formatCentimeters(source.radius_m * 2)}"
          data-physical-radius-cm="${physicalRadiusCm}"
          data-visual-model="hollow-ring"
          cx="${point.x}"
          cy="${point.y}"
          r="${radius}"
          style="stroke-width: ${markerStrokeWidth}px; stroke: ${chargeColor}; fill: none; fill-opacity: 0;"
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

function pointChargeSingularities2d() {
  return state.scene.sources.filter((source) => (
    source.kind === "point" &&
    source.position &&
    Math.abs(sourceChargeValue(source)) > 1e-30
  ));
}

function isNearEquipotentialSingularity(x, y, singularities) {
  return singularities.some((source) => (
    Math.hypot(x - source.position.x, y - source.position.y) <= EQUIPOTENTIAL_SINGULARITY_RADIUS_M
  ));
}

function electricPotential2dAt(x, y, fieldSamples, singularities) {
  if (isNearEquipotentialSingularity(x, y, singularities)) {
    return null;
  }
  let potential = 0;
  for (const sample of fieldSamples) {
    const dx = x - sample.x;
    const dy = y - sample.y;
    const distance = Math.hypot(dx, dy);
    if (!Number.isFinite(distance) || distance <= FIELD_LINE_SINGULARITY_RADIUS_M) {
      return null;
    }
    potential += (COULOMB_CONSTANT * sample.charge) / distance;
  }
  return Number.isFinite(potential) ? potential : null;
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
  return state.scene.sources.filter((source) => (
    ["point", "line_segment", "ring", "disk", "spherical_shell"].includes(source.kind) &&
    source.position &&
    Math.abs(sourceChargeValue(source)) > 1e-30
  ));
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
  stepMetrics,
) {
  const points = [seed];
  let x = seed.x;
  let y = seed.y;
  let previousDirection = null;
  let stopReason = "max-steps";
  let terminalSourceId = "";
  let stepSize = stepMetrics.baseStep;

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
      if (stepSize > stepMetrics.minStep) {
        const halfStepSize = stepSize / 2;
        const halfStep = rk4FieldLineStep(x, y, traceDirection, fieldSamples, halfStepSize);
        const secondHalfStep = halfStep
          ? rk4FieldLineStep(halfStep.x, halfStep.y, traceDirection, fieldSamples, halfStepSize)
          : null;
        if (!secondHalfStep) {
          stepSize = Math.max(stepMetrics.minStep, stepSize * 0.5);
          continue;
        }
        const stepError = Math.hypot(fullStep.x - secondHalfStep.x, fullStep.y - secondHalfStep.y);
        const allowedError = Math.max(FIELD_LINE_ADAPT_ERROR_MIN_M, stepSize * FIELD_LINE_ADAPT_ERROR_FRACTION);
        if (stepError > allowedError) {
          stepSize = Math.max(stepMetrics.minStep, stepSize * 0.5);
          continue;
        }
        next = {
          ...secondHalfStep,
          direction: fullStep.direction,
          stepSize,
        };
      }
      if (directionDot < FIELD_LINE_ADAPT_RETRY_DOT && stepSize > stepMetrics.minStep) {
        stepSize = Math.max(stepMetrics.minStep, stepSize * 0.5);
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
    x = next.x;
    y = next.y;
    points.push({ x, y });
    previousDirection = next.direction;

    if (points.length >= FIELD_LINE_MAX_POINTS) {
      stopReason = "point-budget";
      break;
    }
    if (directionDot > FIELD_LINE_ADAPT_GROW_DOT) {
      stepSize = Math.min(stepMetrics.maxStep, stepSize * 1.35);
    } else if (directionDot < FIELD_LINE_ADAPT_SHRINK_DOT) {
      stepSize = Math.max(stepMetrics.minStep, stepSize * 0.7);
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

function fieldLineNormalizeVector(x, y) {
  const length = Math.hypot(x, y);
  return length <= 1e-12 ? null : { x: x / length, y: y / length };
}

function fieldLineFallbackDirection(points, index) {
  const previous = points[Math.max(0, index - 1)];
  const next = points[Math.min(points.length - 1, index + 1)];
  return fieldLineNormalizeVector(next.x - previous.x, next.y - previous.y) || { x: 1, y: 0 };
}

function fieldLineDisplayDirectionAtPoint(point, fallback, fieldSamples) {
  const field = electricField2dAt(point.x, point.y, fieldSamples);
  const fieldMagnitude = Math.hypot(field.x, field.y);
  const direction = fieldMagnitude > FIELD_LINE_MIN_FIELD
    ? { x: field.x / fieldMagnitude, y: field.y / fieldMagnitude }
    : { ...fallback };
  return direction.x * fallback.x + direction.y * fallback.y < 0
    ? { x: -direction.x, y: -direction.y }
    : direction;
}

function fieldLineCurveTangents(points, fieldSamples) {
  return points.map((point, index) => {
    const fallback = fieldLineFallbackDirection(points, index);
    return fieldLineDisplayDirectionAtPoint(point, fallback, fieldSamples);
  });
}

function fieldLineCurveSegments(points, fieldSamples) {
  if (points.length < 2) {
    return [];
  }
  const tangents = fieldLineCurveTangents(points, fieldSamples);
  const segments = [];
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    const segmentLength = Math.hypot(end.x - start.x, end.y - start.y);
    if (segmentLength <= 1e-12) {
      continue;
    }
    const previousLength = index > 0
      ? Math.hypot(start.x - points[index - 1].x, start.y - points[index - 1].y)
      : segmentLength;
    const nextLength = index + 2 < points.length
      ? Math.hypot(points[index + 2].x - end.x, points[index + 2].y - end.y)
      : segmentLength;
    const startControlLength = Math.min(
      segmentLength * 0.45,
      Math.max(segmentLength, previousLength) * FIELD_LINE_CURVE_CONTROL_FACTOR,
    );
    const endControlLength = Math.min(
      segmentLength * 0.45,
      Math.max(segmentLength, nextLength) * FIELD_LINE_CURVE_CONTROL_FACTOR,
    );
    segments.push({
      start,
      controlStart: {
        x: start.x + tangents[index].x * startControlLength,
        y: start.y + tangents[index].y * startControlLength,
      },
      controlEnd: {
        x: end.x - tangents[index + 1].x * endControlLength,
        y: end.y - tangents[index + 1].y * endControlLength,
      },
      end,
    });
  }
  return segments;
}

function fieldLineCubicPoint(segment, t) {
  const u = 1 - t;
  const uu = u * u;
  const tt = t * t;
  return {
    x:
      uu * u * segment.start.x +
      3 * uu * t * segment.controlStart.x +
      3 * u * tt * segment.controlEnd.x +
      tt * t * segment.end.x,
    y:
      uu * u * segment.start.y +
      3 * uu * t * segment.controlStart.y +
      3 * u * tt * segment.controlEnd.y +
      tt * t * segment.end.y,
  };
}

function fieldLineCubicApproxLength(segment) {
  return (
    Math.hypot(segment.controlStart.x - segment.start.x, segment.controlStart.y - segment.start.y) +
    Math.hypot(segment.controlEnd.x - segment.controlStart.x, segment.controlEnd.y - segment.controlStart.y) +
    Math.hypot(segment.end.x - segment.controlEnd.x, segment.end.y - segment.controlEnd.y)
  );
}

function fieldLineCurveSamplePoints(points, fieldSamples, sampleSpacing) {
  const segments = fieldLineCurveSegments(points, fieldSamples);
  if (segments.length === 0) {
    return points;
  }
  const samples = [{ ...segments[0].start }];
  for (const segment of segments) {
    const sampleCount = Math.max(2, Math.ceil(fieldLineCubicApproxLength(segment) / sampleSpacing));
    for (let sampleIndex = 1; sampleIndex <= sampleCount; sampleIndex += 1) {
      samples.push(fieldLineCubicPoint(segment, sampleIndex / sampleCount));
    }
  }
  return samples;
}

function fieldLinePolylineLength(points) {
  let length = 0;
  for (let index = 1; index < points.length; index += 1) {
    length += Math.hypot(points[index].x - points[index - 1].x, points[index].y - points[index - 1].y);
  }
  return length;
}

function fieldLinePath(points, fieldSamples) {
  const segments = fieldLineCurveSegments(points, fieldSamples);
  if (segments.length === 0) {
    const viewportPoints = points.map((point) => mapToViewport(point.x, point.y));
    return viewportPoints
      .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(3)} ${point.y.toFixed(3)}`)
      .join(" ");
  }
  const first = mapToViewport(segments[0].start.x, segments[0].start.y);
  const commands = [`M ${first.x.toFixed(3)} ${first.y.toFixed(3)}`];
  for (const segment of segments) {
    const controlStart = mapToViewport(segment.controlStart.x, segment.controlStart.y);
    const controlEnd = mapToViewport(segment.controlEnd.x, segment.controlEnd.y);
    const end = mapToViewport(segment.end.x, segment.end.y);
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

function prepareDisplayFieldLineEntry(entry, fieldSamples, stepMetrics) {
  const arrowSource = fieldLineArrowSource(entry);
  if (!arrowSource || !arrowSource.position || entry.topology === "infinity-to-infinity") {
    return null;
  }
  const snappedPoints = snapFieldLineEndpointsToSources(entry.renderPoints, entry);
  const arrowFraction = fieldLineArrowFraction(entry);
  const anchoredPoints = fieldLinePointsWithArrowAnchor(snappedPoints, entry);
  const displayPoints = smoothFieldLineDisplayPoints(anchoredPoints, arrowSource);
  const curvePoints = fieldLineCurveSamplePoints(displayPoints, fieldSamples, stepMetrics.sampleSpacing);
  if (fieldLinePolylineLength(curvePoints) / stepMetrics.metersPerPx < FIELD_LINE_MIN_VISIBLE_LENGTH_PX) {
    return null;
  }
  const directionQuality = fieldLineDirectionQuality(curvePoints, fieldSamples);
  if (!directionQuality.valid) {
    return null;
  }
  return {
    ...entry,
    arrowSource,
    displayPoints,
    curvePoints,
    arrowPoints: fieldLinePointsWithArrowAnchor(curvePoints, entry),
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

function fieldLineCacheKey(seedSources, bounds, stepMetrics) {
  return JSON.stringify({
    sources: state.scene.sources,
    seedSourceIds: seedSources.map((source) => source.id),
    bounds: {
      minX: Number(bounds.minX.toFixed(4)),
      maxX: Number(bounds.maxX.toFixed(4)),
      minY: Number(bounds.minY.toFixed(4)),
      maxY: Number(bounds.maxY.toFixed(4)),
    },
    stepMetrics: {
      baseStep: Number(stepMetrics.baseStep.toFixed(5)),
      minStep: Number(stepMetrics.minStep.toFixed(5)),
      maxStep: Number(stepMetrics.maxStep.toFixed(5)),
      sampleSpacing: Number(stepMetrics.sampleSpacing.toFixed(5)),
    },
    displayStrategy: FIELD_LINE_DISPLAY_STRATEGY,
    targetTotalChargeRays: FIELD_LINE_TARGET_TOTAL_CHARGE_RAYS,
    minChargeRays: FIELD_LINE_MIN_CHARGE_RAYS,
    maxChargeRays: FIELD_LINE_MAX_CHARGE_RAYS,
    displayMaxCount: FIELD_LINE_DISPLAY_MAX_COUNT,
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
  if (fieldLineConflictsWithAccepted(entry.curvePoints, acceptedLineIndex)) {
    return false;
  }
  addAcceptedFieldLine(acceptedLineIndex, entry.curvePoints);
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

function selectDisplayFieldLineEntries(rawEntries, fieldSamples, stepMetrics) {
  const acceptedLineIndex = createFieldLineSpatialIndex();
  const selectedEntries = [];
  const preparedEntries = [];
  const pairCounts = new Map();
  let lowQualityLineCount = 0;
  let dedupedLineCount = 0;
  let conflictRejectedLineCount = 0;

  for (const entry of rawEntries) {
    const displayEntry = prepareDisplayFieldLineEntry(entry, fieldSamples, stepMetrics);
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

function computeFieldLineTraceResult(fieldSamples, seedSources, bounds, stepMetrics) {
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
      stepMetrics,
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
  const displayResult = selectDisplayFieldLineEntries(rawEntries, fieldSamples, stepMetrics);
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
    stepMeters: stepMetrics.baseStep,
    sampleSpacingMeters: stepMetrics.sampleSpacing,
  };
}

function getFieldLineTraceResult(fieldSamples, seedSources, bounds, stepMetrics) {
  const key = fieldLineCacheKey(seedSources, bounds, stepMetrics);
  if (fieldLineTraceCache.key === key && fieldLineTraceCache.result) {
    return fieldLineTraceCache.result;
  }
  const result = computeFieldLineTraceResult(fieldSamples, seedSources, bounds, stepMetrics);
  fieldLineTraceCache = { key, result };
  return result;
}

function backendFieldLineEntry(line) {
  const source = fieldLineSourceById(line.source_id);
  if (!source) {
    return null;
  }
  const charge = sourceChargeValue(source);
  let fieldStartId = source.id;
  let fieldEndId = "infinity";
  let topology = "charge-to-infinity";
  if (line.topology === "source-to-source") {
    topology = "charge-to-charge";
    if (charge >= 0) {
      fieldEndId = line.terminal_source_id;
    } else {
      fieldStartId = line.terminal_source_id;
      fieldEndId = source.id;
    }
  } else if (line.topology === "infinity-to-source") {
    fieldStartId = "infinity";
    fieldEndId = source.id;
    topology = "infinity-to-charge";
  }
  return {
    source,
    charge,
    endpointClass: line.stop_reason === "opposite-charge" ? "opposite-charge" : "infinity",
    fieldStartId,
    fieldEndId,
    topology,
    renderPoints: line.points,
    seedAttempt: 0,
    seedIndex: line.seed_index,
    seedCount: 0,
    sourceOrder: state.scene.sources.indexOf(source),
    seedKind: "charge",
    stopReason: line.stop_reason,
    terminalSourceId: line.terminal_source_id || "",
  };
}

function backendFieldLineTraceResult(result, fieldSamples, seedSources, stepMetrics) {
  const rawEntries = result.lines
    .map((line) => backendFieldLineEntry(line))
    .filter((entry) => entry !== null);
  const displayStepMetrics = {
    ...stepMetrics,
    sampleSpacing: stepMetrics.sampleSpacing * 0.5,
  };
  const displayResult = selectDisplayFieldLineEntries(rawEntries, fieldSamples, displayStepMetrics);
  return {
    entries: displayResult.entries,
    rawLineCount: rawEntries.length,
    candidateLineCount: result.candidate_line_count,
    chargeRayCount: Math.round(result.candidate_line_count / Math.max(1, seedSources.length)),
    rejectedLineCount: result.rejected_line_count,
    dedupedLineCount: displayResult.dedupedLineCount,
    displayConflictRejectedLineCount:
      result.conflict_rejected_line_count + displayResult.conflictRejectedLineCount,
    lowQualityLineCount: displayResult.lowQualityLineCount,
    pairedLineCount: displayResult.pairedLineCount,
    useConflictFilter: rawEntries.length > 1,
    stepMeters: FIELD_LINE_BASE_STEP_M,
    sampleSpacingMeters: displayStepMetrics.sampleSpacing,
    requestId: result.request_id,
    execution: result.execution,
  };
}

function compute2dVisibleWorldBounds() {
  const viewBox = compute2dViewBox();
  const worldBounds = compute2dWorldBounds();
  const minX = viewBox.minX / VIEWPORT_METERS_TO_UNITS;
  const maxX = (viewBox.minX + viewBox.width) / VIEWPORT_METERS_TO_UNITS;
  const minY = -(viewBox.minY + viewBox.height) / VIEWPORT_METERS_TO_UNITS;
  const maxY = -viewBox.minY / VIEWPORT_METERS_TO_UNITS;
  return {
    minX: Math.max(worldBounds.minX, minX),
    maxX: Math.min(worldBounds.maxX, maxX),
    minY: Math.max(worldBounds.minY, minY),
    maxY: Math.min(worldBounds.maxY, maxY),
  };
}

function clampInteger(value, minValue, maxValue) {
  return Math.max(minValue, Math.min(maxValue, Math.round(value)));
}

function equipotentialGridSize(scale) {
  return {
    columns: clampInteger(scale.widthPx / EQUIPOTENTIAL_GRID_TARGET_PX, EQUIPOTENTIAL_GRID_MIN_SIZE, EQUIPOTENTIAL_GRID_MAX_SIZE),
    rows: clampInteger(scale.heightPx / EQUIPOTENTIAL_GRID_TARGET_PX, EQUIPOTENTIAL_GRID_MIN_SIZE, EQUIPOTENTIAL_GRID_MAX_SIZE),
  };
}

function equipotentialCacheKey(fieldSamples, singularities, bounds, gridSize) {
  return JSON.stringify({
    sources: state.scene.sources,
    fieldSampleCount: fieldSamples.length,
    singularityIds: singularities.map((source) => source.id),
    bounds: {
      minX: Number(bounds.minX.toFixed(5)),
      maxX: Number(bounds.maxX.toFixed(5)),
      minY: Number(bounds.minY.toFixed(5)),
      maxY: Number(bounds.maxY.toFixed(5)),
    },
    gridSize,
    targetLevelCount: EQUIPOTENTIAL_TARGET_LEVEL_COUNT,
    maxLevelCount: EQUIPOTENTIAL_MAX_LEVEL_COUNT,
  });
}

function percentile(sortedValues, fraction) {
  if (sortedValues.length === 0) {
    return 0;
  }
  const index = (sortedValues.length - 1) * Math.max(0, Math.min(1, fraction));
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) {
    return sortedValues[lower];
  }
  const t = index - lower;
  return sortedValues[lower] * (1 - t) + sortedValues[upper] * t;
}

function nicePotentialStep(rawStep) {
  if (!Number.isFinite(rawStep) || rawStep <= 0) {
    return 1;
  }
  const exponent = Math.floor(Math.log10(rawStep));
  const base = 10 ** exponent;
  for (const multiplier of [1, 2, 5, 10]) {
    const step = multiplier * base;
    if (rawStep <= step) {
      return step;
    }
  }
  return 10 * base;
}

function sampleEquipotentialGrid(fieldSamples, singularities, bounds, gridSize) {
  const { columns, rows } = gridSize;
  const values = [];
  const finiteValues = [];
  const dx = (bounds.maxX - bounds.minX) / Math.max(1, columns - 1);
  const dy = (bounds.maxY - bounds.minY) / Math.max(1, rows - 1);
  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const x = bounds.minX + column * dx;
      const y = bounds.minY + row * dy;
      const value = electricPotential2dAt(x, y, fieldSamples, singularities);
      values.push(value);
      if (Number.isFinite(value)) {
        finiteValues.push(value);
      }
    }
  }
  return { values, finiteValues, dx, dy };
}

function chooseEquipotentialLevels(finiteValues) {
  if (finiteValues.length < 4) {
    return { levels: [], step: 0, min: 0, max: 0 };
  }
  const sorted = [...finiteValues].sort((a, b) => a - b);
  let low = percentile(sorted, 0.08);
  let high = percentile(sorted, 0.92);
  if (!Number.isFinite(low) || !Number.isFinite(high) || high <= low) {
    low = sorted[0];
    high = sorted[sorted.length - 1];
  }
  const span = high - low;
  if (!Number.isFinite(span) || span <= 1e-12) {
    return { levels: [], step: 0, min: low, max: high };
  }
  const step = nicePotentialStep(span / EQUIPOTENTIAL_TARGET_LEVEL_COUNT);
  const levels = [];
  let value = Math.ceil(low / step) * step;
  while (value <= high + step * 0.001 && levels.length < EQUIPOTENTIAL_MAX_LEVEL_COUNT) {
    if (Math.abs(value) > step * 1e-8) {
      levels.push(value);
    } else {
      levels.push(0);
    }
    value += step;
  }
  return { levels: [...new Set(levels.map((level) => Number(level.toPrecision(12))))], step, min: low, max: high };
}

function gridPoint(bounds, grid, column, row) {
  return {
    x: bounds.minX + column * grid.dx,
    y: bounds.minY + row * grid.dy,
  };
}

function contourEdgePoint(edgeIndex, corners, level) {
  const edgeCorners = [
    [0, 1],
    [1, 2],
    [2, 3],
    [3, 0],
  ][edgeIndex];
  const first = corners[edgeCorners[0]];
  const second = corners[edgeCorners[1]];
  const denominator = second.value - first.value;
  const t = Math.abs(denominator) <= 1e-12 ? 0.5 : (level - first.value) / denominator;
  const clamped = Math.max(0, Math.min(1, t));
  return {
    x: first.x + (second.x - first.x) * clamped,
    y: first.y + (second.y - first.y) * clamped,
  };
}

const MARCHING_SQUARES_SEGMENTS = {
  1: [[3, 0]],
  2: [[0, 1]],
  3: [[3, 1]],
  4: [[1, 2]],
  5: [[3, 2], [0, 1]],
  6: [[0, 2]],
  7: [[3, 2]],
  8: [[2, 3]],
  9: [[0, 2]],
  10: [[0, 3], [1, 2]],
  11: [[1, 2]],
  12: [[1, 3]],
  13: [[0, 1]],
  14: [[3, 0]],
};

function contourSegmentsForLevel(level, bounds, grid, gridSize) {
  const { columns, rows } = gridSize;
  const segments = [];
  const valueAt = (column, row) => grid.values[row * columns + column];
  for (let row = 0; row < rows - 1; row += 1) {
    for (let column = 0; column < columns - 1; column += 1) {
      const corners = [
        { ...gridPoint(bounds, grid, column, row), value: valueAt(column, row) },
        { ...gridPoint(bounds, grid, column + 1, row), value: valueAt(column + 1, row) },
        { ...gridPoint(bounds, grid, column + 1, row + 1), value: valueAt(column + 1, row + 1) },
        { ...gridPoint(bounds, grid, column, row + 1), value: valueAt(column, row + 1) },
      ];
      if (!corners.every((corner) => Number.isFinite(corner.value))) {
        continue;
      }
      const caseIndex = corners.reduce(
        (index, corner, cornerIndex) => index | (corner.value >= level ? 1 << cornerIndex : 0),
        0,
      );
      const edgePairs = MARCHING_SQUARES_SEGMENTS[caseIndex];
      if (!edgePairs) {
        continue;
      }
      for (const [firstEdge, secondEdge] of edgePairs) {
        const first = contourEdgePoint(firstEdge, corners, level);
        const second = contourEdgePoint(secondEdge, corners, level);
        if (Math.hypot(first.x - second.x, first.y - second.y) > 1e-10) {
          segments.push([first, second]);
        }
      }
    }
  }
  return segments;
}

function contourPointKey(point, tolerance) {
  return `${Math.round(point.x / tolerance)}:${Math.round(point.y / tolerance)}`;
}

function segmentKey(firstKey, secondKey) {
  return firstKey < secondKey ? `${firstKey}|${secondKey}` : `${secondKey}|${firstKey}`;
}

function linkContourSegments(segments, tolerance) {
  const nodes = new Map();
  const edges = new Map();
  for (const [first, second] of segments) {
    const firstKey = contourPointKey(first, tolerance);
    const secondKey = contourPointKey(second, tolerance);
    if (firstKey === secondKey) {
      continue;
    }
    if (!nodes.has(firstKey)) {
      nodes.set(firstKey, { point: first, neighbors: new Set() });
    }
    if (!nodes.has(secondKey)) {
      nodes.set(secondKey, { point: second, neighbors: new Set() });
    }
    nodes.get(firstKey).neighbors.add(secondKey);
    nodes.get(secondKey).neighbors.add(firstKey);
    edges.set(segmentKey(firstKey, secondKey), false);
  }

  const paths = [];
  const walk = (startKey, nextKey) => {
    const path = [nodes.get(startKey).point];
    let previousKey = startKey;
    let currentKey = nextKey;
    while (currentKey) {
      const edgeId = segmentKey(previousKey, currentKey);
      if (edges.get(edgeId)) {
        break;
      }
      edges.set(edgeId, true);
      path.push(nodes.get(currentKey).point);
      const currentNode = nodes.get(currentKey);
      const nextCandidates = [...currentNode.neighbors].filter((candidateKey) => (
        candidateKey !== previousKey && !edges.get(segmentKey(currentKey, candidateKey))
      ));
      if (nextCandidates.length === 0) {
        break;
      }
      previousKey = currentKey;
      currentKey = nextCandidates[0];
      if (currentKey === startKey) {
        const closingEdgeId = segmentKey(previousKey, currentKey);
        if (!edges.get(closingEdgeId)) {
          edges.set(closingEdgeId, true);
          path.push(nodes.get(currentKey).point);
        }
        break;
      }
    }
    return path;
  };

  for (const [nodeKey, node] of nodes) {
    if (node.neighbors.size === 2) {
      continue;
    }
    for (const neighborKey of node.neighbors) {
      if (!edges.get(segmentKey(nodeKey, neighborKey))) {
        paths.push(walk(nodeKey, neighborKey));
      }
    }
  }

  for (const [edgeId, visited] of edges) {
    if (visited) {
      continue;
    }
    const [startKey, nextKey] = edgeId.split("|");
    paths.push(walk(startKey, nextKey));
  }

  return paths.filter((path) => path.length >= EQUIPOTENTIAL_MIN_PATH_POINTS);
}

function worldPathLength(points) {
  let length = 0;
  for (let index = 1; index < points.length; index += 1) {
    length += Math.hypot(points[index].x - points[index - 1].x, points[index].y - points[index - 1].y);
  }
  return length;
}

function smoothViewportPath(points) {
  const viewportPoints = points.map((point) => mapToViewport(point.x, point.y));
  if (viewportPoints.length < 2) {
    return "";
  }
  if (viewportPoints.length === 2) {
    return `M ${viewportPoints[0].x.toFixed(3)} ${viewportPoints[0].y.toFixed(3)} L ${viewportPoints[1].x.toFixed(3)} ${viewportPoints[1].y.toFixed(3)}`;
  }
  const commands = [`M ${viewportPoints[0].x.toFixed(3)} ${viewportPoints[0].y.toFixed(3)}`];
  for (let index = 0; index < viewportPoints.length - 1; index += 1) {
    const p0 = viewportPoints[Math.max(0, index - 1)];
    const p1 = viewportPoints[index];
    const p2 = viewportPoints[index + 1];
    const p3 = viewportPoints[Math.min(viewportPoints.length - 1, index + 2)];
    const c1 = {
      x: p1.x + (p2.x - p0.x) / 6,
      y: p1.y + (p2.y - p0.y) / 6,
    };
    const c2 = {
      x: p2.x - (p3.x - p1.x) / 6,
      y: p2.y - (p3.y - p1.y) / 6,
    };
    commands.push(
      `C ${c1.x.toFixed(3)} ${c1.y.toFixed(3)} ${c2.x.toFixed(3)} ${c2.y.toFixed(3)} ${p2.x.toFixed(3)} ${p2.y.toFixed(3)}`,
    );
  }
  return commands.join(" ");
}

function formatPotentialLabel(value, step) {
  if (!Number.isFinite(value)) {
    return "n/a V";
  }
  if (Math.abs(value) <= Math.max(Math.abs(step) * 1e-8, 1e-12)) {
    return "0 V";
  }
  const absValue = Math.abs(value);
  if (absValue >= 10000 || absValue < 0.01) {
    return `${formatNumber(value, 3)} V`;
  }
  const precision = Math.min(3, Math.max(0, decimalPlacesForStep(Math.abs(step || value))));
  return `${value.toFixed(precision).replace(/\.?0+$/, "")} V`;
}

function worldPointToScreen(point, viewBox, scale) {
  const viewportPoint = mapToViewport(point.x, point.y);
  return {
    x: (viewportPoint.x - viewBox.minX) / scale.xUnitsPerPx,
    y: (viewportPoint.y - viewBox.minY) / scale.yUnitsPerPx,
    viewportX: viewportPoint.x,
    viewportY: viewportPoint.y,
  };
}

function equipotentialPathScreenPoints(points, viewBox, scale) {
  return points.map((point) => ({
    world: point,
    ...worldPointToScreen(point, viewBox, scale),
  }));
}

function screenPolylineLength(points) {
  let length = 0;
  for (let index = 1; index < points.length; index += 1) {
    length += Math.hypot(points[index].x - points[index - 1].x, points[index].y - points[index - 1].y);
  }
  return length;
}

function screenPointAtLength(points, targetLength) {
  let consumed = 0;
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const segmentLength = Math.hypot(current.x - previous.x, current.y - previous.y);
    if (segmentLength <= 1e-9) {
      continue;
    }
    if (consumed + segmentLength >= targetLength) {
      const t = (targetLength - consumed) / segmentLength;
      return {
        x: previous.x + (current.x - previous.x) * t,
        y: previous.y + (current.y - previous.y) * t,
        viewportX: previous.viewportX + (current.viewportX - previous.viewportX) * t,
        viewportY: previous.viewportY + (current.viewportY - previous.viewportY) * t,
        tangentX: current.x - previous.x,
        tangentY: current.y - previous.y,
      };
    }
    consumed += segmentLength;
  }
  return null;
}

function normalizedScreenAngle(tangentX, tangentY) {
  let angle = (Math.atan2(tangentY, tangentX) * 180) / Math.PI;
  if (angle > 90) {
    angle -= 180;
  } else if (angle < -90) {
    angle += 180;
  }
  return angle;
}

function equipotentialLabelBox(text, center, angle, scale) {
  const fontPx = scale.fontPx * EQUIPOTENTIAL_LABEL_FONT_RATIO;
  const width = Math.max(26, text.length * fontPx * EQUIPOTENTIAL_LABEL_WIDTH_FACTOR) +
    EQUIPOTENTIAL_LABEL_PADDING_PX * 2;
  const height = fontPx * 1.35 + EQUIPOTENTIAL_LABEL_PADDING_PX * 2;
  return {
    x: center.x - width / 2 - EQUIPOTENTIAL_LABEL_COLLISION_PADDING_PX,
    y: center.y - height / 2 - EQUIPOTENTIAL_LABEL_COLLISION_PADDING_PX,
    width: width + EQUIPOTENTIAL_LABEL_COLLISION_PADDING_PX * 2,
    height: height + EQUIPOTENTIAL_LABEL_COLLISION_PADDING_PX * 2,
    rawWidth: width,
    rawHeight: height,
    angle,
  };
}

function boxesOverlap(first, second) {
  return !(
    first.x + first.width < second.x ||
    second.x + second.width < first.x ||
    first.y + first.height < second.y ||
    second.y + second.height < first.y
  );
}

function boxInsideViewport(box, scale) {
  return (
    box.x >= EQUIPOTENTIAL_LABEL_EDGE_MARGIN_PX &&
    box.y >= EQUIPOTENTIAL_LABEL_EDGE_MARGIN_PX &&
    box.x + box.width <= scale.widthPx - EQUIPOTENTIAL_LABEL_EDGE_MARGIN_PX &&
    box.y + box.height <= scale.heightPx - EQUIPOTENTIAL_LABEL_EDGE_MARGIN_PX
  );
}

function equipotentialSourceObstacleBoxes(singularities, viewBox, scale) {
  return singularities.map((source) => {
    const center = worldPointToScreen(source.position, viewBox, scale);
    const radiusPx = POINT_VISUAL_RADIUS_CM / Math.max(1e-6, scale.xUnitsPerPx);
    const size = radiusPx * 2 + 42;
    return {
      x: center.x - size / 2,
      y: center.y - size / 2,
      width: size,
      height: size,
    };
  });
}

function labelLocalStraightness(points, targetLength, totalLength) {
  const before = screenPointAtLength(points, Math.max(0, targetLength - EQUIPOTENTIAL_LABEL_LOCAL_SAMPLE_PX));
  const center = screenPointAtLength(points, targetLength);
  const after = screenPointAtLength(points, Math.min(totalLength, targetLength + EQUIPOTENTIAL_LABEL_LOCAL_SAMPLE_PX));
  if (!before || !center || !after) {
    return 0;
  }
  const first = { x: center.x - before.x, y: center.y - before.y };
  const second = { x: after.x - center.x, y: after.y - center.y };
  const firstMagnitude = Math.hypot(first.x, first.y);
  const secondMagnitude = Math.hypot(second.x, second.y);
  if (firstMagnitude <= 1e-9 || secondMagnitude <= 1e-9) {
    return 0;
  }
  return (first.x / firstMagnitude) * (second.x / secondMagnitude) +
    (first.y / firstMagnitude) * (second.y / secondMagnitude);
}

function equipotentialLabelCandidate(entry, text, screenPoints, totalLength, fraction, scale, boxes) {
  const targetLength = totalLength * fraction;
  if (labelLocalStraightness(screenPoints, targetLength, totalLength) < EQUIPOTENTIAL_LABEL_STRAIGHTNESS_MIN_DOT) {
    return null;
  }
  const point = screenPointAtLength(screenPoints, targetLength);
  if (!point) {
    return null;
  }
  const tangentMagnitude = Math.hypot(point.tangentX, point.tangentY);
  if (tangentMagnitude <= 1e-9) {
    return null;
  }
  const angle = normalizedScreenAngle(point.tangentX, point.tangentY);
  const box = equipotentialLabelBox(text, point, angle, scale);
  if (!boxInsideViewport(box, scale) || boxes.some((candidateBox) => boxesOverlap(box, candidateBox))) {
    return null;
  }
  return {
    level: entry.level,
    text,
    x: point.viewportX,
    y: point.viewportY,
    angle,
    box,
    widthUnits: box.rawWidth * scale.xUnitsPerPx,
    heightUnits: box.rawHeight * scale.yUnitsPerPx,
    fontSizeUnits: scale.fontPx * EQUIPOTENTIAL_LABEL_FONT_RATIO * scale.yUnitsPerPx,
  };
}

function buildEquipotentialLabels(paths, step, scale, singularities) {
  const viewBox = compute2dViewBox();
  const acceptedBoxes = equipotentialSourceObstacleBoxes(singularities, viewBox, scale);
  const labels = [];
  for (const entry of paths) {
    if (labels.length >= EQUIPOTENTIAL_LABEL_MAX_COUNT) {
      break;
    }
    const screenPoints = equipotentialPathScreenPoints(entry.points, viewBox, scale);
    const totalLength = screenPolylineLength(screenPoints);
    if (totalLength < EQUIPOTENTIAL_LABEL_MIN_PATH_LENGTH_PX) {
      continue;
    }
    const text = formatPotentialLabel(entry.level, step);
    const fractionGroups = totalLength >= EQUIPOTENTIAL_LABEL_DOUBLE_MIN_PATH_LENGTH_PX
      ? EQUIPOTENTIAL_LABEL_DOUBLE_FRACTIONS
      : [EQUIPOTENTIAL_LABEL_CANDIDATE_FRACTIONS];
    for (const fractions of fractionGroups) {
      if (labels.length >= EQUIPOTENTIAL_LABEL_MAX_COUNT) {
        break;
      }
      let accepted = null;
      for (const fraction of fractions) {
        accepted = equipotentialLabelCandidate(entry, text, screenPoints, totalLength, fraction, scale, acceptedBoxes);
        if (accepted) {
          break;
        }
      }
      if (accepted) {
        labels.push(accepted);
        acceptedBoxes.push(accepted.box);
      }
    }
  }
  return labels;
}

function renderEquipotentialLabels(labels) {
  if (labels.length === 0) {
    return '<g class="equipotential-label-layer" data-testid="equipotential-label-layer" data-equipotential-label-count="0"></g>';
  }
  const markup = labels.map((label) => {
    const rectX = -label.widthUnits / 2;
    const rectY = -label.heightUnits / 2;
    return `
      <g
        class="equipotential-label"
        data-testid="equipotential-label-2d"
        data-potential-v="${label.level.toPrecision(6)}"
        data-label-text="${escapeHtml(label.text)}"
        data-label-angle="${label.angle.toFixed(2)}"
        transform="translate(${label.x.toFixed(3)} ${label.y.toFixed(3)}) rotate(${label.angle.toFixed(2)})"
      >
        <rect
          class="equipotential-label-bg"
          x="${rectX.toFixed(3)}"
          y="${rectY.toFixed(3)}"
          width="${label.widthUnits.toFixed(3)}"
          height="${label.heightUnits.toFixed(3)}"
          rx="${(label.heightUnits * 0.28).toFixed(3)}"
        ></rect>
        <text
          class="equipotential-label-text"
          x="0"
          y="0"
          style="font-size: ${label.fontSizeUnits.toFixed(3)}px;"
        >${escapeHtml(label.text)}</text>
      </g>
    `;
  });
  return `
    <g
      class="equipotential-label-layer"
      data-testid="equipotential-label-layer"
      data-equipotential-label-count="${labels.length}"
      data-label-style="contour-inline"
    >
      ${markup.join("")}
    </g>
  `;
}

function computeEquipotentialTraceResult(fieldSamples, singularities, bounds, gridSize, scale) {
  const grid = sampleEquipotentialGrid(fieldSamples, singularities, bounds, gridSize);
  const levelData = chooseEquipotentialLevels(grid.finiteValues);
  const rawPaths = [];
  const minLengthMeters = (EQUIPOTENTIAL_MIN_PATH_LENGTH_PX * ((scale.xUnitsPerPx + scale.yUnitsPerPx) / 2)) /
    VIEWPORT_METERS_TO_UNITS;
  const tolerance = Math.max(grid.dx, grid.dy) * 0.55;
  for (const level of levelData.levels) {
    const segments = contourSegmentsForLevel(level, bounds, grid, gridSize);
    const linkedPaths = linkContourSegments(segments, tolerance);
    for (const points of linkedPaths) {
      const length = worldPathLength(points);
      if (length < minLengthMeters) {
        continue;
      }
      rawPaths.push({
        level,
        points,
        length,
      });
    }
  }
  rawPaths.sort((a, b) => b.length - a.length);
  return {
    paths: rawPaths.slice(0, EQUIPOTENTIAL_MAX_RENDER_PATHS),
    rawPathCount: rawPaths.length,
    levelCount: levelData.levels.length,
    step: levelData.step,
    minPotential: levelData.min,
    maxPotential: levelData.max,
    finiteSampleCount: grid.finiteValues.length,
    gridSize,
  };
}

function getEquipotentialTraceResult(fieldSamples, singularities, bounds, gridSize, scale) {
  const key = equipotentialCacheKey(fieldSamples, singularities, bounds, gridSize);
  if (equipotentialTraceCache.key === key && equipotentialTraceCache.result) {
    return equipotentialTraceCache.result;
  }
  const result = computeEquipotentialTraceResult(fieldSamples, singularities, bounds, gridSize, scale);
  equipotentialTraceCache = { key, result };
  return result;
}

function renderEquipotentialLines2d(scale) {
  if (!state.showEquipotentials) {
    return '<g data-testid="equipotential-layer" data-equipotential-count="0" data-enabled="false"></g>';
  }
  const fieldSamples = state.scene.sources.flatMap((source) => sourceChargeSamples2d(source));
  const singularities = pointChargeSingularities2d();
  if (fieldSamples.length === 0) {
    return '<g data-testid="equipotential-layer" data-equipotential-count="0" data-enabled="true"></g>';
  }
  const bounds = compute2dVisibleWorldBounds();
  const gridSize = equipotentialGridSize(scale);
  const traceResult = getEquipotentialTraceResult(fieldSamples, singularities, bounds, gridSize, scale);
  const labels = buildEquipotentialLabels(traceResult.paths, traceResult.step, scale, singularities);
  const paths = traceResult.paths.map((entry) => `
    <path
      class="equipotential-line"
      data-testid="equipotential-line-2d"
      data-potential-v="${entry.level.toPrecision(6)}"
      data-path-model="marching-squares-catmull-rom"
      data-point-count="${entry.points.length}"
      d="${smoothViewportPath(entry.points)}"
    ></path>
  `);
  return `
    <g
      class="equipotential-layer"
      data-testid="equipotential-layer"
      data-enabled="true"
      data-equipotential-count="${paths.length}"
      data-equipotential-label-count="${labels.length}"
      data-raw-equipotential-count="${traceResult.rawPathCount}"
      data-level-count="${traceResult.levelCount}"
      data-auto-delta-v="${formatNumber(traceResult.step, 5)}"
      data-grid-columns="${traceResult.gridSize.columns}"
      data-grid-rows="${traceResult.gridSize.rows}"
      data-method="marching-squares"
      data-linking="segment-graph"
      data-singularity-radius-m="${EQUIPOTENTIAL_SINGULARITY_RADIUS_M}"
    >
      ${paths.join("")}
      ${renderEquipotentialLabels(labels)}
    </g>
  `;
}

function renderFieldLines2d(scale) {
  if (!state.showFieldLines) {
    return '<g data-testid="field-line-layer" data-field-line-count="0" data-enabled="false"></g>';
  }

  const fieldSamples = state.scene.sources.flatMap((source) => sourceChargeSamples2d(source));
  const seedSources = fieldLineSeedSources2d();
  if (fieldSamples.length === 0 || seedSources.length === 0) {
    return '<g data-testid="field-line-layer" data-field-line-count="0" data-enabled="true" data-compute-source="backend"></g>';
  }

  const stepMetrics = fieldLineStepMetrics(scale);
  const bounds = compute2dFieldLineBounds(scale);
  if (!state.fieldLineResult) {
    return '<g data-testid="field-line-layer" data-field-line-count="0" data-enabled="true" data-compute-source="backend" data-request-current="false"></g>';
  }
  if (ENABLE_LEGACY_FIELD_LINE_DEBUG_COMPARISON) {
    getFieldLineTraceResult(fieldSamples, seedSources, bounds, stepMetrics);
  }
  const traceResult = backendFieldLineTraceResult(
    state.fieldLineResult,
    fieldSamples,
    seedSources,
    stepMetrics,
  );
  const paths = [];
  const arrows = [];
  for (const entry of traceResult.entries) {
    const charge = entry.charge;
    const renderPoints = entry.arrowPoints;
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
          data-path-model="field-tangent-cubic"
          data-display-smoothing="field-tangent"
          data-endpoint-class="${entry.endpointClass}"
          data-terminal-source-id="${entry.terminalSourceId}"
          data-seed-attempt="${entry.seedAttempt}"
          data-seed-index="${entry.seedIndex}"
          data-stop-reason="${entry.stopReason}"
          data-point-count="${renderPoints.length}"
          data-curve-sample-count="${entry.curvePoints.length}"
          data-direction-min-dot="${entry.minDirectionDot.toFixed(3)}"
          d="${fieldLinePath(renderPoints, fieldSamples)}"
        ></path>
      `);
    arrows.push(fieldLineArrowMarkup(entry.arrowPoints, entry, fieldSamples, scale));
  }

  return `
    <g
      class="field-line-layer"
      data-testid="field-line-layer"
      data-field-line-count="${paths.length}"
      data-display-strategy="${FIELD_LINE_DISPLAY_STRATEGY}"
      data-candidates-per-point-charge="${traceResult.chargeRayCount}"
      data-candidates-per-charged-source="${traceResult.chargeRayCount}"
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
      data-trace-step-m="${traceResult.stepMeters.toFixed(5)}"
      data-curve-sample-spacing-m="${traceResult.sampleSpacingMeters.toFixed(5)}"
      data-arrow-placement="arc-fraction"
      data-arrow-fraction-base="${FIELD_LINE_ARROW_FRACTION_BASE}"
      data-conflict-filter="${traceResult.useConflictFilter ? "display-spatial" : "off"}"
      data-compute-source="backend"
      data-rendered-request-id="${traceResult.requestId}"
      data-request-current="${traceResult.requestId === state.fieldLineRequestId ? "true" : "false"}"
      data-effective-backend="${traceResult.execution.backend_effective}"
      data-precision="${traceResult.execution.precision}"
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
    ${renderEquipotentialLines2d(scale)}
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
      ${renderMotionLayer2d()}
      ${sourceMarkup}
    </svg>
  `;
}

function renderMotionLayer2d() {
  const samples = state.motion.samples;
  if (samples.length === 0) {
    return '<g data-testid="motion-layer-2d" data-point-count="0"></g>';
  }
  const visibleSamples = samples.slice(0, state.motion.frameIndex + 1);
  const path = visibleSamples
    .map((sample, index) => {
      const point = mapToViewport(sample.position.x, sample.position.y);
      return `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`;
    })
    .join(" ");
  const current = visibleSamples[visibleSamples.length - 1];
  const marker = mapToViewport(current.position.x, current.position.y);
  const charge = Number(motionInputs.charge.value);
  return `
    <g class="motion-layer" data-testid="motion-layer-2d" data-point-count="${visibleSamples.length}">
      <path class="motion-trail" fill="none" stroke="#39ff14" stroke-width="0.22" d="${path}"></path>
      <circle
        class="motion-particle ${charge >= 0 ? "positive" : "negative"}"
        data-testid="motion-particle-2d"
        cx="${marker.x}"
        cy="${marker.y}"
        fill="#39ff14"
        stroke="#39ff14"
        stroke-width="0.06"
        r="0.16"
        style="fill: #39ff14; stroke: #39ff14; stroke-width: 0.06px;"
      ></circle>
    </g>
  `;
}

function renderMotionFrame2d() {
  const layer = view2d.querySelector("[data-testid='motion-layer-2d']");
  if (!layer) {
    render2d();
    return;
  }
  layer.outerHTML = renderMotionLayer2d();
}

function cancelMotionAnimation() {
  if (state.motion.animationId !== null) {
    window.cancelAnimationFrame(state.motion.animationId);
    state.motion.animationId = null;
  }
  state.motion.running = false;
}

function updateMotionReadout() {
  if (state.motion.samples.length === 0) {
    motionReadout.textContent = "先添加或加载电场源，再计算测试电荷轨迹。";
    return;
  }
  const sample = state.motion.samples[state.motion.frameIndex];
  motionReadout.textContent =
    `t=${formatNumber(sample.t_s, 4)} s；` +
    `位置 (${formatNumber(sample.position.x * 100, 4)}, ${formatNumber(sample.position.y * 100, 4)}) cm；` +
    `速度 (${formatNumber(sample.velocity.x * 100, 4)}, ${formatNumber(sample.velocity.y * 100, 4)}) cm/s`;
}

function clearMotionTrajectory() {
  cancelMotionAnimation();
  state.motion.samples = [];
  state.motion.frameIndex = 0;
  motionState.textContent = "待命";
  updateMotionReadout();
}

function animateMotionTrajectory() {
  cancelMotionAnimation();
  if (state.motion.samples.length === 0) {
    return;
  }
  state.motion.running = true;
  state.motion.frameIndex = 0;
  motionState.textContent = "播放中";
  let previousTime = 0;

  function tick(timestamp) {
    if (!state.motion.running) {
      return;
    }
    if (previousTime === 0 || timestamp - previousTime >= 28) {
      previousTime = timestamp;
      state.motion.frameIndex += 1;
      renderMotionFrame2d();
      updateMotionReadout();
    }
    if (state.motion.frameIndex >= state.motion.samples.length - 1) {
      cancelMotionAnimation();
      motionState.textContent = "播放完成";
      return;
    }
    state.motion.animationId = window.requestAnimationFrame(tick);
  }

  renderMotionFrame2d();
  updateMotionReadout();
  state.motion.animationId = window.requestAnimationFrame(tick);
}

async function runMotionSimulation() {
  if (state.scene.sources.length === 0) {
    motionState.textContent = "请先添加电场源";
    return;
  }
  cancelMotionAnimation();
  motionState.textContent = "计算中";
  setMode("2D");
  const cm = 0.01;
  const result = await evaluateTrajectory({
    request_id: `ui-trajectory-${Date.now()}`,
    scene: state.scene,
    particle: {
      charge_c: Number(motionInputs.charge.value) * 1e-9,
      mass_kg: Number(motionInputs.mass.value) * 1e-6,
      position: {
        x: Number(motionInputs.x.value) * cm,
        y: Number(motionInputs.y.value) * cm,
        z: 0,
        unit: "m",
      },
      velocity: {
        x: Number(motionInputs.vx.value) * cm,
        y: Number(motionInputs.vy.value) * cm,
        z: 0,
        unit: "m",
      },
    },
    dt_s: Number(motionInputs.dt.value),
    steps: Number(motionInputs.steps.value),
    quality: state.quality,
    record_every: 1,
  });
  renderExecutionStatus(result.execution);
  state.motion.samples = result.samples;
  state.motion.frameIndex = 0;
  motionState.textContent = `已计算 ${result.samples.length} 帧`;
  animateMotionTrajectory();
}

function zoom2d(deltaY) {
  const nextZoom = state.view2d.zoom * Math.exp(-deltaY * 0.0012);
  state.view2d.zoom = nextZoom;
  clamp2dView();
  render2d();
  scheduleFieldLineEvaluation();
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
  scheduleFieldLineEvaluation();
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
  if (state.showFieldLines || state.showEquipotentials) {
    const lineCount = view2d.querySelectorAll("[data-testid='field-line-2d']").length;
    const equipotentialCount = view2d.querySelectorAll("[data-testid='equipotential-line-2d']").length;
    overlayStatus.textContent = state.scene.sources.length === 0
      ? "等待源"
      : `电场线 ${lineCount} 条；等势线 ${equipotentialCount} 条`;
    if (state.showFieldLines && state.showEquipotentials) {
      overlaySummary.textContent = "二维视图已显示电场线和等势线；电场线沿合电场方向，等势线来自自动 ΔV 的电势等值线。";
    } else if (state.showFieldLines) {
      overlaySummary.textContent = lineCount > 0
        ? "二维视图已显示电场线；方向按合电场追踪，箭头表示电场方向。"
        : "当前二维源不足以生成电场线。";
    } else {
      overlaySummary.textContent = equipotentialCount > 0
        ? "二维视图已显示等势线；相邻线的电势差由系统自动选择。"
        : "当前二维源不足以生成等势线。";
    }
    return;
  }
  if (!state.overlayResult) {
    overlayStatus.textContent = state.scene.sources.length === 0 ? "等待源" : overlayStatus.textContent;
    overlaySummary.textContent = "点击“显示电场”或“显示等势线”后，二维视图会显示对应的可视化。";
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
  renderOverlayControls();
}

function setEmptyComputationState() {
  state.lastResult = null;
  state.overlayResult = null;
  state.fieldLineResult = null;
  solverStatus.textContent = "等待源";
  overlayStatus.textContent = "等待源";
  if (potentialValue) {
    potentialValue.textContent = "暂无";
  }
  fieldVectorValue.textContent = "暂无";
  fieldMagnitudeValue.textContent = "暂无";
  contributionList.innerHTML = "<li>还没有源贡献。</li>";
  warningList.innerHTML = "<li>暂无提示。</li>";
  overlaySummary.textContent = "点击“显示电场”或“显示等势线”后，二维视图会显示对应的可视化。";
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
  renderExecutionStatus(result.execution);
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
  renderExecutionStatus(result.execution);
  render2d();
  renderOverlaySummary();
}

async function evaluateFieldLinesForView(requestId) {
  const viewBox = compute2dViewBox();
  const scale = screenScaleForViewBox(viewBox);
  const bounds = compute2dFieldLineBounds(scale);
  const result = await evaluateFieldLines({
    request_id: requestId,
    scene: state.scene,
    bounds: {
      min_x: bounds.minX,
      max_x: bounds.maxX,
      min_y: bounds.minY,
      max_y: bounds.maxY,
    },
    quality: state.quality,
    density: 1,
    display_max_count: FIELD_LINE_DISPLAY_MAX_COUNT,
    backend: "auto",
  });
  if (result.request_id !== state.fieldLineRequestId) {
    return;
  }
  state.fieldLineResult = result;
  renderExecutionStatus(result.execution);
  render2d();
  renderOverlaySummary();
}

function scheduleFieldLineEvaluation() {
  fieldLineRequestSerial += 1;
  state.fieldLineRequestId = `ui-field-lines-${fieldLineRequestSerial}`;
  const requestId = state.fieldLineRequestId;
  if (fieldLineEvaluationTimer) {
    window.clearTimeout(fieldLineEvaluationTimer);
    fieldLineEvaluationTimer = null;
  }
  if (state.mode !== "2D" || !state.showFieldLines || state.scene.sources.length === 0) {
    if (state.scene.sources.length === 0) {
      state.fieldLineResult = null;
    }
    return;
  }
  const validationMessage = sceneValidationMessage();
  if (validationMessage) {
    overlayStatus.textContent = validationMessage;
    return;
  }
  render2d();
  fieldLineEvaluationTimer = window.setTimeout(() => {
    fieldLineEvaluationTimer = null;
    evaluateFieldLinesForView(requestId).catch((error) => {
      if (requestId === state.fieldLineRequestId) {
        overlayStatus.textContent = error.message;
      }
    });
  }, 120);
}

let evaluationTimer = null;

function scheduleEvaluation() {
  scheduleFieldLineEvaluation();
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
  clearMotionTrajectory();
  state.scene = preset.scene;
  state.lastResult = null;
  state.overlayResult = null;
  state.fieldLineResult = null;
  state.fieldLineRequestId = "";
  fieldLineTraceCache = { key: "", result: null };
  equipotentialTraceCache = { key: "", result: null };
  refreshSourceIndexes();
  presetStatus.textContent = `已加载：${preset.title}。`;
  renderAll();
  scheduleEvaluation();
}

async function initialiseShell() {
  const config = await getConfig();
  await refreshComputeStatus();
  document.title = "电磁工作台 | 静电场";
  runtimeStatus.textContent =
    `本地 Three.js ${config.runtime.three.version} 已就绪。` +
    "二维与三维交互已启用。";
}

pointSourceForm.addEventListener("submit", addPointSourceFromForm);
lineSegmentSourceForm.addEventListener("submit", addLineSegmentFromForm);
ringSourceForm.addEventListener("submit", addRingFromForm);
diskSourceForm.addEventListener("submit", addDiskFromForm);
document.querySelector("#add-line-segment").addEventListener("click", (event) => {
  event.preventDefault();
  lineSegmentSourceForm.requestSubmit();
});
document.querySelector("#add-ring").addEventListener("click", (event) => {
  event.preventDefault();
  ringSourceForm.requestSubmit();
});
document.querySelector("#add-disk").addEventListener("click", (event) => {
  event.preventDefault();
  diskSourceForm.requestSubmit();
});
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
  renderOverlayControls();
});
toggleEquipotentialLinesButton.addEventListener("click", () => {
  toggleEquipotentials();
  renderOverlayControls();
});
probeForm.addEventListener("submit", measureProbeFromInputs);
probeForm.addEventListener("input", () => {
  solverStatus.textContent = state.scene.sources.length === 0 ? "等待源" : "等待确定";
});
document.querySelector("#motion-run").addEventListener("click", () => {
  runMotionSimulation().catch((error) => {
    motionState.textContent = "计算失败";
    motionReadout.textContent = error.message;
  });
});
document.querySelector("#motion-reset").addEventListener("click", clearMotionTrajectory);
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
    scheduleFieldLineEvaluation();
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
