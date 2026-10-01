// The tutorial: the user's four pages -- an introduction, then one before each
// phase of play -- written in web3d/tutorial.md so they can be reworded
// without touching code. The user: "four pieces here- intro, which is
// immediately followed by the exchange; then declarations and play of tricks
// pop up before those phases of gameplay. users should be able to click on
// the tutorials button at any time to bring these up, and they should be able
// to go back/fwd between them."
//
// The rules they state are the engine's (test/tutorial.test.js checks them
// against its events). This module holds no words of its own.

export const PAGE_KEYS = ["intro", "exchange", "declarations", "tricks"];

// The small piece of Markdown the pages use: `# page`, `## heading`,
// paragraphs, `- ` and `1. ` lists, **bold** and *italic*. A page is
// { key, title, blocks }; a block is { type: "h" | "p", spans } or
// { type: "ul" | "ol", items: [spans] }; a span is { text, bold?, italic? }.
export function parseTutorial(markdown) {
  const pages = [];
  let page = null;
  let para = null; // the paragraph or list item being gathered, as lines
  let list = null;
  const flush = () => {
    if (para) {
      const spans = inline(para.lines.join(" "));
      if (para.list) para.list.items.push(spans);
      else page.blocks.push({ type: "p", spans });
    }
    para = null;
  };
  for (const raw of markdown.split("\n")) {
    const line = raw.trim();
    let m;
    if ((m = /^# (.+)$/.exec(line))) {
      flush();
      list = null;
      page = { key: PAGE_KEYS[pages.length] ?? `page-${pages.length}`, title: m[1], blocks: [] };
      pages.push(page);
    } else if (!page) {
      continue;
    } else if ((m = /^## (.+)$/.exec(line))) {
      flush();
      list = null;
      page.blocks.push({ type: "h", spans: inline(m[1]) });
    } else if ((m = /^(-|\d+\.) (.+)$/.exec(line))) {
      flush();
      const type = m[1] === "-" ? "ul" : "ol";
      if (!list || list.type !== type) {
        list = { type, items: [] };
        page.blocks.push(list);
      }
      para = { lines: [m[2]], list };
    } else if (line === "") {
      flush();
      list = null;
    } else if (para) {
      para.lines.push(line);
    } else {
      para = { lines: [line], list: null };
    }
  }
  flush();
  return pages;
}

// **bold** and *italic*, as spans of plain text.
function inline(text) {
  const spans = [];
  const pattern = /\*\*(.+?)\*\*|\*(.+?)\*/g;
  let at = 0;
  let m;
  while ((m = pattern.exec(text))) {
    if (m.index > at) spans.push({ text: text.slice(at, m.index) });
    spans.push(m[1] !== undefined ? { text: m[1], bold: true } : { text: m[2], italic: true });
    at = pattern.lastIndex;
  }
  if (at < text.length) spans.push({ text: text.slice(at) });
  return spans;
}

// The page for the moment you are in: the phase you are asked to act in, or
// the introduction between them.
export function pageFor(s) {
  switch (s.prompt.kind) {
    case "exchange":
      return "exchange";
    case "declare":
      return "declarations";
    case "play":
      return "tricks";
    default:
      return "intro";
  }
}

// In the tutorial, the phase's page, the first time you act in it -- unless
// you have read it already, paging forward from the introduction.
export function pageDue(s, seen) {
  const key = pageFor(s);
  return key !== "intro" && !seen.includes(key) ? key : null;
}
