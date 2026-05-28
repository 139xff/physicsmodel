import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

import { formatThreeNormal, physicsNormalToThreeComponents } from "./coordinates.js";

let sceneGroup;
let camera;
let renderer;
let controls;
let threeScene;
let animFrameId = null;

function threeVectorFromComponents(components) {
  return new THREE.Vector3(components.x, components.y, components.z);
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

  threeScene.add(new THREE.GridHelper(0.8, 16, 0x8ea3b7, 0xd3dce6));
  threeScene.add(new THREE.AxesHelper(0.28));
  threeScene.add(new THREE.AmbientLight(0xffffff, 0.85));
  sceneGroup = new THREE.Group();
  threeScene.add(sceneGroup);
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
    const geometry = new THREE.TorusGeometry(source.radius_m, 0.004, 10, 72);
    const material = new THREE.MeshBasicMaterial({ color: 0xb7791f });
    const mesh = new THREE.Mesh(geometry, material);
    const threeNormal = threeVectorFromComponents(physicsNormalToThreeComponents(source.normal));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), threeNormal);
    return mesh;
  }

  if (source.kind === "line_segment") {
    const geometry = new THREE.CylinderGeometry(0.004, 0.004, source.length_m, 12);
    const material = new THREE.MeshBasicMaterial({ color: 0x0071e3 });
    const mesh = new THREE.Mesh(geometry, material);
    const direction = threeVectorFromComponents(physicsNormalToThreeComponents(source.orientation));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
    return mesh;
  }

  if (source.kind === "disk" || source.kind === "infinite_plane") {
    const radius = source.kind === "disk" ? source.radius_m : source.display_extent_m * 0.5;
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
    source.kind === "spherical_shell" ? source.radius_m : 0.018,
    24,
    16,
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
    mesh.position.set(source.position.x, source.position.z, source.position.y);
    sceneGroup.add(mesh);
  }

  const probeGeometry = new THREE.SphereGeometry(0.012, 16, 12);
  const probeMaterial = new THREE.MeshBasicMaterial({ color: 0x111827 });
  const probeMesh = new THREE.Mesh(probeGeometry, probeMaterial);
  probeMesh.position.set(state.probe.x, state.probe.z, state.probe.y);
  sceneGroup.add(probeMesh);

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
