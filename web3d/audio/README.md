# The voice's clips

Made by `web3d/tools/voice.py` (Piper, free and local) from the bank in that
file; bundled into the page by `web3d/build.py`. One folder per voice, each
with a `manifest.json` -- the voice, its licence, the words of every
recording (`files`) and the groups the page picks among (`groups`) -- and one
Ogg Opus clip per recording, `<group>.<n>.ogg`, 12 kb/s mono. Everything is
said in several ways, so that nothing is heard the same way twice running;
every phrase, with its source, is written down in `docs/PHRASES.md`.
`docs/VOICE.md` has the reasoning; `CREDITS.md` the voices' provenance (both
public domain).
