// How things are drawn: cel shading, and the ink line.
//
// Cel shading is MeshToonMaterial with a small gradient map, so light falls in
// flat bands. The ink line is an inverted hull: each mesh drawn a second time,
// back faces only, every vertex pushed outward on screen by a constant number
// of pixels, in an ink colour. Where the hull shows past the object's own
// silhouette, that is the line (docs/TABLE3D.md section 8).

import {
  BackSide,
  Color,
  DataTexture,
  MeshToonMaterial,
  NearestFilter,
  RedFormat,
  ShaderMaterial,
  SRGBColorSpace,
  Vector2,
} from "three";

export const INK = "#1d2433"; // a deep ink, not pure black

// A 1-pixel-tall ramp: n bands, lit from the brightest at the right.
export function toonRamp(levels) {
  const texture = new DataTexture(Uint8Array.from(levels, (v) => Math.round(v * 255)), levels.length, 1, RedFormat);
  texture.minFilter = NearestFilter;
  texture.magFilter = NearestFilter;
  texture.generateMipmaps = false;
  texture.unpackAlignment = 1;
  texture.needsUpdate = true;
  return texture;
}

// Card faces are bright-biased so the art always reads; the table is softer.
export const RAMPS = {
  card: () => toonRamp([0.82, 0.94, 1.0]),
  table: () => toonRamp([0.9, 0.96, 1.0]),
};

export function cardTexture(texture, anisotropy = 1) {
  texture.colorSpace = SRGBColorSpace;
  texture.anisotropy = anisotropy;
  texture.needsUpdate = true;
  return texture;
}

export function cardMaterials({ face, back, ramp }) {
  return [
    new MeshToonMaterial({ map: face, gradientMap: ramp }),
    new MeshToonMaterial({ map: back, gradientMap: ramp }),
    new MeshToonMaterial({ color: "#f3efe6", gradientMap: ramp }), // the edge: a cream
  ];
}

// The ink line. `width` is in CSS pixels; the scene converts it to device
// pixels and keeps `resolution`, the drawing buffer's size, current.
export function inkMaterial({ color = INK, width = 2.5 } = {}) {
  return new ShaderMaterial({
    uniforms: {
      inkColor: { value: new Color(color) },
      inkWidth: { value: width },
      resolution: { value: new Vector2(1, 1) },
    },
    // Each vertex is pushed along its outline normal *in the model*, by
    // however far projects to inkWidth pixels on screen. Pushing on screen
    // instead would keep each vertex's depth while moving it sideways, which
    // re-slopes every hull triangle: on the far half of a card tilted away,
    // the hull then stands in front of the face it should hide behind. In the
    // model the hull stays in the card's own plane, and depth stays exact.
    vertexShader: /* glsl */ `
      attribute vec3 outlineNormal;
      uniform float inkWidth;
      uniform vec2 resolution;
      const float PROBE = 0.1;    // cm: how far along the normal to look
      const float MAX_PUSH = 1.0; // cm: an edge seen end-on gets no wider than this
      void main() {
        vec4 clip = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        vec4 ahead = projectionMatrix * modelViewMatrix * vec4(position + outlineNormal * PROBE, 1.0);
        float pixels = length((ahead.xy / ahead.w - clip.xy / clip.w) * resolution * 0.5);
        float push = pixels > 1e-4 ? min(inkWidth * PROBE / pixels, MAX_PUSH) : 0.0;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position + outlineNormal * push, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 inkColor;
      void main() {
        gl_FragColor = vec4(inkColor, 1.0);
        #include <colorspace_fragment>
      }`,
    side: BackSide,
  });
}
