import * as THREE from 'three';
import { EmberField } from '../mechanisms/EmberField.js';

/**
 * TransitionRoom — the thin "breath" room between every project, per the
 * locked hallway pattern. Ambient embers only, plus simple furniture
 * (set-dressing, not functionally sittable) along both sides, outside
 * the clear walkway.
 */
export class TransitionRoom {
  constructor({ position = new THREE.Vector3(0, 0, -30), length = 4 } = {}) {
    this.group = new THREE.Group();
    this.group.position.copy(position);

    this.embers = new EmberField({
      position: new THREE.Vector3(0, 0, 0), // relative to this room's own group
      spread: { x: 2, z: length },
      count: 60, // fewer than the main room — this is a quieter space
    });

    this._buildFurniture(length);
  }

  _buildFurniture(length) {
    // Simple couch-like boxes, set-dressing only. Placed outside the walkway.
    const couchMat = new THREE.MeshStandardMaterial({ color: 0x7a5a42, roughness: 0.8 });
    const couchGeo = new THREE.BoxGeometry(0.6, 0.4, 1.2);

    const leftCouch = new THREE.Mesh(couchGeo, couchMat);
    leftCouch.position.set(-1.6, 0.2, 0);
    this.group.add(leftCouch);

    const rightCouch = new THREE.Mesh(couchGeo, couchMat);
    rightCouch.position.set(1.6, 0.2, -length * 0.4);
    this.group.add(rightCouch);
  }

  addTo(scene) {
    scene.add(this.group);
    this.embers.addTo(this.group); // embers move with the room's group offset
  }

  update(delta) {
    this.embers.update(delta);
  }
}