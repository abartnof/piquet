#!/usr/bin/env python3
"""Build web3d/piquet3d.html: the 3D table, as one self-contained file.

    python3 web3d/build.py

Compiles the engine to WebAssembly (as web/build.py does for the 2D page),
bundles web3d/src with three.js and Material Web through esbuild, and inlines
the engine, the bundle and the stylesheet into web3d/src/index.html. The page
needs no server and no network: open it from disk and play.

It prints what every part weighs. Over 5 MB it warns rather than fails: the user
set that figure as a guideline for modesty ("i want this to be rather modest
and easy to use, but it's not a HARD limit"), so the size is weighed against
what the bytes buy, not treated as a wall.

Needs `npm ci` in web3d/ first (esbuild and the libraries, pinned by
package-lock.json).
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "web3d"
SRC = HERE / "src"
OUT = HERE / "piquet3d.html"
WASM = ROOT / "target" / "wasm32-unknown-unknown" / "release" / "piquet_wasm.wasm"
ESBUILD = HERE / "node_modules" / ".bin" / "esbuild"
CARDS = HERE / "art" / "cards"
GUIDELINE = 5 * 1024 * 1024

# Where each bundled source file is reported, by path prefix; first match wins.
PARTS = [
    ("three.js", "node_modules/three/"),
    ("Material Web + Lit", "node_modules/"),
    ("the table's own code", ""),
]


def build_wasm() -> bytes:
    cargo = Path.home() / ".cargo" / "bin" / "cargo"
    subprocess.run(
        [str(cargo) if cargo.exists() else "cargo", "build", "--release", "-q",
         "-p", "piquet-wasm", "--lib", "--target", "wasm32-unknown-unknown"],
        cwd=ROOT, check=True,
    )
    return WASM.read_bytes()


def bundle() -> tuple[str, dict[str, int]]:
    """The page's script, minified, and how many of its bytes each part owns."""
    if not ESBUILD.exists():
        sys.exit("esbuild is missing: run `npm ci` in web3d/ first")
    with tempfile.TemporaryDirectory() as tmp:
        out, meta = Path(tmp) / "app.js", Path(tmp) / "meta.json"
        subprocess.run(
            [str(ESBUILD), "src/main.js", "--bundle", "--minify", "--format=iife",
             "--target=es2022", "--platform=browser", "--legal-comments=eof",
             # The tutorial's pages are Markdown, inlined as text (web3d/tutorial.md).
             "--loader:.md=text",
             f"--outfile={out}", f"--metafile={meta}", "--log-level=warning"],
            cwd=HERE, check=True,
        )
        code = out.read_text()
        inputs = json.loads(meta.read_text())["outputs"]
    owned = {name: 0 for name, _ in PARTS}
    for output in inputs.values():
        for path, info in output.get("inputs", {}).items():
            name = next(n for n, prefix in PARTS if path.startswith(prefix))
            owned[name] += info["bytesInOutput"]
    # Whatever the inputs do not account for is esbuild's glue and the legal
    # comments gathered at the end of the file; report it with the libraries.
    owned["licence notices and glue"] = len(code.encode()) - sum(owned.values())
    return code, owned


def art(way: str) -> str:
    """The 33 card images as a JSON object keyed by card code (and "back").

    Way A, "webp": data URIs of the images web3d/tools/art.py made, committed.
    Way B, "svg": the SVGs themselves, cut from the pinned originals at build
    time, for the browser to rasterise at whatever size the screen wants.
    """
    if way == "svg":
        sys.path.insert(0, str(HERE / "tools"))
        import art as pipeline
        return json.dumps({**pipeline.face_svgs(), "back": pipeline.back_svg()}, separators=(",", ":"))
    images = sorted(CARDS.glob("*.webp"))
    if len(images) != 33:
        sys.exit(f"expected 33 card images in {CARDS}, found {len(images)}: run web3d/tools/art.py")
    return json.dumps({
        p.stem: "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode("ascii")
        for p in images
    }, separators=(",", ":"))


AUDIO = HERE / "audio"


def voices(kind: str) -> str:
    """The recorded phrases (web3d/tools/voice.py) as a JSON object: for each
    voice, its manifest's particulars, every recording (base64), and the
    groups the page picks among -- the voice at the table, offline
    (docs/VOICE.md, docs/PHRASES.md). Empty if none have been made.

    With `none`, the default, no sound at all: only the words of the
    phrases, for the declarations' dialogue boxes (the user: "i don't want the
    html to have any audio")."""
    out = {}
    if kind == "none":
        # The phrase bank's words (web3d/tools/voice.py --doc writes them).
        out["words"] = json.loads((ROOT / "web3d" / "words.json").read_text())
        return json.dumps(out, separators=(",", ":"), ensure_ascii=False)
    ext = {"mp3": "mp3", "opus": "ogg"}[kind]
    for manifest in sorted(AUDIO.glob("*/manifest.json")):
        spec = json.loads(manifest.read_text())
        folder = manifest.parent
        missing = [key for key in spec["files"] if not (folder / f"{key}.{ext}").exists()]
        if missing:
            sys.exit(f"{folder.name}: no recording of {', '.join(missing[:5])}: run web3d/tools/voice.py")
        clips = {key: base64.b64encode((folder / f"{key}.{ext}").read_bytes()).decode("ascii") for key in spec["files"]}
        out[spec["voice"]] = {"gender": spec["gender"], "format": ext, "clips": clips,
                              "groups": spec["groups"], "texts": spec["files"]}
    return json.dumps(out, separators=(",", ":"))


def fill(template: str, values: dict[str, str]) -> str:
    """Replace every placeholder in one pass, so nothing inserted is rescanned."""
    missing = [k for k in values if k not in template]
    if missing:
        sys.exit(f"the template has no {', '.join(missing)}")
    pattern = re.compile("|".join(re.escape(k) for k in values))
    return pattern.sub(lambda m: values[m.group(0)], template)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 3D table's single-file page.")
    parser.add_argument("--audio", choices=["none", "opus", "mp3"], default="none",
                        help="no sound, only the phrases' words for the dialogue boxes (the default: "
                             "the user, 'i don't want the html to have any audio'); or the voice's "
                             "clips as Ogg Opus or MP3")
    parser.add_argument("--art", choices=["webp", "svg"], default="webp",
                        help="ship the card art rasterised (webp, the default) or as vectors (svg), "
                             "which writes web3d/piquet3d-svg.html instead")
    args = parser.parse_args()
    out = OUT if args.art == "webp" else OUT.with_name("piquet3d-svg.html")
    wasm = build_wasm()
    code, owned = bundle()
    if "</script" in code.lower():
        sys.exit("the bundle contains '</script', which would end the inline script early")
    style = (SRC / "style.css").read_text()
    engine = base64.b64encode(wasm).decode("ascii")
    cards = art(args.art)
    speech = voices(args.audio)
    page = fill((SRC / "index.html").read_text(), {
        "/*STYLE*/": style,
        "/*APP*/": code,
        "__WASM_BASE64__": engine,
        "/*ART*/": cards,
        "/*VOICES*/": speech,
    })
    out.write_text(page)

    size = len(page.encode())
    art_name = "the card art (WebP, base64)" if args.art == "webp" else "the card art (SVG)"
    rows = [("the engine (wasm, base64)", len(engine)), (art_name, len(cards.encode())),
            ("the dialogue's words" if args.audio == "none" else f"the voices ({args.audio}, base64)", len(speech.encode())),
            *owned.items(),
            ("stylesheet", len(style.encode()))]
    rows.append(("page skeleton", size - sum(n for _, n in rows)))
    print(f"{out.relative_to(ROOT)}: {size:,} bytes")
    for name, n in rows:
        print(f"  {n:>10,}  {name}")
    if size > GUIDELINE:
        print(f"note: over the {GUIDELINE:,}-byte guideline -- weigh what the extra buys")
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())
