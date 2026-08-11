import * as THREE from 'three';
import { IrisRing } from '../structures/IrisRing.js';
import { EmberField } from '../mechanisms/EmberField.js';
import { VerdictNodes } from '../mechanisms/VerdictNodes.js';
import { GravityWell } from '../mechanisms/GravityWell.js';

/**
 * GazetteAIRoom — the first project room. Owns its own entry door plus all
 * three chosen mechanisms:
 *   M1-C: gravity well (interactive, press V near it)
 *   M2-A: ember pulse (ambient, constant)
 *   M3-A: visible verdict (wall nodes — demo data for now, see VerdictNodes.js)
 *
 * `position` is where this room's entry ring sits. Everything else
 * (embers, nodes, well) is positioned relative to that entry point, so
 * moving the room only requires changing one Vector3.
 */
export class GazetteAIRoom {
  constructor({ position = new THREE.Vector3(0, 2.0, -10) } = {}) {
    this.entryZ = position.z;

    this.entryRing = new IrisRing({
      leafCount: 5,
      radius: 3.0,
      position: position.clone(),
      previewDistance: 8,
      openDistance: 6,
    });

    this.embers = new EmberField({
      position: new THREE.Vector3(position.x, 0, this.entryZ),
      radius: 3.5,
      zLength: 12,
    });

    this.verdictNodes = new VerdictNodes({
      count: 6,
      roomZStart: this.entryZ - 1,
      roomLength: 8,
    });

    this.gravityWell = new GravityWell({
      position: new THREE.Vector3(position.x, 1.6, this.entryZ - 14),
    });
  }

  addTo(scene) {
    this.entryRing.addTo(scene);
    this.embers.addTo(scene);
    this.verdictNodes.addTo(scene);
    this.gravityWell.addTo(scene);
  }

  /**
   * Starts the verdict nodes' demo color-cycling. Call this once after
   * addTo(), separately, rather than automatically in the constructor —
   * keeps "start faking data" an explicit choice, not silent side effect,
   * and makes it obvious where to swap in the real grade_node call later.
   */
  startDemoData() {
    this.verdictNodes.demoRandomCycle();
  }

  /** Call once per frame. */
  update(delta, cameraPosition) {
    this.entryRing.update(delta, cameraPosition);
    this.embers.update(delta);
    this.verdictNodes.update(delta);
    this.gravityWell.update(delta, cameraPosition);
  }
}