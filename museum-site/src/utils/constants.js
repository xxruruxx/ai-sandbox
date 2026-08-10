// Shared values used across rooms, mechanisms, and structures.
// Keeping these centralized means tuning one number here updates everywhere it's used.

export const COLORS = {
  ringLeaf: 0x5ee6d0,      // cyan-teal, matches iris ring + gravity well
  ringHousing: 0x2a3a48,   // dark metal frame
  emberWarm: 0xe6a05e,     // orange embers (M2-A)
  verdictGreen: 0x6ee65e,  // relevant chunk
  verdictRed: 0xe65e5e,    // rejected chunk
  verdictGrey: 0x5a5a52,   // ungraded / neutral
  background: 0x050708,
};

export const WALKWAY = {
  width: 3.0,          // meters, matches room-sketch spec
  ceilingHeight: 4.2,   // meters
};

export const GAZETTEAI_ROOM = {
  length: 12,           // meters, along Z
  gravityWellZ: -18,    // position of the M1-C interaction point, room midpoint
};