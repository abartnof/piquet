# The voice's clips

Made by `web3d/tools/voice.py` (Piper, free and local) from the inventory in
that file; bundled into the page by `web3d/build.py`. One folder per voice,
each with a `manifest.json` (the voice, its licence, every phrase's words)
and one Ogg Opus clip per phrase, 20 kb/s mono -- clear for speech, and 40%
smaller than MP3. `voice.py --format mp3` makes MP3s instead, for
`build.py --audio mp3`. `docs/VOICE.md` has the reasoning; `CREDITS.md` the
voices' provenance (both public domain).
