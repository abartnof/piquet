// The card images, from what the build inlined, as textures.
//
// Two ways (docs/TABLE3D.md section 3.2): data URIs of WebP images made at
// build time, or the SVGs themselves, rasterised here into canvases at a size
// chosen from the screen's pixel ratio. Either way the GPU gets raster
// textures; the question is only where the rasterising happens.

import { CanvasTexture, Texture } from "three";
import { cardTexture } from "./materials.js";

const ASPECT = 7 / 5;

// Wide enough for a card in the hand on a sharp screen; capped because 33
// textures of 1024 px with mipmaps would take a quarter of a gigabyte of GPU
// memory, which a phone does not have.
export function vectorWidth(pixelRatio) {
  return Math.round(512 * Math.min(Math.max(pixelRatio, 1), 1.5));
}

async function rasterise(svg, width) {
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = Math.round(width * ASPECT);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff"; // the white matte the raster art is made on
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    return new CanvasTexture(canvas);
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function decode(uri) {
  const image = new Image();
  image.src = uri;
  await image.decode();
  return new Texture(image);
}

export async function loadTextures(art, { anisotropy = 1, pixelRatio = 1 } = {}) {
  const started = performance.now();
  const width = vectorWidth(pixelRatio);
  const entries = await Promise.all(
    Object.entries(art).map(async ([name, source]) => {
      const texture = source.startsWith("<svg") ? await rasterise(source, width) : await decode(source);
      return [name, cardTexture(texture, anisotropy)];
    }),
  );
  const textures = Object.fromEntries(entries);
  const back = textures.back;
  delete textures.back;
  const vector = Object.values(art)[0].startsWith("<svg");
  return { faces: textures, back, vector, width: vector ? width : null, ms: performance.now() - started };
}
