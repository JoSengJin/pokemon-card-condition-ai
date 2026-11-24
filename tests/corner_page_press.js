"use strict";
// Runs the generated corner label page script against a minimal DOM built from that page's own markup, then replays presses.
// stdin: {script, articles:[[tag, class, data-*]...], presses:[{card, cell|button} | {card, handle, to:[x,y]}]} -> stdout: result textarea value.
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const node = (data, names = [], kids = []) => ({
  dataset: {...data}, names: new Set(names), kids, style: {}, firstChild: {textContent: ""}, handlers: {}, value: "",
  classList: {toggle: Boolean, remove: Boolean}, setPointerCapture: Boolean,
  getBoundingClientRect: () => ({left: 0, top: 0, width: 1000, height: 1000}),
  addEventListener(type, fn) { this.handlers[type] = fn; },
  querySelectorAll(sel) { return this.kids.filter(k => k.names.has(sel.slice(1))); },
  querySelector(sel) { return this.querySelectorAll(sel)[0]; },
});
const cards = input.articles.map(a => node(a.data, [], a.kids.map(k => node(k.data, k.names))));
const ids = {out: node({}), copy: node({}), msg: node({})};
const document = {querySelectorAll: sel => (sel === "article" ? cards : []), getElementById: id => ids[id]};
new Function("document", input.script)(document);
for (const p of input.presses) {
  const card = cards[p.card];
  if (p.handle) {
    const h = card.querySelectorAll(".h").find(k => k.dataset.k === p.handle);
    h.handlers.pointerdown({pointerId: 1, preventDefault: Boolean});
    h.handlers.pointermove({clientX: p.to[0] * 1000, clientY: p.to[1] * 1000});
    h.handlers.pointerup({});
  } else {
    const target = p.cell ? card.querySelectorAll(".c").find(k => k.dataset.a === p.cell) : card.querySelector("." + p.button);
    target.handlers.click({target});
  }
}
process.stdout.write(ids.out.value);
