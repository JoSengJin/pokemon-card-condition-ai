"use strict";
// Runs a generated label page script (articles with plain data-v buttons) against a minimal DOM built from that page's own markup, then replays presses.
// stdin: {script, articles:[{data, kids:[{data}]}], presses:[{card, v}]} -> stdout: result textarea value; a script error is reported on stderr (the browser keeps the handlers bound before it).
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const node = (data, kids = []) => ({dataset: {...data}, kids, value: "", handlers: {}, classList: {toggle: Boolean}, focus() {}, select() {},
  addEventListener(type, fn) { this.handlers[type] = fn; }, querySelectorAll() { return this.kids; }});
const cards = input.articles.map(a => node(a.data, a.kids.map(k => node(k.data))));
const ids = {out: node({}), copy: node({}), msg: node({}), ...(input.alln ? {alln: node({})} : {})};
const document = {querySelectorAll: sel => (sel === "article" ? cards : []), getElementById: id => ids[id] || null, execCommand: () => true};
try { new Function("document", input.script)(document); } catch (e) { process.stderr.write("script error: " + e.message + "\n"); }
for (const p of input.presses) {
  if (p.id) { (ids[p.id].onclick || (() => { throw new Error("no onclick on #" + p.id); }))(); continue; }  // page-level button by id (alln, copy)
  const button = cards[p.card].kids.find(k => k.dataset.v === p.v);
  (button.handlers.click || (() => { throw new Error("no click handler on " + p.v); }))({target: button});
}
process.stdout.write(input.full ? JSON.stringify({out: ids.out.value, msg: ids.msg.textContent}) : ids.out.value);
