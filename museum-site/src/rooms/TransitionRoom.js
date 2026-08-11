import * as THREE from 'three';
import { EmberField } from '../mechanisms/EmberField.js';
import { IrisRing } from '../structures/IrisRing.js';

/**
 * TransitionRoom — the thin "breath" room between every project, per the
 * locked hallway pattern. Ambient embers, real sittable furniture (press E
 * near a couch), and an iris door on BOTH ends using the same
 * proximity-triggered mechanic as every other door.
 *
 * `position` is the room's ENTRY point (where its first ring sits) — the
 * room then extends further down the tunnel (more negative Z) by `length`,
 * where its exit ring sits.
 */
export class TransitionRoom {
  constructor({ position = new THREE.Vector3(0, 1.8, -30), length = 4 } = {}) {
    this.entryZ = position.z;
    this.exitZ = position.z - length;
    this.length = length;

    this.group = new THREE.Group();
    this.group.position.set(position.x, 0, position.z - length / 2);

    this.embers = new EmberField({
      position: new THREE.Vector3(0, 0, 0),
      radius: 1.8,
      zLength: length,
      count: 60,
    });

    this._buildFurniture(length);

    this.entryRing = new IrisRing({
      leafCount: 5,
      radius: 3.0,
      position: new THREE.Vector3(position.x, position.y, this.entryZ),
      previewDistance: 8,
      openDistance: 6,
    });

    this.exitRing = new IrisRing({
      leafCount: 5,
      radius: 3.0,
      position: new THREE.Vector3(position.x, position.y, this.exitZ),
      previewDistance: 8,
      openDistance: 6,
    });
  }

  _buildFurniture(length) {
    // Simple couch-like boxes — real seats now, see this.seatPositions below.
    const couchMat = new THREE.MeshStandardMaterial({
      color: 0x7a5a42,
      roughness: 0.8,
      emissive: 0x7a5a42,
      emissiveIntensity: 0.15,
    });
    const couchGeo = new THREE.BoxGeometry(0.6, 0.4, 1.2);

    const leftCouch = new THREE.Mesh(couchGeo, couchMat);
    leftCouch.position.set(-4.3, 0.5, 0);
    this.group.add(leftCouch);

    const rightCouch = new THREE.Mesh(couchGeo, couchMat);
    rightCouch.position.set(4.3, 0.5, 0);
    this.group.add(rightCouch);

    // World-space seat positions (eye height when SITTING, lower than standing 1.7).
    // this.group has no rotation, so world = group.position + local offset.
    const sitEyeHeight = 1.0;
    this.seatPositions = [
      new THREE.Vector3(
        this.group.position.x + leftCouch.position.x,
        sitEyeHeight,
        this.group.position.z + leftCouch.position.z
      ),
      new THREE.Vector3(
        this.group.position.x + rightCouch.position.x,
        sitEyeHeight,
        this.group.position.z + rightCouch.position.z
      ),
    ];
  }

  addTo(scene) {
    scene.add(this.group);
    this.embers.addTo(this.group);
    this.entryRing.addTo(scene);
    this.exitRing.addTo(scene);
  }

  /** Call once per frame with delta and the camera's world position. */
  update(delta, cameraPosition) {
    this.embers.update(delta);
    this.entryRing.update(delta, cameraPosition);
    this.exitRing.update(delta, cameraPosition);
  }
}