#!/usr/bin/env python3
"""The phrase bank: every phrase said at the table, for the declarations'
dialogue boxes.

    python3 web3d/tools/phrases.py     # rewrite docs/PHRASES.md and web3d/words.json

The user: "we'll do maximal speaking (anything a human would say, we'll
say)", and then: "i don't want *any* sounds to be repetitive". So the bank
is of *groups* -- each a moment at the table, "Good." or a count of
forty-eight -- and each phrase is said in several ways, which the page picks
among without repeating itself. The wordings come from the period books
(Cavendish 1885, Cady 1896, Foster), with a few of the table's own.

The bank is pure, and tested (test_phrases.py). The page reads it from
web3d/words.json; docs/PHRASES.md lists every phrase with its source.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


# ---- numbers, said the British way ---------------------------------------------

ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
        "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def words(n):
    """1 to 199 in words: 'forty-eight', 'a hundred and four'."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
    rest = n - 100
    return "a hundred" + (" and " + words(rest) if rest else "")


# The highest a player can count in one deal: 170 (docs/DESIGN.md -- Hoyle
# was right). Counting needs every number up to it.
HIGHEST_COUNT = 170

# ---- the bank ----------------------------------------------------------------------

RANKS = ["seven", "eight", "nine", "ten", "knave", "queen", "king", "ace"]
SEQUENCES = ["tierce", "quart", "quint", "sixième", "septième", "huitième"]
SET_RANKS = ["ace", "king", "queen", "knave", "ten"]  # nines and below do not count
PLURAL = {"ace": "aces", "king": "kings", "queen": "queens", "knave": "knaves", "ten": "tens"}

# Where each wording comes from. "T" marks the table's own: a period formula
# carried to a case the books do not spell out, or plain table talk.
SOURCES = {
    "C": "Cavendish, The Laws of Piquet (1885)",
    "Cy": "A. Howard Cady, Piquet: a Treatise on the Game (1896)",
    "F": "Foster's Complete Hoyle (1897 and later)",
    "P": "pagat.com, the modern names",
    "A": "the user",
    "T": "the table's own",
}

def sequence_calls():
    """Every sequence that can be held, called as Cavendish calls it: "A
    quint major", "A quart to a queen", "A tierce minor"."""
    out = []
    for length, name in enumerate(SEQUENCES, start=3):
        tops = range(len(RANKS) - 1, length - 2, -1)  # ace down to the lowest possible top
        for top in tops:
            if length == 8:
                phrase = f"A {name}"
            elif top == len(RANKS) - 1:
                phrase = f"A {name} major"
            elif top == length - 1:
                phrase = f"A {name} minor"
            else:
                phrase = f"A {name} to a {RANKS[top]}"
            out.append((f"seq-{length}-{RANKS[top]}", phrase))
    return out


def _sequence_groups():
    groups = []
    for gid, call in sequence_calls():
        length, top = gid.split("-")[1:]
        name = SEQUENCES[int(length) - 3]
        if int(length) == 8:
            ways = [(f"{call}.", "C"), (f"{name.capitalize()}!", "T"), (f"{call}, the whole suit.", "T")]
        else:
            bare = call[2:]  # "quint major", "quart to a queen"
            ways = [(f"{call}.", "C"), (f"{bare.capitalize()}.", "P"), (f"I have a {name} to the {top}.", "F")]
        groups.append((gid, ways))
    return groups


def _set_groups():
    groups = []
    for count, word in [(3, "Three"), (4, "Four")]:
        for rank in SET_RANKS:
            plural = PLURAL[rank]
            if count == 3:
                ways = [(f"Three {plural}.", "C"), (f"A trio of {plural}.", "P"), (f"I have three {plural}.", "T")]
            else:
                ways = [(f"Four {plural}.", "C"), (f"Quatorze {plural}.", "F"), (f"I have four {plural}.", "T")]
            groups.append((f"set-{count}-{rank}", ways))
    return groups


def phrase_groups():
    """Every group said in words, each with its wordings and their sources,
    in the order the table meets them."""
    out = []
    add = lambda gid, *ways: out.append((gid, list(ways)))

    # The cut for deal.
    add("cut-again", ("Cut again.", "T"), ("Equal. Cut again.", "T"), ("The same rank. Cut again.", "T"))
    add("your-choice", ("Your choice.", "T"), ("The choice is yours.", "T"), ("You cut higher. Your choice.", "T"))
    add("my-deal", ("My deal.", "T"), ("I'll deal first.", "T"), ("I shall deal.", "T"))
    add("your-deal", ("Your deal.", "T"), ("You deal first.", "T"), ("After you. Your deal.", "T"))

    # The exchange: elder announces only when he leaves some (Cavendish p. 57).
    left = {4: "a card", 3: "two cards", 2: "three cards", 1: "four cards"}
    for n in range(4, 0, -1):
        add(f"take-{n}",
            (f"I only take {words(n)}.", "C"),
            (f"I take only {words(n)}.", "Cy"),
            (f"I leave {left[n]}.", "C" if n == 4 else "T"),
            (f"{words(n).capitalize()} for me.", "T"))
    add("carte-blanche-have",
        ("I have a carte blanche.", "C"),
        ("Carte blanche!", "T"),
        ("Carte blanche. Not a court card among them.", "T"))

    # The point: its length, the question, the answers (pp. 60-61).
    # A point may be called short, down to a single card.
    for n in range(1, 9):
        cards = "One card." if n == 1 else f"{words(n).capitalize()} cards."
        have = "I have one card." if n == 1 else f"I have {words(n)} cards."
        ways = [(cards, "C"), (f"Point of {words(n)}.", "P"), (have, "T"), (f"A point of {words(n)}.", "P")]
        add(f"point-{n}", *(ways if 4 <= n <= 6 else ways[:3]))
    # The shapes called bare -- elder gives no more than he must -- and the
    # questions for the tie-break when younger holds the same shape.
    for length, name in enumerate(SEQUENCES, start=3):
        add(f"seq-{length}",
            (f"A {name}.", "C"),
            (f"{name.capitalize()}.", "T"),
            (f"I have a {name}.", "T"))
    add("set-3", ("A trio.", "P"), ("Trio.", "T"), ("I have a trio.", "T"))
    add("set-4", ("A quatorze.", "F"), ("Quatorze.", "T"), ("I have a quatorze.", "T"))
    add("how-high",
        ("How high?", "T"),
        ("To what card?", "T"),
        ("How high is it?", "T"),
        ("And its top card?", "T"))
    add("what-set",
        ("Of what?", "T"),
        ("Which are they?", "T"),
        ("What are they?", "T"),
        ("And what are they?", "T"))
    add("what-make",
        ("What do they make?", "C"),
        ("How many?", "Cy"),
        ("And what do they make?", "T"),
        ("What do they come to?", "T"),
        ("How much?", "T"))
    add("good",
        ("Good.", "C"),
        ("Good!", "A"),
        ("That's good.", "T"),
        ("Yes, good.", "T"),
        ("Ah, good.", "A"),
        ("Good. Go on.", "T"),
        ("Good, I'm afraid.", "T"),
        ("Very well. Good.", "T"))
    add("not-good",
        ("Not good.", "C"),
        ("Not good!", "A"),
        ("Ah, not good.", "A"),
        ("No, not good.", "T"),
        ("Not good, I'm afraid.", "T"),
        ("I'm afraid that's not good.", "T"))
    add("equal",
        ("Equal.", "C"),
        ("Equal!", "T"),
        ("Ah, equal.", "T"),
        ("That's equal.", "T"),
        ("Equal, as it happens.", "T"))
    add("nothing",
        ("Nothing.", "T"),
        ("Nothing to call.", "T"),
        ("I've nothing.", "T"),
        ("Nothing, I'm afraid.", "T"))

    # Sequences (p. 64), quatorzes and trios (p. 67).
    out.extend(_sequence_groups())
    out.extend(_set_groups())

    # The deal's great moments.
    for big in ("pique", "repique"):
        add(big,
            (f"{big.capitalize()}!", "C"),
            (f"A {big}!", "T"),
            (f"And that's a {big}.", "T"),
            (f"{big.capitalize()}, I'm afraid.", "T"))
    add("capot",
        ("Capot!", "C"),
        ("And capot!", "T"),
        ("Every trick. Capot!", "T"),
        ("Capot, I'm afraid.", "T"))
    add("the-cards",
        ("And the cards.", "C"),
        ("The cards.", "Cy"),
        ("The cards are mine.", "T"),
        ("And ten for the cards.", "T"),
        ("The cards, as well.", "T"))

    # Niceties (the user: "include a few niceties (eg, 'Congratulations!' if
    # you win a game)").
    add("well-played",
        ("Well played.", "T"),
        ("Nicely played.", "T"),
        ("A fine hand.", "T"),
        ("You had the cards for that.", "T"),
        ("Well done.", "T"))
    add("congratulations",
        ("Congratulations!", "A"),
        ("Congratulations. Well played.", "T"),
        ("The partie is yours. Congratulations!", "T"),
        ("Bravo. A fine partie.", "T"))
    add("good-game",
        ("Good game.", "T"),
        ("A good game.", "T"),
        ("Thank you for the game.", "T"),
        ("Well fought, all the same.", "T"))
    return out


def files():
    """Every wording: key -> its words."""
    out = {}
    for gid, ways in phrase_groups():
        for k, (text, _) in enumerate(ways):
            out[f"{gid}.{k}"] = text
    for n in range(1, HIGHEST_COUNT + 1):
        out[f"n-{n}.0"] = f"{words(n).capitalize()}."
    # Cavendish: "Forty-nine," or "Making nine" -- the point's value by what
    # it makes over forty. Both his example and Cady's are in the forties, so
    # only the forties are said this way.
    for units in range(1, 10):
        out[f"making-{units}.0"] = f"Making {words(units)}."
    return out


def groups():
    """Every group the page can ask for: id -> the wordings it picks among."""
    everything = files()
    out = {}
    for gid, ways in phrase_groups():
        out[gid] = [f"{gid}.{k}" for k in range(len(ways))]
    for n in range(1, HIGHEST_COUNT + 1):
        out[f"n-{n}"] = [f"n-{n}.0"]
    # The point's value, answering "What do they make?": the number, or in
    # the forties what it is making. The same wordings, grouped again.
    for value in range(7, 76):
        keys = list(out[f"n-{value}"])
        if 41 <= value <= 49:
            keys.append(f"making-{value - 40}.0")
        out[f"value-{value}"] = keys
    assert all(key in everything for keys in out.values() for key in keys)
    return out


def words_json():
    """The words of every group, for the page's dialogue boxes
    (web3d/words.json): the build embeds it."""
    return json.dumps({"groups": groups(), "texts": files()},
                      ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def document():
    """docs/PHRASES.md: every phrase the table says, written down (the user:
    "remember to write these phrases down somewhere local as well")."""
    lines = [
        "# What the table says",
        "",
        "Every phrase the declarations' dialogue boxes say, each in the ways it",
        "is said -- so that nothing is said the same way twice running.",
        "Generated from the bank in `web3d/tools/phrases.py`; edit the bank,",
        "not this file.",
        "",
        "Sources:",
        "",
        *[f"- **{tag}** -- {name}" for tag, name in SOURCES.items()],
        "",
        "| Group | Said | Source |",
        "|---|---|---|",
    ]
    for gid, ways in phrase_groups():
        for k, (text, source) in enumerate(ways):
            lines.append(f"| {'`' + gid + '`' if k == 0 else ''} | {text} | {source} |")
    lines += [
        "",
        "## Numbers",
        "",
        f"Every number from one to {words(HIGHEST_COUNT)} (`n-1` ... `n-{HIGHEST_COUNT}`), for counting",
        "and for a point's value.",
        "",
        "A point's value, answering \"What do they make?\" (`value-24` ...",
        "`value-75`), is the number -- or, in the forties, what it is making,",
        "as Cavendish has it (\"Forty-nine,\" or \"Making nine\") and Cady",
        "(\"Forty-seven,\" or \"Making seven\"): *Making one* ... *Making nine*.",
        "",
    ]
    return "\n".join(lines)


DOC = ROOT / "docs" / "PHRASES.md"
WORDS = ROOT / "web3d" / "words.json"


def main():
    DOC.write_text(document())
    WORDS.write_text(words_json())
    print(f"wrote {DOC.relative_to(ROOT)} and {WORDS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
