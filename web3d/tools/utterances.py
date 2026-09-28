#!/usr/bin/env python3
"""Every utterance the table could say, one recording per event -- counted.

    .venv/bin/python web3d/tools/utterances.py [--list FILE]

Andrew (28 September): "make sure you have a full count of *all* utterances.
that means every event each player does, and how they might respond. it
means important state transitions as well (start, win, congrats, oh well
maybe next time, etc). then do another count where numbers are distinct".

Two ways of recording, both "one phrase per event": every utterance a whole
recording, never spliced from parts --

  maximal   an event says its words and its count in one recording, so "Three
            aces and three queens: nine." and "...: twelve." are two files;
  split     the running count is a recording of its own ("Nine."), and
            everything else is whole.

Derived from the rules, not sampled: every sequence and set a 12-card hand
can hold, every point value, every count a deal can reach. Where a count
depends on what came before in the deal, the preceding totals are the ones
the rules allow, ignoring whether the same twelve cards could make both --
so the maximal count is an upper bound, and says so. docs/VOICE.md §8 has
the numbers and the prices.
"""

import argparse
import itertools
import sys
from functools import lru_cache

from voice import HIGHEST_COUNT, SEQUENCES, words

RANKS = ["seven", "eight", "nine", "ten", "knave", "queen", "king", "ace"]
PIPS = [7, 8, 9, 10, 10, 10, 10, 11]  # a point's value, card by card
SET_RANKS = ["ten", "knave", "queen", "king", "ace"]  # index 3.. of RANKS
PLURAL = {"ace": "aces", "king": "kings", "queen": "queens", "knave": "knaves", "ten": "tens"}
HAND = 12

# ---- what can be held ------------------------------------------------------------


def sequence_score(length):
    """Cavendish: a tierce 3, a quart 4, a quint 15, and a point more a card."""
    return length if length < 5 else length + 10


@lru_cache(maxsize=None)
def runs_in(mask):
    """The sequences (length, top) one suit's cards make: maximal runs of three
    or more."""
    out, run = [], 0
    for rank in range(8):
        if mask >> rank & 1:
            run += 1
        else:
            if run >= 3:
                out.append((run, rank - 1))
            run = 0
    if run >= 3:
        out.append((run, 7))
    return tuple(out)


def sequence_lists():
    """Every set of sequences one hand can hold, as a sorted tuple of
    (length, top): all the sequences in its four suits, within twelve
    cards. The empty list is not a holding."""
    per_suit = {}
    for mask in range(256):
        runs = runs_in(mask)
        cards = sum(length for length, _ in runs)
        # Only the cards the runs need: any others can lie in other suits.
        per_suit.setdefault(runs, cards)
        per_suit[runs] = min(per_suit[runs], cards)
    options = [(runs, cards) for runs, cards in per_suit.items()]
    found = set()
    for combo in itertools.combinations_with_replacement(options, 4):
        if sum(cards for _, cards in combo) > HAND:
            continue
        held = tuple(sorted((r for runs, _ in combo for r in runs), reverse=True))
        if held:
            found.add(held)
    return found


def set_lists():
    """Every set of trios and quatorzes one hand can hold: for each of ten to
    ace, none, three or four, within twelve cards."""
    found = set()
    for counts in itertools.product([0, 3, 4], repeat=len(SET_RANKS)):
        if 0 < sum(counts) <= HAND and any(counts):
            found.add(tuple((c, r) for c, r in sorted(zip(counts, range(5)), reverse=True) if c))
    return found


def point_values(length):
    """Every value a point of this many cards can have."""
    return sorted({sum(c) for c in itertools.combinations(PIPS, length)})


def sequences_said(held):
    names = []
    for length, top in held:
        name = SEQUENCES[length - 3]
        if length == 8:
            names.append(f"a {name}")
        elif top == 7:
            names.append(f"a {name} major")
        elif top == length - 1:
            names.append(f"a {name} minor")
        else:
            names.append(f"a {name} to a {RANKS[top]}")
    return join(names)


def sets_said(held):
    return join([f"{'three' if c == 3 else 'four'} {PLURAL[SET_RANKS[r]]}" for c, r in held])


def join(names):
    text = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return text[0].upper() + text[1:]


def number(n):
    return words(n).capitalize()


# ---- every utterance -------------------------------------------------------------


def utterances():
    """(scenario, role, event, text) for every utterance: scenario "all" for
    the same words every way, else the ways it belongs to -- "maximal",
    "split", "phrases", or several joined by "+"; role "opponent"
    or "player" for lines only one of them says, "either" for the game's own
    lines, which both voices need."""
    out = []

    def add(event, text, role="either", scenario="all"):
        out.append((scenario, role, event, text))

    # The partie begins, the cut, the choice of deal.
    add("the partie begins", "Shall we play? Cut for the deal.", "opponent")
    add("the cut is equal", "The same. Cut again.", "opponent")
    add("you cut higher", "Your choice of deal.", "opponent")
    add("they cut higher", "My choice.", "opponent")
    for role in ("opponent", "player"):
        add("choosing to deal first", "I'll deal first.", role)
        add("letting the other deal first", "You deal first.", role)
    # Each deal: the dealer; the last; an extra deal to break a tie.
    add("a deal begins", "My deal.")
    add("a deal begins", "Your deal.")
    add("the last deal begins", "The last deal.")
    add("an extra deal", "Level. Another deal to settle it.")

    # The exchange (Cavendish p. 57); younger takes as many as she likes.
    for n in range(1, 5):
        add("elder takes fewer than five", f"I only take {words(n)}.")
    add("elder takes all five", "I take five.")
    for n in range(1, 9):
        add("younger takes", f"I take {words(n)}." if n > 1 else "I take one.")
    add("younger takes none", "None for me.")
    add("carte blanche", "I have a carte blanche.")
    add("carte blanche, before the exchange", "Discard for carte blanche.")
    add("carte blanche, as the other", "A carte blanche? Show me.")

    # The point: length, the question, the value, the answer.
    for n in range(1, 9):
        add("point: elder calls its length", "One card." if n == 1 else f"{number(n)} cards.")
    add("point: younger asks its value", "What do they make?")
    values = sorted({v for n in range(1, 9) for v in point_values(n)})
    for v in values:
        add("point: elder gives its value", f"{number(v)}.")
    # Sequences: the shape, how high, the top.
    for length, name in enumerate(SEQUENCES, start=3):
        add("sequence: elder calls its length", f"A {name}.")
    add("sequence: younger asks how high", "How high?")
    for top in RANKS[2:]:
        add("sequence: elder gives its top", f"To the {top}.")
    # Sets: the shape, of what, the rank.
    add("sets: elder calls a trio", "A trio.")
    add("sets: elder calls a quatorze", "A quatorze.")
    add("sets: younger asks of what", "Of what?")
    for rank in SET_RANKS:
        add("sets: elder gives the rank", f"Of {PLURAL[rank]}.")
    for category in ("point", "sequence", "sets"):
        add("nothing to call", f"No {category}." if category != "sets" else "No sets.")
    for answer in ("Good.", "Not good.", "Equal."):
        add("younger answers", answer)

    # Reckoning. Younger names what she won once elder has led (Cavendish p.
    # 77); elder reckons as he scores. Split: the holdings whole, the count
    # apart. Maximal: the holdings and the count in one.
    seqs, sets = sequence_lists(), set_lists()
    for held in seqs:
        add("reckoning sequences", f"{sequences_said(held)}.", scenario="split")
    for held in sets:
        add("reckoning sets", f"{sets_said(held)}.", scenario="split")
    for n in range(1, 9):
        add("reckoning a point", "One card." if n == 1 else f"A point of {words(n)}.", scenario="split+phrases")
    # Phrases: each holding its own recording, said one after another --
    # "A quart to a king." "Three aces." -- as Cavendish reckons them.
    for held in {(r,) for h in seqs for r in h}:
        add("reckoning sequences", f"{sequences_said(held)}.", scenario="phrases")
    for held in {(r,) for h in sets for r in h}:
        add("reckoning sets", f"{sets_said(held)}.", scenario="phrases")
    # Maximal: each list with every count it could bring you to. Younger has
    # scored at most a carte blanche and a point before her sequences, and at
    # most those and her sequences before her sets.
    seq_totals = sorted({sum(sequence_score(length) for length, _ in held) for held in seqs})
    before_seq = sorted({cb + p for cb in (0, 10) for p in [0, *range(1, 9)]})
    before_sets = sorted({b + s for b in before_seq for s in [0, *seq_totals]})
    for held in seqs:
        score = sum(sequence_score(length) for length, _ in held)
        for b in before_seq:
            if b + score <= HIGHEST_COUNT:
                add("reckoning sequences", f"{sequences_said(held)}: {words(b + score)}.", scenario="maximal")
    for held in sets:
        score = sum(3 if c == 3 else 14 for c, _ in held)
        for b in before_sets:
            if b + score <= HIGHEST_COUNT:
                add("reckoning sets", f"{sets_said(held)}: {words(b + score)}.", scenario="maximal")
    for n in range(1, 9):
        for cb in (0, 10):
            said = "One card" if n == 1 else f"A point of {words(n)}"
            add("reckoning a point", f"{said}: {words(n + cb)}.", scenario="maximal")

    # Counting aloud, and the deal's great moments.
    for n in range(1, HIGHEST_COUNT + 1):
        add("counting aloud", f"{number(n)}.")
    for big, lo, hi in (("Pique", 60, 99), ("Repique", 90, HIGHEST_COUNT)):
        add(big.lower(), f"{big}!", scenario="split+phrases")
        for n in range(lo, hi + 1):
            add(big.lower(), f"{big}: {words(n)}!", scenario="maximal")
    add("the cards", "And the cards.", scenario="split+phrases")
    add("capot", "Capot!", scenario="split+phrases")
    for n in range(11, HIGHEST_COUNT + 1):
        add("the cards", f"And the cards: {words(n)}.", scenario="maximal")
    for n in range(41, HIGHEST_COUNT + 1):
        add("capot", f"Capot: {words(n)}!", scenario="maximal")
    add("the last trick", "And the last.", scenario="split+phrases")
    for n in range(1, HIGHEST_COUNT + 1):
        add("the last trick", f"And the last: {words(n)}.", scenario="maximal")
    add("carte blanche scored", "Ten for carte blanche.")

    # The partie's moments, and its end.
    add("crossing the rubicon", "Over the rubicon.")
    add("they cross the rubicon", "You're over the rubicon.", "opponent")
    add("a deal won handsomely", "Well played.", "opponent")
    add("a deal lost heavily", "Oh well. Maybe next deal.", "player")
    add("you win the partie", "Congratulations! Well played.", "opponent")
    add("you win, and rubicon them", "Congratulations! You've rubiconed me.", "opponent")
    add("they win the partie", "Good game.", "opponent")
    add("they win, and rubicon you", "Oh well. Maybe next time.", "opponent")
    add("a drawn partie", "A drawn partie. Well played.", "opponent")
    add("another partie", "Another partie?", "opponent")
    for text in ("Good game.", "Thank you for the game.", "Well played.", "Oh well. Maybe next time."):
        add("the partie ends", text, "player")
    add("thinking", "Hmm.", "opponent")
    add("thinking", "Let me see.", "opponent")
    add("thinking", "One moment.", "opponent")
    return out


SCENARIOS = {
    "maximal": "one recording per event, its count fused in",
    "split": "one recording per event, the count apart",
    "phrases": "each holding and each count its own recording",
}
MS_A_CHARACTER = 78  # measured on the Piper recordings, trimmed (docs/VOICE.md §8)


def belongs(scenario, tag):
    return tag == "all" or scenario in tag.split("+")


def tally():
    """For each scenario and voice: the utterances, their characters, and
    about how many seconds of speech they make."""
    all_ = utterances()
    out = {}
    for scenario in SCENARIOS:
        for voice in ("opponent", "player"):
            said = {u[3] for u in all_ if belongs(scenario, u[0]) and u[1] in ("either", voice)}
            chars = sum(len(t) for t in said)
            out[scenario, voice] = (len(said), chars, chars * MS_A_CHARACTER / 1000)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--list", help="write every utterance, tab-separated, here")
    args = parser.parse_args()
    counts = tally()
    for (scenario, voice), (n, chars, secs) in counts.items():
        print(f"{scenario:8} {voice:9} {n:6,} utterances {chars:10,} characters {secs / 60:7.0f} min")
    print()
    for scenario in SCENARIOS:
        files = sum(counts[scenario, v][0] for v in ("opponent", "player"))
        secs = sum(counts[scenario, v][2] for v in ("opponent", "player"))
        sizes = ", ".join(f"{kbps} kb/s {(secs * kbps / 8 + files * 0.3) / 1000:6.1f} MB" for kbps in (16, 24, 32, 48))
        print(f"{scenario:8} both voices, {files:,} files, {secs / 3600:4.1f} h: {sizes}")
    if args.list:
        with open(args.list, "w") as out:
            for scenario, role, event, text in sorted(set(utterances())):
                out.write(f"{scenario}\t{role}\t{event}\t{text}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
