// The Jumbo Index faces: for a phone, where a fanned hand shows each card
// only by its corner, faces that are nothing but corner -- the rank large in
// the platform's bold UI font (San Francisco on an iPhone), the suit larger
// beneath it, on one axis, at both ends. Drawn here with Canvas 2D, so no
// font is bundled or fetched.
//
// From the user's own recipe (1 October 2026), kept as given in the commit
// that brought it, d2507ac. What differs, for the table: the face is paper
// from edge to edge, because the table's ink line draws every card's edge
// and rounds its corners (the classic art has no border either); the faces
// are drawn at the classic art's width for the screen (art.js); and, at the
// user's word (2 October), the index is fitted into the strip of each card
// a fanned hand shows, rather than drawn at the recipe's sizes and covered.
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
  rankTop: 0.3, // y of the top of the rank's capitals
  rankSize: 2.2, // the recipe's sizes, one for every rank and one for every
  suitSize: 2.8, // suit: the most either is drawn at
  gap: 0.3, // between the rank's capitals and the suit's ink, at the recipe's sizes
  // What a full hand fanned on a phone shows of each card: a strip this
  // wide at its left, all down the index (faces.test.js measures it). The
  // index is fitted into it with `margin` clear either side -- about 3.5 px
  // on a phone -- so no rank or suit is ever under the next card (the user:
  // "shrink the card graphics to be visible within that space (with a few
  // pixels at least of space on the side, for visibility's sake)").
  strip: 1.46,
  margin: 0.25,
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

// The sizes that fit the strip, in units: the rank's, the largest at which
// every one-character rank fits (the canvas narrows a 10 to the same room,
// so every rank stands the same height); the suit's, the largest at which
// every suit's ink fits. Measured in whatever fonts the system has.
function fitted(ctx) {
  const room = JUMBO.strip - 2 * JUMBO.margin;
  const widest = (font, texts) => {
    ctx.font = font;
    return Math.max(...texts.map((t) => {
      const m = ctx.measureText(t);
      return m.actualBoundingBoxLeft + m.actualBoundingBoxRight;
    }));
  };
  const rank = Math.min(JUMBO.rankSize, (100 * room) / widest(`700 100px ${RANK_FONT}`, ["7", "8", "9", "J", "Q", "K", "A"]));
  const suit = Math.min(JUMBO.suitSize, (100 * room) / widest(`100px ${SUIT_FONT}`, Object.values(GLYPH)));
  return { room, rank, suit, axis: JUMBO.margin + room / 2 };
}

// One corner: the rank's capitals from rankTop, centred in the strip; the
// suit placed by its measured ink -- its top a gap below the rank, its
// centre under the rank's -- so the four suits line up whatever symbol font
// the system has.
function corner(ctx, u, rank, suit, fit) {
  ctx.fillStyle = COLOUR[suit];
  ctx.textBaseline = "alphabetic";
  ctx.font = `700 ${fit.rank * u}px ${RANK_FONT}`;
  ctx.textAlign = "center";
  const cap = ctx.measureText("H").actualBoundingBoxAscent;
  ctx.fillText(rank, fit.axis * u, JUMBO.rankTop * u + cap, fit.room * u);

  ctx.font = `${fit.suit * u}px ${SUIT_FONT}`;
  ctx.textAlign = "left";
  const glyph = GLYPH[suit];
  const m = ctx.measureText(glyph);
  const inkLeft = -m.actualBoundingBoxLeft;
  const inkRight = m.actualBoundingBoxRight;
  const suitTop = JUMBO.rankTop * u + cap + JUMBO.gap * (fit.rank / JUMBO.rankSize) * u;
  ctx.fillText(glyph, fit.axis * u - (inkLeft + inkRight) / 2, suitTop + m.actualBoundingBoxAscent);
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
  const fit = fitted(ctx);
  corner(ctx, u, rank, suit, fit);
  ctx.save();
  ctx.translate(width / 2, height / 2);
  ctx.rotate(Math.PI);
  ctx.translate(-width / 2, -height / 2);
  corner(ctx, u, rank, suit, fit);
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
