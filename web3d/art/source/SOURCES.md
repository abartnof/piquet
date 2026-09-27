# Card art — pinned sources

The originals, exactly as downloaded from Wikimedia Commons on 27 September
2026, kept here because a Commons file can be replaced by a later upload under
the same name. Everything the game shows is generated from these two files by
the art pipeline (`docs/TABLE3D.md`, phase 3). Credits and licences for
players are in `/CREDITS.md`.

| File | What | Author | Licence | SHA-256 |
|---|---|---|---|---|
| `public-domain-complete-playing-card-deck.svg` | All 54 cards (A–K in four suits, two jokers) | AustinGabriel64 | CC0 1.0 | `a9616db42c1caa16e80f1727e966268e271d458c3d58dfeee6bd7362cbc60517` |
| `reverso-baraja-espanola.svg` | The card back: a blue lace pattern | Germarquezm | CC BY-SA 3.0 | `0d657965a171ed4b6ae1cdbe186ead5c2f9de72a30eb960835b36ede2d641419` |

Retrieved from:

- https://commons.wikimedia.org/wiki/File:Public_domain_complete_playing_card_deck.svg
  (uploaded 27 July 2026; 2,278,001 bytes)
- https://commons.wikimedia.org/wiki/File:Reverso_baraja_espa%C3%B1ola.svg
  (2 February 2013; 16,136 bytes). Its Commons page credits elements
  from https://commons.wikimedia.org/wiki/File:Baraja_espa%C3%B1ola.svg, by the
  same author under the same licence.

## What the deck file is, measured

- A 6750 × 6300 viewBox holding a **9 × 6 grid of 750 × 1050 cells** — exactly
  5:7, the poker proportion (2.5 × 3.5 in, 63.5 × 88.9 mm).
- **54 top-level `<g>` elements, one per card**, in the order A 2 … 10 J Q K of
  spades, then hearts, clubs, diamonds, then the black and the red joker. Card
  *n* (from 0) is centred at (375 + 750·(*n* mod 9), 525 + 1050·⌊*n*/9⌋): each
  group's transform is `matrix(0.24,0,0,0.24,x,y)` with that centre.
- Each card is a white rounded rectangle, corner radius 37.5 of 750 (5% of the
  width), with **no border stroke** — on a white page the card edge is
  invisible, which the 3D table's ink outline supplies.
- No `<defs>`, `<use>`, `<symbol>`, clip paths or embedded images: plain paths.
- Weight: the 32 piquet cards (7 to ace) are 2.16 MB of the 2.33 MB, and the
  twelve court cards alone are 1.95 MB. Trimming the SVG to the piquet cards
  would save almost nothing, which is why the game ships rasterised faces.

## What the back file is

- 208 × 319: the proportions of a Spanish-suited card (about 1:1.53), taller
  than the faces' 5:7 (1:1.4). A white rounded border around a navy/white lace
  pattern of crossed crosses, holly leaves and four-leaf clovers.
- Fitting it to the faces' proportions means cropping or re-framing it, which
  is an *adaptation* under its licence: the version the game uses must itself
  be CC BY-SA 3.0, and attributed. See `/CREDITS.md`.
