#!/usr/bin/env python3
"""The 3D table in a real browser, offline, played by clicking.

    python3 web3d/build.py
    .venv/bin/python web3d/test/browser.py [screenshot-dir]

Needs Playwright's Python package (the project `.venv` on the dev VM) and the
system Chromium (`/usr/bin/chromium`, from apt). WebGL runs on SwiftShader, so
no GPU is needed. The page is opened from a file:// URL with `?test`, which
makes every motion instant.

Checks what only a browser can show: that the page makes **no network request
of any kind** -- it is one file and must work offline; that a whole partie can
be played the way a person plays it, by clicking the spread, the cards and the
buttons; that the running score tab agrees with the engine at every step;
that a card that may not be played is refused on screen in the engine's
words; that undo, the hints key, settings and a reload all work; that the
motion demo runs; that a phone gets a working page with no sideways scroll;
and that nothing is ever written to the console in error.
"""

import io
import re
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "web3d" / "piquet3d.html"
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else None
LOCAL = ("file:", "data:", "blob:")


def shot(page, name):
    if SHOTS:
        page.screenshot(path=str(SHOTS / f"{name}.png"))


def open_page(browser, query="test", viewport=None, fresh=True):
    """A fresh context, offline, recording every request the page makes."""
    context = browser.new_context(viewport=viewport or {"width": 1280, "height": 800})
    context.set_offline(True)
    page = context.new_page()
    page.requests = []
    page.errors = []
    page.on("request", lambda r: page.requests.append(r.url))
    page.on("console", lambda m: m.type == "error" and page.errors.append(m.text))
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    goto(page, query, fresh)
    return page


def goto(page, query, fresh=True):
    page.goto(f"{PAGE.as_uri()}?{query}")
    if fresh:
        page.evaluate("localStorage.clear()")
        page.goto(f"{PAGE.as_uri()}?{query}")
    page.wait_for_function("window.piquet3d && window.piquet3d.ready()", timeout=120_000)


def state(page):
    return page.evaluate("window.piquet3d.state()")


def canvas_image(page):
    return Image.open(io.BytesIO(page.locator("canvas#stage").screenshot())).convert("RGB")


def check_offline(page, failures):
    remote = [u for u in page.requests if not u.startswith(LOCAL)]
    if remote:
        failures.append(f"the page asked the network for {len(remote)} things: {remote[:5]}")
    pages = {u.split("?")[0] for u in page.requests if u.startswith("file:")}
    if len(pages) != 1:
        failures.append(f"expected the page to load exactly one file, it loaded {pages}")


def check_drawn(page, failures, where=""):
    """A lit table: the canvas is not one colour, and not mostly black (the
    colour of WebGL that failed)."""
    small = canvas_image(page).resize((160, 100))
    colours = small.getcolors(maxcolors=160 * 100)
    dark = sum(n for n, (r, g, b) in colours if r + g + b < 60)
    if len(colours) < 4:
        failures.append(f"the canvas is nearly flat {where}: {len(colours)} colours")
    if dark > 0.5 * 160 * 100:
        failures.append(f"the canvas is mostly black {where} -- WebGL may have failed")


def click_card(page, code=None, zone=None, index=0):
    point = page.evaluate("([c, z, i]) => window.piquet3d.screenPoint(c, z, i)", [code, zone, index])
    if point is None:
        raise AssertionError(f"no card {code or zone} to click")
    page.mouse.click(point["x"], point["y"])


def button(page, name):
    return page.get_by_role("button", name=name)


def dull(s, n=0):
    """The dullest legal decision, varied by n (as test/partie.js's): a few
    cards thrown, a call in full or sunk, the first or last legal card."""
    p = s["prompt"]
    kind = p["kind"]
    if kind == "cut":
        return f"cut {2 + (n * 7) % 29}"
    if kind == "choose_dealer":
        return "dealer them" if n % 2 else "dealer you"
    if kind == "exchange":
        k = 1 + n % min(p["limit"], 3)
        return "exchange " + " ".join(s["hand"][-k:])
    if kind == "declare":
        return f"declare {len(p['options']) - 1 if n % 3 == 2 else 0}"
    if kind == "play":
        return "play " + (p["legal"][-1] if n % 2 else p["legal"][0])
    if kind == "next_deal":
        return "next"
    return None


def check_tab(page, failures, where):
    """The running tab's deal total is the engine's score for the deal."""
    s = state(page)
    if s["phase"] == "cut":
        return
    totals = page.locator(".tab-grid .stage.total.run").all_inner_texts()
    if totals and [int(x) for x in totals] != [s["score"]["you"], s["score"]["them"]]:
        failures.append(f"the tab says {totals} at {where}, the engine {s['score']}")
    head = page.locator(".tab-head").first.inner_text()
    if f"{s['score']['you']}" not in head or f"{s['score']['them']}" not in head:
        failures.append(f"the tab's first line {head!r} disagrees with {s['score']} at {where}")


def take_turn(page, failures, n, checked):
    """One human decision, made by clicking. False once the partie is over."""
    s = state(page)
    kind = s["prompt"]["kind"]
    if kind == "cut":
        click_card(page, zone="pack", index=14)
    elif kind == "choose_dealer":
        button(page, "Deal first").click()
    elif kind == "exchange":
        for code in s["hand"][: 1 + n % 3]:
            click_card(page, code=code)
        chosen = page.evaluate("window.piquet3d.placement().filter((m) => m.zone === 'your-hand').length")
        if chosen != 12:
            failures.append("choosing cards to throw moved them out of the hand")
        button(page, re.compile(r"^Throw")).click()
    elif kind == "declare":
        page.keyboard.press("1")
    elif kind == "play":
        legal = s["prompt"]["legal"]
        illegal = [c for c in s["hand"] if c not in legal]
        if illegal and "illegal" not in checked:
            checked.add("illegal")
            click_card(page, code=illegal[0])
            refused = state(page)
            if not refused["error"] or not page.locator("#prompt .error").is_visible():
                failures.append("a card that may not be played was not refused on screen")
            elif refused["error"] not in page.locator("#prompt .error").inner_text():
                failures.append("the refusal on screen is not the engine's")
        click_card(page, code=legal[0])
    elif kind == "next_deal":
        button(page, "Deal the next hand").click()
    else:
        return False
    after = state(page)
    if after["record"] == s["record"] and kind != "play":
        failures.append(f"clicking through a {kind} prompt did nothing")
    check_tab(page, failures, f"{kind} {n}")
    return True


def check_peek(page, failures):
    """Your own discards may be consulted: a click picks them up, face up,
    another puts them down."""
    pile = page.evaluate("window.piquet3d.screenPoint(null, 'your-discards', 0)")
    page.mouse.click(pile["x"], pile["y"])
    held = page.evaluate("window.piquet3d.screenPoint(null, 'your-discards', 0)")
    if held["y"] > pile["y"] - 30:
        failures.append("clicking your discards did not pick them up to look at")
    shot(page, "03-peek")
    page.mouse.click(held["x"], held["y"])
    back = page.evaluate("window.piquet3d.screenPoint(null, 'your-discards', 0)")
    if abs(back["y"] - pile["y"]) > 2 or abs(back["x"] - pile["x"]) > 2:
        failures.append("clicking your discards again did not put them back")


def check_keyboard_play(page, failures):
    """The whole hand can be played from the keyboard: the arrows move along
    it, Space plays the card they rest on, and the prompt says which it is."""
    before = state(page)
    page.keyboard.press("ArrowRight")
    focused = page.locator("#prompt .keyboard-focus").inner_text() if page.locator("#prompt .keyboard-focus").count() else ""
    if not focused:
        failures.append("the arrow keys named no card in the prompt")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Space")
    after = state(page)
    if len(after["record"]) <= len(before["record"]) and not after["error"]:
        failures.append("Space played nothing from the keyboard")


def check_undo_hints_settings(page, failures):
    s = state(page)
    if not s["can_undo"]:
        return
    page.keyboard.press("u")
    back = state(page)
    if len(back["record"]) >= len(s["record"]):
        failures.append("U did not take anything back")
    # H switches hints; E switches the interpretations (Andrew: facts, the
    # prescriptive layer, and hints -- the last two each easy to turn off).
    hints = back["aids"]["hints"]
    page.keyboard.press("h")
    if state(page)["aids"]["hints"] == hints:
        failures.append("H did not toggle hints")
    page.keyboard.press("h")
    notes = page.locator("#prompt .asked .note").count()
    page.keyboard.press("e")
    if notes and page.locator("#prompt .asked .note").count():
        failures.append("E did not hide the interpretation")
    page.keyboard.press("e")
    if notes and not page.locator("#prompt .asked .note").count():
        failures.append("E again did not bring the interpretation back")
    # Sorting is always to hand, as a segmented button under it.
    sort = page.locator("md-outlined-segmented-button[data-sort='rank']")
    if not sort.is_visible():
        failures.append("the sort is not under the hand")
    else:
        sort.click()
        if not page.evaluate("document.querySelector(\"md-outlined-segmented-button[data-sort='rank']\").selected"):
            failures.append("choosing Rank did not select it")
        page.locator("md-outlined-segmented-button[data-sort='auto']").click()

    page.locator("#settings-open").click()
    page.wait_for_selector("md-dialog#settings[open]")
    shot(page, "05-settings")
    if page.locator("md-dialog#settings .keys dt").count() < 6:
        failures.append("settings does not list the keys")
    button(page, "Done").click()
    page.wait_for_function("!document.querySelector('md-dialog#settings[open]')")


def main() -> int:
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])

        page = open_page(browser, "test&level=3&seed=7")
        check_drawn(page, failures, "at the cut")
        if state(page)["prompt"]["kind"] != "cut":
            failures.append("a new partie should open on the cut")
        shot(page, "01-cut")

        checked = set()
        for n in range(400):
            if n == 3:
                shot(page, "02-early")
                check_undo_hints_settings(page, failures)
                # A reload resumes the game in progress exactly.
                before = state(page)["record"]
                goto(page, "test&level=3&seed=7", fresh=False)
                if state(page)["record"] != before:
                    failures.append("a reload did not resume the game in progress")
            s = state(page)
            if "peek" not in checked and s["prompt"]["kind"] == "play" and s["discards"]:
                checked.add("peek")
                check_peek(page, failures)
            if "keys" not in checked and s["prompt"]["kind"] == "play" and not s["trick"] and len(s["hand"]) > 3:
                checked.add("keys")
                check_keyboard_play(page, failures)
                continue
            if n == 30:
                shot(page, "03-play")
            if not take_turn(page, failures, n, checked):
                break
        final = state(page)
        if final["prompt"]["kind"] != "over":
            failures.append(f"the partie did not finish by clicking: stuck at {final['prompt']['kind']}")
        # The live score shows the partie's totals, once its numbers stop counting.
        page.wait_for_timeout(800)
        for who in ("you", "them"):
            shown = page.locator(f"#bug .side.{who} .n").inner_text()
            if shown != str(final["partie"][who]):
                failures.append(f"the score shows {shown} for {who}, the partie {final['partie'][who]}")
        check_drawn(page, failures, "at the end")
        shot(page, "04-over")
        check_offline(page, failures)
        if page.errors:
            failures.append(f"console errors: {page.errors[:5]}")
        page.context.close()

        # The motion demo: every primitive, frozen part-way and at the end.
        demo = open_page(browser, "test&demo")
        for t in (0.37, 1):
            demo.evaluate(f"window.piquet3d.demoAt({t})")
            check_drawn(demo, failures, "in the demo")
        shot(demo, "06-demo")
        if demo.errors:
            failures.append(f"console errors in the motion demo: {demo.errors}")
        demo.context.close()

        # The voice: clips bundled, decoded by the browser, and the right ones
        # asked for as the table talks.
        talk = open_page(browser, "test&voice&level=2&seed=31")
        for command in ["cut 14", "dealer them"]:
            talk.evaluate(f"window.piquet3d.send({command!r})")
        for _ in range(12):
            s = state(talk)
            if s["prompt"]["kind"] == "declare":
                talk.evaluate("window.piquet3d.send('declare 0')")
            elif s["prompt"]["kind"] == "exchange":
                talk.evaluate(f"window.piquet3d.send('exchange {s['hand'][0]}')")
            else:
                break
        talk.wait_for_timeout(1500)
        heard = talk.evaluate("window.piquet3d.voice()")
        if not heard["recorded"]:
            failures.append("the page cannot play its own recorded voice")
        elif not any(line.split(":")[1].startswith("point-") for line in heard["said"]):
            failures.append(f"no point was called aloud: {heard['said'][:8]}")
        elif heard["decoded"] == 0 or heard["failed"]:
            failures.append(f"the voice's clips did not decode: {heard}")
        # Each thing said was said one of its ways (docs/PHRASES.md): a
        # recording of that group, never nothing.
        bank = talk.evaluate("Object.values(VOICES)[0].groups")
        # Only your opponent's lines are heard: your own calls are off
        # unless you turn them on.
        groups = [line.split(":")[1] for line in heard["said"] if line.startswith("them:")]
        wrong = [(g, k) for g, k in zip(groups, heard["picked"]) if k not in bank.get(g, [])]
        if len(heard["picked"]) != len(groups) or wrong:
            failures.append(f"the voice did not pick a way of saying each thing: {wrong[:4] or heard['picked'][:8]}")
        if talk.errors:
            failures.append(f"console errors with the voice on: {talk.errors}")
        talk.context.close()

        # A phone, held upright: it loads, draws, and never scrolls sideways.
        phone = open_page(browser, "test&level=3&seed=7", viewport={"width": 390, "height": 844})
        check_drawn(phone, failures, "on a phone")
        take_turn(phone, failures, 0, {"illegal"})
        width = phone.evaluate("document.documentElement.scrollWidth")
        if width > 390:
            failures.append(f"a phone scrolls sideways: the page is {width}px wide")
        shot(phone, "07-phone")
        # The table is framed between the strips framing.js assumes: the
        # information along the top and the controls at the foot must keep
        # to them, whatever is asked -- two whole deals, played quickly.
        strips = phone.evaluate("window.piquet3d.strips()")
        worst = {"top": 0, "foot": 0}
        for n in range(200):
            s = state(phone)
            if s["prompt"]["kind"] == "next_deal" and s["deal"] >= 2:
                break
            bands = phone.evaluate("""() => {
                const box = (id) => { const n = document.getElementById(id); return n && !n.hidden && n.offsetParent ? n.getBoundingClientRect() : null; };
                const top = Math.max(...["bug", "worth"].map(box).filter(Boolean).map((r) => r.bottom));
                const controls = box("controls");
                return { top, foot: controls && controls.height ? innerHeight - controls.top : 0 };
            }""")
            for k in worst:
                if bands[k] > worst[k]:
                    worst[k] = bands[k]
                if bands[k] > strips[k]:
                    failures.append(f"on a phone at {s['phase']}, the {k} strip is {bands[k]:.0f}px, over the {strips[k]}px the table is framed for")
            command = dull(s, n)
            if command is None:
                break
            phone.evaluate(f"window.piquet3d.send({command!r})")
        print(f"  phone strips at their tallest: top {worst['top']:.0f}px, foot {worst['foot']:.0f}px (framed for {strips['top']}, {strips['foot']})")
        if phone.errors:
            failures.append(f"console errors on a phone: {phone.errors}")
        phone.context.close()

        browser.close()

    for f in failures:
        print("FAIL:", f)
    if not failures:
        print("web3d browser test: all checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
