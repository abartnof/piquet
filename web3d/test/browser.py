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
motion demo runs; that each round of the declarations is introduced, with
play held until its name has gone (`?test&breaks`); that a phone gets a
working page with no sideways scroll; and that nothing is ever written to the
console in error.
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


# The moment between the declarations' rounds, as it lands on the page: each
# box and card in the order it is put up, and when.
AFLOAT_LOG = """() => {
  window.__afloat = [];
  new MutationObserver((ms) => { for (const m of ms) for (const n of m.addedNodes) if (n.classList)
    window.__afloat.push({ t: performance.now(), cls: n.className, text: n.textContent }); })
    .observe(document.getElementById('afloat'), { childList: true });
  window.__overlap = 0;
  setInterval(() => {
    if (document.querySelector('#afloat .interlude') && document.querySelector('#prompt .options, #prompt .actions')) window.__overlap++;
  }, 25);
}"""


def check_breaks(browser, failures, dealer):
    """The user: "an on-screen thing pop up for a moment before each part of
    the declarations, after each player is done speaking from the last one.
    they may start again once the on-screen thing is gone." Played through
    the first deal's declarations, as elder (`dealer them`: you open every
    round) or younger (your opponent does, in the middle of your move)."""
    where = "as elder" if dealer == "them" else "as younger"
    page = open_page(browser, "test&breaks&level=1&seed=7")
    page.evaluate(AFLOAT_LOG)
    refused = 0
    for _ in range(400):
        s = state(page)
        p = s["prompt"]
        if p["kind"] == "play" or s["deal"] > 1:
            break
        command = {"cut": lambda: "cut 14", "choose_dealer": lambda: f"dealer {dealer}",
                   "exchange": lambda: f"exchange {s['hand'][-1]}", "declare": lambda: "declare 0"}[p["kind"]]()
        if not page.evaluate(f"window.piquet3d.send({command!r})"):
            # Refused only while a round's name is up, or one is still to come.
            refused += 1
        page.wait_for_timeout(100)
    page.wait_for_timeout(4000)
    log = page.evaluate("window.__afloat")
    cards = [(i, e) for i, e in enumerate(log) if e["cls"] == "interlude"]
    if [e["text"] for _, e in cards] != ["Point", "Sequences", "Sets"]:
        failures.append(f"{where}, the rounds were introduced as {[e['text'] for _, e in cards]}")
    for i, card in cards:
        boxes = [e for e in log[i + 1:] if e["cls"].startswith("dialogue")]
        if boxes and boxes[0]["t"] < card["t"] + 950:
            failures.append(f"{where}: \"{boxes[0]['text']}\" was said {boxes[0]['t'] - card['t']:.0f} ms into {card['text']}")
    if page.evaluate("window.__overlap"):
        failures.append(f"{where}, your buttons were up with a round's name")
    if not refused:
        failures.append(f"{where}, no move was ever held back for a round's name")
    if page.errors:
        failures.append(f"console errors in the declarations' breaks {where}: {page.errors}")
    page.context.close()


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
    # H switches hints; E switches the interpretations (the user: facts, the
    # prescriptive layer, and hints -- the last two each easy to turn off).
    hints = back["aids"]["hints"]
    page.keyboard.press("h")
    if state(page)["aids"]["hints"] == hints:
        failures.append("H did not toggle hints")
    page.keyboard.press("h")
    # The interpretation: beside the table on a wide screen (the user: "long
    # explanations ... on the left side, and shorthand on the bottom"),
    # under the hand only on a phone.
    told = "#rule:not([hidden]) .rule-text, #prompt .asked .note"
    notes = page.locator(told).count()
    if page.locator("#prompt .asked .note").count():
        failures.append("on a wide screen the long explanation should be in the left column, not under the hand")
    page.keyboard.press("e")
    if notes and page.locator(told).count():
        failures.append("E did not hide the interpretation")
    page.keyboard.press("e")
    if notes and not page.locator(told).count():
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
            # The cards cast shadows (the user: "confirm that at every segment
            # of the game, all cards are casting shadows"): drawn with them
            # and without, your hand held up, the frames differ. (Cards lying
            # flat hide their shadows under themselves, as real ones do.)
            if "shadows" not in checked and s["prompt"]["kind"] == "exchange":
                checked.add("shadows")
                cast = page.evaluate("window.piquet3d.shadowPixels()")
                if cast < 2000:
                    failures.append(f"the cards' shadows add only {cast} pixels with your hand held up")
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

        # The welcome and the tutorial: the user's four pages -- the introduction,
        # then each phase's page when it comes ("declarations and play of
        # tricks pop up before those phases ... click on the tutorials button
        # at any time ... go back/fwd between them").
        tut = open_page(browser, "test&welcome&level=2&seed=31")
        tut.locator("#welcome").get_by_role("button", name="Tutorial").click()
        tut.wait_for_timeout(800)
        page_title = lambda: tut.locator("#tutorial .tutorial-title").inner_text()
        is_open = lambda: tut.locator("#tutorial").get_attribute("open") is not None
        # The user: "a little x (md3) in the top-right of the tutorial pages".
        close_x = lambda: tut.locator("#tutorial .tutorial-close").click()
        if page_title() != "Introduction":
            failures.append(f"the tutorial did not open on its introduction: {page_title()!r}")
        # In the tutorial the introduction says the rest will come by themselves.
        if not tut.locator("#tutorial .tutorial-note").is_visible():
            failures.append("the introduction has no note that the other pages come by themselves")
        shot(tut, "09-tutorial")
        # One arrangement on every page (the user: "choose one alignment schema
        # and stick with it"): Back at the left edge, Next at the right. And
        # paging ahead does not stop a page coming at its moment.
        edges = set()
        for _ in range(4):
            back = tut.locator("#tutorial .tutorial-back").bounding_box()
            nxt = tut.locator("#tutorial .tutorial-next").bounding_box()
            edges.add((round(back["x"]), round(nxt["x"] + nxt["width"])))
            if tut.locator("#tutorial .tutorial-next").get_attribute("disabled") is None:
                tut.locator("#tutorial .tutorial-next").click()
                tut.wait_for_timeout(300)
        if len(edges) != 1:
            failures.append(f"the tutorial's Back and Next move between pages: {sorted(edges)}")
        # Closed, nothing follows until the deal is decided (the user: "the
        # second tutorial page should pop up after the player decides if they
        # are younger/elder").
        close_x()
        tut.wait_for_timeout(700)
        if is_open():
            failures.append(f"a page followed the introduction at once: {page_title()!r}")
        seen = []
        for _ in range(60):
            if is_open():
                if page_title() != (seen[-1] if seen else None):
                    seen.append(page_title())
                close_x()
                tut.wait_for_timeout(700)
                continue
            s = state(tut)
            p = s["prompt"]
            if "The Tricks" in seen:
                break
            if p["kind"] == "cut":
                tut.evaluate("window.piquet3d.send('cut 14')")
            elif p["kind"] == "choose_dealer":
                tut.evaluate("window.piquet3d.send('dealer them')")
            elif p["kind"] == "exchange":
                tut.evaluate(f"window.piquet3d.send('exchange {s['hand'][-1]}')")
            elif p["kind"] == "declare":
                tut.evaluate("window.piquet3d.send('declare 0')")
            elif p["kind"] == "play":
                tut.evaluate(f"window.piquet3d.send('play {p['legal'][0]}')")
            tut.wait_for_timeout(1200)
        if seen != ["The Exchange", "The Declarations", "The Tricks"]:
            failures.append(f"the tutorial's pages came as {seen}")
        t = tut.evaluate("window.piquet3d.tutorial()")
        if not t["on"] or not state(tut)["aids"]["hints"]:
            failures.append(f"the tutorial is not on, with hints: {t}")
        # The ? brings the pages up at any time, at the page for the moment.
        tut.locator("#tutorial-open").click()
        tut.wait_for_timeout(500)
        if not is_open() or page_title() != "The Tricks":
            failures.append(f"the ? did not open the page for the play: {is_open()}, {page_title()!r}")
        tut.locator("#tutorial .tutorial-back").click()
        tut.wait_for_timeout(300)
        backward = page_title()
        tut.locator("#tutorial .tutorial-next").click()
        tut.wait_for_timeout(300)
        forward = page_title()
        if (backward, forward) != ("The Declarations", "The Tricks"):
            failures.append(f"back and forward went to {backward!r} and {forward!r}")
        if tut.locator("#tutorial .tutorial-dots .dot.on").count() != 1 or tut.locator("#tutorial .tutorial-note").is_visible():
            failures.append("the dots do not mark one page, or the note shows off the introduction")
        tut.keyboard.press("ArrowLeft")
        tut.wait_for_timeout(300)
        if page_title() != "The Declarations":
            failures.append(f"the left arrow went to {page_title()!r}")
        tut.keyboard.press("Escape")
        tut.wait_for_timeout(700)
        if is_open():
            failures.append("Escape did not close the tutorial")
        # The switch in Settings shows it on, for this partie; the next
        # partie has none of it ("2nd partie has no more tutorial popups").
        switch = tut.locator("md-switch[data-tutorial]")
        if not switch.evaluate("s => s.selected"):
            failures.append("Settings does not show the tutorial on in the tutorial's partie")
        tut.locator("#new").click()
        tut.wait_for_timeout(1500)
        popped = False
        for _ in range(12):
            if is_open():
                popped = True
                break
            s = state(tut)
            p = s["prompt"]
            if p["kind"] == "cut":
                tut.evaluate("window.piquet3d.send('cut 14')")
            elif p["kind"] == "choose_dealer":
                tut.evaluate("window.piquet3d.send('dealer them')")
            elif p["kind"] == "exchange":
                tut.evaluate(f"window.piquet3d.send('exchange {s['hand'][-1]}')")
            elif p["kind"] == "declare":
                break
            tut.wait_for_timeout(1000)
        if popped or tut.evaluate("window.piquet3d.tutorial()")["on"] or switch.evaluate("s => s.selected"):
            failures.append("the second partie still has the tutorial")
        # Outside the tutorial only explanations are on by default; the hints
        # the tutorial brought go with it.
        if state(tut)["aids"]["hints"]:
            failures.append("hints stayed on after the tutorial's partie")
        # The top bar's plus says what it does on hover.
        tut.mouse.move(640, 420)  # away first: the click that began this partie hid it
        tut.wait_for_timeout(200)
        tut.locator("#new").hover()
        tut.wait_for_timeout(700)
        tip = tut.locator(".tip.shown")
        if tip.count() != 1 or tip.inner_text() != "Start a new partie" or tip.evaluate("t => getComputedStyle(t).opacity") != "1":
            failures.append(f"the plus has no visible tooltip: {tip.all_inner_texts()}")
        # Settings holds only what the page does not.
        if tut.locator("#settings").get_by_role("button", name="New partie").count() or \
                tut.locator('#settings md-outlined-select[label="Order your hand"]').count():
            failures.append("Settings still repeats New partie or the hand's order")
        # Turned on in Settings, the pages come again, once each.
        tut.locator("#settings-open").click()
        tut.wait_for_timeout(500)
        switch.click()
        tut.get_by_role("button", name="Done").click()
        tut.wait_for_timeout(1500)
        if not is_open() or page_title() != "The Declarations":
            failures.append(f"switched on at the declarations, their page did not come: {is_open()}")
        else:
            close_x()
        if tut.errors:
            failures.append(f"console errors in the tutorial: {tut.errors}")
        tut.context.close()

        # You younger, so your opponent moves first in every phase: each page
        # comes at the phase's very start, the table held still behind it
        # (the user: "the pop ups pop up at the beginning of each of the
        # phases").
        # The tutorial deals a new partie on a random seed, so who is elder
        # is the cut's: cut until the deal is decided, and begin again until
        # it makes you younger (about one try in two).
        for _ in range(12):
            yng = open_page(browser, "test&welcome&level=2&seed=2")
            yng.locator("#welcome").get_by_role("button", name="Tutorial").click()
            yng.wait_for_timeout(800)
            yng.locator("#tutorial .tutorial-close").click()
            yng.wait_for_timeout(700)
            for _ in range(10):
                kind = state(yng)["prompt"]["kind"]
                if kind not in ("cut", "choose_dealer"):
                    break
                yng.evaluate("window.piquet3d.send('cut 14')" if kind == "cut" else "window.piquet3d.send('dealer you')")
                yng.wait_for_timeout(1200)
            if any(e["kind"] == "deal_begins" and e["elder"] == "them" for e in state(yng)["events"]):
                break
            yng.context.close()
        theirs = lambda kind: any(e["kind"] == kind and e.get("who") == "them" for e in state(yng)["events"])
        held = {}
        for _ in range(40):
            if yng.locator("#tutorial").get_attribute("open") is not None:
                title = yng.locator("#tutorial .tutorial-title").inner_text()
                # Held at a gate before your opponent's first move of the
                # phase -- not come to by the table falling still.
                phase_move = {"The Exchange": "exchanged", "The Declarations": "called", "The Tricks": "played"}.get(title)
                held[title] = bool(phase_move) and yng.evaluate("window.piquet3d.held()") and theirs(phase_move)
                yng.locator("#tutorial .tutorial-close").click()
                yng.wait_for_timeout(700)
                continue
            s = state(yng)
            p = s["prompt"]
            if "The Tricks" in held:
                break
            if p["kind"] == "cut":
                yng.evaluate("window.piquet3d.send('cut 14')")
            elif p["kind"] == "choose_dealer":
                yng.evaluate("window.piquet3d.send('dealer you')")
            elif p["kind"] == "exchange":
                yng.evaluate(f"window.piquet3d.send('exchange {s['hand'][-1]}')")
            elif p["kind"] == "declare":
                yng.evaluate("window.piquet3d.send('declare 0')")
            elif p["kind"] == "play":
                yng.evaluate(f"window.piquet3d.send('play {p['legal'][0]}')")
            yng.wait_for_timeout(1200)
        if held != {"The Exchange": True, "The Declarations": True, "The Tricks": True}:
            failures.append(f"as younger, the pages did not hold the table at each phase's start: {held}")
        if yng.errors:
            failures.append(f"console errors in the younger tutorial: {yng.errors}")
        yng.context.close()

        for dealer in ("them", "you"):
            check_breaks(browser, failures, dealer)

        # The celebrations' staging (the user: "the dummy ending where the game
        # is basically over, and i get to scroll through the different
        # endings"): two cards left in the last deal; play one, the partie
        # ends, a celebration comes; the arrows step; the X gives the table
        # back.
        end = open_page(browser, "test&ending")
        s = state(end)
        if not (s["deal"] >= 6 and s["prompt"]["kind"] == "play" and len(s["hand"]) == 2):
            failures.append(f"the staging did not open on the last deal's last two cards: deal {s['deal']}, {s['prompt']['kind']}, {s['hand']}")
        end.evaluate(f"window.piquet3d.send('play {s['prompt']['legal'][0]}')")
        end.wait_for_function("window.piquet3d.celebration() !== null", timeout=15_000)
        names = end.evaluate("window.piquet3d.celebrations()")
        first = end.evaluate("window.piquet3d.celebration()")
        end.evaluate("window.piquet3d.celebrationTick(1500)")
        shot(end, "10-celebration")
        if not end.locator(".celebrate-bar").is_visible() or end.locator("#controls").is_visible():
            failures.append("a celebration should have its bar, and the table's controls stepped aside")
        stepped = []
        for _ in names:
            end.locator(".celebrate-bar .celebrate-forward").click()
            end.wait_for_timeout(300)
            end.evaluate("window.piquet3d.celebrationTick(2500)")
            stepped.append(end.evaluate("window.piquet3d.celebration()"))
        if first != names[0] or stepped[-1] != names[0] or sorted(set(stepped)) != sorted(names):
            failures.append(f"the arrows did not step through every celebration: {first}, then {stepped}")
        end.locator(".celebrate-bar .celebrate-close").click()
        end.wait_for_timeout(500)
        if end.evaluate("window.piquet3d.celebration()") is not None or end.locator(".celebrate").is_visible():
            failures.append("the X did not give the table back")
        check_drawn(end, failures, "after a celebration")
        if end.errors:
            failures.append(f"console errors in the celebrations: {end.errors}")
        end.context.close()

        # In a real partie (the user: "regardless of if they win/lose ...
        # randomly chosen- if they don't do file?ending, they can't scroll
        # left/right to pick an ending"): one at random, no arrows.
        real = open_page(browser, "test&level=2&seed=31")
        real.evaluate("window.piquet3d.celebrate()")
        chosen = real.evaluate("window.piquet3d.celebration()")
        if chosen not in names:
            failures.append(f"a real partie's celebration was not one of them: {chosen}")
        if real.locator(".celebrate-bar .celebrate-forward").count() or real.locator(".celebrate-bar .celebrate-back").count():
            failures.append("outside ?ending there should be no arrows to pick a celebration")
        if not real.locator(".celebrate-bar .celebrate-close").is_visible():
            failures.append("a real partie's celebration should still have its way back")
        real.context.close()

        # No sound of any kind (the user: "i don't want the html to have any
        # audio"): no audio made, no speech -- but the declarations still
        # come as a dialogue, in boxes.
        talk = open_page(browser, "test&level=2&seed=31")
        talk.evaluate("""() => {
            window.__sound = { contexts: 0, spoken: 0 };
            for (const name of ["AudioContext", "webkitAudioContext"]) {
                const Made = window[name];
                if (Made) window[name] = class extends Made { constructor(...a) { super(...a); window.__sound.contexts++; } };
            }
            if (window.speechSynthesis) window.speechSynthesis.speak = () => window.__sound.spoken++;
            window.__boxes = [];
            new MutationObserver((changes) => changes.forEach((c) => c.addedNodes.forEach((n) => {
                if (!n.classList || !n.classList.contains("dialogue")) return;
                const r = n.getBoundingClientRect();
                window.__boxes.push({ who: n.classList.contains("you") ? "you" : "them", text: n.textContent, top: r.top, bottom: r.bottom });
            }))).observe(document.getElementById("afloat"), { childList: true });
        }""")
        talk.mouse.click(10, 790)
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
        talk.wait_for_timeout(4000)
        sound = talk.evaluate("window.__sound")
        if sound["contexts"] or talk.locator("audio, video").count():
            failures.append(f"the page makes sound: {sound}")
        if sound["spoken"]:
            failures.append("the page spoke through the browser's own voice")
        # The declarations as a dialogue (the user: "two dialogue boxes to pop
        # up every move"): both speak, in boxes by their own hands.
        boxes = talk.evaluate("window.__boxes")
        mine = [b for b in boxes if b["who"] == "you"]
        theirs = [b for b in boxes if b["who"] == "them"]
        if not mine or not theirs:
            failures.append(f"the declarations put up no dialogue for both players: {boxes[:6]}")
        elif min(b["top"] for b in mine) <= max(b["bottom"] for b in theirs):
            failures.append(f"your dialogue box is not below your opponent's: {boxes[:6]}")
        elif any(not b["text"].strip() for b in boxes):
            failures.append(f"an empty dialogue box: {boxes[:6]}")
        if talk.errors:
            failures.append(f"console errors at the dialogue: {talk.errors}")
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
