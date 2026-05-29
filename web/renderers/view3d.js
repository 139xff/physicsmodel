import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

import { formatThreeNormal, physicsNormalToThreeComponents } from "./coordinates.js";

let sceneGroup;
let camera;
let renderer;
let controls;
let threeScene;
let gridHelper;
let axesHelper;
let animFrameId = null;
const GRID_AXIS_LIMIT_M = 10;
const GRID_SIZE_M = GRID_AXIS_LIMIT_M * 2;
const GRID_CELL_SIZE_M = 0.01;
const GRID_DIVISIONS = GRID_SIZE_M / GRID_CELL_SIZE_M;
const DEFAULT_CAMERA_ZOOM = 100;
const CAMERA_NEAR_M = 0.001;
const CAMERA_FAR_M = 10000;
const CAMERA_MAX_DISTANCE_M = 5000;
const MIN_DISPLAY_MARKER_RADIUS = 0.005;
const AXIS_COLORS = {
  x: 0xff4d4f,
  y: 0x2563eb,
  z: 0x22c55e,
};

function threeVectorFromComponents(components) {
  return new THREE.Vector3(components.x, components.y, components.z);
}

function threePointFromPosition(position) {
  return new THREE.Vector3(position.x, position.z, position.y);
}

function createFullAxesHelper(size) {
  const vertices = new Float32Array([
    -size,
    0,
    0,
    size,
    0,
    0,
    0,
    0,
    -size,
    0,
    0,
    size,
    0,
    -size,
    0,
    0,
    size,
    0,
  ]);
  const xColor = new THREE.Color(AXIS_COLORS.x);
  const yColor = new THREE.Color(AXIS_COLORS.y);
  const zColor = new THREE.Color(AXIS_COLORS.z);
  const colors = new Float32Array([
    xColor.r,
    xColor.g,
    xColor.b,
    xColor.r,
    xColor.g,
    xColor.b,
    yColor.r,
    yColor.g,
    yColor.b,
    yColor.r,
    yColor.g,
    yColor.b,
    zColor.r,
    zColor.g,
    zColor.b,
    zColor.r,
    zColor.g,
    zColor.b,
  ]);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(vertices, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const material = new THREE.LineBasicMaterial({
    linewidth: 2,
    vertexColors: true,
  });
  const helper = new THREE.LineSegments(geometry, material);
  helper.name = "full-coordinate-axes";
  return helper;
}

function surfaceSize(container) {
  const rect = container.getBoundingClientRect();
  return {
    width: Math.max(320, Math.floor(rect.width || container.clientWidth || 640)),
    height: Math.max(360, Math.floor(rect.height || container.clientHeight || 520)),
  };
}

function ensure3d(view3d) {
  if (renderer) {
    return;
  }

  const { width, height } = surfaceSize(view3d);
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height, false);
  view3d.appendChild(renderer.domElement);

  threeScene = new THREE.Scene();
  threeScene.background = new THREE.Color(0xf7f9fc);
  camera = new THREE.PerspectiveCamera(48, width / height, CAMERA_NEAR_M, CAMERA_FAR_M);
  camera.position.set(12, 10, 12);
  camera.zoom = DEFAULT_CAMERA_ZOOM;
  camera.updateProjectionMatrix();
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.maxDistance = CAMERA_MAX_DISTANCE_M;
  controls.target.set(0, 0, 0);
  controls.addEventListener("change", () => {
    renderer.render(threeScene, camera);
  });

  gridHelper = new THREE.GridHelper(GRID_SIZE_M, GRID_DIVISIONS, 0x8ea3b7, 0xd3dce6);
  axesHelper = createFullAxesHelper(GRID_AXIS_LIMIT_M);
  threeScene.add(gridHelper);
  threeScene.add(axesHelper);
  threeScene.add(new THREE.AmbientLight(0xffffff, 0.85));
  sceneGroup = new THREE.Group();
  threeScene.add(sceneGroup);
}

function update3dFrame(view3d) {
  camera.near = CAMERA_NEAR_M;
  camera.far = CAMERA_FAR_M;
  camera.zoom = DEFAULT_CAMERA_ZOOM;
  camera.updateProjectionMatrix();
  camera.position.set(12, 10, 12);
  controls.target.set(0, 0, 0);
  controls.update();
  gridHelper.position.set(0, 0, 0);
  axesHelper.position.set(0, 0, 0);
  view3d.dataset.gridSizeMeters = GRID_SIZE_M.toString();
  view3d.dataset.gridCellSizeMeters = GRID_CELL_SIZE_M.toString();
  view3d.dataset.gridDivisions = GRID_DIVISIONS.toString();
  view3d.dataset.axisLimitMeters = GRID_AXIS_LIMIT_M.toString();
  view3d.dataset.axisMinMeters = (-GRID_AXIS_LIMIT_M).toString();
  view3d.dataset.axisMaxMeters = GRID_AXIS_LIMIT_M.toString();
  view3d.dataset.cameraZoom = camera.zoom.toString();
  view3d.dataset.cameraFarMeters = camera.far.toString();
  view3d.dataset.controlsMaxDistanceMeters = controls.maxDistance.toString();
}

function startAnimLoop() {
  if (animFrameId !== null) {
    return;
  }
  function animate() {
    animFrameId = requestAnimationFrame(animate);
    controls.update();
    renderer.render(threeScene, camera);
  }
  animate();
}

export function stopAnimLoop() {
  if (animFrameId !== null) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }
}

function meshForSource(source) {
  if (source.kind === "ring") {
    const radius = Math.max(source.radius_m, MIN_DISPLAY_MARKER_RADIUS);
    const geometry = new THREE.TorusGeometry(radius, Math.max(radius * 0.05, 0.003), 10, 72);
    const material = new THREE.MeshBasicMaterial({ color: 0xb7791f });
    const mesh = new THREE.Mesh(geometry, material);
    const threeNormal = threeVectorFromComponents(physicsNormalToThreeComponents(source.normal));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), threeNormal);
    return mesh;
  }

  if (source.kind === "line_segment") {
    const length = Math.max(source.length_m, MIN_DISPLAY_MARKER_RADIUS * 2);
    const geometry = new THREE.CylinderGeometry(0.004, 0.004, length, 12);
    const material = new THREE.MeshBasicMaterial({ color: 0x0071e3 });
    const mesh = new THREE.Mesh(geometry, material);
    const direction = threeVectorFromComponents(physicsNormalToThreeComponents(source.orientation));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
    return mesh;
  }

  if (source.kind === "disk" || source.kind === "infinite_plane") {
    const radius = Math.max(
      source.kind === "disk" ? source.radius_m : source.display_extent_m * 0.5,
      MIN_DISPLAY_MARKER_RADIUS,
    );
    const geometry = new THREE.CircleGeometry(radius, 72);
    const material = new THREE.MeshBasicMaterial({
      color: source.kind === "disk" ? 0x0f766e : 0x6366f1,
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
    source.kind === "spherical_shell"
      ? Math.max(source.radius_m, MIN_DISPLAY_MARKER_RADIUS)
      : MIN_DISPLAY_MARKER_RADIUS,
    16,
    12,
  );
  const material = new THREE.MeshBasicMaterial({
    color: source.charge_c >= 0 ? 0x0071e3 : 0xff5a72,
    wireframe: source.kind === "spherical_shell",
  });
  return new THREE.Mesh(geometry, material);
}

function _disposeMesh(child) {
  if (child.geometry) {
    child.geometry.dispose();
  }
  if (child.material) {
    if (Array.isArray(child.material)) {
      for (const mat of child.material) {
        mat.dispose();
      }
    } else {
      child.material.dispose();
    }
  }
}

const ARROW_COLOR = 0x374151;
const ARROW_SCALE = 0.028;

function _addFieldArrows(parent, state) {
  if (!state.overlayResult || state.overlaySamples.length === 0) {
    return;
  }
  const magnitudes = state.overlayResult.samples.map((s) => s.field_magnitude_v_per_m);
  const maxMag = Math.max(...magnitudes, 1);
  for (let i = 0; i < state.overlayResult.samples.length; i += 1) {
    const sample = state.overlayResult.samples[i];
    const pt = state.overlaySamples[i];
    const field = sample.field_v_per_m;
    const mag = magnitudes[i];
    if (mag < 1e-30) {
      continue;
    }
    const dir = new THREE.Vector3(field.x, field.z, field.y).normalize();
    const len = ARROW_SCALE * (1.0 + 4.0 * (mag / maxMag));
    const origin = threePointFromPosition(pt);
    const arrow = new THREE.ArrowHelper(dir, origin, len, ARROW_COLOR, len * 0.28, len * 0.16);
    parent.add(arrow);
  }
}

export function render3d(view3d, state) {
  view3d.removeAttribute("data-ring-normal-three");
  const firstRing = state.scene.sources.find((source) => source.kind === "ring");
  if (firstRing) {
    view3d.dataset.ringNormalThree = formatThreeNormal(
      physicsNormalToThreeComponents(firstRing.normal),
    );
  }

  ensure3d(view3d);

  const { width, height } = surfaceSize(view3d);
  const canvas = renderer.domElement;
  if (canvas.width !== width || canvas.height !== height) {
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  while (sceneGroup.children.length > 0) {
    _disposeMesh(sceneGroup.children[0]);
    sceneGroup.remove(sceneGroup.children[0]);
  }

  for (const source of state.scene.sources) {
    const mesh = meshForSource(source);
    mesh.position.copy(threePointFromPosition(source.position));
    sceneGroup.add(mesh);
  }

  const probeGeometry = new THREE.SphereGeometry(MIN_DISPLAY_MARKER_RADIUS, 12, 8);
  const probeMaterial = new THREE.MeshBasicMaterial({
    color: 0xff3b30,
    transparent: true,
    opacity: 0.7,
  });
  const probeMesh = new THREE.Mesh(probeGeometry, probeMaterial);
  probeMesh.position.copy(threePointFromPosition(state.probe));
  sceneGroup.add(probeMesh);

  _addFieldArrows(sceneGroup, state);
  update3dFrame(view3d);
  startAnimLoop();
  renderer.render(threeScene, camera);
}

export function resize3d(view3d, _state) {
  if (!renderer || !camera) {
    return;
  }
  const { width, height } = surfaceSize(view3d);
  if (width === 0 || height === 0) {
    return;
  }
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.render(threeScene, camera);
}
