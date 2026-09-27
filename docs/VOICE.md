# The voice — what the table says aloud, and how it is said

> Andrew, 27 September 2026: *"price out how much it would cost … to
> generate audio for ALL of the events that are spoken during this game …
> down-res'd so the game doesn't get enormous … we can also use another
> option (eg Piper TTS, espeak-ng)"*; then *"do an exhaustive search and think
> about exactly which audio files we'll need. i think we can get started
> using a free service, not google. think about how to make the voice work
> so it can pronounce the words correctly."* This file is the plan and the
> record. `PLAN.md` TODO 14 points here.

## 1. Pronunciation

Piquet's vocabulary is French, and an English voice left to itself says
"quatorze" and "capot" wrongly. The table below is what the voice must say,
with where each came from. Where a dictionary records English usage for the
card game, that wins; where none does, the French.

| term | say it | IPA (target) | source |
|---|---|---|---|
| piquet | pi-KET (or pi-KAY) | /pɪˈkɛt/, /pɪˈkeɪ/ | Merriam-Webster (both); Parlett rhymes it with "ticket" |
| tierce | TEERS | /tɪəs/ | Merriam-Webster |
| quart | KART ("cart") | /kɑːt/ | piquet usage, per web search (to confirm) |
| quint | KWINT | /kwɪnt/ | Wiktionary, the piquet sense |
| sixième | see-ZYEM | /siˈzjɛm/ | French /si.zjɛm/ (Wiktionary; no English entry) |
| septième | set-YEM | /sɛˈtjɛm/ | French /sɛ.tjɛm/ |
| huitième | weet-YEM | /ɥiˈtjɛm/ | French /ɥi.tjɛm/ (Wiktionary; no English entry) |
| quatorze | kuh-TORZ | /kəˈtɔːz/ | Merriam-Webster |
| trio | TREE-oh | /ˈtriːəʊ/ | standard English |
| pique | PEEK | /piːk/ | Merriam-Webster (as in repique) |
| repique | ruh-PEEK | /rɪˈpiːk/ | Merriam-Webster |
| capot | kuh-POT (or kuh-POH) | /kəˈpɒt/ | Merriam-Webster (first sense) |
| carte blanche | kart BLAHNSH | /ˌkɑːt ˈblɒ̃ʃ/ | standard English |

Sources: <https://www.merriam-webster.com/dictionary/quatorze>,
<https://www.merriam-webster.com/dictionary/capot>,
<https://www.merriam-webster.com/dictionary/repique>,
<https://www.merriam-webster.com/dictionary/tierce>,
<https://www.merriam-webster.com/dictionary/piquet>,
<https://en.wiktionary.org/wiki/quint>,
<https://en.wiktionary.org/wiki/sixi%C3%A8me>,
<https://en.wiktionary.org/wiki/huiti%C3%A8me>,
<https://www.parlettgames.uk/histocs/piquet.html>.

**How the voice is made to say them.** The free voices (Piper) turn text into
sounds with espeak-ng, so what a word will sound like can be *read* before
anything is heard: `espeak-ng -v en-gb --ipa "quatorze"` prints the phonemes.
Each term above is fed to the voice as a respelling (or as raw phonemes) and
checked this way against the target IPA, since these words cannot be
listened to on the VM.

## 2. What is said — the inventory

Found by having the engine play 240 parties and collecting everything said,
then checked against the rules so that calls too rare to have come up are
not missed. The engine's calls are **compound** — one call may name several
holdings ("quint to the ace, tierce to the king"; "quatorze of aces, trio of
queens") — so the voice records **atoms** and plays them in turn with a short
pause, rather than every combination.

(The counts follow in §3 once the inventory is generated.)
