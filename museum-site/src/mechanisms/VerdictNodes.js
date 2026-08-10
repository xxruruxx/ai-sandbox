import * as THREE from 'three';
import { COLORS } from '../utils/constants.js';

/**
 * VerdictNodes — M3-A "Visible Verdict".
 * Wall-mounted spheres representing candidate chunks. Each can be graded
 * green (relevant) or red (rejected) or stay neutral grey (ungraded).
 *
 * NOTE: this is a placeholder/demo implementation — it does NOT call your
 * real grade_node yet (that's backend integration, separate from this
 * geometry/visual layer). For now, call `.setVerdict(index, 'green'|'red')`
 * manually or use `.demoRandomCycle()` to see the visual working.
 *
 * IMPORTANT per locked memory: this stays Variant A (whole-node color flip)
 * until grade_node is fixed to item-level grading — do NOT build the
 * fragment-splitting "Fracture" variant before that backend fix ships.
 */
export class VerdictNodes {
  constructor({
    count = 8,
    wallPositions = null, // optional explicit array of THREE.Vector3; auto-generated if omitted
    roomLength = 12,
    roomZStart = -14,
    wallX = 2.2, // widened from 1.4 — more clear walking room in the center
  } = {}) {
    this.nodes = [];
    this.group = new THREE.Group();

    const positions = wallPositions || this._generateWallPositions(count, roomLength, roomZStart, wallX);

    positions.forEach((pos) => {
      const geometry = new THREE.SphereGeometry(0.14, 16, 16);
      const material = new THREE.MeshStandardMaterial({
        color: COLORS.verdictGrey,
        emissive: COLORS.verdictGrey,
        emissiveIntensity: 0.3,
        metalness: 0.3,
        roughness: 0.5,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.copy(pos);
      this.group.add(mesh);
      this.nodes.push({ mesh, verdict: 'grey', targetColor: new THREE.Color(COLORS.verdictGrey) });
    });
  }

  _generateWallPositions(count, roomLength, roomZStart, wallX) {
    const positions = [];
    const slotSize = roomLength / count; // guarantees a minimum gap between consecutive nodes

    for (let i = 0; i < count; i++) {
      const side = i % 2 === 0 ? -1 : 1; // alternate left/right
      const slotStart = i * slotSize;
      // random position WITHIN this slot (80% of slot width, so it never touches the next slot's node)
      const z = roomZStart - slotStart - Math.random() * slotSize * 0.8;
      const xJitter = (Math.random() - 0.5) * 1.4; // widened from 0.4 — same-side nodes were lining up in a straight receding line, looking clustered from a distance
      positions.push(new THREE.Vector3(side * wallX + xJitter, 1.2, z));
    }
    return positions;
  }

  /** Set a specific node's verdict. verdict: 'green' | 'red' | 'grey' */
  setVerdict(index, verdict) {
    if (!this.nodes[index]) return;
    const colorMap = {
      green: COLORS.verdictGreen,
      red: COLORS.verdictRed,
      grey: COLORS.verdictGrey,
    };
    this.nodes[index].verdict = verdict;
    this.nodes[index].targetColor = new THREE.Color(colorMap[verdict] ?? COLORS.verdictGrey);
  }

  /** DEMO ONLY: randomly cycles verdicts so you can see the visual before backend is wired up. */
  demoRandomCycle(intervalMs = 2000) {
    this._demoInterval = setInterval(() => {
      const i = Math.floor(Math.random() * this.nodes.length);
      const options = ['green', 'red'];
      this.setVerdict(i, options[Math.floor(Math.random() * options.length)]);
    }, intervalMs);
  }

  stopDemoCycle() {
    if (this._demoInterval) clearInterval(this._demoInterval);
  }

  /** Call once per frame — eases each node's color toward its target verdict color. */
  update(delta) {
    this.nodes.forEach((node) => {
      node.mesh.material.color.lerp(node.targetColor, Math.min(delta * 3, 1));
      node.mesh.material.emissive.lerp(node.targetColor, Math.min(delta * 3, 1));
    });
  }

  addTo(scene) {
    scene.add(this.group);
  }
}