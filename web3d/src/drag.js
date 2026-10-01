// A panel the player may drag about a phone's screen (the user: "make it
// floating so you can drag it around, since mobile phone real estate is
// sparce"): where it may sit, and when a press has become a drag. Pure, so
// the page only applies it.

export const MARGIN = 8; // px a panel is kept in from the screen's edge
export const DRAG_FROM = 6; // px a press travels before it is a drag, not a tap

// `at` (its top-left corner) moved as little as it can be for the whole of a
// panel of `size` to lie within `view`, MARGIN in from each edge; a panel too
// big for the view keeps its top-left corner in it.
export function keepOnScreen(at, size, view, margin = MARGIN) {
  const x = Math.max(margin, Math.min(at.x, view.width - size.width - margin));
  const y = Math.max(margin, Math.min(at.y, view.height - size.height - margin));
  return { x, y };
}

export const isDrag = (from, to) => Math.hypot(to.x - from.x, to.y - from.y) >= DRAG_FROM;
