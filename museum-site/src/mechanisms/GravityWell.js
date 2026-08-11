import * as THREE from 'three';
import { COLORS } from '../utils/constants.js';

/**
 * GravityWell — M1-C "Visitor as Gravity Well".
 *
 * Press V (a ONE-SHOT trigger, not a toggle) to start a
 * pull-in event. Particles travel toward the visitor, and each one that
 * arrives FREEZES and fades to true invisibility (not just dimmed) —
 * "consumed" by the search, like a matched result being resolved. Once
 * everything's consumed, it automatically resets after a short pause so
 * it's ready to be triggered again.
 *
 * Uses a custom shader (not the built-in PointsMaterial) because true
 * per-particle transparency — as opposed to per-particle color/dimming —
 * isn't something the built-in material supports.
 */
export class GravityWell {
  constructor({
    count = 60,
    spread = 3.5,
    position = new THREE.Vector3(0, 1.6, -18),
    pullStrength = 1.8,
    color = COLORS.ringLeaf,
    pointSize = 1.2, // was hardcoded at 5.0 in the shader — way too large; tune this number directly
  } = {}) {
    this.position = position;
    this.pullStrength = pullStrength;

    // phase: 'idle' (waiting for trigger) -> 'active' (pulling/fading) -> 'resetting' -> 'idle'
    this.phase = 'idle';
    this._resetTimer = 0;

    const positions = new Float32Array(count * 3);
    const alphas = new Float32Array(count);
    this._homePositions = [];
    this._consumed = new Uint8Array(count); // 1 = arrived + faded out, frozen, ignores further pull

    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const r = Math.random() * spread;
      const x = Math.cos(angle) * r;
      const y = (Math.random() - 0.5) * spread * 0.6;
      const z = Math.sin(angle) * r;
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
      alphas[i] = 0.85;
      this._homePositions.push(new THREE.Vector3(x, y, z));
    }

    this._settleOffsets = [];
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const r = 0.3 + Math.random() * 0.4;
      this._settleOffsets.push(new THREE.Vector3(
        Math.cos(angle) * r,
        (Math.random() - 0.5) * 0.5,
        Math.sin(angle) * r
      ));
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('alpha', new THREE.BufferAttribute(alphas, 1));

    // Custom shader: same look as a normal point sprite, but alpha comes
    // from a per-vertex attribute instead of one shared material value.
    const material = new THREE.ShaderMaterial({
      uniforms: {
        color: { value: new THREE.Color(color) },
        pointSize: { value: pointSize },
      },
      vertexShader: `
        attribute float alpha;
        varying float vAlpha;
        uniform float pointSize;
        void main() {
          vAlpha = alpha;
          vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = pointSize * (30.0 / -mvPosition.z);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        uniform vec3 color;
        varying float vAlpha;
        void main() {
          if (vAlpha < 0.01) discard; // fully faded particles skip rendering entirely
          gl_FragColor = vec4(color, vAlpha);
        }
      `,
      transparent: true,
      depthWrite: false,
    });

    this.points = new THREE.Points(geometry, material);
    this.points.position.copy(position);
    this._count = count;

    this._nearEnough = false;
    document.addEventListener('keydown', (e) => {
      if (e.key.toLowerCase() === 'v' && this._nearEnough && this.phase === 'idle') {
        this._startPull();
      }
    });
  }

  _startPull() {
    this.phase = 'active';
    this._consumed.fill(0);
  }

  _resetToHome() {
    this.phase = 'idle';
    const posAttr = this.points.geometry.attributes.position;
    const alphaAttr = this.points.geometry.attributes.alpha;
    for (let i = 0; i < this._count; i++) {
      posAttr.array[i * 3] = this._homePositions[i].x;
      posAttr.array[i * 3 + 1] = this._homePositions[i].y;
      posAttr.array[i * 3 + 2] = this._homePositions[i].z;
      alphaAttr.array[i] = 0.85;
    }
    posAttr.needsUpdate = true;
    alphaAttr.needsUpdate = true;
    this._consumed.fill(0);
  }

  /** Call once per frame with delta and the camera's world position. */
  update(delta, cameraPosition) {
    const distanceToWell = this.position.distanceTo(cameraPosition);
    this._nearEnough = distanceToWell < 4;

    if (this.phase === 'idle') return; // nothing to animate, particles sit at rest

    const posAttr = this.points.geometry.attributes.position;
    const alphaAttr = this.points.geometry.attributes.alpha;
    const localTarget = new THREE.Vector3().subVectors(cameraPosition, this.position);
    const safeDelta = Math.min(delta, 0.1);

    if (this.phase === 'active') {
      let allConsumed = true;

      for (let i = 0; i < this._count; i++) {
        if (this._consumed[i]) continue; // frozen — skip movement AND fade, it's already gone

        allConsumed = false;
        const target = localTarget.clone().add(this._settleOffsets[i]);

        const x = THREE.MathUtils.damp(posAttr.array[i * 3], target.x, this.pullStrength, safeDelta);
        const y = THREE.MathUtils.damp(posAttr.array[i * 3 + 1], target.y, this.pullStrength, safeDelta);
        const z = THREE.MathUtils.damp(posAttr.array[i * 3 + 2], target.z, this.pullStrength, safeDelta);
        posAttr.array[i * 3] = x;
        posAttr.array[i * 3 + 1] = y;
        posAttr.array[i * 3 + 2] = z;

        const distToTarget = Math.hypot(x - target.x, y - target.y, z - target.z);
        if (distToTarget < 0.15) {
          // arrived — fade out fast, then freeze for good
          alphaAttr.array[i] = THREE.MathUtils.damp(alphaAttr.array[i], 0, 6, safeDelta);
          if (alphaAttr.array[i] < 0.02) {
            alphaAttr.array[i] = 0;
            this._consumed[i] = 1;
          }
        }
      }

      posAttr.needsUpdate = true;
      alphaAttr.needsUpdate = true;

      if (allConsumed) {
        this.phase = 'resetting';
        this._resetTimer = 0;
      }
    } else if (this.phase === 'resetting') {
      // brief pause with everything invisible, then snap back and re-enable triggering
      this._resetTimer += delta;
      if (this._resetTimer > 0.6) {
        this._resetToHome();
      }
    }
  }

  addTo(scene) {
    scene.add(this.points);
  }
}