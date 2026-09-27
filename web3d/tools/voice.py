#!/usr/bin/env python3
"""The voice: every phrase said aloud at the table, spoken and encoded.

    .venv/bin/python web3d/tools/voice.py [--voices cori,north] [--only ID,ID]

Andrew: "we'll do maximal speaking (anything a human would say, we'll say)".
The inventory follows Cavendish, *The Laws of Piquet* (1885) -- how the
point, sequences and sets are called and answered, the running count said
aloud, the exchange's announcements -- plus a few niceties. docs/VOICE.md
holds the reasoning and the pronunciation table this module applies.

Phrases are atoms: a compound call ("A quint major. Three kings.") is its
atoms played in turn, so nothing is recorded twice. The inventory is pure,
and tested (test_voice.py); only `main` needs Piper, espeak-ng and ffmpeg.
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

# The free voices, chosen for their licences (docs/VOICE.md): a female voice
# trained on public-domain LibriVox recordings, and a male one from OpenSLR 83
# (CC BY-SA 4.0).
VOICES = {
    "cori": {"model": "en_GB-cori-high", "gender": "female", "licence": "public domain (LibriVox)"},
    "north": {"model": "en_GB-northern_english_male-medium", "gender": "male", "licence": "CC BY-SA 4.0 (OpenSLR 83)"},
}

# ---- pronunciation ------------------------------------------------------------
#
# What espeak-ng -- and so Piper -- would get wrong, given as exact phonemes
# (Piper reads [[ ... ]] as raw espeak phonemes). Targets and sources are in
# docs/VOICE.md; each was checked by reading `espeak-ng -v en-gb --ipa`.
PRONOUNCE = {
    "quart": "[[kˈɑːt]]",
    "sixième": "[[siːzjˈɛm]]",
    "septième": "[[sɛtjˈɛm]]",
    "huitième": "[[wiːtjˈɛm]]",
    "quatorze": "[[kətˈɔːz]]",
    "capot": "[[kəpˈɒt]]",
    "piquet": "[[pɪkˈɛt]]",
}


def speakable(text):
    """The phrase as the voice is given it: the hard words as phonemes.

    Two things read wrongly next to a phoneme block, found by reading the
    phonemes rather than hearing them: an article before it is said as the
    letter ("EY quart"), and punctuation after it is said as a word ("capot
    exclamation"). So both go inside the block.
    """
    def swap(match):
        article, word, stop = match.group(1) or "", match.group(2), match.group(3) or ""
        phonemes = PRONOUNCE.get(word.lower())
        if not phonemes:
            return match.group(0)
        inner = phonemes[2:-2]
        return f"[[{'ɐ ' if article else ''}{inner}{stop}]]"
    return re.sub(r"(\b[Aa] )?([A-Za-zÀ-ÿ]+)([.!?,])?", swap, text)


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

# ---- the inventory ---------------------------------------------------------------

RANKS = ["seven", "eight", "nine", "ten", "knave", "queen", "king", "ace"]
SEQUENCES = ["tierce", "quart", "quint", "sixième", "septième", "huitième"]
SUITS = ["spades", "hearts", "diamonds", "clubs"]
SET_RANKS = ["ace", "king", "queen", "knave", "ten"]  # nines and below do not count
PLURAL = {"ace": "aces", "king": "kings", "queen": "queens", "knave": "knaves", "ten": "tens"}


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


def inventory():
    """Every phrase the table says: (id, words), ids unique and stable."""
    phrases = []
    add = lambda pid, text: phrases.append((pid, text))

    # The exchange (Cavendish p. 57) and carte blanche (p. 69).
    for n in range(1, 5):
        add(f"take-{n}", f"I only take {words(n)}.")
    add("leave-1", "I leave a card.")
    for n in range(2, 5):
        add(f"leave-{n}", f"I leave {words(n)} cards.")
    add("carte-blanche-have", "I have a carte blanche.")
    add("carte-blanche-discard", "Discard for carte blanche.")

    # The point (pp. 60-61): its length, the question, the suit. Its value is
    # a number, said from the counting bank below.
    for n in range(3, 9):
        add(f"point-{n}", f"{words(n).capitalize()} cards.")
    add("what-make", "What do they make?")
    for suit in SUITS:
        add(f"in-{suit}", f"In {suit}.")

    # Sequences (p. 64) and quatorzes and trios (p. 67).
    phrases.extend(sequence_calls())
    for count, word in [(3, "Three"), (4, "Four")]:
        for rank in SET_RANKS:
            add(f"set-{count}-{rank}", f"{word} {PLURAL[rank]}.")

    # The answers, and a call of nothing.
    add("good", "Good.")
    add("not-good", "Not good.")
    add("equal", "Equal.")
    add("nothing", "Nothing.")

    # Counting aloud, every number a deal can reach, and the joins of a
    # count said whole: "Four tens fourteen, and three queens seventeen";
    # "Five and four are nine".
    for n in range(1, HIGHEST_COUNT + 1):
        add(f"n-{n}", f"{words(n).capitalize()}.")
    add("and", "and")
    add("are", "are")

    # The deal's great moments.
    add("pique", "Pique!")
    add("repique", "Repique!")
    add("capot", "Capot!")
    add("the-cards", "And the cards.")

    # Niceties (Andrew: "include a few niceties (eg, 'Congratulations!' if you
    # win a game)").
    add("congratulations", "Congratulations!")
    add("well-played", "Well played.")
    add("good-game", "Good game.")
    add("your-deal", "Your deal.")
    add("my-deal", "My deal.")
    add("your-lead", "Your lead.")
    add("cut-again", "Cut again.")
    add("another", "Another partie?")
    add("thank-you", "Thank you.")
    return phrases


# ---- speaking and encoding --------------------------------------------------------


def speak(voice, text, wav_path):
    with wave.open(str(wav_path), "wb") as wav:
        voice.synthesize_wav(text, wav)


def encode(wav_path, out_path, kind):
    """Trim the silence either end, then encode small: speech needs far
    less than music."""
    trim = "silenceremove=start_periods=1:start_threshold=-50dB:stop_periods=-1:stop_threshold=-50dB:stop_duration=0.15"
    codec = {
        "mp3": ["-ac", "1", "-ar", "22050", "-codec:a", "libmp3lame", "-b:a", "32k"],
        "opus": ["-ac", "1", "-codec:a", "libopus", "-b:a", "20k", "-application", "voip"],
    }[kind]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav_path), "-af", trim, *codec, str(out_path)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--voices", default=",".join(VOICES))
    parser.add_argument("--only", default="")
    parser.add_argument("--format", default="mp3", choices=["mp3", "opus", "both"])
    args = parser.parse_args()
    from piper import PiperVoice  # only here: the inventory needs no Piper

    wanted = set(filter(None, args.only.split(",")))
    phrases = [p for p in inventory() if not wanted or p[0] in wanted]
    formats = ["mp3", "opus"] if args.format == "both" else [args.format]
    ext = {"mp3": "mp3", "opus": "ogg"}
    for name in args.voices.split(","):
        spec = VOICES[name]
        voice = PiperVoice.load(str(MODELS / f"{spec['model']}.onnx"))
        folder = OUT / name
        folder.mkdir(parents=True, exist_ok=True)
        total = dict.fromkeys(formats, 0)
        seconds = 0.0
        with tempfile.TemporaryDirectory() as tmp:
            for pid, text in phrases:
                wav = Path(tmp) / f"{pid}.wav"
                speak(voice, speakable(text), wav)
                with wave.open(str(wav)) as w:
                    seconds += w.getnframes() / w.getframerate()
                for kind in formats:
                    out = folder / f"{pid}.{ext[kind]}"
                    encode(wav, out, kind)
                    total[kind] += out.stat().st_size
        manifest = {"voice": name, **spec, "phrases": {pid: text for pid, text in phrases}}
        (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
        sizes = ", ".join(f"{total[k] / 1024:.0f} kB as {k}" for k in formats)
        print(f"{name}: {len(phrases)} phrases, {seconds:.0f} s of speech before trimming; {sizes}")


if __name__ == "__main__":
    sys.exit(main())
