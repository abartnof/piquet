# The table protocol

How a client plays Piquet against the engine. The 3D table in `web3d/` is one
such client and deliberately a disposable one (it replaced a plain 2D page,
`web/`, retired on 1 October 2026); anything that replaces it — a native app,
a bot harness — talks to the engine in exactly this way and needs no game
logic of its own.

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

**Reloading.** `record` is everything taken from the human's seat, with `*`
on what the table did automatically. `replay L S` followed by those entries,
one per line, rebuilds the table in a single pass — automatic moves are
replayed as recorded, so aids switched mid-game never stop a record fitting —
after which the client switches its aids back on with `set`. That is what a
page keeps across a reload, and what "Copy game record" hands over.

The same `level` and `seed` always produce the same partie — the same packs,
the same opponent, the same style — and so do the terminal (`piquet --level L
--seed S`) and every build of the engine, native or WebAssembly (checked byte
for byte: both must end fifteen scripted parties exactly as
`crates/piquet-wasm/tests/dull-parties.txt` records them -- `cargo test` for
the native build, `web3d/test/wasm.test.js` for the WebAssembly one). A seed
plus the list of accepted commands is therefore a complete record of a game:
that is what the page's "Copy game record" produces, and replaying it
reproduces the game exactly.

## Commands

| Command | When | Meaning |
|---|---|---|
| `cut N` | `prompt.kind == "cut"` | Cut for the deal: lift `N` cards (2 to 30, Cavendish Law 3) and show the bottom one |
| `dealer you` / `dealer them` | `prompt.kind == "choose_dealer"` | Having cut higher, choose who deals first |
| `exchange 7C 8C KC` | `prompt.kind == "exchange"` | Throw these cards (1 to `prompt.limit`) and draw as many from the talon |
| `declare N` | `prompt.kind == "declare"` | Choose option `N` (0-based) of `prompt.options` |
| `play KS` | `prompt.kind == "play"` | Lead or follow with this card |
| `next` | `prompt.kind == "next_deal"` | Deal the next hand |
| `undo` | `can_undo` | Take back the last decision, with the opponent's replies and anything the table did automatically after it |
| `set <aid> on` / `off` | any time | Switch an aid: `hints`, `play_forced`, `declare_for_me`, `play_winners` |
| `replay L S` + one record entry per line | any time | Rebuild the table at level `L`, seed `S`, from a `record` — how a client reloads a game |

**Aids** change what the human is asked, never what happens. `play_forced`
plays a card when it is the only legal one; `declare_for_me` calls everything
in every category without asking; `play_winners` plays out a hand of certain
winners — on lead, every card beating everything unaccounted for and every
talon card elder watched younger take; `hints` puts `hint` in the state. A
declaration with nothing to call is never put to the human whatever the aids.
Switching one on takes effect at once — `declare_for_me` at a declaration
prompt makes the call.

**Undo** replays the game from its seed and everything taken from the human's
seat except the last real decision. Automatic moves are recorded as such, so
switching aids mid-game never stops a record fitting. Undoing costs a replay
of the opponent's thinking so far — a second or two late in a level-5 partie.

Cards are written as two characters, rank then suit: `7 8 9 T J Q K A` and
`C D H S`. A command the rules forbid — a card not held, a card that fails to
follow suit, too many discards, the wrong command for the prompt — is refused:
the table is left exactly as it was and `state.error` says why, in words fit to
show a player ("you must follow hearts while you can"). The next accepted
command clears it.

A client may send a move it suspects is illegal and show the refusal. The page
does exactly that for a card that does not follow suit, because the engine's
reason is the lesson.

## The cut for deal

A partie begins with the cut (pagat; Cavendish, Laws 3–4). The ace is high and
suits do not rank; the higher card has the choice of deal, and equal cards are
cut again. Until it is settled, `phase` is `"cut"`, `you_are` is `null` and the
hand is empty: a hand seen before choosing who deals would be a hand chosen.
When the opponent cuts higher it chooses to deal first — the choice the books
advise, since the first dealer is elder in the sixth deal — and when the human
does, the hint says the same. The cut has a generator of its own, so a seed
deals the same packs however it falls.

## The state

Everything in it is derived from the human's own view of the deal, so a client
cannot show more than the human could know, however it is written. The
protocol test walks every string in the state, narration included, and fails
if one names a card the opponent is still holding.

```jsonc
{
  "protocol": 2,                 // bumped when the shape changes
  "seed": 42, "level": 3,
  "opponent": { "level": 3, "skill": "remembers what has been played" },
                                 // never a name: the machine is "your opponent"

  "deal": 2,                     // the deal on the table, from 1
  "you_are": "elder",            // or "younger"; alternates every deal
  "phase": "play",               // elder_exchange, younger_exchange,
                                 // declare_point, declare_sequences,
                                 // declare_sets, play, complete
  "standing": { "you": 11, "them": 24, "deals_left": 5 },  // when this deal began
  "rubicon": { "permille": 800, "words": "about 4 in 5" }, // your chance of
                                 // reaching 100; null in the first deal

  "hand": ["AS", "KS", "9H"],    // yours, spades-hearts-diamonds-clubs, high first
  "worth": [                     // what it could call, holding by holding,
                                 // and what each scores if it is good
    { "text": "point of 4 (40) in spades", "category": "point",
      "cards": ["AS", "KS", "9S", "7S"], "score": 4 },
    { "text": "trio of aces", "category": "sets", "cards": ["AS", "AH", "AC"],
      "score": 3 } ],
  "discards": ["7C"],            // yours
  "talon_seen": ["8D"],          // talon cards you have legitimately looked at
  "talon_remaining": 3,
  "their_discards": 5,           // the size of your opponent's pile, never its cards

  "trick": { "leader": "them", "led": "QH", "followed": null },  // in progress, or null
  "last_trick": { "leader": "you", "led": "AS", "followed": "7S", "winner": "you" },
  "tricks_played": [ ... ],      // every trick this deal, in order, same shape: they
                                 // lie face up and either player may look at them
  "tricks": { "you": 3, "them": 2 },
  "score": { "you": 12, "them": 7 },  // this deal so far

  "prompt": { ... },             // see below
  "aids": { "hints": false, "play_forced": false, "declare_for_me": false,
            "play_winners": false },
  "can_undo": true,
  "record": ["exchange 7C", "declare 0", "*play 8S", "next"],  // everything taken
                                 // from your seat; * marks what the table did for you
  "hint": null,                  // with hints on: { "text": "Lead K♠.",
                                 //   "command": "play KS", "cards": ["KS"] }
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
{ "kind": "cut", "fewest": 2, "most": 30 }
{ "kind": "choose_dealer" }
{ "kind": "exchange", "limit": 5 }
{ "kind": "declare", "category": "point",          // point, sequences, sets
  "answering": "point of 5",                        // what elder just called, or null
  "options": [ { "text": "point of 6 (56)", "score": 6, "full": true,
                 "cards": ["AH", "KH", "QH", "JH", "9H", "8H"] },
               { "text": "nothing", "score": 0, "full": false, "cards": [] },
               { "text": "point of 5 (46)", "score": 5, "full": false,
                 "cards": ["AH", "KH", "QH", "JH", "9H"] } ] }
{ "kind": "play", "legal": ["QH", "9H"] }
{ "kind": "next_deal" }
{ "kind": "over" }
```

A declaration's first option is the full call; then saying nothing; then
calling one step short, which is how the rules let a player *sink* part of a
holding. Each option names the cards it is made of — what would be laid on the
table if it were shown — so a client can show a claim before it is made. A category with nothing to call is never put to the human — the table
calls it for them and says so in the narration.

### Events

The narration, oldest first, for the whole partie. Every event has `kind`,
`deal` (the deal it belongs to) and `text` (one sentence, ready to print), plus
fields by kind for a client that wants to animate rather than print:

| kind | fields |
|---|---|
| `cut` | `who`, `card` — a card shown in the cut for deal |
| `cut_again` | — the cuts were equal |
| `choice_of_deal` | `who` — cut higher, and chooses |
| `first_dealer` | `chooser`, `dealer` |
| `deal_begins` | `elder`, `you_total`, `them_total`, `rubicon_permille` |
| `exchanged` | `who`, `count` |
| `drew` | `discarded`, `drew` (yours only) |
| `looked` | `who` (you), `cards` — as elder, having taken fewer than five, the rest of your five, which the rules let you look at (yours only) |
| `they_took` | `who` (them), `cards` — of the cards you left, those your opponent drew; they draw yours first, and are holding them (yours only) |
| `called` | `who`, `category`, `said` — what was said aloud, never a suit |
| `decided` | `category`, `winner` (`null` if equal), `asked` (whether elder was asked for the tie-break -- the point's value, a sequence's top card, a set's rank -- which happens only when both hold the same shape) |
| `showed` | `who`, `what` — a combination the opponent had to expose |
| `scored` | `who`, `amount`, `what`, `category` — carte_blanche, point, sequences, sets, play, cards or bonus |
| `nothing_to_call` | `category` |
| `played` | `who`, `card` |
| `took_trick` | `who`, `number` |
| `deal_ends` | `you`, `them` |
| `partie_ends` | `you`, `them` |

Younger's calls, showings and scores appear only once elder has led to the
first trick, because that is when she makes them.

### Animating between two states

One accepted command can carry the table a long way — your card, your
opponent's answer, the trick taken, their next lead; or the cut, the deal and
elder's exchange — and the state shows only where it ended. The events added
since the previous state say what happened, in order, and they are enough to
rebuild every state in between: `played` moves a card from a hand to the
trick, `took_trick` moves the trick to its winner, `drew` names your discards
and your draw, `exchanged` counts your opponent's, `deal_begins` deals.

The 3D table (`web3d/src/choreography.js`) does exactly that: a small reducer
replays the new events from the previous state, lays out each intermediate
state, and animates from one to the next, so every waypoint is a true
position rather than a guess. Two rules make it safe: if the events are not
a continuation of the previous state's — an undo, a new partie — the client
jumps straight to the new state; and whatever the replay produced, it ends by
settling on the state the engine returned, which is the only truth. Any
change to these events' fields is therefore a change a client would notice,
and bumps `protocol`.

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

## Hints

A hint is what the top of the opponent ladder would do in the human's place — the exact solver in the endgame and Hoyle's judgement before
it — computed from the human's own view, so it cannot tell them anything they
could not know. The advisor has its own generator, seeded from where the game
stands: asking twice gives the same answer, and asking at all changes nothing
about the game. `hint.command` is exactly what to send to follow it, and
`hint.cards` is what to point at: the discards, the card, or the cards of the
recommended declaration.
