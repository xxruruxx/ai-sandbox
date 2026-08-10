import * as THREE from 'three';
import { COLORS } from '../utils/constants.js';

/**
 * GravityWell — M1-C "Visitor as Gravity Well".
 * Spacebar-toggled: while active, nearby particles drift toward the
 * visitor's position (query embedding pulling matched chunks). Deliberately
 * opt-in, not automatic — this is the interaction we chose specifically so
 * standing still feels like a choice, not an awkward forced pause.
 */
export class GravityWell {
  constructor({
    count = 60,
    spread = 3.5,             // radius particles start scattered within
    position = new THREE.Vector3(0, 1.6, -18), // room midpoint, matches locked room-sketch
    pullStrength = 1.8,
    color = COLORS.ringLeaf,
  } = {}) {
    this.position = position;
    this.pullStrength = pullStrength;
    this.isActive = false;

    const positions = new Float32Array(count * 3);
    this._velocities = [];
    this._homePositions = [];

    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const r = Math.random() * spread;
      const x = Math.cos(angle) * r;
      const y = (Math.random() - 0.5) * spread * 0.6;
      const z = Math.sin(angle) * r;
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
      this._velocities.push(new THREE.Vector3());
      this._homePositions.push(new THREE.Vector3(x, y, z));
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const material = new THREE.PointsMaterial({
      color,
      size: 0.05,
      transparent: true,
      opacity: 0.85,
      depthWrite: false,
    });

    this.points = new THREE.Points(geometry, material);
    this.points.position.copy(position);
    this._count = count;

    // Spacebar toggle — only active while visitor is near enough to matter.
    this._nearEnough = false;
    document.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && this._nearEnough) {
        this.isActive = !this.isActive;
      }
    });
  }

  /** Call once per frame with delta and the camera's world position. */
  update(delta, cameraPosition) {
    const distanceToWell = this.position.distanceTo(cameraPosition);
    this._nearEnough = distanceToWell < 4; // must be roughly inside the well's zone to toggle

    const posAttr = this.points.geometry.attributes.position;
    // Camera position relative to the well's local space (since points group is offset by `position`)
    const localTarget = new THREE.Vector3().subVectors(cameraPosition, this.position);

    for (let i = 0; i < this._count; i++) {
      const current = new THREE.Vector3(
        posAttr.array[i * 3],
        posAttr.array[i * 3 + 1],
        posAttr.array[i * 3 + 2]
      );

      let target;
      if (this.isActive) {
        // pull toward the visitor's local position within the well
        target = current.clone().lerp(localTarget, this.pullStrength * delta);
      } else {
        // relax back toward original scattered position when inactive
        target = current.clone().lerp(this._homePositions[i], 1.5 * delta);
      }

      posAttr.array[i * 3] = target.x;
      posAttr.array[i * 3 + 1] = target.y;
      posAttr.array[i * 3 + 2] = target.z;
    }

    posAttr.needsUpdate = true;
  }

  addTo(scene) {
    scene.add(this.points);
  }
}