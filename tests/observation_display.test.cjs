"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const {resolveObjectURL} = require("node:buffer");
const {makeHarness} = require("./observation_browser_fixture.cjs");

async function main() {
  const page = fs.readFileSync(process.argv[2], "utf8");
  if (process.argv[3] === "zoom") {
    const h = makeHarness(page);
    h.context.window.visualViewport = {scale: 2, listeners: new Map(), addEventListener: h.context.window.addEventListener};
    await h.context.initialize(); assert.equal(h.context.displayReady(), false);
    assert.equal(h.doc.answers[0].disabled, true);
    console.log("display synthetic checks passed"); return;
  }
  if (process.argv[3] === "initial") {
    const h = makeHarness(page); h.doc.images[1].owner = h; h.doc.images[1].decode = disruptedDecode;
    await h.context.initialize(); assert.equal(h.context.displayReady(), false);
    assert.equal(h.doc.answers[0].disabled, true);
    console.log("display synthetic checks passed"); return;
  }
  if (process.argv[3] === "ref") {
    const h = makeHarness(page); await h.context.initialize();
    h.doc.images[0].dataset.ref = "assets/a2.png";
    assert.equal(h.context.displayReady(), false);
    h.state.observer.callback([{type: "attributes", attributeName: "data-ref"}]);
    assert.equal(h.doc.answers[0].disabled, true);
    console.log("display synthetic checks passed"); return;
  }
  const h = makeHarness(page);
  assert.equal(h.doc.answers[0].disabled, true);
  await h.context.initialize();
  assert.equal(h.context.displayReady(), true);
  assert.equal(h.doc.answers[0].disabled, false);
  for (const proof of h.state.proofs) {
    assert.equal(proof.verified, true); assert.equal(proof.decoded, true);
    const bound = h.state.bindings.get(proof.element_ids[0]);
    const bytes = new Uint8Array(await resolveObjectURL(bound.url).arrayBuffer());
    const encoded = JSON.parse(h.doc.getElementById("assets").textContent)[proof.ref];
    assert.deepEqual(Buffer.from(bytes), Buffer.from(encoded, "base64"));
  }
  h.doc.images[0].src = "blob:synthetic-replacement";
  assert.equal(h.context.displayReady(), false);
  h.context.invalidate({type: "mutation"});
  assert.equal(h.doc.answers[0].disabled, true);
  assert.equal(h.state.proofs[0].verified, false);
  const corrupt = makeHarness(page);
  const data = JSON.parse(corrupt.doc.getElementById("assets").textContent);
  data[Object.keys(data)[0]] = Buffer.from("different synthetic bytes").toString("base64");
  corrupt.doc.getElementById("assets").textContent = JSON.stringify(data);
  await corrupt.context.initialize();
  assert.equal(corrupt.context.displayReady(), false);
  assert.equal(corrupt.doc.answers[0].disabled, true);
  const failed = makeHarness(page); failed.doc.images[0].failDecode = true;
  await failed.context.initialize(); assert.equal(failed.context.displayReady(), false);
  const noCrypto = makeHarness(page); noCrypto.context.crypto = {};
  await noCrypto.context.initialize(); assert.equal(noCrypto.context.displayReady(), false);
  console.log("display synthetic checks passed");
}
async function disruptedDecode() {
  this.complete = true; this.naturalWidth = this.expected[0]; this.naturalHeight = this.expected[1];
  await Promise.resolve();
  this.owner.doc.images[0].isConnected = false;
  this.owner.doc.images[0].isConnected = true;
  if (this.owner.state.observer) this.owner.state.observer.callback([{type: "childList"}]);
}
function fail(error) { console.error(error); process.exitCode = 1; }
main().catch(fail);
