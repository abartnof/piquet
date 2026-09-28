# The voice — what the table says aloud, and how it is said

> **28 September: unwired.** Andrew: *"i don't want the html to have any
> audio"*, then *"i think the audio is a nice feature, but it all sounds
> really tinny."* The page ships no sound; the code, the recordings and the
> phrase bank stay here, and `web3d/build.py --audio opus` puts this voice
> back. The declaration dialogue boxes use the bank's words, silently. A
> second try — whole utterances from a first-class voice — is `PLAN.md`
> TODO 14.

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

**How the voice is made to say them: English respellings.** The free
voices (Piper) turn text into sounds with espeak-ng, so what a word will
sound like can be *read* before anything is heard: `espeak-ng -v en --ipa
"cart"` prints the phonemes.

The first build fed the French terms to the voices as **raw phonemes**,
checked only by reading them. That was wrong: the male voice babbled on
*capot* — Andrew, 28 September: *"some of the men's voice sounds kind of
spastic. is there a 'ne ne ne' sound?"*, then, having listened, *"yes,
verified- that one is busted"*. A voice can list a phoneme in its table
without ever having been trained to say it. His fix: *"an obvious way is to
use english homonyms, no?"* So every term is now **respelt as English the
voice already knows**, which each voice says through its own trained path,
in its own accent — checked through espeak's `en`, `en-gb` and `en-us`:

| term | respelt | espeak reads it |
|---|---|---|
| quart | cart | kɑːt (kɑːɹt, American) |
| quatorze | kuh-torz | kʌtɔːz |
| capot | kuh-pot | kʌ pɒt (kʌ pɑːt, American) |
| sixième | seez yem | siːz jɛm |
| septième | set yem | sɛt jɛm |
| huitième | wheat yem | wiːt jɛm |
| piquet | pick-ett | pɪkɛt |

Every recording with one of these words in it — seventeen groups, in both
voices — was made again this way. The rest (tierce, quint, pique, repique,
trio, carte blanche) espeak already says as the table above wants. Reading
phonemes is a proxy; the ear is the check, and only Andrew can apply it.

## 2. How it is actually said — Cavendish, 1885

Andrew: *"we'll do maximal speaking (anything a human would say, we'll say).
you may revisit the classic books."* The source is Cavendish, *The Laws of
Piquet adopted by the Portland and Turf Clubs, with a Treatise on the Game*
(De la Rue, 1885), <https://archive.org/details/lawsofpiquetadop00caveuoft>;
page numbers are that edition's.

- **The exchange** (p. 57): elder taking fewer than five "must announce the
  fact by saying 'I only take four,' — or three, or less …; or, 'I leave a
  card,' — or two, or more cards."
- **Carte blanche** (p. 69): "he must inform his adversary at once, by saying,
  'I have a carte blanche,' or 'Discard for carte blanche.'"
- **The point** (pp. 60–61): elder calls its length — "Five cards." Younger
  answers "Good.", "Not good." or "Equal."; on equal (or when asked "What do
  they make?") elder gives its value — "Forty-eight," or "Making eight."
  If good, elder names the suit — "In spades" — and counts: "Five."
- **Sequences** (p. 64): "A quint minor," "A quart to a queen," "quart
  major," answered the same way; if good, the suit is named.
- **Quatorze and trio** (p. 67): "Four aces," "Three queens" — answered
  "Good" or "Not good". He says **knaves** throughout, never jacks.
- **Counting aloud**: each player counts his running score as he scores it —
  "Five and four are nine" (p. 77); younger, once elder has led: "Four tens
  fourteen, and three queens seventeen"; in the play, "Ten." "Eleven,
  twelve, thirteen, fourteen." — and, when not scoring, repeats his score.
  A pique counts **"Sixty"** at the moment it would have been "Thirty"; a
  repique turns "Thirty-four" into **"Ninety-four"** (pp. 70–71).
- **Questions** a player may ask (pp. 72–74): "Which queen do you not
  reckon?", "How many hearts?" — "Two."

The engine's own words differ in places ("tierce to the ace" for "tierce
major", "trio of jacks" for "three knaves"). The voice follows Cavendish;
whether the captions should follow him too is a question for Andrew.

**Niceties** (Andrew: *"include a few niceties (eg, 'Congratulations!' if you
win a game)"*): congratulations, well played, good game, your deal, your
lead, another partie?

## 3. What is said — the bank, and saying it several ways

Found by having the engine play 240 parties and collecting everything said,
then checked against the rules so that calls too rare to have come up are
not missed. The engine's calls are **compound** — one call may name several
holdings ("quint to the ace, tierce to the king"; "quatorze of aces, trio of
queens") — so the voice records **groups** and plays them in turn with a
short pause, rather than every combination.

**Nothing is said only one way.** Andrew, 28 September: *"i don't want
*any* sounds to be repetitive- so, things like 'good', 'not good', can become
variations like 'ah, not good' or 'not good!' etc."*, and on the price:
*"7mb is fine"*. So each group — a moment at the table — has several
recordings, and each speaker picks among them from a shuffled bag
(`web3d/src/bag.js`, node-tested): every way once before any comes round
again, and never the same way twice running.

**How many ways follows how often it is heard.** Counted over twelve
simulated parties (a scripted player against the ladder), a partie says
about 170 things, 117 of them numbers — but spread thin: the commonest
number is heard about five times a partie, most once or twice. The
phrases repeat most: "Good." eight times a partie, the point's length
six, "Not good." five, "And the cards." five. So:

- **Phrases** have wordings roughly in step with how often they are
  heard: "Good." eight, "Not good." six, "What do they make?" five, the
  point's length four (heard about six times a partie, so each way about
  once or twice), the rarest (a septième to a king) three. The wordings come from the period books — below — and a few
  of the table's own, each tagged with its source in `docs/PHRASES.md`.
- **Numbers** are the same words in several takes: three up to forty, two
  above. Piper renders the same text differently every time (measured: two
  renderings of "Forty-eight." differed in length by a tenth), and the takes
  are spoken at paces 1.0, 0.93 and 1.08 besides.
- **A point's value** is a group of its own, answering "What do they
  make?": the number — or, in the forties, what it is *making*, as
  Cavendish ("Forty-nine," or "Making nine") and Cady ("Forty-seven," or
  "Making seven") both have it. The same recordings, grouped again, so
  nothing is stored twice.

**The books consulted for the wordings**, all read from the Internet
Archive's scans:

| Book | Archive identifier | What it gave |
|---|---|---|
| Cavendish, *The Laws of Piquet* (1885; and 1881) | `lawsofpiquetadop00caveuoft`, `lawspiquet00cavegoog` | the whole procedure (§2); "I leave a card"; "Making nine" |
| A. Howard Cady, *Piquet: a Treatise on the Game* (1896) | `piquettreatiseon00cady` | "I take only four"; "How many?" beside "What do they make?"; "Making seven" |
| *Foster's Complete Hoyle* (1897 and later) | `fosterscompleteh00fost` | "Quatorze aces"; "sixième to the king" for a sequence |
| H. G. Bohn, *The Hand-book of Games* (1850) | `handbookofgamesc00bohn` | read; its one spoken phrase, "one for the last card", is not a call anyone makes aloud |
| Hoyle, *A Short Treatise on the Game of Piquet* (1744) | `bim_eighteenth-century_a-short-treatise-on-the-_hoyle-edmond_1744` | read; nothing spoken — a treatise on play |
| Chateauneuf, *A New Treatise on Piquet*, French and English (1770) | `bim_eighteenth-century_a-new-treatise-on-piquet_chateauneuf-mr-de_1770` | read; counts in running totals, in French ("16 & 14 d'as c'est 30") — not used |
| Cotton, *The Compleat Gamester* (1709 printing) | `bim_eighteenth-century_the-compleat-gamester-o_cotton-charles_1709` | too poorly scanned to read |

`web3d/tools/voice.py` holds the bank as code, and `test_voice.py` holds it
to the rules and to Andrew's brief: every group has at least two ways,
"Good." at least eight, every number to **170** (the most a deal can
score), every sequence that can be held (**21**) and every trio and
quatorze (10), every point value, and every recording used. **The phrases
are written down** in `docs/PHRASES.md`, generated from the bank (Andrew:
*"remember to write these phrases down somewhere local as well"*); a test
keeps the two in step.

The engine's events become a queue of groups in `web3d/src/speech.js`
(node-tested, including that every group it asks for over whole parties was
recorded, in more than one way), and `web3d/src/voice.js` picks a way for
each and plays them in turn, in the voice of whoever speaks. Besides the
calls, your opponent hands you the choice of deal when you cut higher
("Your choice."), remarks on a deal you win by thirty or more ("Well
played." — only then, or it would be as tiresome as silence), and says
something at the end of the partie.

Not yet said: the suit of a good point ("In spades." — the engine's events
do not carry it), and the talk from the list Andrew pasted that has no event
behind it yet (thinking aloud, asking you to cut, prompting when idle — the
last would want a switch of its own).

## 4. The voices

**English, not French.** Andrew raised a French voice, "if the pronunciations
are hard". Nearly everything said is English -- "Good", "Four aces",
counting to 170 -- which a French voice would mangle; the six French terms
are handled exactly with phonemes (§1), read back and correct. So English.

**Free, local, and clean.** Piper (GPL-3.0; a tool, not shipped) speaks;
espeak-ng underneath decides pronunciation. The voices were chosen by
licence *and lineage*: most Piper voices -- every British one but Cori --
are fine-tuned from "lessac", whose Blizzard 2013 data is licensed for
research only, with no redistribution
(<https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html>),
so a clip from them is not ours to ship. The two chosen were both trained
from scratch on public-domain LibriVox recordings, by Bryce Beattie
(<https://brycebeattie.com/files/tts/>):

| voice | model | gender, accent | licence |
|---|---|---|---|
| Cori | `en_GB-cori-high` | female, British | public domain |
| Norman | `en_US-norman-medium` | male, American | public domain |

There is no clean British male voice. Rejected: the Northern English male
(CC BY-SA data, but fine-tuned from lessac), Alan, Alba, Aru, VCTK
(lessac-derived), Semaine (lessac-derived, non-commercial), Ryan
(non-commercial).

By default your opponent speaks as Cori and you as Norman; Settings swaps
them, and can mute your own calls or the voice altogether.

## 5. Size, measured

**Now (28 September): 601 recordings a voice** in 280 groups, trimmed of
silence either end, as Ogg Opus at **12 kb/s** mono: Cori 1,146 kB, Norman
1,084 kB — about 1.8 kB a recording, against 2.9 kB before, the lower rate
paying for the wordier ways of saying things. With both voices **the page
is 6.11 MB** (voices 3.12 MB in base64), inside the 7 MB Andrew allowed for
it (*"7mb is fine"*). 12 kb/s was chosen as the rate at which Opus is still
wideband speech; it has not been compared by ear against 20 kb/s, and the
build takes `voice.py --bitrate` if it should be.

Before, for the record — all 241 phrases, one way each, each voice:

| | Cori | Norman |
|---|---|---|
| MP3, 32 kb/s mono | 1,231 kB | 1,116 kB |
| **Ogg Opus, 20 kb/s mono (shipped)** | **745 kB** | **688 kB** |

Counting aloud is most of it -- the 170 numbers are 72% of Cori's bytes.
Opus, a codec made for speech, is clear at 20 kb/s and 40% smaller than
MP3; with both voices the page is **4.96 MB** (voices 1.98 MB in base64,
the card art 1.63 MB, the engine 0.43 MB), inside the 5 MB guideline
(Andrew: "a goal to ensure the game can be easily downloaded/run, nothing
more"). A browser that cannot play Ogg Opus (Safari before 18.4) speaks the
same words in its own voice, respelled for the French terms, at no cost in
size. If the page ever needs room, numbers above ninety-nine could be said
as "a hundred and" + a smaller number, saving about a third of the voices.

## 6. What is said, in practice

From a real deal (`speech.js`, partie 3/7, deal 1):

    you   I only take three. Five cards.
    them  What do they make?
    you   Fifty.
    them  Good.
    you   Five. A tierce to a knave.
    them  Not good.
    you   Nothing. Six.
    them  A tierce major. Three. Three aces. Three queens. Nine.
    you   Seven.
    them  Ten. Eleven. Twelve. … Twenty-one. And the cards. Thirty-one.

**Open for Andrew:** Cavendish says *knave*, *tierce major*, *quart
minor*; the captions and the worth card say *jack* and *tierce to the ace*.
Should the words on screen follow the voice?

## 7. The audit (28 September)

Andrew: *"i'm mostly concerned with audio in the declarations phase. is that
fully wired up with audio?"*, then *"i found that after deal 1, no audio
plays"*, and *"a code review of the audio code, + simulate a few games to
make sure the audio passes your QC"*. What the review and the simulations
found, and what became of it.

**Defects, fixed:**

1. *Your opponent's bare calls were silent.* Elder gives no more than he
   must — "a quart", "a trio" — and there was no recording for a shape
   without its top or rank: over 48 simulated parties, 97 of 278 of their
   sequence calls and 134 of 264 of their set calls said nothing. Now "A
   quart.", "A trio." (and "A quatorze.", every length) are recorded.
2. *The tie-break was garbled when your opponent was elder.* With points of
   equal length, "What do they make?" was never asked, the value never
   said, "Four cards." said twice, and the answer came before the value it
   answers — the engine reports the decision before the tie-break, and
   `speech.js` followed its order. Now the decision carries `asked`
   (`docs/PROTOCOL.md`; a Rust test holds it to what was said, over 59
   parties), and the dialogue runs call — question — tie-break — answer:
   "A quart." "How high?" "A quart major." "Good."
3. *"What do they make?" was asked of your point even when it was not
   needed*: your calls carry their value always. Now only when `asked`.
4. *Speech ran ahead of the cards*: it was said when the engine answered,
   before anything moved, so a run of your opponent's plays was counted
   while the first card was still in the air. Now every line waits for its
   event's moment on the animation's clock — a card's count when it lands,
   a call as their cards stir (`choreography.js` `beats`, tested over whole
   parties).
5. *Two batches of speech could play out of order*, if the first was still
   decoding its clips when the second came. Now strictly in turn.
6. *An undo or a new partie did not silence speech still decoding.* Now it
   does.
7. *Every clip ever decoded was kept*, about 190 kB a second of speech.
   Now the 160 most recent.
8. *As elder with nothing to call, you said nothing* (heard only with your
   own voice on). Now "Nothing."
9. *Elder, winning on a bare call, never named what he held.* Now he names
   it as he reckons it: "Three aces. Three kings. Six."

**Suspected, not reproduced: silence after deal 1.** In headless Chromium,
in real animated play, the voice kept speaking through deals 2 and 3, before
the changes and after. The likeliest cause: the browser put the sound to
sleep — Safari "interrupts" it when the window loses the audio, and a
browser may suspend it — and the page only ever woke it from "suspended",
and never from a click. Now it is woken from any sleeping state, on every
click and key and when the page is shown again, and what cannot be said
now is dropped rather than said all at once, late. Only Andrew's browser
can confirm it.

**The QC, kept as tests.** `speech.test.js` plays eight simulated parties
(levels 1 to 4) and checks that, spoken move by move as the page speaks
them, they say exactly what each deal says spoken whole; that every call of
elder's is voiced as its shape; that each category runs call, then question
and tie-break only when asked, then answer; that every count said is the
running total; and that no line strays into another deal.
`choreography.test.js` checks each event's moment against the cards.

**For Andrew — interpretations, not defects:**

- With your own voice off (the default), your half of the dialogue is
  silent: you hear "A quart." and then "A quart major.", your "How high?"
  unsaid. One option: voice your questions and answers even then.
- Cavendish has each player repeat his score as he plays every card; the
  table counts aloud only when a score is made.
- A good point's suit ("In spades.") is not said: the engine's events do
  not carry it.

## 8. A second try, costed (28 September)

Andrew: *"what about if there was 2 genders (one for opponent, one for
player), 1 phase per event, one recording per event. think maximally- that
means 'I have 21' and 'i have 20' are two wholly distinct recordings. we'd do
it on a first-class voice-producer, like google"*; then *"make sure you have
a full count of *all* utterances ... every event each player does, and how
they might respond ... important state transitions as well (start, win,
congrats, oh well maybe next time, etc). then do another count where numbers
are distinct ... price it out to use a google first-rate voice product"*.

**The count** — `web3d/tools/utterances.py`, derived from the rules rather
than sampled (tested, `test_utterances.py`). Every event either player
makes and every reply: the cut and the choice of deal, each deal and the
last, the exchange (elder and younger), carte blanche, the point, sequences
and sets called, asked about and answered, reckoning, counting aloud, pique,
repique, the cards, capot, the last trick, the rubicon crossed, a deal won
or lost heavily, the partie won, lost, rubiconed or drawn, and a few words
while thinking. Every sequence a twelve-card hand can hold (as lists: 912),
every set of trios and quatorzes (135), every point value (49), every count
to 170. Both voices need the game's lines, since either player can be
elder; each has its own few.

| | per voice | speech, both voices | 16 kb/s | 24 kb/s | 32 kb/s | 48 kb/s |
|---|---|---|---|---|---|---|
| **Maximal** — each event one recording, its count fused in ("Three aces and three queens: nine.") | ~24,100 | ~61 h | 457 MB | 679 MB | 900 MB | 1.34 GB |
| **Numbers apart** — each event whole, the count its own recording | ~1,300 | 2.5 h | 19 MB | 28 MB | 37 MB | 55 MB |
| **Phrases** — each holding and each count its own whole recording, said in turn | ~280 | 12 min | 1.5 MB | 2.2 MB | 2.8 MB | 4.1 MB |

Andrew: *"go smaller for the kb/s. add whatever i remember for SNES and
n64"* — the same three plans, as files, lower, and at what those consoles
spent on speech:

| | phrases | numbers apart | maximal |
|---|---|---|---|
| Opus 6 kb/s | 0.7 MB | 7.6 MB | 181 MB |
| Opus 8 kb/s | 0.8 MB | 9.8 MB | 236 MB |
| Opus 10 kb/s | 1.0 MB | 12.1 MB | 291 MB |
| Opus 12 kb/s (the Piper try) | 1.2 MB | 14.4 MB | 347 MB |
| Opus 16 kb/s | 1.5 MB | 18.9 MB | 457 MB |
| SNES speech — BRR, 8 kHz (~36 kb/s) | 3.0 MB | 41 MB | 1.0 GB |
| SNES speech — BRR, 16 kHz (~72 kb/s) | 6.0 MB | 81 MB | 2.0 GB |
| N64 speech — VADPCM, 11 kHz (~50 kb/s) | 4.1 MB | 56 MB | 1.4 GB |
| N64 speech — VADPCM, 22 kHz (~99 kb/s) | 8.2 MB | 112 MB | 2.7 GB |

The consoles, from what is known of them: the SNES stored samples as BRR,
nine bytes for sixteen samples (4.5 bits a sample), usually recorded at 8 to
16 kHz, and all its sounds at once had to fit in 64 KB of audio RAM — about
fourteen seconds at 8 kHz, before any music; the N64's VADPCM was also about
4.5 bits a sample, speech usually at 11 to 22 kHz, the limit being the
cartridge. Opus is a far better codec for the bits: at 6 to 8 kb/s it is
telephone-band speech, about the bandwidth of an 8 kHz SNES sample and
cleaner; from about 12 kb/s it is wideband, better than the N64's typical
speech. Those last two comparisons are by what the codecs do, not by ear.

Sizes are the recordings as files, as they would sit in the repository;
embedded in the page they are a third larger (base64), on a page of 3.0 MB
without them. Speech is taken at 78 ms a character, measured on the Piper
recordings. The maximal count is an upper bound — it allows every count
the rules allow before each reckoning, without checking that twelve cards
could hold both — and 400 simulated parties turned up 1,090 of its kind
(§7's run), still climbing; either way it is thousands. Almost all of the
difference between the second and third rows is the lists: a hand's
sequences said as one sentence come in 912 forms, and its sets in 135;
said one holding at a time, they are 21 and 10. Every utterance of the
second and third plans is written down in `docs/UTTERANCES.tsv`
(`utterances.py --list` writes the maximal one too).

**The price** — Google Cloud Text-to-Speech, as its pricing page stood on
28 September 2026 (characters count spaces and punctuation):

| | Chirp 3: HD (1M characters a month free, then $30 a million) | Gemini 2.5 Pro TTS ($1 a million text tokens, $20 a million audio tokens, 25 a second) |
|---|---|---|
| Maximal, 2.84M characters, ~61 h | ~$55 (or free, spread over three months) | ~$112 |
| Numbers apart, 116k characters, 2.5 h | free | ~$4.50 |
| Phrases, 8.5k characters, 12 min | free | ~$0.35 |

Each extra take made to choose the best multiplies these. Other voices,
for comparison: Studio $160 a million after 1M free; Neural2 $16 after 1M
free; WaveNet and Standard $4 after 4M free; Gemini 2.5 Flash TTS half
Gemini Pro's price. To call it from this VM, the Text-to-Speech API must be
enabled on `abartnof-piquet` and the VM given the cloud-platform scope (its
service account lacks it — it cannot even read the billing), or a user
credential used. Spending is Andrew's decision.
