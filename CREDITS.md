# Credits

Credit where it is due — including where no licence demands it. **Every
third-party asset is recorded here, in the commit that brings it in**: art,
fonts, icons, libraries, build tools, and the design systems we follow.

## Card art

### The faces

**"Public domain complete playing card deck"**, by **AustinGabriel64**, from
Wikimedia Commons (uploaded 27 July 2026).
<https://commons.wikimedia.org/wiki/File:Public_domain_complete_playing_card_deck.svg>

Licence: **CC0 1.0 Universal** — a public-domain dedication
(<https://creativecommons.org/publicdomain/zero/1.0/>). No attribution is
required; it is given anyway, gladly. The game uses the 32 piquet cards (seven
to ace in each suit), rasterised from the vector original.

### The back

**"Reverso baraja española"**, by **Germarquezm**, from Wikimedia Commons (2013).
<https://commons.wikimedia.org/wiki/File:Reverso_baraja_espa%C3%B1ola.svg>

It includes elements from **"Baraja española.svg"**, also by Germarquezm
(<https://commons.wikimedia.org/wiki/File:Baraja_espa%C3%B1ola.svg>).

Licence: **CC BY-SA 3.0** (<https://creativecommons.org/licenses/by-sa/3.0/>).
Attribution is **required**, and ShareAlike applies to adaptations.

Our changes: rasterised, and re-framed from its Spanish proportions (about
1:1.53) to the 5:7 of the face cards. That makes the back the game shows an
adaptation, so **that image is itself licensed CC BY-SA 3.0**, and the game
credits it on screen, not only here.

The pinned originals, with checksums and measurements, are in
`web3d/art/source/`.

## Design system

**Material Design 3**, by **Google** — <https://m3.material.io/>. The 3D
table's controls follow its components, colour system, shape and motion
guidance (Andrew: "clear designs, organic motion, and favors smooth lines over
sharp lines"). The guidelines are Google's; the components are used through
`@material/web` (below), and the colour scheme is generated from one seed
colour with Google's Material Color Utilities (build tools, below). The
motion curves and durations are the ones `@material/web` ships as tokens, and the
folds' spring is Material 3 Expressive's spatial spring (damping ratio 0.8), sampled
for CSS `linear()` — <https://m3.material.io/styles/motion/overview>. The hand's sort
is Material Web's outlined segmented button, from its `labs`.

The page's few icons (undo, settings, narration, fold and unfold) are simple
strokes drawn for it; no icon font or Material Symbols is used.

## Software in the page

The 3D table's single-file page (`web3d/piquet3d.html`; see
`docs/TABLE3D.md`) bundles exactly these — the list is what esbuild's
metafile says is in the bundle, not merely what is installed. The licences
require their notices to travel with the copies: the build keeps each
library's licence comment at the end of the script, and the page's Credits
screen (Settings → Credits) names them.

| Package | Version | Licence | Holder | In the page |
|---|---|---|---|---|
| three.js | 0.186.1 | MIT | three.js authors | 535 KB |
| @material/web (Material Design 3 components) | 2.5.0 | Apache-2.0 | Google LLC | 191 KB |
| lit-html (part of Lit 3.3.3) | 3.3.3 | BSD-3-Clause | Google LLC | 10 KB |
| @lit/reactive-element (part of Lit) | 2.1.2 | BSD-3-Clause | Google LLC | 9 KB |
| lit-element (part of Lit) | 4.2.2 | BSD-3-Clause | Google LLC | 1 KB |
| tslib (TypeScript's helpers, used by Material Web) | 2.8.1 | 0BSD | Microsoft Corporation | 0.3 KB |

Installed but not in the page: `@lit/context` (BSD-3-Clause), a dependency of
Material Web that the bundle never reaches.

The rules engine and everything else in this repository are the project's own.

## Build tools (used, not shipped)

| Tool | Version | Licence | Use |
|---|---|---|---|
| esbuild | 0.28.2 | MIT | Bundling the page's JavaScript |
| Material Color Utilities (`@material/material-color-utilities`) | 0.4.0 | Apache-2.0 | Generating the 3D table's colour scheme from one seed (`web3d/tools/scheme.mjs`) |
| librsvg (`rsvg-convert`) | Debian 12 | LGPL-2.1+ | Rasterising the card art |
| Pillow | current | MIT-CMU (HPND) | Cropping and encoding the card images |

## Rules, history and method

The sources behind the rules — pagat.com, Cavendish's *Laws of Piquet* (1892),
Foster's *Complete Hoyle* (1897), Hoyle (1744), Cotton (1674) — and the
mathematics behind the opponents are credited in `docs/LITERATURE.md`.
