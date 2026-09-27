# The 3D table — design and plan

> A fresh session should be able to build this from this file alone. It holds
> the brief (in Andrew's words), every decision taken and why, the physics, the
> architecture, the tests, and a phased TODO with acceptance criteria. The
> engine, protocol and 2D page it builds on are described in `PLAN.md`,
> `docs/PROTOCOL.md` and `web/`. Written 27 September 2026, before any 3D code.

## 1. The brief, verbatim

Andrew, 27 September 2026:

> "start to devise a new gui- 3d (threejs, if you prefer). the cards will be
> these (Public domain complete playing card deck.svg). the back of the cards
> will be this (Reverso baraja española.svg). please note these in the
> documentation, so we can give credit where credit is due. we'll start with a
> very clean aesthetic and build upon it. remember- this now exists in 3d, with
> an implied table as the foundation for what we can see. so, when a card is
> flipped, it should not just spin in the air- one side must be constrained by
> the table. cards that the player can see should be held floating in the air
> before them; the dealer's card should be held floating with only the
> backsides visible. tricks that have been made should be pushed to the side.
> i'd like a border around each 3d item, like a cartoon has (That effect is
> called toon shading (or cel shading), and the black outline technique itself
> is known as an ink line, toon outline, or contour rendering.). update the
> todo thoroughly, and then go ahead! think critically about the physics
> involved. try to use motion easing, and include shadows."

> "your aesthetic is: clean and a bit cartoonish, for visual clarity's sake;
> bright and easy to use. not childish. what would a computer version of cards
> look like if it were freed of the cultural heritage of having to use grubby
> cards on dirty furniture"

> "you may simply use material design 3 components if you want- that aligns
> with our design (but of course, anything you use must be downloaded so this
> may work offline). material design has clear designs, organic motion, and
> favors smooth lines over sharp lines- this makes it look pleasant instead of
> cheap and old"

> "i'd like the score to be a floating 2d running tab on the screen. think: a
> collapsable list with all the gameplay stages, with the subtotal for each
> part running as it goes- score for the player, and score for the opponent."

> "remember to take copeous notes- it's probably a good idea to plan all this
> and then tell me- we'll clear the context and you can proceed that way?"

Standing rules that still apply (from `PLAN.md` and the project memory): TDD;
atomic commits straight to `main`, often; `set -e` on multi-step shell
commands; a single self-contained HTML page that stays modest (5 MB is a
guideline, not a hard limit — Andrew: "i want this to be rather modest and
easy to use, but it's not a HARD limit"); everything offline;
no proper names for the opponent — "your opponent"; every aid a toggle; the
GUI is a client of the protocol and holds no rules.

## 2. What we are making

A second client, **`web3d/piquet3d.html`**: the same engine and the same
protocol as the 2D page (`web/piquet.html`), drawn as a small 3D scene. The 2D
page stays — it is the fastest way to test the engine, and a fallback.

**The look, in one paragraph.** A bright, calm, slightly cartoonish scene: a
clean pale surface that reads as "a table" only because things rest on it and
cast shadows on it — not felt, not wood, not a casino. Cards are crisp white
with a dark ink outline, lit with two or three flat tones (cel shading), their
faces always readable. Your hand floats before you, fanned, facing you; your
opponent's floats across the table showing only backs. Cards move the way a
careful hand moves them: they accelerate and settle, they are laid down rather
than dropped, turned over along an edge that stays on the table, and swept
aside when a trick is won. The 2D controls float over the scene as Material
Design 3 surfaces: rounded, quiet, clear.

**What "freed of grubby cards on dirty furniture" rules out**: green felt and
wood textures; casino chips, ashtrays and lamps; paper grain and wear;
dark moody lighting; skeuomorphic chrome on the controls. **What it keeps**:
the cards themselves (the art Andrew chose), the table as a plane of contact,
and the real choreography of the game — dealing in twos, the talon's five
crossed over three, tricks face up in front of their winner.

## 3. Assets

### 3.1 The art, and its licences

Pinned originals: `web3d/art/source/` (see its `SOURCES.md` for URLs,
checksums and measurements). Credits: `/CREDITS.md`.

- **Faces — CC0.** "Public domain complete playing card deck", AustinGabriel64.
  One SVG, 6750 × 6300, a 9 × 6 grid of 750 × 1050 cells (5:7), 54 top-level
  `<g>`, one per card, in order A…K of ♠ ♥ ♣ ♦ then two jokers; card *n* is
  centred at (375 + 750·(*n* mod 9), 525 + 1050·⌊*n*/9⌋). No card border
  stroke. Corner radius 37.5/750.
- **Back — CC BY-SA 3.0, attribution required.** "Reverso baraja española",
  Germarquezm, adapting his "Baraja española.svg". 208 × 319 (≈1:1.53).
  Re-framing it to 5:7 makes our version an adaptation, so **the back image we
  ship is CC BY-SA 3.0** and must be credited **in the game** (a Credits screen
  reachable from the settings), not only in the repository.

### 3.2 The art pipeline: build both ways, and choose by eye

Andrew's decision (27 September 2026): **keep the page small enough that we
can try the card art both ways — rasterised and vector — and see which we
prefer.** So phase 3 builds both, behind a build flag, and puts them side by
side before anything is settled. Neither is the default until he has looked.

**What each way buys.** Measured so far: the 32 piquet cards are 2.16 MB of
the 2.33 MB SVG, the twelve courts alone 1.95 MB.

| | Raster (WebP, made at build time) | Vector (SVG, rasterised in the browser) |
|---|---|---|
| File size | Smaller: est. 0.8–1.3 MB for 33 images | Larger: 2.2 MB raw; perhaps ~1–1.3 MB after trimming path precision (SVGO-style), and it gzips well when served |
| Crispness | Fixed at the chosen resolution (512 px wide) | Rasterised at load at whatever the device needs (DPR 2–3, a close-up of one card) |
| Recolouring | A separate image set per variant | Trivial — suit colours are fills: e.g. a **four-colour deck** as an accessibility aid (a toggle, like every aid), or a high-contrast deck |
| First load | Fast (image decode) | Slower: 33 SVGs rasterised on load — measure it, on a phone too |
| Build | Needs `rsvg-convert` + Pillow on the VM | Needs neither; the browser is the rasteriser |
| Fidelity | Near-lossless at q≈88 | The artist's original |

Either way the GPU gets raster textures (WebGL samples images, not paths); the
question is only whether the rasterising happens once at build time or on the
player's machine at load.

**Measured in phase 3** (27 September 2026, on the VM):

| | Way A, raster | Way B, vector |
|---|---|---|
| The art as files | 33 WebP, 1.22 MB | 33 SVG, 2.14 MB |
| In the page | 1.63 MB (base64) | 2.18 MB (JSON text) |
| The whole page | **2.60 MB** | **3.15 MB** |
| Gzipped, if ever served | ~1.2 MB (WebP barely compresses) | **~0.49 MB** |
| First frame on screen, DPR 1 | 7.2–7.3 s | 7.6–8.5 s |
| First frame on screen, DPR 2 | 8.4–8.9 s | 9.8–10.3 s |
| Texture width | 512 px | 512 × DPR, capped at 768 |
| A close-up, far closer than play | slightly soft in fine lines | crisp |

Three things the measuring turned up:

- **Trimming path precision is not worth it.** The deck is already written to
  three decimals, and its paths are *relative*, so rounding errors accumulate
  along each one: two decimals saved 7% and moved hundreds of pixels per
  card, some to the opposite colour; one decimal saved 15% and moved
  thousands. Way B ships the SVGs untouched.
- **The first frame is later than `render()` returning.** Timed at the call,
  WebP looked ready in 1.9 s and SVG in 2.2 s — while the page stayed stalled
  until 7–8 s. The honest clock waits two animation frames after the first
  render (`piquet3d.art().readyMs`). Most of those seconds are SwiftShader
  emulating a GPU on two CPU cores — shader compiles, mipmaps, the shadow
  blur — and a real GPU should take a fraction of that. **Andrew's machine is
  the number that decides this**, and has not been taken.
- The capped texture width is a memory decision, not a looks one: 33 textures
  at 1024 px with mipmaps would take ~250 MB of GPU memory; at 768, ~145 MB;
  at 512, ~64 MB.

So on the VM the choice is closer than it first looked: vector costs ~0.5 MB
on disk and 0.5–1.5 s at load, and buys crisper close-ups, a four-colour deck
for almost nothing, and a much smaller download if the page is ever served
compressed. A 768 px WebP set would buy most of the crispness for ~1.2 MB more.

**Way A — raster**, as first planned:

- `web3d/tools/art.py` (Python, the project `.venv`):
  1. rasterise the deck SVG once with `rsvg-convert` (apt: `librsvg2-bin`) at
     scale 512/750, giving a 4608 × 4301 sheet (each card 512 × 717);
  2. crop the 32 cells (7–A of each suit) with Pillow; keep the white rounded
     rectangle and make the area outside the corner radius transparent;
  3. build the back: rasterise `reverso-baraja-espanola.svg`, take its lace
     field, fit it ("cover") into a 5:7 card with a clean white border of the
     same proportion as the faces', same corner radius — the adaptation;
  4. encode each as WebP (Pillow, quality ≈ 88; lossless for the back if
     smaller); write `web3d/art/cards/{AS,KS,…,7D}.webp` and `back.webp`;
  5. print sizes; fail if the art exceeds its budget (1.2 MB total).
- **Commit the generated images** (they are the game's art; the Mac has no
  toolchain and the pipeline needs apt packages) and regenerate only when the
  pipeline changes. Record regeneration in `docs/VM.md`.
- Card codes follow the protocol: rank `A K Q J T 9 8 7`, suit `S H D C`.

Resolution: a card in the floating fan is roughly 130–180 CSS px wide on a
laptop; at DPR 2 that is up to ~360 device px, and a hovered card lifts closer.
512 px wide with mipmaps is ample; revisit only if screenshots look soft.

**Way B — vector.** At build time, cut the deck SVG down to the 32 piquet cards
(one standalone SVG per card, viewBox on its 750 × 1050 cell), trim numeric
precision in path data (never in the transforms, whose scale factors must stay
exact), and embed them. At load, draw each into a canvas at a size chosen from
the device pixel ratio and use the canvas as the texture; re-draw one card
larger if it is ever shown up close. The back is prepared the same way (its
5:7 re-framing done in SVG). A **four-colour deck** becomes a cheap option: swap
the suits' fill colours before rasterising.

### 3.3 Budget (single file; kept modest — 5 MB is a guideline, not a wall)

| Part | Estimate | Note |
|---|---|---|
| three.js (tree-shaken, minified) | 350–550 KB | only the classes used |
| @material/web + Lit (a handful of components) | 80–180 KB | per-component imports |
| Engine (wasm, base64) | ~425 KB | as today |
| Card art (32 faces + back, WebP, base64) | 0.8–1.3 MB | measured in phase 3 |
| App code + CSS | 60–120 KB | |
| **Total** | **~1.8–2.6 MB raster; ~2.5–3.5 MB vector** | the build reports every part and warns over 5 MB |

No web fonts and no icon font: a system font stack, and a few inline SVG
icons. (Roboto would be ~100 KB+ per weight; the M3 components work with any
font via their tokens.)

## 4. The stack

- **three.js 0.186.1** (MIT) — WebGL2 renderer, shadow maps, `MeshToonMaterial`.
- **@material/web 2.5.0** (Apache-2.0) with **Lit 3.3.3** (BSD-3-Clause) for
  the overlay: `md-filled-button`, `md-outlined-button`, `md-text-button`,
  `md-icon-button`, `md-switch`, `md-filter-chip`/`md-assist-chip`,
  `md-dialog`, `md-list`/`md-list-item` (the score tab), `md-linear-progress`
  (opponent thinking), `md-elevation`. Themed with M3 colour tokens generated
  from one seed colour (see §8). Material Web was released in July 2026, so it
  is maintained; check its changelog for deprecations when installing.
- **esbuild 0.28.2** (MIT, build only) bundles `web3d/src/**` + three + Material
  Web into one minified IIFE, which `web3d/build.py` inlines into the page with
  the wasm and the art, exactly as `web/build.py` does for the 2D page.
- **Dependencies via npm with a lockfile.** `sudo apt install npm` on the VM;
  `web3d/package.json` pins exact versions; `package-lock.json` is committed;
  `node_modules/` is git-ignored; `npm ci` then `node_modules/.bin/esbuild`.
  (Hand-fetching tarballs was considered and rejected: Material Web has a
  dependency tree, and a lockfile is the honest way to pin it.)
- **Offline, verified.** The browser test blocks every network request and
  fails if the page attempts one.

## 5. Architecture

The page is a client of the existing protocol (`docs/PROTOCOL.md`, version 2)
and holds no rules. It is structured so that each piece is testable without a
browser.

```
web3d/src/
  main.js          boot: load wasm + art, build the scene, wire the overlay
  engine.js        the wasm wrapper (as in web/src/app.js: start/state/send)
  units.js         dimensions and zone positions (§6) — one source of truth
  easing.js        minimum-jerk, friction, gravity, M3 cubic-béziers   [node-tested]
  kinematics.js    hinge flip, transfer arc, slide, lay-down, pick-up   [node-tested]
  layout.js        protocol state -> target poses for all 32 cards      [node-tested]
  choreography.js  (previous state, new events) -> a timeline of motions [node-tested]
  timeline.js      runs motions against the clock; speed; skip-to-end   [node-tested]
  cards.js         card geometry (rounded slab, 3 material groups, outline normals)
  materials.js     toon gradient, face/back/edge materials, ink-outline hull shader
  scene.js         renderer, camera, lights, shadows, table surface, resize, DPR
  interact.js      raycasting: hover, click, drag (later); test hooks
  overlay/         Material Web components: prompt, score tab, settings, credits
  test/*.test.js   node --test (test/browser.py: Playwright)
```

### 5.1 The card model: identities only where the view has them

The scene holds **32 card meshes** for the whole partie. Each has a *pose*, a
*zone* (pack, talon, your hand, their hand, your discards, their discards,
trick, your won tricks, their won tricks, cut) and an *identity* — a card code
**or unknown**. A mesh's face texture is assigned **only when the protocol
state reveals that card to the human** (your hand, your discards, cards played,
cards shown in the cut, talon cards you drew); until then it shows the back on
both sides. This is the 3D equivalent of the rule that everything a client
shows is derived from the human's view, and it gets a test: at every step of a
scripted partie, no mesh in the opponent's hand, the talon or their discards
carries a face.

### 5.2 Layout: where everything is at rest

`layout(state) → Map<meshSlot, Pose>` is a pure function of the protocol state:

- **Your hand**: `state.hand` in the chosen sort order (reuse the 2D page's
  grouping logic: Auto/Suit/Rank/Combinations), fanned and floating (§6).
- **Their hand**: `12 − (tricks played) − (their card on the table)`
  anonymous cards, fanned and floating, backs to you.
- **Talon**: `talon_remaining` cards; before the exchange, five crossed over
  three (Foster: "the five top cards being laid crosswise on the three at the
  bottom").
- **Discards**: yours face down (you may lift them to look — later), theirs
  face down, `their_discards` of them.
- **The trick**: `state.trick`, face up in the centre, the leader's card
  nearer the leader.
- **Won tricks**: `state.tricks_played`, face up, pushed to the winner's side,
  each trick a crossed pair, overlapping in a row so every card stays
  readable (Cavendish, Law 60: examinable at any time).
- **The cut**: during `phase == "cut"`, the pack in the centre; after a cut,
  the two cut cards shown.

### 5.3 Choreography: how things get there

`choreograph(prev, next)` turns the events added since the last state into a
timeline of motions (§7), then `layout(next)` is the resting truth the
timeline must end at — the test for every choreography is that it ends exactly
at the layout. Events it reads: `cut`, `cut_again`, `first_dealer`,
`deal_begins`, `exchanged`, `drew`, `called`, `decided`, `showed`, `scored`,
`nothing_to_call`, `played`, `took_trick`, `deal_ends`, `partie_ends`.
Unknown cards are matched by zone: "your opponent exchanges 5" moves five
anonymous meshes from their hand to their discards and five from the talon to
their hand.

### 5.4 Rendering on demand

Render only while something moves (or the pointer is over a card): a card game
at rest should cost nothing. The timeline says when it is active.

## 6. Space: units, table, camera, zones

**Units: centimetres.** y is up, the table top is y = 0, the human sits at +z,
the opponent at −z, x runs to the human's right.

- **Card**: 6.35 × 8.89 cm (5:7), corner radius 0.3175 cm, thickness
  0.03 cm. Stacked cards rise by a thickness and 0.02 cm each, and rest
  0.02 cm above the table, so no two surfaces are coplanar and nothing
  needs a polygon offset (§8.2).
- **Table**: an implied surface: a large, very slightly rounded slab
  (~140 × 100 cm) whose edge fades into the background, bright and plain,
  receiving shadows. No texture. Its outline, if visible at all, is soft.
- **Camera**: the human's eyes, about 55 cm above the table and 60 cm back
  from its centre, looking at the centre (the spike tried ~8 cm in front of
  it, which put your opponent's hand off the top of the screen); vertical
  field of view ~40°. Fixed for now (a slight mouse parallax is an open
  question, §12). Resize and DPR handled; DPR capped at 2.
- **Zones**: `web3d/src/units.js` is the source of truth — `ZONES` across
  the table, `ZONES_PORTRAIT` stacked down it for a phone or tablet held
  upright (below an aspect of 0.85, under `CAMERA_PORTRAIT`). As built,
  across the table: your hand a fan at (0, 15, 27), 16 cm radius, 5.6°
  between cards and 2.6° more between groups, leaning back 14°; theirs
  held upright at (0, 12, −22); the talon at (−18, −3), five crossed over
  three; discards at (−31, 9) and (−31, −14); the trick in the middle
  with each card in front of whoever played it; won tricks shingled in rows
  to the right at z = 7 and −9 (moved in from the plan's ±12 so the score
  tab never covers them); the cut a ribbon spread across the middle. The
  first sketch here put the hands at y = 18, z = ±30, which set your
  opponent's hand off the top of the screen.

## 7. Motion and physics

Principles: **cards are rigid, thin and light, and almost always moved by a
hand**, so most motion is the smooth start-and-stop of a guided movement, not
ballistic flight. Paper does not bounce. Nothing passes through the table or
through another card. A card on the table that turns over does so about an
edge that stays on the table.

### 7.1 Easing, with its physics

| Motion | Profile | Why |
|---|---|---|
| Hand-guided moves (deal, play, pick up, lay down) | **Minimum jerk**: s(t) = 10t³ − 15t⁴ + 6t⁵ | Human reaching movements follow the minimum-jerk profile (Flash & Hogan, 1985): zero velocity and acceleration at both ends, peak speed 1.875× the mean at mid-course |
| A card slid across the table after a push (tricks aside) | **Coulomb friction**: constant deceleration a = μg, so s(t) = 1 − (1 − t)² | With μ ≈ 0.25 on a smooth top and g = 981 cm/s², a ≈ 245 cm/s²: a 30 cm slide starts at ≈ 121 cm/s and stops in ≈ 0.5 s. Stopping distance v₀²/2μg |
| The falling half of a flip | **Gravity**: accelerating, ease-in | Past vertical, the card falls about its hinge under gravity |
| Interface (overlay panels, chips, the score tab) | **M3 easing**: standard `cubic-bezier(0.2, 0, 0, 1)`; emphasized decelerate `(0.05, 0.7, 0.1, 1)`; emphasized accelerate `(0.3, 0, 0.8, 0.15)`; durations 50–600 ms by size (verify the tokens against m3.material.io when implementing) | Material's "organic motion" |

Durations (starting points, tuned by eye; a speed setting scales them):
deal one pair 180 ms (overlapping); play a card 420 ms; pick up 380 ms; lay
down 360 ms; flip 480 ms; trick gathered and pushed 520 ms; cut lift and show
700 ms. `prefers-reduced-motion` and the test mode shorten everything to near
zero.

### 7.2 The primitives

1. **Transfer** (hand-guided, used by most moves). Position along a quadratic
   Bézier arc from start to end, apex raised by clearance h = max(3 cm,
   0.25 × distance) so the card clears everything between; orientation by
   quaternion slerp. Both driven by minimum jerk; the rotation finishes at
   ~85% of the way so the card arrives already level and is *set down*, not
   rotated into the table.
2. **Lay down** (hand → table). A transfer that ends flat; the last 10% is a
   vertical approach so the card meets the surface face-parallel. Paper does
   not bounce: at most a 1–2° settling wobble over 120 ms, optional.
3. **Pick up** (table → hand). Lift the near edge first (a hinge on the far
   edge, 15–25°), then a transfer into the floating fan pose. The face turns
   toward the player during the transfer — in the air, in a hand, which is
   physically fine; the "no spinning in the air" rule is about turning cards
   *over on the table*.
4. **Flip on the table** — Andrew's constraint. Rotate 180° about one edge
   (the hinge), which stays on the table at its stack height the whole time;
   the card ends one card-width over, face up. θ from 0 to π/2 is driven by a
   finger (ease-out, decelerating to the top); θ from π/2 to π is a fall under
   gravity (ease-in, accelerating), about 0.6 of the first half's duration;
   no bounce, a tiny settle. **Invariant: every point of the card stays at or
   above the table plane for all t** — true by construction for θ ∈ [0, π]
   about an edge on the plane, and tested. Which edge: the one on the side the
   card should end up.
5. **Slide** (on the table). Translate along the surface, flat, with the
   friction profile; a small yaw (±3°, deterministic per card code, so a
   replay looks the same) makes it organic. Several cards pushed together
   move as one.
6. **Fan** (in the air). Place n cards on an arc about a pivot below the
   hand's centre; each card tilted toward the camera. Reordering (sorting)
   moves cards along the arc by transfer. An idle sway (±0.2 cm, ~4 s) keeps
   a held hand from looking frozen; off under reduced motion.

### 7.3 The game's choreography

| Moment | What happens |
|---|---|
| **Partie begins: the cut** | The pack lies in the centre. Hovering its long side shows where you would cut (the upper packet lifts slightly); click to cut. Each packet is lifted and tilted up to show its bottom card to both players (a hand-held motion), held for a moment, then set back; equal cuts, cut again. The higher card chooses (see `docs/PIQUET.md`). |
| **The deal** | The dealer's side deals from the pack **two at a time** (Cavendish), alternately, face down onto the table before each player; then the eight-card talon: three, and five crossed over them (Foster). Each player picks up their twelve: yours rise into the floating fan and turn to face you (faces assigned now); theirs rise showing backs. |
| **Exchange** | Chosen discards lift out of your fan and are laid face down on your discard pile; the same number are picked up from the top of the talon into your fan. Your opponent's move the same way, anonymously. |
| **Declarations** | The dialogue is 2D (the overlay says "Your opponent: point of 5"); a shown combination may later be briefly lifted and turned toward the other player — a v2 touch, needing a protocol addition (the cards of `showed` events). |
| **A card played** | Yours: from the fan, transfer + lay down, face up, onto the trick spot. Theirs: the card is tipped **forward, away from its holder, about its lower edge** as it is laid down — which turns its face from them to the sky, face up, the natural motion — landing upside-down to you, as it would at a real table. |
| **A trick won** | A beat to read it (the 2D page's 0.9 s pause, but in place); then the winner's side gathers the pair — the second card slides onto the first — and pushes it aside to the winner's row of tricks (slide, friction), face up, overlapping the previous tricks. |
| **Deal ends** | The score tab fills in; all 32 cards are swept together (slides) into a pack, which is squared and set aside for the next dealer. |

## 8. The look: toon shading, ink lines, light and colour

### 8.1 Cel shading
`MeshToonMaterial` with a small `gradientMap` (a 3–4 texel `DataTexture`,
`NearestFilter`) so light falls in flat bands. Card faces use a bright-biased
ramp (e.g. 0.82 / 0.94 / 1.0) so the art stays fully readable; the table uses a
softer ramp; card edges a cream tone. Colour management: sRGB textures,
`ColorManagement` on.

### 8.2 Ink lines (contour rendering)
**Plan A — inverted hull, per object.** Each mesh gets an outline child: the
same geometry drawn with `side: BackSide` in a custom `ShaderMaterial` that
pushes each vertex outward in **clip space** along a *smoothed* normal, so the
line has a constant screen width (≈ 2.5 px at DPR 1, scaled by DPR). The
smoothed normal is a separate vertex attribute, `outlineNormal`, computed by
averaging the normals of vertices that share a position; this is what keeps the
line unbroken at a card's hard edges, where three.js's stock `OutlineEffect`
tears. Colour: a deep ink, not pure black (e.g. `#1d2433`).

**Measured in the look spike (P2): Plan A works, with one change.** Pushing
the hull *on screen* — clip-space x and y, depth kept — fails on a card tilted
away: moving a vertex sideways while keeping its depth re-slopes every hull
triangle, and on the far half of the card the hull stands *in front of* the
face (a 2.5 px stretch over a 50 px triangle spanning 4 cm of depth moves it
~0.2 cm, against a card 0.03 cm thick). The result was a dark "envelope flap"
on every card. The fix: push each vertex **in the model, within the card's
plane**, by whatever distance projects to the ink width in pixels. The hull
then stays coplanar with the back, depth is exact, and the line is continuous
at every attitude tried — flat, 20° to 150°, on edge, floating, turned
(`?angles` shows them). The push is capped at 1 cm so an edge seen end-on
cannot balloon. The outline normal is the in-plane one for the same reason:
a slab's face normals push its near and far rims apart.

Cards on the table rest 0.02 cm above it and each card on a pile 0.02 cm above
the last, so no two surfaces are coplanar and nothing needs a polygon offset
(a slope-scaled offset would push the hull through its own card at grazing
angles). The camera's near plane is 20 cm, which keeps a 24-bit depth buffer
thousands of steps finer than a card's thickness.

**Plan B — post-process edges**, if Plan A misbehaves on the very thin cards
(test it first, in the look spike): render an object-ID buffer and a depth
buffer, and draw ink where the ID changes or depth jumps. Robust for any
geometry, one extra pass.

**Ink as interface.** The line is also the selection language, which keeps the
scene free of glows and badges: hovered-and-playable → slightly thicker ink;
hinted → a cyan ink; selected for discard → amber ink and lifted; illegal →
the face dims. (The 2D page's colours, carried over.)

### 8.3 Light and shadow
A hemisphere light (sky/ground) for the bright, airy base, and one directional
key light high and to the front-left, casting soft shadows (2048² map, bias
tuned for the thin cards). **three r186 removed `PCFSoftShadowMap`** — it
falls back to `PCFShadowMap` with a console warning — so the spike compares
the two that remain: `PCFShadowMap` (five hardware-filtered taps on a rotated
disk: a defined edge, slightly soft) and `VSMShadowMap` (a Gaussian blur: a
soft, light, diffuse shadow, much like Material's elevation shadows).
Provisionally **VSM**, pending Andrew's eye; `?shadow=pcf` shows the other.

**What VSM costs, measured (P8).** The click-driven browser test crawled —
13 to 27 s a turn — and the cause was not the test: every frame re-renders
the shadow map and blurs all of it twice, so the cost goes with the map's
area times the blur's samples. On the software-rendered VM: 2048² with 16
samples, **4.3 s a frame**; PCF, 0.45 s; anisotropic filtering, no
difference at all. The softness is the blur radius in *centimetres*, so a
smaller map at a proportionally smaller radius in texels looks the same:
2048/16, 1024/8 and 512/8 could not be told apart by eye in the same crop.
**Default now 512² with 8 samples: 0.5 s a frame there**, nearly an
eighth of the work — on a real GPU a few hundred microseconds either way,
but on a phone it is battery. `?shadowmap=` and `?blur=` vary it. And a
table at rest renders nothing at all, whatever the shadows cost. **Shadows are the depth cue for the
floating hands**: their soft shadows on the table say "held above it". The
table receives; cards cast and receive.

### 8.4 Colour
One M3 seed colour generates the overlay's scheme (light theme). Proposal to
show Andrew in the look spike: a clear blue seed (the card back is navy and
white), with warm amber for "you" and a teal for "your opponent" in the score
tab. The table: two or three candidate pale surfaces in the spike's
screenshots — warm paper-white, pale sky, soft sage — for him to choose.

## 9. The 2D overlay (Material Design 3)

Floating surfaces over the canvas, nothing modal unless it must be.

- **The score tab** — Andrew's spec: *a floating 2D running tab, a collapsible
  list with all the gameplay stages, the subtotal for each part running as it
  goes, for the player and for the opponent.*
  - A floating M3 card (top-right on a laptop; a bottom sheet on a phone),
    collapsible with one tap. **Collapsed**: a single line — this deal, you
    · your opponent; the partie, you · your opponent.
  - **Expanded, this deal**: one row per stage in reckoning order (Law 67):
    carte blanche (only if it happened), point, sequences, sets, pique /
    repique (only if it happened), the play (live trick count), the cards /
    capot, then the deal's total. Each row shows the stage's points and the
    **running subtotal after it**, for each side. Stages not reached yet are
    listed greyed, so the whole shape of a deal is visible from the start;
    the current stage is highlighted; a stage's figures animate in (M3
    emphasized decelerate) as they are scored.
  - **Expanded, the partie**: a second fold with the six deals (plus extra
    deals on a tie), each deal's two scores, the running partie totals, the
    rubicon line at 100 with the chance of crossing it (`state.rubicon`).
  - Data: the protocol already carries everything — `scored` events with
    `category`, `deal`, `who`, `amount`; `deals`; `partie`; `phase`;
    `tricks`. No engine change needed.
  - A toggle in settings, like every aid.
- **The prompt**: a floating card at the bottom centre with the question and
  its actions (`md-filled-button` for the main action; `md-outlined-button`
  for the rest); the declaration options as buttons whose hover lifts the
  claim's cards in the 3D hand; the hint line with Follow; errors in the
  engine's words.
- **Top bar**: level (skill descriptions, never names), New partie, a hints
  `md-switch`, Undo, Settings.
- **Narration**: a collapsible side sheet, folded by deal, as on the 2D page.
- **Settings dialog**: the aids (hints, play forced, play winners, declare for
  me), the running tab, pause on tricks, animation speed, reduced motion, sort
  order, and **Credits** (the art and software licences — required by CC
  BY-SA and by the libraries' notices).
- **Worth chips and the sort bar**: as on the 2D page, over the hand.

## 10. Interaction

- **Raycasting** against your hand's meshes (and the pack during the cut).
  Hover: the card lifts toward you and its ink thickens. Click: select for
  discard, or play. Keyboard as on the 2D page (Enter, digits, U, H, Escape).
- **Illegal clicks are sent anyway** and the engine's refusal shown, as now —
  the reason is the lesson.
- **The keyboard plays the whole game** (built after P9): ← and → move a
  keyboard pointer along whatever may be chosen now — your hand, or the
  spread when cutting — in the order the cards lie on screen, looking
  exactly like pointing (the card rises, its line thickens); Space plays,
  chooses or cuts there; Enter is still the prompt's main action, and plays
  the card when there is none; the prompt names the card in a polite live
  region, since the table itself is a picture to a screen reader. Found on
  the way: a falsy-zero test on the pointer's card — card 0 is a card.
  Every key is listed under **Keys** in Settings, since a shortcut nobody
  can find is not one.
- **Test hooks** (`window.piquet3d`): `screenPoint(code)` gives a card's
  projected screen position, `busy()`, `state()`; the browser test clicks
  cards through them. `?test` makes every motion instant.
- **Your discards**, which the rules let you consult ("Both players keep
  their own discards beside them and may consult them during play. Neither
  may look at the other's" — `docs/PIQUET.md`): click the pile and you pick
  the cards up, near edge first, into a small fan held up face to you; click
  again, or make any move, and they are laid back down. Built after P9 —
  the 2D page shows your discards face up, and in 3D they had become the
  one thing you could no longer see.
- Later: drag a card to the table to play it; click a won trick to examine
  it.

## 11. Testing

- **Node (`node --test`, Node 18)** for the pure modules, test-first:
  - `easing`: minimum jerk has s(0)=0, s(1)=1, zero slope and curvature at
    both ends, symmetric about ½; friction profile has zero slope at the end
    only; the cubic-bézier evaluator matches known M3 values.
  - `kinematics`: the hinge flip keeps the hinge edge fixed and **every
    corner at or above the table for all t**, ends face up one width over;
    a transfer's apex clears the given obstacles; lay-down ends flat at stack
    height; the fan faces the camera (normals point at the eye).
  - `layout`: for scripted protocol states, zone counts match the state; no
    two resting cards overlap unless stacked with distinct layers; **no face
    texture on any card the view does not reveal**; won tricks are face up.
  - `choreography`: each event kind ends exactly at `layout(next)`; unknown
    cards are conserved (32 always); a `played` by the opponent assigns that
    card's identity only as it lands.
- **Browser (Playwright, system Chromium)**: the page loads **with the
  network blocked** and makes no requests; the canvas is not blank; a whole
  partie can be played by clicking cards through the test hooks; the score
  tab's rows sum to the deal totals; undo, hints, settings, reload; a phone
  viewport; no console errors; screenshots at each stage, read back by eye.
- **Budget**: the build prints the size of each part and warns over 5 MB;
  size is weighed against what it buys, with Andrew, not treated as a wall.

## 12. Open questions for Andrew (after the look spike)

1. The table's colour and mood — from the spike's two or three candidates.
2. Camera: fixed, or a slight parallax following the pointer?
3. Play by clicking (now) — add drag-to-play?
4. Declarations: keep the dialogue purely 2D, or have shown combinations
   lifted in 3D (needs the shown cards in the protocol)?
5. Defaults for the aids stay as on the 2D page unless he says otherwise
   (hints on, play forced on, play winners on, declare for me off).

## 13. Phased TODO

Each phase ends committed and pushed, with `PLAN.md` updated. Tests first
throughout.

- [x] **P0 — Assets and credits.** Originals pinned in `web3d/art/source/`
      with checksums and measurements; `CREDITS.md`. (`3be2e5f`)
- [x] **P1 — Toolchain and skeleton.** `apt install npm librsvg2-bin`;
      `web3d/package.json` + lockfile (three 0.186.1, @material/web 2.5.0, lit
      3.3.3, esbuild 0.28.2); `web3d/build.py` producing a single
      `web3d/piquet3d.html` with the wasm inlined; an empty three.js scene
      renders; the Playwright test asserts no network requests and a
      non-blank canvas; the size report. *Accept*: the page opens from disk,
      offline, and shows a lit surface.
      *Landed*: 960 KB — engine 423 KB, three.js 533 KB (the renderer pulls
      in nearly all of it; tree-shaking saves little), our code 2 KB. A table
      alone is one flat tone from the player's eye — it fills the view — so
      the skeleton floats a placeholder card whose shadow is the proof of
      light. Headless Chromium draws WebGL 2 on SwiftShader.
- [x] **P2 — Look spike.** Table surface, hemisphere + directional light,
      soft shadows, toon materials, ink outline (Plan A) on a flat card, a
      floating tilted card and the table; a placeholder card texture.
      Screenshots of two or three surface colours for Andrew. *Accept*: the
      ink line is continuous around a flat card and a tilted one at several
      angles; shadows of a floating card are visible and soft; it looks
      bright and clean. Decide Plan A or B here.
      *Landed*: **Plan A**, pushed in the model rather than on screen (§8.2).
      Real art rather than a placeholder — the art pipeline came first
      (`web3d/tools/art.py`). The spike (`web3d/src/spike.js`) sets a table
      mid-deal by hand; `?surface=paper|sky|sage`, `?shadow=pcf|vsm`,
      `?ink=<px>`, `?eye=x,y,z&at=x,y,z&fov=deg` and `?angles` vary it.
      Camera settled at eye (0, 55, 60) looking at the table's centre; your
      opponent's hand is held **upright** (aimed at their own eye, it was
      edge-on to you). Provisional defaults, awaiting Andrew: **sky**
      surface, **VSM** shadows, 2.5 px ink.
- [ ] **P3 — Card art, both ways.** Build **raster (WebP) and vector (SVG,
      rasterised at load)** behind a build flag (§3.2), take the listed
      measurements, and show Andrew the two side by side — size, load time,
      a close-up — for him to choose. Card geometry with three material
      groups and UVs (faces upright, the back not mirrored) and
      `outlineNormal`. *Accept*: every card renders the right face, upright,
      with the back on the reverse, in both variants; the comparison is in
      front of Andrew; his choice recorded here.
      *Built, awaiting his choice.* `python3 web3d/build.py --art svg` writes
      `web3d/piquet3d-svg.html` (not committed); raster stays the default.
      Measurements in §3.2. His machine's load time is still to be taken:
      open each page and read `piquet3d.art().readyMs` in the console.
- [x] **P4 — Motion library (node-tested).** `easing.js`, `kinematics.js`,
      `timeline.js` with the invariants in §11. *Accept*: tests green; a
      demo page shows each primitive.
      *Landed*: 38 node tests, mutation-checked (a flip that swings down, a
      flip on one pivot, a lay-down that skids in: each caught). Two pieces
      of physics changed the design. **A card rolls over its thickness**:
      flipped about one bottom edge it would finish sunk a thickness into
      the table, so the flip pivots on one corner of its edge until upright
      and on the other as it falls. **A flip crests without stopping**: the
      first version decelerated to a dead stop upright and hung there for a
      seventh of a second; now both halves are evenly accelerated
      (`evenly(startSlope)`, of which friction and gravity are the two ends),
      slowest at the crest at 30% of the rising speed, and continuous across
      it. The M3 curves and durations are the tokens @material/web ships.
      `deck.js` makes the card meshes and assigns faces; `?demo` loops every
      primitive (`&slow=3`), and `piquet3d.demoAt(t)` freezes them for
      filmstrips — the way to check motion from a headless browser.
- [x] **P5 — Layout (node-tested).** `layout.js` from protocol states, with
      the anonymity test. *Accept*: every zone right for scripted states
      across a partie; no hidden face ever assigned.
      *Landed*: `layout(state, view)` → 32 slots `{ zone, index, code,
      pose }`, tested over every state of four real parties played through
      the wasm by a scripted human (`test/partie.js`): the count, each
      zone's count, anonymity, which way every card faces, no two resting
      cards interpenetrating (a separating-axis test on their footprints),
      nothing below the table, the hand's order, lifting. Mutation-checked:
      leaking `talon_seen` into the talon and flattening the piles are both
      caught. Two decisions: **rows are shingled**, as cards spread on a
      table are — each rests on the one before, tilted ~2° to clear it —
      so a row of 24 won cards stays on the table instead of climbing a
      centimetre; and **the cut is a ribbon spread** across the table rather
      than a squared pack whose edge you hover (§7.3): 32 targets 1.45 cm
      wide instead of one edge 1.3 cm tall. `talon_seen` cards that younger
      takes are *known* but held backs-to-you, so they stay faceless — the
      rule is simply "nothing in their hand, the talon or their discards
      has a face". Zone positions live in `units.js`. The page now shows
      the real game at rest (`?spike` keeps the hand-set table).
- [x] **P6 — Choreography (node-tested).** Each event kind animated and
      ending at the layout; speed setting; skip-to-end. *Accept*: a scripted
      partie animates end to end with every step ending at its layout.
      *Landed*: `choreography.js` — a reducer replays the events between two
      states into the intermediate states the engine never shows (you
      played, they followed, they took it, they led), and `layout` gives
      each one, so every stage runs between two true layouts; a final
      settle lands exactly on `layout(next)`, and an undo or anything
      unfollowable is one direct transition. `director.js` runs it on the
      page: the timeline, faces turned as motions begin and land, rendering
      only while something moves, `?manual` for hand-driven stills.
      Tested over every step of five parties: the reducer rebuilds each
      state exactly; every card lands on its slot; **no motion starts
      anywhere but where its card is**; no card is in two motions at once;
      no face appears that the destination does not allow; nothing dips
      below the table mid-flight. Mutation-checked (a teleporting slide, a
      frozen face). The browser test plays a whole partie through it.
      Found by the tests, all physical: **a card must never spin while
      tilted** — sliding off the shingled spread with a half turn dipped a
      corner half a millimetre into the table — so a flip's edge is chosen
      to leave a face-down card the standard way (a short edge reverses
      its top, a long one keeps it); **a pile about to be turned must be
      squared exactly**, or corners proud of the hinge dip as it stands;
      **won tricks keep each card as it was played** (yours upright to
      you, theirs to them), as a gathered trick does; and **a squared row
      turns over as one rigid block** (`flipPile`), rolling over its own
      height. The timeline finishes each motion before the next starts, so
      a card hidden as it lands and shown as it rises ends up shown.
      The ceremony, filmed: the cut (cards slide out face down and roll
      over on the table, a beat to read them), the gather, the deal in
      pairs, the pick-up; a trick (laid down, a pause, the answer, a beat,
      swept to the winner). Timings in `TIMING`; the cut-to-first-hand
      ceremony is about 7 s, most of it the deal — a speed setting and
      skip-on-click are P7's.
- [x] **P7 — Interaction and the overlay.** Raycasting, hover, select, play;
      the M3 overlay: prompt, top bar, **score tab** (§9), narration, settings,
      credits; keyboard; hints as cyan ink. *Accept*: a human can play a whole
      partie with the mouse; the score tab tracks every stage live.
      *Landed*: `overlay.js` (Material Web: buttons, switches, selects,
      dialogs; icons are simple strokes drawn for the page, so no icon font),
      `main.js` as the app (preferences, aids and the game kept in
      `localStorage` and resumed by replay, as on the 2D page), and the
      director's **decoration**: a card pointed at rises and takes a heavier
      line, hinted cards a cyan one, cards chosen to throw an amber one and
      stand clear of the hand, cards that may not be played are dimmed; the
      cut's spread lifts the packet you would take. A click while cards move
      finishes the move (Space too). Colours: `web3d/tools/scheme.mjs`
      generates the M3 scheme from one seed (#2f5da8) with Google's
      Material Color Utilities, used at build time only, plus harmonised
      amber and teal for you and your opponent. Material Web + Lit weigh
      197 KB. Layout lessons: the prompt sits beside the hand, sized from the
      window (`(100vw − 76vh) / 2` is what the fan leaves), and the won-trick
      rows moved toward the middle so the tab never covers them (Law 60 —
      examinable at any time). Two bugs found on the way: the tab called the
      stage being declared "done", and **`pointer-events: none` on the
      overlay is inherited**, which left every button in the settings dialog
      unclickable until the browser test tried to press "Done".
- [x] **P8 — The whole game, tested in a browser.** The Playwright suite in
      §11, offline; phone layout. *Accept*: green, no console errors,
      screenshots reviewed.
      *Landed*: `web3d/test/browser.py` plays **a whole partie by clicking**
      — the spread to cut, cards by their on-screen position
      (`piquet3d.screenPoint`), the Material buttons by name, declarations
      by key — and checks at every step that the tab's figures are the
      engine's; that an illegal card is refused on screen in the engine's
      words; undo (U), hints (H), the settings dialog, a reload resuming
      exactly; the motion demo; a phone; no network request of any kind;
      no console error. About four minutes on the VM. **The phone got a
      layout of its own**: below an aspect of 0.85 the table uses
      `ZONES_PORTRAIT` — zones stacked down the table, not spread across
      it — under `CAMERA_PORTRAIT`, and turning the phone re-lays the
      table; every layout and choreography invariant is tested on both
      arrangements. On a phone the running score is a chip in the top bar
      that opens the tab, and the opponent and New partie live in
      settings. A landscape window narrower than 16:10 widens the view to
      keep the table's width. Three things only a real browser showed:
      the soft shadows' cost (§8.3); the dialog's buttons made unclickable
      by an inherited `pointer-events: none`; and headless Chromium
      painting the prompt card's background over the opponent's hand when
      the card was a scroll container — found by elimination, fixed by not
      making it one. Whether real phones share that last one is unknown
      and does not matter now.
- [x] **P9 — Polish.** Idle sway, reduced motion, render on demand, DPR,
      the cut ceremony's details, the talon crossed five-over-three, README
      and PROTOCOL notes, `PLAN.md`.
      *Landed*: reduced motion (the system's preference makes cards simply
      arrive, unless the player has chosen a speed); rendering only while
      something moves; ink and textures scaled to the pixel ratio; the
      talon five crossed over three; README and `docs/PROTOCOL.md` ("Animating
      between two states"); cards just drawn stand a little proud of the
      hand until play begins (as the 2D page marks them "new"); a thinking
      bar while the engine decides for your opponent, which runs on the
      page's own thread. **The cut differs from §7.3**: rather than lifting
      two packets to show their bottom cards, the cut cards slide out of the
      spread face down and roll over on the table where both players can
      read them, then roll back — the same information, and every turn of a
      card on the table, as Andrew asked. **Left open, for Andrew**: the
      idle sway would mean rendering every frame forever, the very cost the
      rest of the page avoids (render on demand), so it is not built; it
      could be an opt-in "a living table" setting. And sound — a soft snap
      as a card lands, a whisper as one slides — could be synthesised in
      the page with no files at all, if he wants it.

- [x] **P10 — Andrew's notes from playing it (27 September 2026).** Nine,
      given while he played the first build, all built:
      1. *"sorting your hand should always be an option, with a md3 ...
         Segmented button near the deck (below?)"* — Material Web's
         outlined segmented button (labs), Auto / Suit / Rank /
         Combinations, always under the hand.
      2. *"we speak a LOT in piquet- those things we say during gameplay are
         a part of the game ... a text box ... split into two
         vertically-stacked halves"* — the dialogue box: your opponent's
         words and points above in red, yours below in black, the table's
         between. `talk.js` (node-tested) turns the protocol's events into
         lines, using the books' own replies — *good*, *not good*,
         *equal* — and one line for a card and its point ("Leads A♥ +1").
         What is asked of you is the last line of your half.
      3. *"the hands are sort of tilted away from the player at ~75
         degrees. the shadows should reflect that"* — both hands at 75° to
         the table (a phone's overhead eye keeps yours at 50°); the light
         rebalanced toward the key, so a shadow is a third darker than the
         table where it had been a fifth, and a card's follows it down.
      4. *"a sharp tug pulling the card from the deck, and then it's placed
         on the table"* — `kinematics.pull`: snapped out along its own
         length, then carried and set down, the beats overlapping.
      5. *"the cards on the table should be placed a little further back"*
         — `staging.test.js` looks through the page's own camera
         (`framing.js`) at five window shapes and fails if any card on the
         table overlaps any held card on screen, every card raised; the
         zones are moved back and in until it passes.
      6. *"hints should work like lists in MD3- with a toggle"* — the hint
         is a fold under the hand that floats up when opened (H too);
         closed by default, remembered.
      7. *"those elements are animated. animate those with a lot of motion
         easing"* — every chevron turns and every fold grows on Material 3
         Expressive's spatial spring (damping 0.8, a point and a half of
         overshoot), sampled into CSS `linear()`; closing uses M3's
         emphasized accelerate, quicker, as M3 has things leave.
      8. *"any information display should be on the left, or top; any area
         with buttons that influence gameplay should be on the
         right/bottom ... right below the deck"* — the score tab, the
         dialogue and what your hand is worth down the left; the prompt's
         buttons, the sort, undo and the hint under the hand; the table
         framed beside the column by a lens shift (`camera.filmOffset`),
         so its perspective does not change. On a phone the column runs
         along the top.
      9. *"how during WNBA broadcasts, 3-pointers have a little on-screen
         animation in the score box ... for special events (not for every
         event)"* — a repique, pique, capot, carte blanche, quatorze,
         sixième or longer, or crossing the rubicon (`talk.flairOf`) sweeps
         a slab in the scorer's colour into their half, with a sheen and
         their figure in the tab popping; the line stays marked. Nothing
         replays on reload; nothing moves under reduced motion.
      One colour per side everywhere now — your opponent red, you black —
      where the tab had used amber and teal.
      **Left for later:** the phone's table wants its own pass: the hand is
      small, the information strip covers the opponent's hand, and the held
      hand's shadow reads as a heavy blob from the overhead eye.

- [x] **P11 — The dialogue box, replaced by a live score (27 September).**
      Seeing the two-halves box, Andrew: *"this box ... is no good. here's
      what i want, ultimately: 1. the immediacy of a WNBA on-screen live
      score display. 2 numbers, one for each team- and when you score,
      there's a minor animation to update the score- unless you score big,
      in which case there's a little celebratory animation ... 2. the table
      above it is still necessary- it's the log of the game."* Built:
      a **score bug** under the stage table (`scorebug.js`, node-tested):
      the partie as it stands this instant (`standing` + `score` — the
      protocol's `partie` counts finished deals only), the deal as the
      period, a thin bar under each number filling toward the rubicon, and
      one caption: the latest thing *said* (cards played and points scored
      are left to the table and the numbers). An ordinary score counts the
      number up, bumps it and floats a "+N" off it; a big one (`flairOf`, or
      crossing the rubicon) sweeps a banner in the scorer's colour across
      the bug, and as it leaves, their number pops and a ring goes out.
      The question put to you moved under your hand, over its buttons.
      `talk.js` stays: it names the moments and writes the caption.

- [x] **P12 — Motion, text layers, the cut, the table tops (27 September).**
      Andrew's next round, all built:
      - *"moving cards should start with strong jerks, then end with
        gravity-like acceleration"* — §7.1's minimum-jerk glide is retired
        for anything thrown. `kinematics.toss` (onto the table: launched at
        speed, an exactly solved parabola, a landing with the speed of the
        fall and a short friction slide) and `kinematics.rise` (into a
        hand: flicked up, slowing under gravity into the grip); the
        choreography's `carry` picks one by where a card is going. Only a
        re-sort within a hand still glides.
      - The cut: *optional* — **Cut for me** where the pointer rests — and
        *"peel the card out of the deck, then flip it up and look at it"*:
        peeled towards its cutter, flicked up and looked at, tossed face up.
      - Your opponent's calls: *"the cards should rise from the deck a
        bit"* — `kinematics.bob`, as many anonymous backs as the call holds
        (`cardsNamed`), so nothing is shown that the words did not say.
      - Text in three kinds — true, prescriptive, hints — the last two each
        a toggle chip under the hand (**Explain**, **Hints**; E and H).
      - The "+N" is a bubble over nothing; the opponent's level lives in
        Settings only (*"unnecessary noise when the game is happening"*).
      - **The table tops** (Andrew's spec, eighteen procedural monochrome
        patterns): `surfaces.js`, one ink over #EDEEF0, a seamless 1024 px
        tile repeating every 48 cm of an unlit table; shadows laid over it
        by a shadow-only sheet. Chosen at random when a partie begins, kept
        with the saved game, pickable in Settings. This settles §12's open
        question on the table's colour: the candidates "paper / sky / sage"
        are gone.

## 14. Notes for the implementer

- Read `docs/PROTOCOL.md` for the state and commands, and `web/src/app.js` for
  a working client: the resume/replay logic, the sort grouping and the pacing
  are worth reusing as-is.
- `web/test/ffi.mjs` and `web/test/browser.py` show how the wasm is driven in
  node and how the page is driven in Chromium on this VM.
- The engine never needs to know the scene exists. If something seems to need
  an engine change, it is probably a protocol addition — make it there, with a
  test, and bump `protocol` if a client would notice.
- `cargo` needs `source ~/.cargo/env`; Playwright is in the project `.venv`;
  shell commands with several steps start with `set -e`.
- **Credit every asset as it arrives.** Andrew: "remember where we get all our
  assets, so we can credit them (now, that includes MD3)". Anything
  third-party — art, fonts, icons, libraries, build tools, design systems —
  gets its entry in `/CREDITS.md` (what, who, URL, version, licence, our
  changes) in the same commit that brings it in; art is pinned with a
  checksum; licences that require it are honoured on the in-game Credits
  screen.
