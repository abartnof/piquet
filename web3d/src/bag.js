// Saying a thing several ways without repeating yourself (the user: "i don't
// want *any* sounds to be repetitive"). Each thing said has a bag of the
// ways it can be said: they come out in a shuffled order, every one before
// any comes round again, and the bag is refilled so that its first is never
// the last one heard -- so nothing is ever said the same way twice running.
//
// createBags(random) -> pick(id, ways): one of `ways`, or null if none.

export function createBags(random = Math.random) {
  const bags = new Map(); // id -> { left: ways still to come, last: the one heard }
  const shuffled = (items) => {
    const out = [...items];
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(random() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  };
  return function pick(id, ways) {
    if (!ways || !ways.length) return null;
    const bag = bags.get(id) ?? { left: [], last: null };
    if (!bag.left.length) {
      bag.left = shuffled(ways);
      // The next out is the end of the list: not the one just heard.
      const end = bag.left.length - 1;
      if (end > 0 && bag.left[end] === bag.last) [bag.left[0], bag.left[end]] = [bag.left[end], bag.left[0]];
    }
    const way = bag.left.pop();
    bag.last = way;
    bags.set(id, bag);
    return way;
  };
}
