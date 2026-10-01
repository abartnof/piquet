# Piquet

**[Play it in your browser](https://abartnof.github.io/piquet/)**

Piquet is a card game for two players and a 32-card pack. It was France's
national card game from the sixteenth century until it faded after the First
World War, and David Parlett calls it "still one of the most skill-rewarding
card games for two". This is a version you can play against the computer, and
learn as you play.

## Learning the game

- **[pagat.com](https://www.pagat.com/notrump/piquet.html)**: the clearest
  modern rules, and the ones this game follows.
- **[Wikipedia](https://en.wikipedia.org/wiki/Piquet)**: the history and the
  variants.
- **The game's own tutorial**, offered on its welcome screen, introduces each
  phase of play as you reach it.

## How it works

The whole game is one self-contained web page, `web3d/piquet3d.html` (about
3 MB). It needs no installation, no server and no network, so you can also
download it and open it from disk.

You play a partie of six deals against your opponent, settled by the rubicon.
There are five levels of opponent, from one that "plays their highest card and
hopes" to one that "reads the endgame exactly". Explanations, hints and undo
can each be switched on or off.

- **The rules engine** is written in Rust (`crates/piquet-core`) and compiled to
  WebAssembly inside the page. It deals, scores and plays your opponent, whose
  stronger levels work out what they can about your hand from what you declare
  and discard.
- **The table** is drawn with three.js and Material Web (`web3d/`).
- **The engine is checked against an oracle.** The project began in Python
  (`python/`), and that version's answers are kept as golden test vectors
  (`vectors/`) that the Rust engine must reproduce.
- A **terminal version** plays the same game: `cargo run -p piquet-cli`.

To build and test it yourself:

```
python3 web3d/build.py                  # rebuild the page; needs Rust's wasm32 target and `npm ci` in web3d/
cargo test --release                    # the engine
(cd web3d && npm test)                  # the table
(cd python && pytest)                   # the Python oracle
```

`docs/PIQUET.md` has the rules as implemented, with their sources;
`docs/DESIGN.md` explains why the engine is built the way it is;
`docs/TABLE3D.md` covers the table.

## Thanks

- **John McLeod's [pagat.com](https://www.pagat.com/)**, our authority on the
  rules, and **David Parlett**.
- The period writers whose books we read on the
  [Internet Archive](https://archive.org): **Charles Cotton** (1674),
  **Edmond Hoyle** (1744), **Cavendish** (*The Laws of Piquet*),
  **A. Howard Cady** (1896) and **R. F. Foster** (*Foster's Complete Hoyle*,
  1897).
- **AustinGabriel64** for the card faces (CC0) and **Germarquezm** for the card
  back (CC BY-SA 3.0), both from Wikimedia Commons.
- **three.js**, and Google's **Material Design 3**, **Material Web**, **Lit**
  and **Material Symbols**.

`CREDITS.md` lists everything with its licence. `docs/LITERATURE.md` lists
every source we read.

## Licence

© 2026 Andrew Bartnof, under the MIT License (`LICENSE`). Third-party pieces
keep their own licences, listed in `CREDITS.md`.
