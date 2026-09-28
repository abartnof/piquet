#!/usr/bin/env python3
"""The voice: every phrase said aloud at the table, spoken and encoded.

    .venv/bin/python web3d/tools/voice.py [--voices cori,norman] [--only ID,ID]
    .venv/bin/python web3d/tools/voice.py --doc      # rewrite docs/PHRASES.md

Andrew: "we'll do maximal speaking (anything a human would say, we'll say)",
and then: "i don't want *any* sounds to be repetitive". So the bank is of
*groups* -- each a moment at the table, "Good." or a count of forty-eight --
and each group is said in several ways, which the page picks among without
repeating itself. The wordings come from the period books (Cavendish 1885,
Cady 1896, Foster), with a few of the table's own; numbers are the same words
in several takes, which Piper speaks differently every time. How many ways
a group has follows how often it is heard in a partie.

The bank is pure, and tested (test_voice.py); only `main` needs Piper,
espeak-ng and ffmpeg. docs/VOICE.md holds the reasoning and the
pronunciation table; docs/PHRASES.md, generated from here, every phrase.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web3d" / "audio"
MODELS = Path.home() / "piper-voices"

# The free voices, chosen for their licences and their lineage (docs/VOICE.md):
# both trained from scratch, by Bryce Beattie, on public-domain LibriVox
# recordings. Most other Piper voices are fine-tuned from "lessac", whose
# Blizzard 2013 data is licensed for research only, with no redistribution --
# so none of those ship. There is no clean British male voice: Norman is
# American.
VOICES = {
    "cori": {"model": "en_GB-cori-high", "gender": "female", "licence": "public domain (LibriVox), trained from scratch"},
    "norman": {"model": "en_US-norman-medium", "gender": "male", "licence": "public domain (LibriVox), trained from scratch"},
}

# ---- pronunciation ------------------------------------------------------------
#
# What an English voice would get wrong, respelled as English it already
# knows. The first build fed these to Piper as raw espeak phonemes, checked
# only by reading them; the male voice babbled on "capot" ("kind of
# spastic ... a 'ne ne ne' sound" -- Andrew, who heard it and checked it),
# since a model can list a phoneme it was never trained to say. Respelt,
# each voice says them through its own trained path, in its own accent
# (Andrew: "an obvious way is to use english homonyms, no?"). Targets and
# sources are in docs/VOICE.md; each respelling was checked by reading
# `espeak-ng -v en --ipa`, and en-gb and en-us.
RESPELL = {
    "quart": "cart",  # kɑːt; kɑːɹt in America
    "quatorze": "kuh-torz",  # kʌtɔːz
    "capot": "kuh-pot",  # kʌ pɒt; kʌ pɑːt in America
    "sixième": "seez yem",  # siːz jɛm
    "septième": "set yem",  # sɛt jɛm
    "huitième": "wheat yem",  # wiːt jɛm
    "piquet": "pick-ett",  # pɪkɛt
}


def speakable(text):
    """The phrase as the voice is given it: the French words respelt."""
    def swap(match):
        word = match.group(0)
        said = RESPELL.get(word.lower())
        if said is None:
            return word
        return said.capitalize() if word[0].isupper() else said
    return re.sub(r"[A-Za-zÀ-ÿ]+", swap, text)


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
# was right). Counting aloud needs every number up to it.
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
    "A": "Andrew",
    "T": "the table's own",
}

# Numbers are the same words in several takes, a little faster or slower,
# and Piper renders each differently anyway. A count up to forty is heard a
# few times a partie; a larger one hardly ever.
PACES = [1.0, 0.93, 1.08]


def takes_of_number(n):
    return 3 if n <= 40 else 2


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
    for n in range(3, 9):
        ways = [(f"{words(n).capitalize()} cards.", "C"), (f"Point of {words(n)}.", "P"),
                (f"I have {words(n)} cards.", "T"), (f"A point of {words(n)}.", "P")]
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

    # Niceties (Andrew: "include a few niceties (eg, 'Congratulations!' if
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
    """Every recording: key -> the words, and the pace they are said at."""
    out = {}
    for gid, ways in phrase_groups():
        for k, (text, _) in enumerate(ways):
            out[f"{gid}.{k}"] = {"text": text, "pace": 1.0}
    for n in range(1, HIGHEST_COUNT + 1):
        for k in range(takes_of_number(n)):
            out[f"n-{n}.{k}"] = {"text": f"{words(n).capitalize()}.", "pace": PACES[k]}
    # Cavendish: "Forty-nine," or "Making nine" -- the point's value by what
    # it makes over forty. Both his example and Cady's are in the forties, so
    # only the forties are said this way.
    for units in range(1, 10):
        for k in range(2):
            out[f"making-{units}.{k}"] = {"text": f"Making {words(units)}.", "pace": PACES[k]}
    return out


def groups():
    """Every group the page can ask for: id -> the recordings it picks among."""
    everything = files()
    out = {}
    for gid, ways in phrase_groups():
        out[gid] = [f"{gid}.{k}" for k in range(len(ways))]
    for n in range(1, HIGHEST_COUNT + 1):
        out[f"n-{n}"] = [f"n-{n}.{k}" for k in range(takes_of_number(n))]
    # The point's value, answering "What do they make?": the number, or in
    # the forties what it is making. The same recordings, grouped again.
    for value in range(24, 76):
        keys = list(out[f"n-{value}"])
        if 41 <= value <= 49:
            keys += [f"making-{value - 40}.{k}" for k in range(2)]
        out[f"value-{value}"] = keys
    assert all(key in everything for keys in out.values() for key in keys)
    return out


def document():
    """docs/PHRASES.md: every phrase the table says, written down (Andrew:
    "remember to write these phrases down somewhere local as well")."""
    lines = [
        "# What the table says",
        "",
        "Every phrase the voice says, each in the ways it is said -- so that",
        "nothing is heard the same way twice running (Andrew: \"i don't want",
        "*any* sounds to be repetitive\"). Generated from the bank in",
        "`web3d/tools/voice.py` by `voice.py --doc`; edit the bank, not this",
        "file. The reasoning, the pronunciation and the sizes are in",
        "`docs/VOICE.md`.",
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
    counts = sum(takes_of_number(n) for n in range(1, HIGHEST_COUNT + 1))
    lines += [
        "",
        "## Numbers",
        "",
        f"Every number from one to {words(HIGHEST_COUNT)} (`n-1` ... `n-{HIGHEST_COUNT}`), for counting",
        "aloud and for a point's value: the same words in several takes, at",
        f"paces {', '.join(str(p) for p in PACES)} -- three takes up to forty, heard a few",
        f"times a partie, and two above ({counts} recordings).",
        "",
        "A point's value, answering \"What do they make?\" (`value-24` ...",
        "`value-75`), is the number -- or, in the forties, what it is making,",
        "as Cavendish has it (\"Forty-nine,\" or \"Making nine\") and Cady",
        "(\"Forty-seven,\" or \"Making seven\"): *Making one* ... *Making nine*,",
        "two takes each.",
        "",
    ]
    return "\n".join(lines)


# ---- speaking and encoding --------------------------------------------------------

DOC = ROOT / "docs" / "PHRASES.md"

# Opus at 12 kb/s: wideband speech still, and about two thirds the size of
# the 20 kb/s the voice first shipped at -- which is what pays for saying
# everything several ways (Andrew: "7mb is fine").
BITRATE = "12k"


def speak(voice, text, wav_path, pace=1.0):
    from piper import SynthesisConfig

    with wave.open(str(wav_path), "wb") as wav:
        voice.synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=pace))


def encode(wav_path, out_path, kind, bitrate=BITRATE):
    """Trim the silence either end, then encode small: speech needs far
    less than music."""
    trim = "silenceremove=start_periods=1:start_threshold=-50dB:stop_periods=-1:stop_threshold=-50dB:stop_duration=0.15"
    codec = {
        "mp3": ["-ac", "1", "-ar", "22050", "-codec:a", "libmp3lame", "-b:a", "32k"],
        "opus": ["-ac", "1", "-codec:a", "libopus", "-b:a", bitrate, "-application", "voip"],
    }[kind]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav_path), "-af", trim, *codec, str(out_path)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--voices", default=",".join(VOICES))
    parser.add_argument("--only", default="", help="groups to re-record, comma-separated")
    parser.add_argument("--format", default="opus", choices=["mp3", "opus"])
    parser.add_argument("--bitrate", default=BITRATE, help="Opus bitrate, e.g. 12k")
    parser.add_argument("--doc", action="store_true", help="only rewrite docs/PHRASES.md")
    args = parser.parse_args()
    DOC.write_text(document())
    if args.doc:
        print(f"wrote {DOC.relative_to(ROOT)}")
        return 0
    from piper import PiperVoice  # only here: the bank needs no Piper

    everything, grouped = files(), groups()
    wanted = set(filter(None, args.only.split(",")))
    keys = [k for k in everything if not wanted or k.rsplit(".", 1)[0] in wanted]
    ext = {"mp3": "mp3", "opus": "ogg"}[args.format]
    for name in args.voices.split(","):
        spec = VOICES[name]
        voice = PiperVoice.load(str(MODELS / f"{spec['model']}.onnx"))
        folder = OUT / name
        folder.mkdir(parents=True, exist_ok=True)
        if not wanted:
            for stale in folder.glob(f"*.{ext}"):
                if stale.stem not in everything:
                    stale.unlink()
        seconds = 0.0
        with tempfile.TemporaryDirectory() as tmp:
            for key in keys:
                wav = Path(tmp) / f"{key}.wav"
                speak(voice, speakable(everything[key]["text"]), wav, everything[key]["pace"])
                with wave.open(str(wav)) as w:
                    seconds += w.getnframes() / w.getframerate()
                encode(wav, folder / f"{key}.{ext}", args.format, args.bitrate)
        manifest = {
            "voice": name, **spec, "bitrate": args.bitrate,
            "files": {key: spec_["text"] for key, spec_ in everything.items()},
            "groups": grouped,
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
        total = sum(p.stat().st_size for p in folder.glob(f"*.{ext}"))
        print(f"{name}: {len(keys)} recordings, {seconds:.0f} s of speech before trimming; "
              f"{len(everything)} in all, {total / 1024:.0f} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
