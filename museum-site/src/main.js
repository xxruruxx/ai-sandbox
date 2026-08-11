import * as THREE from 'three';
import { GazetteAIRoom } from './rooms/GazetteAIRoom.js';
import { TransitionRoom } from './rooms/TransitionRoom.js';

// ============ SCENE ============
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x050708);
scene.fog = new THREE.Fog(0x050708, 5, 40);

// ============ CAMERA ============
const camera = new THREE.PerspectiveCamera(
  90,
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
const grid = new THREE.GridHelper(120, 120, 0x2a3a48, 0x1c2530);
grid.position.z = -40;
scene.add(grid);

// ============ ROOMS — this is the pattern for adding future projects ============
// Each room owns its own door(s) and content. To add a new project room later,
// just instantiate it with a position further down the tunnel (more negative Z)
// than wherever the previous room ends, then call .addTo(scene) and include it
// in the update loop below. No other files need to change.

const gazetteRoom = new GazetteAIRoom({
  position: new THREE.Vector3(0, 2.0, -10),
});
gazetteRoom.addTo(scene);
gazetteRoom.startDemoData(); // TODO: replace with real grade_node integration later

const transitionRoom = new TransitionRoom({
  position: new THREE.Vector3(0, 2.0, -30),
  length: 4,
});
transitionRoom.addTo(scene);

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

// ============ RUNNING ============
let isRunning = false;
document.addEventListener('keydown', (e) => {
  if (e.key === 'Shift') isRunning = true;
});
document.addEventListener('keyup', (e) => {
  if (e.key === 'Shift') isRunning = false;
});

// ============ JUMPING ============
let verticalVelocity = 0;
const gravity = -18;
const jumpStrength = 6;
const groundY = 1.7;

document.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && !isSeated && camera.position.y <= groundY + 0.01) {
    verticalVelocity = jumpStrength;
  }
});

// ============ SITTING ============
let isSeated = false;
let standingPosition = new THREE.Vector3();

document.addEventListener('keydown', (e) => {
  if (e.key.toLowerCase() !== 'e') return;

  if (!isSeated) {
    const seats = transitionRoom.seatPositions;
    const nearSeat = seats.find(seat => camera.position.distanceTo(seat) < 1.8);
    if (nearSeat) {
      standingPosition.copy(camera.position);
      camera.position.copy(nearSeat);
      isSeated = true;
    }
  } else {
    camera.position.copy(standingPosition);
    isSeated = false;
  }
});

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

  if (!isSeated) {
    const currentSpeed = isRunning ? moveSpeed * 2 : moveSpeed;
    const moveDir = new THREE.Vector3();
    if (keys.w) moveDir.add(forward);
    if (keys.s) moveDir.sub(forward);
    if (keys.d) moveDir.add(right);
    if (keys.a) moveDir.sub(right);

    if (moveDir.lengthSq() > 0) {
      moveDir.normalize().multiplyScalar(currentSpeed * delta);
      camera.position.add(moveDir);
    }

    verticalVelocity += gravity * delta;
    camera.position.y += verticalVelocity * delta;
    if (camera.position.y < groundY) {
      camera.position.y = groundY;
      verticalVelocity = 0;
    }
  }

  gazetteRoom.update(delta, camera.position);
  transitionRoom.update(delta, camera.position);

  renderer.render(scene, camera);
}
animate();

// ============ RESIZE HANDLING ============
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});