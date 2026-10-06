import * as THREE from 'three';
import { COLORS } from '../utils/constants.js';

/**
 * EmberField — M2-A "tide/fountain pulse".
 * Ambient particles drift upward and fade, like embers off a campfire.
 * Constant, low-key — meant to read as background life, not a focal moment.
 * Reused by both GazetteAIRoom and TransitionRoom.
 */
export class EmberField {
  constructor({
    count = 200,
    radius = 3.5,                 // circular spread radius, centered on `position`
    zLength = 12,                  // how far along Z the field extends
    position = new THREE.Vector3(0, 0, -10),
    riseSpeed = 0.4,             // meters/sec upward drift
    maxHeight = 4,                // resets to bottom after rising this far
    color = COLORS.emberWarm,
  } = {}) {
    this.position = position;
    this.radius = radius;
    this.zLength = zLength;
    this.riseSpeed = riseSpeed;
    this.maxHeight = maxHeight;

    const positions = new Float32Array(count * 3);
    this._heights = new Float32Array(count); // tracked separately for wraparound logic

    for (let i = 0; i < count; i++) {
      const { x, z } = this._randomCircularPoint();
      const y = Math.random() * maxHeight;
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
      this._heights[i] = y;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const material = new THREE.PointsMaterial({
      color,
      size: 0.05,
      transparent: true,
      opacity: 0.7,
      depthWrite: false, // avoids particles harshly occluding each other
    });

    this.points = new THREE.Points(geometry, material);
    this.points.position.copy(position);
    this._count = count;
  }

  /** Uniform random point within a circle — using sqrt(random) avoids clumping at the center. */
  _randomCircularPoint() {
    const angle = Math.random() * Math.PI * 2;
    const r = Math.sqrt(Math.random()) * this.radius;
    const x = Math.cos(angle) * r;
    const z = (Math.random() - 0.5) * this.zLength; // still spread along the room's length
    return { x, z };
  }

  /** Call once per frame. No camera/interaction dependency — purely ambient. */
  update(delta) {
    const posAttr = this.points.geometry.attributes.position;

    for (let i = 0; i < this._count; i++) {
      this._heights[i] += this.riseSpeed * delta;
      if (this._heights[i] > this.maxHeight) {
        this._heights[i] = 0; // reset to bottom, re-randomize position for variety
        const { x, z } = this._randomCircularPoint();
        posAttr.array[i * 3] = x;
        posAttr.array[i * 3 + 2] = z;
      }
      posAttr.array[i * 3 + 1] = this._heights[i];
    }

    posAttr.needsUpdate = true;
  }

  addTo(scene) {
    scene.add(this.points);
  }
}