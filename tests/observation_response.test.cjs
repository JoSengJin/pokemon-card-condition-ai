"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const {makeHarness} = require("./observation_browser_fixture.cjs");

async function main() {
  const h = makeHarness(fs.readFileSync(process.argv[2], "utf8"));
  h.context.attachResponseControls();
  await h.context.initialize();
  const selected = h.doc.getElementById("answer-r1");
  const note = h.doc.getElementById("note-r1");
  assert.equal(h.context.buildResponse().entries[0].state, "unreviewed");
  const root = h.doc.getElementById("response-controls");
  for (const state of ["normal", "defect", "unassessable", "unreviewed"]) {
    selected.value = state;
    root.listeners.get("change")({type: "change", target: selected});
    assert.equal(h.context.buildResponse().entries[0].state, state);
  }
  note.value = "  합성 메모\n ";
  root.listeners.get("input")({type: "input", target: note});
  selected.value = "defect";
  root.listeners.get("change")({type: "change", target: selected});
  h.context.handleEnvironment({type: "resize"});
  h.context.handleEnvironment({type: "visibilitychange"});
  const raw = h.doc.getElementById("export").listeners.get("click")({type: "click"});
  assert.equal(h.doc.getElementById("out").value, raw);
  const body = JSON.parse(raw);
  assert.equal(body.entries[0].note, "  합성 메모\n ");
  assert.equal(body.observations.events.at(-1).event, "export");
  assert.equal(body.collection_status, "not_executable_pending_collection_contract_approval");
  assert.equal(body.data_origin, "synthetic_fixture");
  if (process.argv[3]) fs.writeFileSync(process.argv[3], raw);
  h.doc.images[0].src = "blob:changed";
  const invalid = h.context.buildResponse();
  assert.equal(invalid.entries[0].state, "defect");
  assert.equal(invalid.entries[0].note, note.value);
  assert.equal(invalid.observations.assets[0].verified, false);
  assert.equal(selected.disabled, true);
  assert.equal(body.observations.assets[0].verified, true);
  console.log("response synthetic checks passed");
}
function fail(error) { console.error(error); process.exitCode = 1; }
main().catch(fail);
