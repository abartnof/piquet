#!/usr/bin/env python3
"""Build web/piquet.html: the engine and the page, as one self-contained file.

    python3 web/build.py

Compiles crates/piquet-wasm to WebAssembly, then inlines it (base64), the
stylesheet and the script into web/src/index.html. The result needs no server
and no network: open it from disk and play. The whole thing must stay well
under the 5 MB the project set itself, and the build refuses to write a page
that does not.
"""

import base64
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "src"
OUT = ROOT / "web" / "piquet.html"
WASM = ROOT / "target" / "wasm32-unknown-unknown" / "release" / "piquet_wasm.wasm"
BUDGET = 5 * 1024 * 1024


def main() -> int:
    cargo = Path.home() / ".cargo" / "bin" / "cargo"
    subprocess.run(
        [str(cargo) if cargo.exists() else "cargo", "build", "--release", "-q",
         "-p", "piquet-wasm", "--lib", "--target", "wasm32-unknown-unknown"],
        cwd=ROOT, check=True,
    )
    wasm = WASM.read_bytes()
    page = (SRC / "index.html").read_text()
    for placeholder, content in [
        ("/*STYLE*/", (SRC / "style.css").read_text()),
        ("/*APP*/", (SRC / "app.js").read_text()),
        ("__WASM_BASE64__", base64.b64encode(wasm).decode("ascii")),
    ]:
        if placeholder not in page:
            print(f"the template has no {placeholder}", file=sys.stderr)
            return 1
        page = page.replace(placeholder, content, 1)

    size = len(page.encode())
    if size > BUDGET:
        print(f"{size:,} bytes is over the {BUDGET:,}-byte budget", file=sys.stderr)
        return 1
    OUT.write_text(page)
    print(f"{OUT.relative_to(ROOT)}: {size:,} bytes ({len(wasm):,} of them the engine, before base64)")
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())
