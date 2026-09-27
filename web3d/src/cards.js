// A card's geometry: a thin rounded slab, drawn in three material groups --
// the face (group 0), the back (group 1) and the edge (group 2).
//
// In the card's own frame x runs to the right of the face, y up it, and z out
// of it: the face is at z = +thickness/2, the back at -thickness/2. So a card
// with no rotation stands upright facing +z, the way the human holds one.
//
// Every vertex also carries `outlineNormal`, the direction the ink line pushes
// it: outward *within the card's plane*. A thin slab's face normals are useless
// for that -- the near rim and the far rim would be pushed in opposite
// directions, and at a grazing angle the line would disappear.

import { BufferGeometry, Float32BufferAttribute } from "three";
import { CARD } from "./units.js";

export function roundedOutline({ width, height, radius, segments }) {
  // Counter-clockwise seen from +z, starting at the top-right corner's arc.
  const corners = [
    [width / 2 - radius, height / 2 - radius, 0],
    [-width / 2 + radius, height / 2 - radius, Math.PI / 2],
    [-width / 2 + radius, -height / 2 + radius, Math.PI],
    [width / 2 - radius, -height / 2 + radius, (3 * Math.PI) / 2],
  ];
  const points = [];
  for (const [cx, cy, start] of corners) {
    for (let i = 0; i <= segments; i++) {
      const a = start + (i / segments) * (Math.PI / 2);
      const [nx, ny] = [Math.cos(a), Math.sin(a)];
      points.push({ x: cx + radius * nx, y: cy + radius * ny, nx, ny });
    }
  }
  return points;
}

export function cardGeometry({
  width = CARD.width,
  height = CARD.height,
  radius = CARD.radius,
  thickness = CARD.thickness,
  segments = 6,
} = {}) {
  const rim = roundedOutline({ width, height, radius, segments });
  const n = rim.length;
  const half = thickness / 2;
  const position = [];
  const normal = [];
  const uv = [];
  const outline = [];
  const index = [];

  const vertex = (x, y, z, normalZ, u, v, ox, oy, nx = 0, ny = 0) => {
    position.push(x, y, z);
    normal.push(nx, ny, normalZ);
    uv.push(u, v);
    outline.push(ox, oy, 0);
    return position.length / 3 - 1;
  };

  // The face: a fan from the centre, counter-clockwise seen from the front.
  const faceStart = index.length;
  const faceCentre = vertex(0, 0, half, 1, 0.5, 0.5, 0, 0);
  const faceRim = rim.map((p) => vertex(p.x, p.y, half, 1, p.x / width + 0.5, p.y / height + 0.5, p.nx, p.ny));
  for (let i = 0; i < n; i++) index.push(faceCentre, faceRim[i], faceRim[(i + 1) % n]);

  // The back: the same fan, wound the other way, its texture flipped in u so
  // that it reads unmirrored from behind.
  const backStart = index.length;
  const backCentre = vertex(0, 0, -half, -1, 0.5, 0.5, 0, 0);
  const backRim = rim.map((p) => vertex(p.x, p.y, -half, -1, 0.5 - p.x / width, p.y / height + 0.5, p.nx, p.ny));
  for (let i = 0; i < n; i++) index.push(backCentre, backRim[(i + 1) % n], backRim[i]);

  // The edge: a band joining the two rims, facing outward.
  const edgeStart = index.length;
  const top = rim.map((p) => vertex(p.x, p.y, half, 0, 0, 0, p.nx, p.ny, p.nx, p.ny));
  const bottom = rim.map((p) => vertex(p.x, p.y, -half, 0, 0, 0, p.nx, p.ny, p.nx, p.ny));
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    index.push(bottom[i], bottom[j], top[j], bottom[i], top[j], top[i]);
  }

  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(position, 3));
  geometry.setAttribute("normal", new Float32BufferAttribute(normal, 3));
  geometry.setAttribute("uv", new Float32BufferAttribute(uv, 2));
  geometry.setAttribute("outlineNormal", new Float32BufferAttribute(outline, 3));
  geometry.setIndex(index);
  geometry.addGroup(faceStart, backStart - faceStart, 0);
  geometry.addGroup(backStart, edgeStart - backStart, 1);
  geometry.addGroup(edgeStart, index.length - edgeStart, 2);
  return geometry;
}
