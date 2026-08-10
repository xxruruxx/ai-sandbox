import * as THREE from 'three';

/**
 * IrisRing — a mechanical door built from N leaf petals arranged radially,
 * like a camera aperture. Leaves hinge from a point on the rim and swing
 * WITHIN the ring's own flat plane to open — not tipping toward the viewer.
 *
 * States (locked spec):
 *   idle    — fully closed, visible as a landmark ahead
 *   preview — ~35% open, proximity-triggered, glimpse of what's beyond
 *   open    — fully open, proximity-triggered, unobstructed entry
 *
 * Trigger: automatic, based on distance from camera. No button.
 */
export class IrisRing {
  constructor({
    leafCount = 5,
    radius = 1.6,
    position = new THREE.Vector3(0, 1.6, -10),
    previewDistance = 8,
    openDistance = 3,
    color = 0x5ee6d0,
  } = {}) {
    this.leafCount = leafCount;
    this.radius = radius;
    this.previewDistance = previewDistance;
    this.openDistance = openDistance;

    this.group = new THREE.Group();
    this.group.position.copy(position);

    this.leaves = [];       // hinge pivot groups (what we rotate to open/close)
    this.baseAngles = [];   // each leaf's resting angular slot around the ring
    this._buildLeaves(color);
    this._buildHousing();   // static outer rim, masks any blade overflow past the circle

    this.state = 'idle';
    this._targetSweep = 0;   // extra rotation (radians) applied ON TOP of baseAngle to open
    this._currentSweep = 0;
    this._rotationLerpSpeed = 2.7; // lower = heavier/more mechanical, higher = snappier
  }

  _buildLeaves(color) {
    const angleStep = (Math.PI * 2) / this.leafCount;
    const innerR = this.radius * 0.15;
    const outerR = this.radius;
    const arc = angleStep * 1.02; // slight OVERLAP (not gap) so leaves sit flush/seamless when closed

    // Build ONE wedge shape template, defined relative to a hinge at the RIM
    // (local origin = hinge point, at what would be world (outerR, 0) unshifted).
    const shape = new THREE.Shape();
    const hingeX = outerR;

    shape.moveTo(innerR - hingeX, 0);
    shape.lineTo(outerR - hingeX, 0);
    shape.absarc(-hingeX, 0, outerR, 0, arc, false);
    shape.lineTo(
      innerR * Math.cos(arc) - hingeX,
      innerR * Math.sin(arc)
    );
    shape.absarc(-hingeX, 0, innerR, arc, 0, true);

    const extrudeSettings = { depth: 0.08, bevelEnabled: false };
    const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);

    const material = new THREE.MeshStandardMaterial({
      color,
      metalness: 0.6,
      roughness: 0.35,
      emissive: color,
      emissiveIntensity: 0.08,
      side: THREE.DoubleSide,
    });

    for (let i = 0; i < this.leafCount; i++) {
      const baseAngle = i * angleStep;
      this.baseAngles.push(baseAngle);

      const leafMesh = new THREE.Mesh(geometry, material);

      // Hinge pivot sits at the rim point for this leaf's angular slot.
      // Rotating THIS group's Z (in-plane) swings the leaf like a real aperture blade.
      const hinge = new THREE.Group();
      hinge.position.set(
        Math.cos(baseAngle) * outerR,
        Math.sin(baseAngle) * outerR,
        0
      );
      hinge.rotation.z = baseAngle;
      hinge.add(leafMesh);

      this.group.add(hinge);
      this.leaves.push(hinge);
    }
  }

  /**
   * A fixed, non-rotating rim ring that sits slightly IN FRONT of the leaves.
   * Its inner edge lines up with the leaves' outer radius, so any part of a
   * blade that swings past the circle boundary while opening gets visually
   * hidden behind this frame — same trick a real camera lens barrel uses to
   * hide its aperture mechanism.
   */
  _buildHousing() {
    const outerR = this.radius;
    const housingOuter = outerR * 2.10;
    const housingInner = outerR * 1.05; // slight overlap so there's no visible seam

    const housingShape = new THREE.Shape();
    housingShape.absarc(0, 0, housingOuter, 0, Math.PI * 2, false);
    const hole = new THREE.Path();
    hole.absarc(0, 0, housingInner, 0, Math.PI * 2, true);
    housingShape.holes.push(hole);

    const geometry = new THREE.ExtrudeGeometry(housingShape, {
      depth: 0.05,
      bevelEnabled: false,
    });

    const material = new THREE.MeshStandardMaterial({
      color: 0x2a3a48, // dark metal frame, distinct from the leaf color
      metalness: 0.75,
      roughness: 0.4,
    });

    const housing = new THREE.Mesh(geometry, material);
    // Sit in front of the leaves' front face (leaves extrude 0 -> 0.08 locally).
    // If it renders BEHIND the leaves instead of masking them, flip this to -0.12.
    housing.position.z = 0.12;

    this.group.add(housing);
  }

  /** Call once per frame with the camera's world position. */
  update(delta, cameraPosition) {
    const distance = this.group.position.distanceTo(cameraPosition);

    let newState = 'idle';
    if (distance < this.openDistance) newState = 'open';
    else if (distance < this.previewDistance) newState = 'preview';

    if (newState !== this.state) {
      this.state = newState;
      this._setTargetSweep(newState);
    }

    this._currentSweep = THREE.MathUtils.damp(
      this._currentSweep,
      this._targetSweep,
      this._rotationLerpSpeed,
      delta
    );

    for (let i = 0; i < this.leaves.length; i++) {
      // final angle = resting slot MINUS how far it's swept open, in-plane (Z only).
      // Negative sweep direction = blades swing AWAY from center to open, rather
      // than rotating further into each other (which was the "retracting" bug).
      this.leaves[i].rotation.z = this.baseAngles[i] - this._currentSweep;
    }
  }

  _setTargetSweep(state) {
    const maxSweep = Math.PI / 2.4; // how far each blade swings open, in-plane
    if (state === 'preview') this._targetSweep = maxSweep * 0.35; // locked: ~35% open
    else if (state === 'open') this._targetSweep = maxSweep;
    else this._targetSweep = 0;
  }

  addTo(scene) {
    scene.add(this.group);
  }
}