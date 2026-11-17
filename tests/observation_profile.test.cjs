"use strict";
const fs = require("node:fs");
const assert = require("node:assert/strict");
const {makeHarness} = require("./observation_browser_fixture.cjs");

async function main() {
  const page = fs.readFileSync(process.argv[2], "utf8");
  for (const scenario of ["matching", "viewport", "dpr", "css", "resize", "bad-change"]) {
    const h = makeHarness(page);
    for (const image of h.doc.images) { image.width = 100; image.height = 100; }
    h.context.attachResponseControls();
    if (scenario === "viewport") h.context.window.innerWidth = 320;
    if (scenario === "dpr") h.context.window.devicePixelRatio = 2;
    if (scenario === "css") h.doc.images[0].width = 10;
    await h.context.initialize();
    if (["viewport", "dpr", "css"].includes(scenario)) {
      assert.equal(h.context.displayReady(), false, scenario);
      assert.equal(h.doc.answers[0].disabled, true, scenario); continue;
    }
    assert.equal(h.context.displayReady(), true, scenario);
    if (scenario === "resize") {
      h.context.window.innerWidth = 320;
      h.context.window.listeners.get("resize")({type: "resize"});
      assert.equal(h.doc.answers[0].disabled, true);
      h.context.window.innerWidth = 800;
      assert.equal(h.context.displayReady(), false);
    }
    if (scenario === "bad-change") {
      h.doc.images[0].width = 0;
      h.doc.selects[0].value = "defect"; h.doc.notes[0].value = "  unchanged synthetic note\n ";
      h.doc.getElementById("response-controls").listeners.get("change")({target: h.doc.selects[0], type: "change"});
      h.doc.images[0].width = 100;
      assert.equal(h.context.displayReady(), false);
      const body = h.context.buildResponse();
      assert.equal(body.entries[0].state, "defect"); assert.equal(body.entries[0].note, "  unchanged synthetic note\n ");
      assert.equal(body.observations.assets[0].verified, false);
    }
  }
  console.log("profile synthetic checks passed");
}
function fail(error) { console.error(error); process.exitCode = 1; }
main().catch(fail);
