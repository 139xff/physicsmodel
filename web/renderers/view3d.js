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
const DISPLAY_SCENE_RADIUS = 0.45;
const MIN_DISPLAY_MARKER_RADIUS = 0.005;
const MIN_WORLD_SPAN_M = 0.36;

function threeVectorFromComponents(components) {
  return new THREE.Vector3(components.x, components.y, components.z);
}

function threePointFromPosition(position, transform) {
  if (!transform) {
    return new THREE.Vector3(position.x, position.z, position.y);
  }
  return new THREE.Vector3(
    (position.x / transform.scaleBase - transform.centerXNorm) * transform.unitsPerNorm,
    (position.z / transform.scaleBase - transform.centerZNorm) * transform.unitsPerNorm,
    (position.y / transform.scaleBase - transform.centerYNorm) * transform.unitsPerNorm,
  );
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
  camera = new THREE.PerspectiveCamera(48, width / height, 0.01, 100);
  camera.position.set(0.45, 0.38, 0.42);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.addEventListener("change", () => {
    renderer.render(threeScene, camera);
  });

  gridHelper = new THREE.GridHelper(0.8, 16, 0x8ea3b7, 0xd3dce6);
  axesHelper = new THREE.AxesHelper(0.28);
  threeScene.add(gridHelper);
  threeScene.add(axesHelper);
  threeScene.add(new THREE.AmbientLight(0xffffff, 0.85));
  sceneGroup = new THREE.Group();
  threeScene.add(sceneGroup);
}

function sourceBoundingRadius(source) {
  if (source.kind === "point") {
    return 0.018;
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
  return 0.018;
}

function collect3dFrameItems(state) {
  const items = state.scene.sources.map((source) => ({
    position: source.position,
    radius: sourceBoundingRadius(source),
  }));
  items.push({ position: state.probe, radius: 0.012 });
  return items;
}

function frameScaleBase(items) {
  const values = [MIN_WORLD_SPAN_M];
  for (const item of items) {
    values.push(
      Math.abs(item.position.x),
      Math.abs(item.position.y),
      Math.abs(item.position.z),
      Math.abs(item.radius),
    );
  }
  return Math.max(...values.filter((value) => Number.isFinite(value)));
}

function compute3dDisplayTransform(state) {
  const items = collect3dFrameItems(state);
  const scaleBase = frameScaleBase(items);
  const bounds = {
    minX: Infinity,
    maxX: -Infinity,
    minY: Infinity,
    maxY: -Infinity,
    minZ: Infinity,
    maxZ: -Infinity,
  };

  for (const item of items) {
    const radiusNorm = item.radius / scaleBase;
    const xNorm = item.position.x / scaleBase;
    const yNorm = item.position.y / scaleBase;
    const zNorm = item.position.z / scaleBase;
    bounds.minX = Math.min(bounds.minX, xNorm - radiusNorm);
    bounds.maxX = Math.max(bounds.maxX, xNorm + radiusNorm);
    bounds.minY = Math.min(bounds.minY, yNorm - radiusNorm);
    bounds.maxY = Math.max(bounds.maxY, yNorm + radiusNorm);
    bounds.minZ = Math.min(bounds.minZ, zNorm - radiusNorm);
    bounds.maxZ = Math.max(bounds.maxZ, zNorm + radiusNorm);
  }

  const minSpanNorm = MIN_WORLD_SPAN_M / scaleBase;
  const spanXNorm = Math.max(bounds.maxX - bounds.minX, minSpanNorm);
  const spanYNorm = Math.max(bounds.maxY - bounds.minY, minSpanNorm);
  const spanZNorm = Math.max(bounds.maxZ - bounds.minZ, minSpanNorm);
  const halfSpanNorm = Math.max(spanXNorm, spanYNorm, spanZNorm) * 0.62;

  return {
    scaleBase,
    centerXNorm: (bounds.minX + bounds.maxX) / 2,
    centerYNorm: (bounds.minY + bounds.maxY) / 2,
    centerZNorm: (bounds.minZ + bounds.maxZ) / 2,
    unitsPerNorm: DISPLAY_SCENE_RADIUS / halfSpanNorm,
  };
}

function radiusToDisplay(radius, transform, minimum = 0) {
  return Math.max(minimum, (radius / transform.scaleBase) * transform.unitsPerNorm);
}

function computeSceneFrame(state, transform) {
  const entries = state.scene.sources.map((source) => ({
    center: threePointFromPosition(source.position, transform),
    radius: radiusToDisplay(sourceBoundingRadius(source), transform, MIN_DISPLAY_MARKER_RADIUS),
  }));
  entries.push({
    center: threePointFromPosition(state.probe, transform),
    radius: radiusToDisplay(0.012, transform, MIN_DISPLAY_MARKER_RADIUS),
  });

  const box = new THREE.Box3();
  for (const entry of entries) {
    const radiusVector = new THREE.Vector3(entry.radius, entry.radius, entry.radius);
    box.expandByPoint(entry.center.clone().sub(radiusVector));
    box.expandByPoint(entry.center.clone().add(radiusVector));
  }

  const center = new THREE.Vector3();
  const size = new THREE.Vector3();
  box.getCenter(center);
  box.getSize(size);

  const radius = Math.max(
    ...entries.map((entry) => entry.center.distanceTo(center) + entry.radius),
    0.35,
  );
  return { center, radius, size };
}

function update3dFrame(view3d, state, transform) {
  const frame = computeSceneFrame(state, transform);
  const fovRadians = THREE.MathUtils.degToRad(camera.fov);
  const distance = Math.max(0.7, frame.radius / Math.sin(fovRadians / 2));
  const direction = new THREE.Vector3(0.62, 0.52, 0.58).normalize();

  camera.position.copy(frame.center).add(direction.multiplyScalar(distance));
  camera.near = Math.max(0.0001, Math.min(0.01, frame.radius / 1000));
  camera.far = Math.max(100, distance + frame.radius * 4);
  camera.updateProjectionMatrix();

  controls.target.copy(frame.center);
  controls.update();

  const gridSize = Math.max(0.8, frame.radius * 2.4);
  gridHelper.scale.setScalar(gridSize / 0.8);
  gridHelper.position.set(frame.center.x, 0, frame.center.z);
  axesHelper.scale.setScalar(Math.max(1, frame.radius / 0.28));
  axesHelper.position.copy(frame.center);

  view3d.dataset.sceneRadiusThree = Number(frame.radius.toPrecision(8)).toString();
  view3d.dataset.cameraFarThree = Number(camera.far.toPrecision(8)).toString();
  view3d.dataset.cameraTargetThree = [frame.center.x, frame.center.y, frame.center.z]
    .map((component) => Number(component.toPrecision(8)).toString())
    .join(",");
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

function meshForSource(source, transform) {
  if (source.kind === "ring") {
    const radius = radiusToDisplay(source.radius_m, transform, MIN_DISPLAY_MARKER_RADIUS);
    const geometry = new THREE.TorusGeometry(radius, Math.max(radius * 0.05, 0.003), 10, 72);
    const material = new THREE.MeshBasicMaterial({ color: 0xb7791f });
    const mesh = new THREE.Mesh(geometry, material);
    const threeNormal = threeVectorFromComponents(physicsNormalToThreeComponents(source.normal));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), threeNormal);
    return mesh;
  }

  if (source.kind === "line_segment") {
    const length = radiusToDisplay(source.length_m, transform, MIN_DISPLAY_MARKER_RADIUS * 2);
    const geometry = new THREE.CylinderGeometry(0.004, 0.004, length, 12);
    const material = new THREE.MeshBasicMaterial({ color: 0x0071e3 });
    const mesh = new THREE.Mesh(geometry, material);
    const direction = threeVectorFromComponents(physicsNormalToThreeComponents(source.orientation));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
    return mesh;
  }

  if (source.kind === "disk" || source.kind === "infinite_plane") {
    const radius = radiusToDisplay(
      source.kind === "disk" ? source.radius_m : source.display_extent_m * 0.5,
      transform,
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
      ? radiusToDisplay(source.radius_m, transform, MIN_DISPLAY_MARKER_RADIUS)
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

function _addFieldArrows(parent, state, transform) {
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
    const origin = threePointFromPosition(pt, transform);
    const arrow = new THREE.ArrowHelper(dir, origin, len, ARROW_COLOR, len * 0.28, len * 0.16);
    parent.add(arrow);
  }
}

export function render3d(view3d, state) {
  const transform = compute3dDisplayTransform(state);
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
    const mesh = meshForSource(source, transform);
    mesh.position.copy(threePointFromPosition(source.position, transform));
    sceneGroup.add(mesh);
  }

  const probeGeometry = new THREE.SphereGeometry(MIN_DISPLAY_MARKER_RADIUS, 12, 8);
  const probeMaterial = new THREE.MeshBasicMaterial({
    color: 0xff3b30,
    transparent: true,
    opacity: 0.7,
  });
  const probeMesh = new THREE.Mesh(probeGeometry, probeMaterial);
  probeMesh.position.copy(threePointFromPosition(state.probe, transform));
  sceneGroup.add(probeMesh);

  _addFieldArrows(sceneGroup, state, transform);
  update3dFrame(view3d, state, transform);
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
