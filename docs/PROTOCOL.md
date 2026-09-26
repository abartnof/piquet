# The table protocol

How a client plays Piquet against the engine. The browser page in `web/` is one
such client and deliberately a disposable one; anything that replaces it — a
three-dimensional table, a native app, a bot harness — talks to the engine in
exactly this way and needs no game logic of its own.

The engine side is `piquet_core::table` (the session: a partie advanced one
human decision at a time) and `crates/piquet-wasm` (the same thing as JSON and
one-line commands). A native Rust client can use `Table` directly and skip the
JSON; the shapes are the same.

## The loop

```
start(level, seed)        -> state
loop:
    read state.prompt     -- what the human must decide now
    draw state            -- hand, table, scores, narration
    send(command)         -> accepted? ; state again
```

The engine runs the opponent between human decisions, so after any accepted
command the state is already at the human's next decision. Nothing happens
while the client waits.

The same `level` and `seed` always produce the same partie — the same packs,
the same opponent, the same style — and so do the terminal (`piquet --level L
--seed S`) and every build of the engine, native or WebAssembly (checked byte
for byte by `web/test/ffi.mjs`). A seed plus the list of accepted commands is
therefore a complete record of a game: that is what the page's "Copy game
record" produces, and replaying it reproduces the game exactly.

## Commands

| Command | When | Meaning |
|---|---|---|
| `exchange 7C 8C KC` | `prompt.kind == "exchange"` | Throw these cards (1 to `prompt.limit`) and draw as many from the talon |
| `declare N` | `prompt.kind == "declare"` | Choose option `N` (0-based) of `prompt.options` |
| `play KS` | `prompt.kind == "play"` | Lead or follow with this card |
| `next` | `prompt.kind == "next_deal"` | Deal the next hand |

Cards are written as two characters, rank then suit: `7 8 9 T J Q K A` and
`C D H S`. A command the rules forbid — a card not held, a card that fails to
follow suit, too many discards, the wrong command for the prompt — is refused:
the table is left exactly as it was and `state.error` says why, in words fit to
show a player ("you must follow hearts while you can"). The next accepted
command clears it.

A client may send a move it suspects is illegal and show the refusal. The page
does exactly that for a card that does not follow suit, because the engine's
reason is the lesson.

## The state

Everything in it is derived from the human's own view of the deal, so a client
cannot show more than the human could know, however it is written. The
protocol test walks every string in the state, narration included, and fails
if one names a card the opponent is still holding.

```jsonc
{
  "protocol": 1,                 // bumped when the shape changes
  "seed": 42, "level": 3,
  "opponent": { "name": "Cavendish", "gloss": "remembers what has been played" },

  "deal": 2,                     // the deal on the table, from 1
  "you_are": "elder",            // or "younger"; alternates every deal
  "phase": "play",               // elder_exchange, younger_exchange,
                                 // declare_point, declare_sequences,
                                 // declare_sets, play, complete
  "standing": { "you": 11, "them": 24, "deals_left": 5 },  // when this deal began
  "rubicon": { "permille": 800, "words": "about 4 in 5" }, // your chance of
                                 // reaching 100; null in the first deal

  "hand": ["AS", "KS", "9H"],    // yours, spades-hearts-diamonds-clubs, high first
  "worth": ["point of 4 (40) in spades", "trio of aces"],  // what it could call
  "discards": ["7C"],            // yours
  "talon_seen": ["8D"],          // talon cards you have legitimately looked at
  "talon_remaining": 3,

  "trick": { "leader": "them", "led": "QH", "followed": null },  // in progress, or null
  "last_trick": { "leader": "you", "led": "AS", "followed": "7S", "winner": "you" },
  "tricks": { "you": 3, "them": 2 },
  "score": { "you": 12, "them": 7 },  // this deal so far

  "prompt": { ... },             // see below
  "events": [ ... ],             // see below
  "deals": [ { "number": 1, "you": 11, "them": 24 } ],  // finished deals
  "partie": { "you": 11, "them": 24 },                  // running totals
  "settlement": null,            // when over: { "winner": "you"|"them"|null,
                                 //   "points": 351, "rubicon": true }
  "error": null                  // why the last command was refused
}
```

`"you"` and `"them"` are used throughout rather than seats, because the seats
swap every deal and a player thinks of themselves, not of elder.

### Prompts

```jsonc
{ "kind": "exchange", "limit": 5 }
{ "kind": "declare", "category": "point",          // point, sequences, sets
  "answering": "point of 5",                        // what elder just called, or null
  "options": [ { "text": "point of 6 (56)", "score": 6, "full": true },
               { "text": "nothing", "score": 0, "full": false },
               { "text": "point of 5 (46)", "score": 5, "full": false } ] }
{ "kind": "play", "legal": ["QH", "9H"] }
{ "kind": "next_deal" }
{ "kind": "over" }
```

A declaration's first option is the full call; then saying nothing; then
calling one step short, which is how the rules let a player *sink* part of a
holding. A category with nothing to call is never put to the human — the table
calls it for them and says so in the narration.

### Events

The narration, oldest first, for the whole partie. Every event has `kind`,
`deal` (the deal it belongs to) and `text` (one sentence, ready to print), plus
fields by kind for a client that wants to animate rather than print:

| kind | fields |
|---|---|
| `deal_begins` | `elder`, `you_total`, `them_total`, `rubicon_permille` |
| `exchanged` | `who`, `count` |
| `drew` | `discarded`, `drew` (yours only) |
| `called` | `who`, `category`, `said` — what was said aloud, never a suit |
| `decided` | `category`, `winner` (`null` if equal) |
| `showed` | `who`, `what` — a combination the opponent had to expose |
| `scored` | `who`, `amount`, `what` |
| `nothing_to_call` | `category` |
| `played` | `who`, `card` |
| `took_trick` | `who`, `number` |
| `deal_ends` | `you`, `them` |
| `partie_ends` | `you`, `them` |

Younger's calls, showings and scores appear only once elder has led to the
first trick, because that is when she makes them.

## WebAssembly

The module has no imports and exports four functions and its memory:

| Export | |
|---|---|
| `piquet_new(level: u32, seed: u32)` | sit down at a new table |
| `piquet_alloc(len: usize) -> *mut u8` | a buffer to write a command into |
| `piquet_send(len: usize) -> u32` | carry out the command just written; 1 if accepted |
| `piquet_state() -> *const u8`, `piquet_state_len() -> usize` | the state, as UTF-8 JSON |

```js
const { instance } = await WebAssembly.instantiate(bytes, {});
const ex = instance.exports;
ex.piquet_new(3, 42);
const state = () => JSON.parse(new TextDecoder().decode(
  new Uint8Array(ex.memory.buffer, ex.piquet_state(), ex.piquet_state_len())));
const send = (command) => {
  const b = new TextEncoder().encode(command);
  const at = ex.piquet_alloc(b.length);
  new Uint8Array(ex.memory.buffer, at, b.length).set(b);
  return ex.piquet_send(b.length) === 1;
};
```

Read `memory.buffer` afresh after every call: the module may grow its memory,
which detaches any view taken before.
