// piquet-card-faces.js
// Jumbo Index card faces (SF Pro Bold, suit size 2.8) drawn with Canvas 2D and handed to three.js as textures.
// No bundled fonts: ranks use the platform UI font (SF on iPhone/Mac), suits use the platform symbol font.
//
// Usage:
//   import { makeDeck } from './piquet-card-faces.js';
//   const deck = makeDeck({ width: 512, anisotropy: renderer.capabilities.getMaxAnisotropy() });
//   const front = new THREE.Mesh(
//     new THREE.PlaneGeometry(0.7, 0.98),                                  // 5:7
//     new THREE.MeshToonMaterial({ map: deck.get('10H'), alphaTest: 0.5 }) // or your cel-shader; just feed `map`
//   );
//   // keys are rank + suit: '7S' ... '10H' ... 'AC'

import * as THREE from 'three';

export const RANKS = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']; // piquet's 32-card deck
export const SUITS = ['S', 'H', 'D', 'C'];                       // spades, hearts, diamonds, clubs

// Design spec. All lengths are in "card units": the card is 7 wide x 9.8 tall.
export const SPEC = {
  w: 7, h: 9.8,
  paper: '#fbfaf6', edge: '#c9c6bc', edgeWidth: 0.05, radius: 0.5,
  ink: '#15171c', red: '#c8202c',
  axis: 1.0,       // x of the shared centre line for rank and suit
  rankTop: 0.3,    // y of the top of the rank (cap height)
  rankSize: 2.2,   // font size; identical for every rank, including "10"
  suitTop: 2.15,   // y of the top of the suit glyph's ink
  suitSize: 2.8,
};

const RANK_FONT = '-apple-system, system-ui, sans-serif';
const SUIT_FONT = '"Apple Symbols", "Segoe UI Symbol", "Noto Sans Symbols 2", system-ui, sans-serif';
// U+FE0E asks for the plain text glyph, so hearts and diamonds don't turn into colour emoji
const GLYPH = { S: '\u2660\uFE0E', H: '\u2665\uFE0E', D: '\u2666\uFE0E', C: '\u2663\uFE0E' };
const COLOR = { S: SPEC.ink, C: SPEC.ink, H: SPEC.red, D: SPEC.red };

// One corner index (top-left). The bottom-right one is this, rotated 180 degrees about the card centre.
function drawCorner(ctx, u, rank, suit) {
  ctx.fillStyle = COLOR[suit];
  ctx.textBaseline = 'alphabetic';

  // Rank: top of the capitals at rankTop, centred on the axis.
  ctx.font = `700 ${SPEC.rankSize * u}px ${RANK_FONT}`;
  ctx.textAlign = 'center';
  const cap = ctx.measureText('H').actualBoundingBoxAscent;
  ctx.fillText(rank, SPEC.axis * u, SPEC.rankTop * u + cap);

  // Suit: placed by its measured ink (top edge at suitTop, ink centred on the axis),
  // so the four suits line up even if the system falls back to a different symbol font.
  ctx.font = `${SPEC.suitSize * u}px ${SUIT_FONT}`;
  ctx.textAlign = 'left';
  const g = GLYPH[suit];
  const m = ctx.measureText(g);
  const inkLeft = -m.actualBoundingBoxLeft;
  const inkRight = m.actualBoundingBoxRight;
  ctx.fillText(g, SPEC.axis * u - (inkLeft + inkRight) / 2, SPEC.suitTop * u + m.actualBoundingBoxAscent);
}

export function drawCardFace(ctx, width, rank, suit) {
  const u = width / SPEC.w;
  const W = width;
  const H = SPEC.h * u;
  const e = SPEC.edgeWidth * u;

  ctx.clearRect(0, 0, W, H);
  ctx.beginPath();
  ctx.roundRect(e / 2, e / 2, W - e, H - e, SPEC.radius * u); // Safari 16+, Chrome 99+
  ctx.fillStyle = SPEC.paper;
  ctx.fill();
  ctx.lineWidth = e;
  ctx.strokeStyle = SPEC.edge;
  ctx.stroke();

  drawCorner(ctx, u, rank, suit);

  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.rotate(Math.PI);
  ctx.translate(-W / 2, -H / 2);
  drawCorner(ctx, u, rank, suit);
  ctx.restore();
}

export function makeCardFaceTexture(rank, suit, { width = 512, anisotropy = 8 } = {}) {
  const height = Math.round((width * SPEC.h) / SPEC.w);
  const canvas = typeof OffscreenCanvas !== 'undefined'
    ? new OffscreenCanvas(width, height)
    : Object.assign(document.createElement('canvas'), { width, height });
  drawCardFace(canvas.getContext('2d'), width, rank, suit);

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace; // three r152+; on older versions use tex.encoding = THREE.sRGBEncoding
  tex.anisotropy = anisotropy;
  return tex;
}

// All 32 faces, keyed by rank + suit ('7S', '10H', 'AC', ...).
export function makeDeck(opts) {
  const deck = new Map();
  for (const s of SUITS) for (const r of RANKS) deck.set(r + s, makeCardFaceTexture(r, s, opts));
  return deck;
}
