import * as THREE from 'three';
import { EmberField } from '../mechanisms/EmberField.js';
import { VerdictNodes } from '../mechanisms/VerdictNodes.js';
import { GravityWell } from '../mechanisms/GravityWell.js';
import { GAZETTEAI_ROOM } from '../utils/constants.js';

/**
 * GazetteAIRoom — combines all three chosen mechanisms per the locked spec:
 *   M1-C: gravity well (interactive, spacebar)
 *   M2-A: ember pulse (ambient, constant)
 *   M3-A: visible verdict (wall nodes, current code-state — NOT the Fracture variant)
 */
export class GazetteAIRoom {
  constructor({ entryZ = -14 } = {}) {
    this.embers = new EmberField({
      position: new THREE.Vector3(0, 0, entryZ - GAZETTEAI_ROOM.length / 2),
      spread: { x: 2.5, z: GAZETTEAI_ROOM.length },
    });

    this.verdictNodes = new VerdictNodes({
      count: 8,
      roomZStart: entryZ,
      roomLength: GAZETTEAI_ROOM.length,
    });

    this.gravityWell = new GravityWell({
      position: new THREE.Vector3(0, 1.6, GAZETTEAI_ROOM.gravityWellZ),
    });
  }

  addTo(scene) {
    this.embers.addTo(scene);
    this.verdictNodes.addTo(scene);
    this.gravityWell.addTo(scene);
  }

  /** Call once per frame. */
  update(delta, cameraPosition) {
    this.embers.update(delta);
    this.verdictNodes.update(delta);
    this.gravityWell.update(delta, cameraPosition);
  }
}