/**
 * Universal Explode Vector Handler
 * Section 31 of Master Context: Translates parts along assembly vectors while preserving orientation.
 */

export const ExplodeEngine = {
  applyExplode(meshMap, parts, factor) {
    parts.forEach(part => {
      const group = meshMap.get(part.id);
      if (!group) return;

      const basePos = part.assembledPos;
      const ev = part.explodeVec || [0, 0, 0];

      group.position.x = basePos[0] + ev[0] * factor;
      group.position.y = basePos[1] + ev[1] * factor;
      group.position.z = basePos[2] + ev[2] * factor;
    });
  }
};
