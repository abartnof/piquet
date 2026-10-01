// The Jumbo Index faces: for a phone, where a fanned hand shows each card
// only by its corner, faces that are nothing but corner -- the rank large in
// the platform's bold UI font (San Francisco on an iPhone), the suit larger
// beneath it, on one axis, at both ends. Drawn here with Canvas 2D, so no
// font is bundled or fetched.
//
// From the user's own recipe (1 October 2026), kept as given in the commit
// that brought it, d2507ac. Two things differ, for the table: the face is
// paper from edge to edge, because the table's ink line draws every card's
// edge and rounds its corners (the classic art has no border either); and
// the faces are drawn at the classic art's width for the screen (art.js).
//
// Settings calls them "Large Text (Optimized for smaller screens)" (the
// user's words). The classic faces stay the default on iPads and computers; Settings can
// choose either anywhere, and the change is live.

import { CanvasTexture } from "three";
import { cardTexture } from "./materials.js";

// All lengths in card units: the card is 7 wide by 9.8 tall, the 5:7 of the
// classic art.
export const JUMBO = Object.freeze({
  w: 7,
  h: 9.8,
  paper: "#fbfaf6",
  ink: "#15171c",
  red: "#c8202c",
  axis: 1.0, // x of the line the rank and suit are centred on
  rankTop: 0.3, // y of the top of the rank's capitals
  rankSize: 2.2, // one size for every rank, the ten included
  suitTop: 2.15, // y of the top of the suit's ink
  suitSize: 2.8,
});

const RANK_FONT = "-apple-system, system-ui, sans-serif";
const SUIT_FONT = '"Apple Symbols", "Segoe UI Symbol", "Noto Sans Symbols 2", system-ui, sans-serif';
// U+FE0E asks for the text glyph, so hearts and diamonds never turn into
// colour emoji.
const GLYPH = { S: "♠︎", H: "♥︎", D: "♦︎", C: "♣︎" };
const COLOUR = { S: JUMBO.ink, C: JUMBO.ink, H: JUMBO.red, D: JUMBO.red };

// A phone, held either way: a touch screen whose short side is a phone's.
// An iPad mini's is 744 CSS pixels, the largest phone's about 440.
export function isPhone({ coarse, shortSide }) {
  return !!coarse && shortSide < 600;
}

export function phoneHere() {
  const coarse = !!(window.matchMedia && window.matchMedia("(pointer: coarse)").matches);
  return isPhone({ coarse, shortSide: Math.min(window.screen.width, window.screen.height) });
}

// The faces to show for the setting: automatic is Jumbo Index on a phone,
// classic elsewhere.
export function facesFor(choice, phone) {
  if (choice === "classic" || choice === "jumbo") return choice;
  return phone ? "jumbo" : "classic";
}

export const rankAndSuit = (code) => [code[0] === "T" ? "10" : code[0], code[1]];

// One corner: the rank's capitals from rankTop, centred on the axis; the
// suit placed by its measured ink -- its top at suitTop, its centre on the
// axis -- so the four suits line up whatever symbol font the system has.
function corner(ctx, u, rank, suit) {
  ctx.fillStyle = COLOUR[suit];
  ctx.textBaseline = "alphabetic";
  ctx.font = `700 ${JUMBO.rankSize * u}px ${RANK_FONT}`;
  ctx.textAlign = "center";
  const cap = ctx.measureText("H").actualBoundingBoxAscent;
  ctx.fillText(rank, JUMBO.axis * u, JUMBO.rankTop * u + cap);

  ctx.font = `${JUMBO.suitSize * u}px ${SUIT_FONT}`;
  ctx.textAlign = "left";
  const glyph = GLYPH[suit];
  const m = ctx.measureText(glyph);
  const inkLeft = -m.actualBoundingBoxLeft;
  const inkRight = m.actualBoundingBoxRight;
  ctx.fillText(glyph, JUMBO.axis * u - (inkLeft + inkRight) / 2, JUMBO.suitTop * u + m.actualBoundingBoxAscent);
}

// The face of the card `code` ("TH", "AS", ...) on a 2D context `width`
// pixels wide and 1.4 times as tall. The bottom corner is the top one turned
// half round the card's centre.
export function drawJumbo(ctx, width, code) {
  const [rank, suit] = rankAndSuit(code);
  const u = width / JUMBO.w;
  const height = JUMBO.h * u;
  ctx.fillStyle = JUMBO.paper;
  ctx.fillRect(0, 0, width, height);
  corner(ctx, u, rank, suit);
  ctx.save();
  ctx.translate(width / 2, height / 2);
  ctx.rotate(Math.PI);
  ctx.translate(-width / 2, -height / 2);
  corner(ctx, u, rank, suit);
  ctx.restore();
}

// The 32 faces as textures, keyed by the table's codes, `width` pixels wide.
export function jumboTextures(codes, { width, anisotropy = 1 }) {
  return Object.fromEntries(
    codes.map((code) => {
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = Math.round((width * JUMBO.h) / JUMBO.w);
      drawJumbo(canvas.getContext("2d"), width, code);
      return [code, cardTexture(new CanvasTexture(canvas), anisotropy)];
    }),
  );
}
