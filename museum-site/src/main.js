import * as THREE from 'three';
import { IrisRing } from './structures/IrisRing.js';
import { EmberField } from './mechanisms/EmberField.js';
import { VerdictNodes } from './mechanisms/VerdictNodes.js';

// ============ SCENE ============
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x050708);
scene.fog = new THREE.Fog(0x050708, 5, 40);

// ============ CAMERA ============
const camera = new THREE.PerspectiveCamera(
  70,
  window.innerWidth / window.innerHeight,
  0.1,
  1000
);
camera.position.set(0, 1.7, 5);

// ============ RENDERER ============
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.body.appendChild(renderer.domElement);

// ============ REFERENCE GRID ============
const grid = new THREE.GridHelper(40, 40, 0x2a3a48, 0x1c2530);
scene.add(grid);

// ============ IRIS RING ============
const irisRing = new IrisRing({
  leafCount: 5,
  radius: 3.0,
  position: new THREE.Vector3(0, 2.0, -10),
  previewDistance: 8,
  openDistance: 6,
});
irisRing.addTo(scene);

// ============ EMBERS (M2-A) — Step 1 of room integration ============
const embers = new EmberField({
  position: new THREE.Vector3(0, 0, -10),
  radius: 3.5,
  zLength: 12,
});
embers.addTo(scene);

// ============ VERDICT NODES ============
const verdictNodes = new VerdictNodes({
  count: 6,
  roomZStart: -11,
  roomLength: 6,
});
verdictNodes.addTo(scene);
verdictNodes.demoRandomCycle();

// ============ LIGHTING ============
const ambient = new THREE.AmbientLight(0x404040, 1.5);
scene.add(ambient);

const pointLight = new THREE.PointLight(0x5ee6d0, 2, 20);
pointLight.position.set(0, 3, -8);
scene.add(pointLight);

// ============ MOUSE-LOOK ============
let yaw = 0;
let pitch = 0;
let isPointerLocked = false;

renderer.domElement.addEventListener('click', () => {
  renderer.domElement.requestPointerLock();
});

document.addEventListener('pointerlockchange', () => {
  isPointerLocked = document.pointerLockElement === renderer.domElement;
});

document.addEventListener('mousemove', (e) => {
  if (!isPointerLocked) return;
  const sensitivity = 0.002;
  yaw -= e.movementX * sensitivity;
  pitch -= e.movementY * sensitivity;
  pitch = Math.max(-Math.PI / 2.5, Math.min(Math.PI / 2.5, pitch));
});

// ============ KEYBOARD MOVEMENT (WASD) ============
const keys = { w: false, a: false, s: false, d: false };

document.addEventListener('keydown', (e) => {
  if (e.key.toLowerCase() in keys) keys[e.key.toLowerCase()] = true;
});
document.addEventListener('keyup', (e) => {
  if (e.key.toLowerCase() in keys) keys[e.key.toLowerCase()] = false;
});

const moveSpeed = 4;
const clock = new THREE.Clock();

// ============ RENDER LOOP ============
function animate() {
  requestAnimationFrame(animate);

  const delta = clock.getDelta();

  camera.rotation.set(pitch, yaw, 0, 'YXZ');

  const forward = new THREE.Vector3(0, 0, -1).applyEuler(camera.rotation);
  forward.y = 0;
  forward.normalize();
  const right = new THREE.Vector3(1, 0, 0).applyEuler(camera.rotation);
  right.y = 0;
  right.normalize();

  const moveDir = new THREE.Vector3();
  if (keys.w) moveDir.add(forward);
  if (keys.s) moveDir.sub(forward);
  if (keys.d) moveDir.add(right);
  if (keys.a) moveDir.sub(right);

  if (moveDir.lengthSq() > 0) {
    moveDir.normalize().multiplyScalar(moveSpeed * delta);
    camera.position.add(moveDir);
  }

  irisRing.update(delta, camera.position);
  embers.update(delta);
  verdictNodes.update(delta);

  renderer.render(scene, camera);
}
animate();

// ============ RESIZE HANDLING ============
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});