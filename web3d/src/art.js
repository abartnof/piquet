// The card images, from the data URIs the build inlines, as textures.

import { Texture } from "three";
import { cardTexture } from "./materials.js";

export async function loadTextures(art, anisotropy = 1) {
  const entries = await Promise.all(
    Object.entries(art).map(async ([name, uri]) => {
      const image = new Image();
      image.src = uri;
      await image.decode();
      return [name, cardTexture(new Texture(image), anisotropy)];
    }),
  );
  const textures = Object.fromEntries(entries);
  const back = textures.back;
  delete textures.back;
  return { faces: textures, back };
}
